import unittest

from orderlift.orderlift_logistics.technical_qty_limit import (
    OrderliftTechnicalQtyLimitMixin,
)


class Row:
    """Minimal stand-in for a child row: .doctype, .get() and .set()."""

    def __init__(self, doctype="Material Request Item", **values):
        self.doctype = doctype
        self._values = values

    def get(self, fieldname, default=None):
        return self._values.get(fieldname, default)

    def set(self, fieldname, value):
        self._values[fieldname] = value


class FakeController:
    """Stands in for the ERPNext controller the mixin sits in front of.

    Records what the native check would have seen, which is the only thing that
    matters: status_updater skips a row whose join_field is empty.
    """

    def __init__(self, rows):
        self._rows = rows
        self.seen = None
        self.raise_in_validate = False

    def get_all_children(self):
        return self._rows

    def validate_qty(self):
        self.seen = [(row.get("item_code"), row.get("sales_order_item")) for row in self._rows]
        if self.raise_in_validate:
            raise ValueError("native guard tripped")


class Doc(OrderliftTechnicalQtyLimitMixin, FakeController):
    pass


class TestTechnicalQtyLimit(unittest.TestCase):
    def test_stamped_rows_are_hidden_from_the_native_guard(self):
        """Rule 20: the approved execution qty is the cap, so a revision raising a
        quantity above the sold quantity must still be requestable. Hiding the link is
        what makes status_updater skip the row."""
        stamped = Row(
            item_code="ECL-00001",
            sales_order_item="l8cndlei1j",
            custom_technical_revision="TLR-11397",
        )
        doc = Doc([stamped])
        doc.validate_qty()

        # During the native check the link was hidden...
        self.assertEqual(doc.seen, [("ECL-00001", None)])
        # ...and restored afterwards, so update_qty can still maintain requested_qty.
        self.assertEqual(stamped.get("sales_order_item"), "l8cndlei1j")

    def test_unstamped_rows_keep_the_native_guard(self):
        plain = Row(item_code="I-2", sales_order_item="SOI-2")
        doc = Doc([plain])
        doc.validate_qty()

        self.assertEqual(doc.seen, [("I-2", "SOI-2")])
        self.assertEqual(plain.get("sales_order_item"), "SOI-2")

    def test_a_mixed_document_exempts_only_the_stamped_row(self):
        stamped = Row(item_code="I-1", sales_order_item="SOI-1",
                      custom_technical_revision="TLR-1")
        plain = Row(item_code="I-2", sales_order_item="SOI-2")
        doc = Doc([stamped, plain])
        doc.validate_qty()

        self.assertEqual(doc.seen, [("I-1", None), ("I-2", "SOI-2")])
        self.assertEqual(stamped.get("sales_order_item"), "SOI-1")
        self.assertEqual(plain.get("sales_order_item"), "SOI-2")

    def test_a_stamped_row_with_no_sales_order_link_is_left_alone(self):
        """An engineering addition has no Sales Order line, so the native guard never
        looked at it and there is nothing to hide."""
        addition = Row(item_code="I-3", sales_order_item="",
                       custom_technical_revision="TLR-1")
        doc = Doc([addition])
        doc.validate_qty()

        self.assertEqual(doc.seen, [("I-3", "")])

    def test_the_link_is_restored_even_when_the_native_guard_throws(self):
        """A throw must never leave the document missing its Sales Order link -- that
        would silently break requested_qty tracking and the lineage validation."""
        stamped = Row(item_code="I-1", sales_order_item="SOI-1",
                      custom_technical_revision="TLR-1")
        doc = Doc([stamped])
        doc.raise_in_validate = True

        with self.assertRaises(ValueError):
            doc.validate_qty()
        self.assertEqual(stamped.get("sales_order_item"), "SOI-1")

    def test_purchase_order_rows_are_exempt_too(self):
        """Purchase Order is capped against Sales Order Item as well -- that entry is
        appended at runtime by update_status_updater(), not declared in __init__."""
        stamped = Row(
            doctype="Purchase Order Item",
            item_code="ECL-00001",
            sales_order_item="l8cndlei1j",
            custom_technical_revision="TLR-11397",
        )
        doc = Doc([stamped])
        doc.validate_qty()

        self.assertEqual(doc.seen, [("ECL-00001", None)])
        self.assertEqual(stamped.get("sales_order_item"), "l8cndlei1j")

    def test_unrelated_child_doctypes_are_passed_straight_through(self):
        """Only the two doctypes ERPNext caps against Sales Order Item are touched."""
        other = Row(
            doctype="Sales Invoice Item",
            item_code="I-9",
            sales_order_item="SOI-9",
            custom_technical_revision="TLR-1",
        )
        doc = Doc([other])
        doc.validate_qty()

        self.assertEqual(doc.seen, [("I-9", "SOI-9")])

    def test_the_mixin_calls_through_rather_than_replacing_the_guard(self):
        """extend_doctype_class puts the mixin first in the MRO, so super() reaches the
        controller. Replacing the check instead of delegating would drop the native
        negative-qty and negative-rate validations that live in the same method."""
        doc = Doc([Row(item_code="I-1", sales_order_item="SOI-1")])
        doc.validate_qty()
        self.assertIsNotNone(doc.seen)


if __name__ == "__main__":
    unittest.main()
