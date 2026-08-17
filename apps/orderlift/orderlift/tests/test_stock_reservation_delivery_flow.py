import importlib
import sys
import types
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestStockReservationDeliveryFlow(unittest.TestCase):
    def test_stock_reservation_capability_is_registered(self):
        source = (APP_ROOT / "role_capabilities.py").read_text()

        self.assertIn("CAPABILITY_STOCK_RESERVATION_MANAGEMENT", source)
        self.assertIn('"stock_reservation_management"', source)
        self.assertIn('"Stock Reservation Management"', source)
        self.assertIn("Reserve customer stock through Pick Lists", source)

    def test_stock_notification_uses_dynamic_capability_recipients(self):
        source = (APP_ROOT / "sales" / "utils" / "stock_notifier.py").read_text()
        hooks = (APP_ROOT / "hooks.py").read_text()

        self.assertIn("notify_stock_reservation_team", source)
        self.assertIn("get_stock_reservation_recipients", source)
        self.assertIn("CAPABILITY_STOCK_RESERVATION_MANAGEMENT", source)
        self.assertIn("user_has_capability", source)
        self.assertIn("user_can_access_company", source)
        self.assertIn("Review shortages manually", source)
        self.assertIn('filters={"enabled": 1, "user_type": "System User"}', source)
        self.assertNotIn("Material Request", source)
        self.assertNotIn('filters={"role": "Stock Manager"', source)
        self.assertNotIn('"Has Role"', source)
        self.assertIn("orderlift.sales.utils.stock_notifier.notify_stock_reservation_team", hooks)

    def test_delivery_note_protects_reservations_and_allows_unreserved_stock(self):
        source = (
            APP_ROOT
            / "orderlift_logistics"
            / "utils"
            / "delivery_note_reservation_guard.py"
        ).read_text()
        hooks = (APP_ROOT / "hooks.py").read_text()

        self.assertIn("validate_delivery_note_pick_list_reservation", source)
        self.assertIn("against_pick_list", source)
        self.assertIn("pick_list_item", source)
        self.assertIn("stock_reserved_qty", source)
        self.assertIn("picked_qty", source)
        self.assertIn("Delivery quantity cannot exceed the reserved quantity", source)
        self.assertIn("_available_unreserved_qty", source)
        self.assertIn("direct delivery quantity", source)
        self.assertIn("_direct_serial_batch_problems", source)
        self.assertIn("Delivery Stock Validation", source)
        self.assertIn(
            "orderlift.orderlift_logistics.utils.delivery_note_reservation_guard.validate_delivery_note_pick_list_reservation",
            hooks,
        )

    def test_pick_list_submission_and_cancellation_manage_reservations(self):
        source = (
            APP_ROOT
            / "orderlift_logistics"
            / "utils"
            / "pick_list_reservation.py"
        ).read_text()
        hooks = (APP_ROOT / "hooks.py").read_text()

        self.assertIn("reserve_submitted_pick_list", source)
        self.assertIn("create_stock_reservation_entries", source)
        self.assertIn("cancel_pick_list_reservations", source)
        self.assertIn("cancel_stock_reservation_entries", source)
        self.assertIn("orderlift.orderlift_logistics.utils.pick_list_reservation.reserve_submitted_pick_list", hooks)
        self.assertIn("orderlift.orderlift_logistics.utils.pick_list_reservation.cancel_pick_list_reservations", hooks)

    def test_pick_list_and_stock_reservation_entry_are_company_scoped(self):
        company_access = (APP_ROOT / "company_access.py").read_text()
        hooks = (APP_ROOT / "hooks.py").read_text()

        for doctype in ["Pick List", "Stock Reservation Entry"]:
            self.assertIn(f'"{doctype}",', company_access)
            self.assertIn(f'"{doctype}": "orderlift.company_access.has_company_permission"', hooks)
        self.assertIn("def pick_list_query", company_access)
        self.assertIn("def stock_reservation_entry_query", company_access)
        self.assertIn('"Pick List": "orderlift.company_access.pick_list_query"', hooks)
        self.assertIn(
            '"Stock Reservation Entry": "orderlift.company_access.stock_reservation_entry_query"',
            hooks,
        )


class AttrDict(dict):
    __getattr__ = dict.get


class ValidationError(Exception):
    pass


class TestStockReservationDeliveryRuntime(unittest.TestCase):
    MODULE_NAMES = (
        "frappe",
        "frappe.utils",
        "orderlift.orderlift_logistics.utils.delivery_note_reservation_guard",
        "orderlift.orderlift_logistics.utils.pick_list_reservation",
    )

    def setUp(self):
        self.original_modules = {name: sys.modules.get(name) for name in self.MODULE_NAMES}
        frappe_stub = types.ModuleType("frappe")
        frappe_stub._ = lambda message, *args, **kwargs: message
        frappe_stub.throw = lambda message, title=None: (_ for _ in ()).throw(ValidationError(message))
        frappe_stub.get_cached_value = self._get_cached_value
        frappe_stub.get_all = lambda *args, **kwargs: []
        frappe_stub.db = AttrDict(
            get_single_value=lambda *args, **kwargs: 1,
            exists=lambda *args, **kwargs: False,
        )
        sys.modules["frappe"] = frappe_stub

        utils_stub = types.ModuleType("frappe.utils")
        utils_stub.cint = lambda value=0: int(value or 0)
        utils_stub.flt = lambda value=0: float(value or 0)
        sys.modules["frappe.utils"] = utils_stub

        for module_name in self.MODULE_NAMES[2:]:
            sys.modules.pop(module_name, None)
        self.guard = importlib.import_module(
            "orderlift.orderlift_logistics.utils.delivery_note_reservation_guard"
        )
        self.pick_list_reservation = importlib.import_module(
            "orderlift.orderlift_logistics.utils.pick_list_reservation"
        )
        self.guard._active_row_reservation_qty = lambda row, warehouse: 0
        self.guard._direct_serial_batch_problems = lambda row, warehouse: []

    def tearDown(self):
        for module_name, original in self.original_modules.items():
            if original is None:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = original

    @staticmethod
    def _get_cached_value(doctype, name, fieldname, **kwargs):
        if isinstance(fieldname, (list, tuple)):
            return AttrDict(has_serial_no=0, has_batch_no=0)
        return 1

    @staticmethod
    def _direct_row(qty, idx=1):
        return AttrDict(
            idx=idx,
            item_code="ITEM-1",
            warehouse="Stores - OMD",
            qty=qty,
            stock_qty=qty,
            conversion_factor=1,
            against_pick_list="",
            pick_list_item="",
            against_sales_order="SO-1",
            so_detail=f"SO-ITEM-{idx}",
            delivered_by_supplier=0,
        )

    def test_direct_delivery_uses_only_unreserved_balance(self):
        self.guard._available_unreserved_qty = lambda item_code, warehouse: 3

        self.guard.validate_delivery_note_pick_list_reservation(
            AttrDict(is_return=0, items=[self._direct_row(3)])
        )

        with self.assertRaisesRegex(ValidationError, "exceeds unreserved stock"):
            self.guard.validate_delivery_note_pick_list_reservation(
                AttrDict(is_return=0, items=[self._direct_row(4)])
            )

    def test_direct_delivery_aggregates_duplicate_item_rows(self):
        self.guard._available_unreserved_qty = lambda item_code, warehouse: 3

        with self.assertRaisesRegex(ValidationError, "exceeds unreserved stock"):
            self.guard.validate_delivery_note_pick_list_reservation(
                AttrDict(is_return=0, items=[self._direct_row(2, 1), self._direct_row(2, 2)])
            )

    def test_direct_delivery_requires_pick_list_for_own_reservation(self):
        self.guard._active_row_reservation_qty = lambda row, warehouse: 1
        self.guard._available_unreserved_qty = lambda item_code, warehouse: 10

        with self.assertRaisesRegex(ValidationError, "has reserved stock"):
            self.guard.validate_delivery_note_pick_list_reservation(
                AttrDict(is_return=0, items=[self._direct_row(1)])
            )

    @staticmethod
    def _pick_list_row(**overrides):
        row = AttrDict(
            idx=1,
            item_code="ITEM-1",
            warehouse="Stores - OMD",
            qty=5,
            stock_qty=5,
            conversion_factor=1,
            against_pick_list="PL-1",
            pick_list_item="PL-1-ROW-1",
            against_sales_order="",
            so_detail="",
            custom_technical_revision="",
            delivered_by_supplier=0,
        )
        row.update(overrides)
        return row

    def _install_pick_list(self, docstatus=1, picked_qty=5, stock_reserved_qty=5):
        pick_list = AttrDict(name="PL-1", docstatus=docstatus)
        pick_list["locations"] = [
            AttrDict(
                name="PL-1-ROW-1",
                picked_qty=picked_qty,
                stock_reserved_qty=stock_reserved_qty,
            )
        ]
        self.guard.frappe.db.exists = lambda *args, **kwargs: True
        self.guard.frappe.get_doc = lambda doctype, name: pick_list
        return pick_list

    def _validate(self, row):
        self.guard.validate_delivery_note_pick_list_reservation(
            AttrDict(is_return=0, items=[row])
        )

    def test_a_lineage_stamped_addition_needs_no_sales_order_reference(self):
        """Spec rule 3: an engineering addition carries no Sales Order link, because
        that link is what would pull it onto an invoice. Delivering a picked addition
        must therefore not be rejected for a missing Sales Order reference."""
        self._install_pick_list()

        self._validate(self._pick_list_row(custom_technical_revision="TLR-1"))

    def test_an_unstamped_pick_list_row_still_requires_the_sales_order_reference(self):
        self._install_pick_list()

        with self.assertRaisesRegex(ValidationError, "Sales Order reference is required"):
            self._validate(self._pick_list_row())

    def test_a_stamped_addition_still_needs_both_pick_list_references(self):
        self._install_pick_list()

        with self.assertRaisesRegex(ValidationError, "both Pick List and Pick List Item"):
            self._validate(
                self._pick_list_row(custom_technical_revision="TLR-1", pick_list_item="")
            )

    def test_a_stamped_addition_still_needs_a_submitted_pick_list(self):
        self._install_pick_list(docstatus=0)

        with self.assertRaisesRegex(ValidationError, "must be submitted"):
            self._validate(self._pick_list_row(custom_technical_revision="TLR-1"))

    def test_a_stamped_addition_still_needs_picked_and_reserved_quantity(self):
        self._install_pick_list(picked_qty=0, stock_reserved_qty=0)

        with self.assertRaisesRegex(ValidationError, "must have a picked quantity"):
            self._validate(self._pick_list_row(custom_technical_revision="TLR-1"))

    def test_a_stamped_addition_cannot_deliver_more_than_was_picked(self):
        self._install_pick_list(picked_qty=2, stock_reserved_qty=2)

        with self.assertRaisesRegex(ValidationError, "cannot exceed the picked quantity"):
            self._validate(self._pick_list_row(custom_technical_revision="TLR-1"))

    def test_pick_list_submit_and_cancel_manage_reservation(self):
        calls = []
        doc = AttrDict(name="PL-1", docstatus=1, purpose="Delivery")
        doc.has_unreserved_stock = lambda: True
        doc.create_stock_reservation_entries = lambda notify=False: calls.append(("reserve", notify))
        doc.cancel_stock_reservation_entries = lambda notify=False: calls.append(("cancel", notify))

        self.pick_list_reservation.reserve_submitted_pick_list(doc)
        self.pick_list_reservation.frappe.db.exists = lambda *args, **kwargs: True
        self.pick_list_reservation.cancel_pick_list_reservations(doc)

        self.assertEqual(calls, [("reserve", False), ("cancel", False)])


if __name__ == "__main__":
    unittest.main()
