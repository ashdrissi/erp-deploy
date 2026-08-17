import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class AttrDict(dict):
    __getattr__ = dict.get


def revision_stub(**values):
    """A revision double that is deliberately NOT a dict.

    AttrDict subclasses dict, so `.items` resolves to the real `dict.items` method
    and never reaches `__getattr__`. A Frappe Document exposes `.items` as its child
    table, so a revision double has to be a plain namespace to behave like one.
    """
    return types.SimpleNamespace(**values)


class FakeDB:
    def exists(self, *args, **kwargs):
        return False

    def get_value(self, *args, **kwargs):
        return None


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda message, *args, **kwargs: message
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(ValueError(message))
frappe_stub.db = FakeDB()

utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(value or 0)
utils_stub.flt = lambda value=0: float(value or 0)
utils_stub.getdate = lambda value: value
utils_stub.nowdate = lambda: "2026-08-15"
utils_stub.now_datetime = lambda: "2026-08-15 00:00:00"

sys.modules.setdefault("frappe", frappe_stub)
sys.modules.setdefault("frappe.utils", utils_stub)

model_stub = types.ModuleType("frappe.model")
document_stub = types.ModuleType("frappe.model.document")


class _StubDocument:
    pass


document_stub.Document = _StubDocument
sys.modules.setdefault("frappe.model", model_stub)
sys.modules.setdefault("frappe.model.document", document_stub)

from orderlift.orderlift_logistics import technical_allocation, technical_procurement


APP_ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = APP_ROOT / "orderlift_logistics" / "doctype"


class FakeMeta:
    def __init__(self, fields):
        self.fields = set(fields)

    def get_field(self, fieldname):
        return AttrDict(fieldname=fieldname) if fieldname in self.fields else None


class TestTechnicalProcurement(unittest.TestCase):
    def test_exact_core_doctypes_and_safe_adapters(self):
        self.assertEqual(
            technical_procurement.REVISION_DOCTYPE,
            "Sales Order Technical List Revision",
        )
        self.assertEqual(
            technical_procurement.TECHNICAL_LIST_DOCTYPE,
            "Sales Order Technical List",
        )
        self.assertEqual(
            technical_procurement.SAFE_ADAPTERS,
            {
                "revision_to_material_request": "Material Request",
                "revision_to_purchase_order": "Purchase Order",
                "revision_to_delivery_note": "Delivery Note",
                "revision_to_pick_list": "Pick List",
            },
        )
        self.assertTrue(all("." not in key for key in technical_procurement.SAFE_ADAPTERS))

    def test_pick_list_is_registered_with_its_own_pool_and_child_table(self):
        self.assertEqual(
            technical_procurement.SAFE_ADAPTERS["revision_to_pick_list"], "Pick List"
        )
        self.assertEqual(
            technical_procurement.PROCUREMENT_ITEM_DOCTYPES["Pick List"], "Pick List Item"
        )
        self.assertIn("Pick List", technical_procurement.SUPPORTED_PROCUREMENT_DOCTYPES)
        # Pick List stores rows in "locations", not "items".
        self.assertEqual(technical_procurement.TARGET_CHILD_TABLES["Pick List"], "locations")
        # Picking has its own pool: a pick that becomes its own Delivery Note must not
        # consume the approved quantity twice.
        self.assertEqual(
            technical_allocation.ADAPTER_POOLS["revision_to_pick_list"], "picking"
        )
        # Pick List must never enter the procurement allocation pool.
        self.assertNotIn("Pick List", technical_allocation.ALLOCATION_ITEM_DOCTYPES)

    def test_delivery_note_carries_lineage_and_row_validation(self):
        self.assertEqual(
            technical_procurement.PROCUREMENT_ITEM_DOCTYPES["Delivery Note"],
            "Delivery Note Item",
        )
        self.assertIn("Delivery Note", technical_procurement.SUPPORTED_PROCUREMENT_DOCTYPES)
        self.assertEqual(technical_procurement.TARGET_CHILD_TABLES["Delivery Note"], "items")

    def test_action_doctype_registry_matches_the_adapter_registry(self):
        from orderlift.orderlift_logistics.doctype.technical_procurement_action import (
            technical_procurement_action,
        )

        self.assertEqual(
            technical_procurement_action.SAFE_ADAPTERS,
            technical_procurement.SAFE_ADAPTERS,
        )
        action = json.loads(
            (
                DOCTYPE_ROOT
                / "technical_procurement_action"
                / "technical_procurement_action.json"
            ).read_text()
        )
        fields = {field["fieldname"]: field for field in action["fields"]}
        self.assertIn("revision_to_delivery_note", fields["adapter_key"]["options"])
        self.assertIn("Delivery Note", fields["target_doctype"]["options"])
        self.assertIn("revision_to_pick_list", fields["adapter_key"]["options"])
        self.assertIn("Pick List", fields["target_doctype"]["options"])

    def test_delivery_note_rows_use_against_sales_order_and_so_detail(self):
        """Delivery Note Item has no sales_order/sales_order_item columns. Native
        delivered-qty tracking hangs off so_detail, and an engineering addition has
        no Sales Order line so both fields must stay empty for it."""
        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        branch = source.split('if target_doctype == "Delivery Note":', 1)[1].split(
            "    _set_known_fields", 1
        )[0]
        self.assertIn("customer", branch)
        self.assertIn("posting_date", branch)

        rows = source.split("def _delivery_row_values", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("against_sales_order", rows)
        self.assertIn("so_detail", rows)
        self.assertNotIn('"sales_order_item": line.sales_order_item', rows)

    def test_delivery_row_values_omit_sales_order_link_for_added_lines(self):
        sold = AttrDict(item_code="I-1", item_name="One", description="d",
                        sales_order_item="SOI-1", uom="Nos", conversion_factor=1,
                        stock_uom="Nos", warehouse="WH - O", required_date=None)
        added = AttrDict(item_code="I-2", item_name="Two", description="d",
                         sales_order_item="", uom="Nos", conversion_factor=1,
                         stock_uom="Nos", warehouse="WH - O", required_date=None)
        revision = AttrDict(sales_order="SO-1", project="PROJ-1")

        sold_values = technical_procurement._delivery_row_values(revision, sold, 4)
        added_values = technical_procurement._delivery_row_values(revision, added, 3)

        self.assertEqual(sold_values["against_sales_order"], "SO-1")
        self.assertEqual(sold_values["so_detail"], "SOI-1")
        self.assertEqual(sold_values["qty"], 4)
        # Added lines were never sold, so they must not link to the Sales Order:
        # that link is what would pull them into an invoice.
        self.assertEqual(added_values["against_sales_order"], "")
        self.assertEqual(added_values["so_detail"], "")

    def test_delivery_rows_carry_the_contract_rate_not_the_price_list_rate(self):
        """Without an explicit rate, ERPNext's set_missing_values fetches the price
        list rate: the bon de livraison would print list prices instead of the
        negotiated ones, and any discount would read as a rate mismatch to the
        price-list guard. Additions are absorbed, so they carry zero."""
        sold = AttrDict(item_code="I-1", item_name="One", description="d",
                        sales_order_item="SOI-1", uom="Nos", conversion_factor=1,
                        stock_uom="Nos", warehouse="WH - O", required_date=None)
        added = AttrDict(item_code="I-2", item_name="Two", description="d",
                         sales_order_item="", uom="Nos", conversion_factor=1,
                         stock_uom="Nos", warehouse="WH - O", required_date=None)
        revision = AttrDict(sales_order="SO-1", project="PROJ-1")
        calls = []

        def get_value(doctype, name, fieldnames, as_dict=False):
            calls.append((doctype, name))
            return AttrDict(
                rate=80,
                price_list_rate=100,
                discount_percentage=20,
                discount_amount=20,
            )

        with patch.object(frappe_stub.db, "get_value", side_effect=get_value):
            sold_values = technical_procurement._delivery_row_values(revision, sold, 4)
            added_values = technical_procurement._delivery_row_values(revision, added, 3)

        self.assertEqual(sold_values["rate"], 80)
        self.assertEqual(sold_values["price_list_rate"], 100)
        self.assertEqual(sold_values["discount_percentage"], 20)
        self.assertEqual(sold_values["discount_amount"], 20)
        self.assertEqual(added_values["rate"], 0)
        self.assertEqual(added_values["price_list_rate"], 0)
        # One fetch for the sold row, none for the addition.
        self.assertEqual(calls, [("Sales Order Item", "SOI-1")])

    def test_delivery_rows_survive_a_missing_sales_order_item_row(self):
        sold = AttrDict(item_code="I-1", item_name="One", description="d",
                        sales_order_item="SOI-1", uom="Nos", conversion_factor=1,
                        stock_uom="Nos", warehouse="WH - O", required_date=None)
        revision = AttrDict(sales_order="SO-1", project="PROJ-1")
        with patch.object(frappe_stub.db, "get_value", return_value=None):
            values = technical_procurement._delivery_row_values(revision, sold, 4)
        self.assertEqual(values["against_sales_order"], "SO-1")

    def test_create_from_revision_picks_the_pool_matching_the_adapter(self):
        """The adapter must consume its own pool, and it must do so through the one
        shared helper -- not a second copy of the mapping that can drift from the
        one get_available_actions filters with."""
        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        body = source.split("def _create_from_revision", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("remaining_for_adapter(adapter_key, revision, {})", body)
        self.assertNotIn("delivery_remaining_by_line(", body)
        self.assertEqual(
            technical_allocation.ADAPTER_POOLS["revision_to_delivery_note"], "delivery"
        )
        self.assertEqual(
            technical_allocation.ADAPTER_POOLS["revision_to_material_request"], "procurement"
        )
        self.assertEqual(
            technical_allocation.ADAPTER_POOLS["revision_to_purchase_order"], "procurement"
        )

    def test_create_delivery_note_is_whitelisted_and_takes_no_supplier(self):
        import inspect

        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        self.assertIn(
            '@frappe.whitelist()\ndef create_delivery_note(', source
        )
        signature = inspect.signature(technical_procurement.create_delivery_note)
        self.assertEqual(
            list(signature.parameters),
            ["revision", "selected_row_ids", "quantities"],
        )

    def test_company_policy_fields_are_exact(self):
        self.assertEqual(
            (
                technical_procurement.COMPANY_ENABLED_FIELD,
                technical_procurement.COMPANY_EFFECTIVE_FROM_FIELD,
                technical_procurement.COMPANY_APPLY_ALL_FIELD,
                technical_procurement.COMPANY_BUSINESS_TYPES_FIELD,
                technical_procurement.COMPANY_DEFAULT_ROUTE_FIELD,
            ),
            (
                "custom_enable_sales_order_technical_lists",
                "custom_technical_list_effective_from",
                "custom_technical_list_apply_all_business_types",
                "custom_technical_list_business_types",
                "custom_technical_list_default_procurement_route",
            ),
        )

    def test_lineage_fields_are_exact(self):
        self.assertEqual(
            set(technical_procurement.LINEAGE_FIELDS),
            {
                "custom_technical_list",
                "custom_technical_revision",
                "custom_technical_revision_item",
                "custom_technical_line_key",
                "custom_technical_approval_hash",
                "custom_technical_procurement_route",
                "custom_technical_procurement_action",
            },
        )
        meta = FakeMeta(technical_procurement.LINEAGE_FIELDS)
        values = {
            "technical_list": "TL-1",
            "revision": "TLR-1",
            "revision_item": "TLRI-1",
            "line_key": "SOI-1",
            "approval_hash": "abc",
            "route": "Default",
            "action": "MR",
        }
        self.assertEqual(len(technical_procurement._lineage_values(meta, values)), 7)

    def test_selection_accepts_ids_quantity_map_and_rejects_invalid_values(self):
        self.assertEqual(
            technical_procurement._normalise_selection(
                '["ROW-1", "ROW-2"]', '{"ROW-1": 2}'
            ),
            {"ROW-1": 2.0, "ROW-2": None},
        )
        with self.assertRaises(ValueError):
            technical_procurement._normalise_selection(["ROW-1", "ROW-1"])
        with self.assertRaises(ValueError):
            technical_procurement._normalise_selection(["ROW-1"], {"ROW-1": 0})

    def test_revision_quantity_uses_execution_stock_quantity(self):
        line = AttrDict(execution_qty=3, execution_stock_qty=12, conversion_factor=4)
        self.assertEqual(technical_allocation.line_stock_qty(line), 12)
        self.assertEqual(
            technical_allocation.row_stock_qty(
                {"qty": 3, "stock_qty": 0, "conversion_factor": 4}
            ),
            12,
        )

    def test_allocation_key_prefers_sales_order_item(self):
        self.assertEqual(
            technical_allocation.allocation_key(
                {"sales_order_item": "SOI-1", "item_code": "I-1"}
            ),
            "SOI-1",
        )
        self.assertEqual(
            technical_allocation.allocation_key({"sales_order_item": "", "item_code": "I-1"}),
            "item::I-1",
        )

    def test_only_material_requests_and_direct_purchase_orders_reserve_quantity(self):
        self.assertTrue(
            technical_allocation.is_root_allocation(
                {"doctype": "Material Request"}, {"material_request_item": ""}
            )
        )
        self.assertTrue(
            technical_allocation.is_root_allocation(
                {"doctype": "Purchase Order"}, {"material_request_item": ""}
            )
        )
        self.assertFalse(
            technical_allocation.is_root_allocation(
                {"doctype": "Purchase Order"}, {"material_request_item": "MRI-1"}
            )
        )

    def test_revision_reference_resolves_parent_current_revision(self):
        supplied = AttrDict(
            doctype=technical_procurement.REVISION_DOCTYPE,
            name="TLR-OLD",
            technical_list="TL-1",
            check_permission=lambda *args: None,
        )
        parent = AttrDict(
            doctype=technical_procurement.TECHNICAL_LIST_DOCTYPE,
            name="TL-1",
            sales_order="SO-1",
            current_revision="TLR-CURRENT",
            check_permission=lambda *args: None,
        )
        current = AttrDict(
            doctype=technical_procurement.REVISION_DOCTYPE,
            name="TLR-CURRENT",
            technical_list="TL-1",
            check_permission=lambda *args: None,
        )
        documents = {
            (technical_procurement.REVISION_DOCTYPE, "TLR-OLD"): supplied,
            (technical_procurement.TECHNICAL_LIST_DOCTYPE, "TL-1"): parent,
            (technical_procurement.REVISION_DOCTYPE, "TLR-CURRENT"): current,
        }
        with patch.object(
            frappe_stub,
            "get_doc",
            side_effect=lambda doctype, name: documents[(doctype, name)],
            create=True,
        ), patch.object(
            technical_procurement, "_technical_schema_ready", return_value=True
        ), patch.object(technical_procurement, "_validate_revision"):
            _reference, resolved_parent, resolved_revision = (
                technical_procurement._resolve_current_revision(
                    technical_procurement.REVISION_DOCTYPE, "TLR-OLD"
                )
            )

        self.assertIs(resolved_parent, parent)
        self.assertIs(resolved_revision, current)

    def test_business_type_policy_uses_values_not_labels(self):
        fields = {
            technical_procurement.COMPANY_ENABLED_FIELD,
            technical_procurement.COMPANY_APPLY_ALL_FIELD,
            technical_procurement.COMPANY_BUSINESS_TYPES_FIELD,
        }
        values = {
            technical_procurement.COMPANY_ENABLED_FIELD: 1,
            technical_procurement.COMPANY_APPLY_ALL_FIELD: 0,
        }
        company = AttrDict(
            custom_technical_list_business_types=[AttrDict(business_type="TYPE-42")]
        )
        source = AttrDict(company="Orderlift", custom_crm_business_type="TYPE-42")
        with patch.object(
            technical_procurement, "_meta", return_value=FakeMeta(fields)
        ), patch.object(
            frappe_stub.db,
            "get_value",
            side_effect=lambda doctype, name, fieldname: values.get(fieldname),
        ), patch.object(frappe_stub, "get_doc", return_value=company, create=True):
            self.assertTrue(technical_procurement._technical_policy_applies(source))
            source["custom_crm_business_type"] = "TYPE-OTHER"
            self.assertFalse(technical_procurement._technical_policy_applies(source))

    def test_setup_doctypes_define_ordered_safe_routes(self):
        action = json.loads(
            (
                DOCTYPE_ROOT
                / "technical_procurement_action"
                / "technical_procurement_action.json"
            ).read_text()
        )
        route = json.loads(
            (
                DOCTYPE_ROOT
                / "technical_procurement_route"
                / "technical_procurement_route.json"
            ).read_text()
        )
        step = json.loads(
            (
                DOCTYPE_ROOT
                / "technical_procurement_route_step"
                / "technical_procurement_route_step.json"
            ).read_text()
        )
        action_fields = {field["fieldname"]: field for field in action["fields"]}
        route_fields = {field["fieldname"]: field for field in route["fields"]}
        step_fields = {field["fieldname"]: field for field in step["fields"]}

        self.assertEqual(action_fields["adapter_key"]["fieldtype"], "Select")
        self.assertNotIn(".", action_fields["adapter_key"]["options"])
        self.assertEqual(route_fields["company"]["options"], "Company")
        self.assertEqual(route_fields["steps"]["options"], "Technical Procurement Route Step")
        self.assertEqual(step_fields["action"]["options"], "Technical Procurement Action")
        self.assertEqual(
            step_fields["required_previous_action"]["options"],
            "Technical Procurement Action",
        )

    def test_source_contract_uses_parent_current_revision_and_execution_fields(self):
        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        self.assertIn("technical_list.current_revision", source)
        self.assertNotIn("custom_current_revision", source)
        self.assertNotIn("custom_current_technical_revision", source)
        for fieldname in (
            "item_code",
            "item_name",
            "description",
            "sales_order_item",
            "sales_order_qty",
            "execution_qty",
            "execution_stock_qty",
            "uom",
            "conversion_factor",
            "stock_uom",
            "warehouse",
            "required_date",
            "procurement_route",
            "line_key",
            "execution_relevant",
        ):
            self.assertIn(fieldname, source)
        self.assertIn("_recalculate_approval_hash", source)
        self.assertIn("parent_doc.docstatus < 2", source)
        allocation_source = (APP_ROOT / "orderlift_logistics" / "technical_allocation.py").read_text()
        self.assertIn("parent_doc.docstatus < 2", allocation_source)
        self.assertIn("AND child.sales_order = %s{extra}", allocation_source)
        self.assertIn("def allocation_key", allocation_source)
        self.assertNotIn('"custom_technical_revision_item", "qty"', source)
        self.assertIn("FOR UPDATE", source)
        self.assertIn("target.insert()", source)
        self.assertNotIn("target.submit()", source)
        self.assertNotIn("ignore_permissions=True", source)
        self.assertNotIn("bypass", source.lower())

    def test_allocation_registry_is_separate_from_lineage_registry(self):
        """Delivery Note carries lineage but must never enter the procurement
        allocation pool: _allocated_stock_qty joins on child.sales_order, a column
        Delivery Note Item does not have, and deliveries are not procurement."""
        self.assertEqual(
            technical_allocation.ALLOCATION_ITEM_DOCTYPES,
            {
                "Material Request": "Material Request Item",
                "Purchase Order": "Purchase Order Item",
            },
        )
        self.assertNotIn("Delivery Note", technical_allocation.ALLOCATION_ITEM_DOCTYPES)
        self.assertFalse(hasattr(technical_procurement, "ROOT_TARGET_ITEM_DOCTYPES"))

    def test_lineage_lookups_use_the_lineage_registry_not_the_allocation_registry(self):
        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        # These three read a child doctype for lineage purposes and must resolve
        # Delivery Note, so they cannot read the allocation registry.
        self.assertIn("PROCUREMENT_ITEM_DOCTYPES.get(target_doctype)", source)
        self.assertNotIn("ALLOCATION_ITEM_DOCTYPES", source)
        # Only the allocation pool may be keyed off the allocation registry, and it
        # now lives in technical_allocation: one definition, one reader.
        allocation_source = (APP_ROOT / "orderlift_logistics" / "technical_allocation.py").read_text()
        self.assertIn("ALLOCATION_ITEM_DOCTYPES.items()", allocation_source)
        self.assertEqual(allocation_source.count("ALLOCATION_ITEM_DOCTYPES"), 2)

    def test_delivery_remaining_survives_a_new_revision(self):
        """Counting delivered per revision would reset the total to zero whenever a
        revision is approved, making the hard cap bypassable by the very mechanism
        that is supposed to raise it. Delivered totals are keyed per Sales Order
        line across the whole Technical List."""
        source = (APP_ROOT / "orderlift_logistics" / "technical_allocation.py").read_text()
        delivered = source.split("def delivered_stock_qty", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("child.custom_technical_list = %s", delivered)
        self.assertNotIn("custom_technical_revision = %s", delivered)
        self.assertIn("parent_doc.docstatus < 2", delivered)

    def test_picked_pool_is_anchored_on_the_technical_list_not_the_revision(self):
        """Rule 6 applies to picking exactly as it does to delivery: counting per
        revision would reset picked totals whenever engineering approves a new one."""
        source = (
            APP_ROOT / "orderlift_logistics" / "technical_allocation.py"
        ).read_text()
        body = source.split("def picked_stock_qty", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("child.custom_technical_list = %s", body)
        self.assertNotIn("custom_technical_revision = %s", body)
        self.assertIn("parent_doc.docstatus < 2", body)
        self.assertIn("tabPick List Item", body)

    def test_picking_remaining_is_independent_of_delivery(self):
        """A pick that later becomes its own Delivery Note must not consume the
        approved quantity twice, so the two pools never see each other."""
        revision = revision_stub(
            name="TLR-1",
            technical_list="TL-1",
            items=[
                AttrDict(name="R1", sales_order_item="SOI-1", item_code="I-1",
                         execution_stock_qty=10, execution_relevant=1),
            ],
        )
        with patch.object(
            technical_allocation, "picked_stock_qty", return_value={"SOI-1": 4}
        ), patch.object(
            technical_allocation, "delivered_stock_qty", return_value={"SOI-1": 10}
        ):
            picking = technical_allocation.picking_remaining_by_line(revision)
            delivery = technical_allocation.delivery_remaining_by_line(revision)
        # 4 picked of 10 approved leaves 6 pickable, regardless of what was delivered.
        self.assertEqual(picking["R1"], 6)
        self.assertEqual(delivery["R1"], 0)

    def test_delivery_remaining_subtracts_delivered_from_execution_qty(self):
        revision = revision_stub(
            name="TLR-2",
            technical_list="TL-1",
            items=[
                AttrDict(name="R1", sales_order_item="SOI-1", item_code="I-1",
                         execution_stock_qty=12, execution_relevant=1),
                AttrDict(name="R2", sales_order_item="", item_code="I-2",
                         execution_stock_qty=5, execution_relevant=1),
                AttrDict(name="R3", sales_order_item="SOI-3", item_code="I-3",
                         execution_stock_qty=9, execution_relevant=0),
            ],
        )
        with patch.object(
            technical_allocation,
            "delivered_stock_qty",
            return_value={"SOI-1": 8, "item::I-2": 5},
        ):
            remaining = technical_allocation.delivery_remaining_by_line(revision)

        self.assertEqual(remaining["R1"], 4)      # 12 approved - 8 delivered
        self.assertEqual(remaining["R2"], 0)      # added line, fully delivered
        self.assertNotIn("R3", remaining)         # not execution relevant

    def test_delivery_remaining_never_goes_negative(self):
        """A revision that lowers execution qty below what already shipped must
        report zero remaining, not a negative that would read as credit."""
        revision = revision_stub(
            name="TLR-3",
            technical_list="TL-1",
            items=[AttrDict(name="R1", sales_order_item="SOI-1", item_code="I-1",
                            execution_stock_qty=6, execution_relevant=1)],
        )
        with patch.object(
            technical_allocation, "delivered_stock_qty", return_value={"SOI-1": 10}
        ):
            self.assertEqual(
                technical_allocation.delivery_remaining_by_line(revision)["R1"], 0
            )

    def test_target_sales_order_resolves_delivery_note_rows(self):
        """Delivery Note Item stores the link as against_sales_order/so_detail.
        Without this the native block cannot find the source Sales Order and every
        Opportunity-origin Delivery Note would pass unchecked."""
        with patch.object(
            frappe_stub.db, "get_value", return_value="SO-1"
        ):
            self.assertEqual(
                technical_procurement._target_sales_order({"so_detail": "SOI-1"}),
                "SO-1",
            )
        self.assertEqual(
            technical_procurement._target_sales_order(
                {"against_sales_order": "SO-2", "so_detail": ""}
            ),
            "SO-2",
        )

    def test_delivery_cumulative_cap_uses_the_delivery_pool(self):
        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        body = source.split("def validate_procurement_document", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("delivered_stock_qty(", body)
        self.assertIn("exceeds the remaining delivery quantity", body)

    def test_delivery_cap_aggregates_lines_sharing_an_allocation_key(self):
        """Engineering additions collapse to "item::<item_code>", so two distinct
        revision lines can share one pool bucket. Checking each line separately
        against that bucket would let one document ship the budget twice, so both
        the requested total and the budget must be summed per key."""
        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        body = source.split("def validate_procurement_document", 1)[1].split("\ndef ", 1)[0]
        delivery = body.split('if doctype == "Delivery Note":', 1)[1]
        self.assertIn("requested[key] += total", delivery)
        # The budget comes from the whole revision, not from this document's rows.
        self.assertIn("budget_by_key(revision)", delivery)
        # The cap must be evaluated once per key, after aggregation -- not inside
        # the loop that walks revision lines.
        self.assertLess(
            delivery.index("requested[key] += total"),
            delivery.index("existing + total > budget[key]"),
        )

    def test_available_actions_filter_each_action_against_its_own_pool(self):
        """A line raised as a full Material Request has zero procurement remaining
        but is still undelivered. Filtering the whole payload against the
        procurement pool drops it from the delivery action too, which silently
        produces a Delivery Note missing the procured line."""
        revision = revision_stub(
            name="TLR-1",
            technical_list="TL-1",
            sales_order="SO-1",
            company="Orderlift",
            approval_hash="abc",
            items=[
                AttrDict(
                    name="R1",
                    line_key="SOI-1",
                    sales_order_item="SOI-1",
                    item_code="I-1",
                    execution_stock_qty=5,
                    execution_relevant=1,
                )
            ],
        )
        technical_list = AttrDict(
            doctype=technical_procurement.TECHNICAL_LIST_DOCTYPE,
            name="TL-1",
            sales_order="SO-1",
        )
        reference = AttrDict(doctype="Sales Order", name="SO-1")
        route = AttrDict(name="ROUTE-1")
        steps = [
            (
                AttrDict(sequence=10, required_previous_action=""),
                AttrDict(
                    name="ACT-MR",
                    action_label="Create Material Request",
                    adapter_key="revision_to_material_request",
                    sequence=10,
                ),
            ),
            (
                AttrDict(sequence=20, required_previous_action=""),
                AttrDict(
                    name="ACT-DN",
                    action_label="Create Delivery Note",
                    adapter_key="revision_to_delivery_note",
                    sequence=20,
                ),
            ),
        ]

        with patch.object(
            technical_procurement,
            "_resolve_current_revision",
            return_value=(reference, technical_list, revision),
        ), patch.object(technical_procurement, "_validate_revision"), patch.object(
            frappe_stub,
            "get_doc",
            return_value=AttrDict(
                name="SO-1", company="Orderlift", check_permission=lambda *args: None
            ),
            create=True,
        ), patch.object(
            technical_procurement, "_technical_policy_applies", return_value=True
        ), patch.object(
            technical_procurement, "_route_for_line", return_value=route
        ), patch.object(
            technical_procurement, "_route_actions", return_value=steps
        ), patch.object(
            technical_allocation, "remaining_by_line", return_value={}
        ) as procurement_pool, patch.object(
            technical_allocation, "delivery_remaining_by_line", return_value={"R1": 5}
        ) as delivery_pool:
            payload = technical_procurement.get_available_actions("Sales Order", "SO-1")

        actions = {action["adapter_key"]: action for action in payload["actions"]}
        self.assertIn("revision_to_delivery_note", actions)
        self.assertEqual(actions["revision_to_delivery_note"]["row_ids"], ["R1"])
        self.assertNotIn("revision_to_material_request", actions)
        # Each pool costs SQL, so it must be computed at most once.
        self.assertEqual(procurement_pool.call_count, 1)
        self.assertEqual(delivery_pool.call_count, 1)

    def _return_delivery_note(self, *, is_return):
        revision = revision_stub(
            name="TLR-1",
            technical_list="TL-1",
            company="Orderlift",
            project="PROJ-1",
            sales_order="SO-1",
            approval_hash="abc",
            check_permission=lambda *args: None,
            items=[
                AttrDict(
                    name="R1",
                    line_key="SOI-1",
                    sales_order_item="SOI-1",
                    item_code="I-1",
                    uom="Nos",
                    conversion_factor=1,
                    stock_uom="Nos",
                    warehouse="WH - O",
                    execution_relevant=1,
                    execution_stock_qty=6,
                )
            ],
        )
        technical_list = AttrDict(
            name="TL-1", technical_list="TL-1", check_permission=lambda *args: None
        )
        row = AttrDict(
            item_code="I-1",
            qty=-2,
            stock_qty=-2,
            conversion_factor=1,
            uom="Nos",
            stock_uom="Nos",
            warehouse="WH - O",
            project="PROJ-1",
            against_sales_order="SO-1",
            so_detail="SOI-1",
            custom_technical_list="TL-1",
            custom_technical_revision="TLR-1",
            custom_technical_revision_item="R1",
            custom_technical_line_key="SOI-1",
            custom_technical_approval_hash="abc",
            custom_technical_procurement_route="ROUTE-1",
            custom_technical_procurement_action="ACT-DN",
        )
        doc = AttrDict(
            doctype="Delivery Note",
            docstatus=0,
            is_return=1 if is_return else 0,
            name="DN-RET-1",
            company="Orderlift",
            project="PROJ-1",
            items=[row],
        )
        documents = {
            (technical_procurement.REVISION_DOCTYPE, "TLR-1"): revision,
            (technical_procurement.TECHNICAL_LIST_DOCTYPE, "TL-1"): technical_list,
        }
        return doc, documents

    def test_sales_returns_against_a_technical_delivery_note_are_allowed(self):
        """make_sales_return copies the lineage fields (they are not no_copy) onto a
        return whose rows have negative qty. Without an is_return guard the row
        validation throws "quantity must be greater than zero" and no client refusal
        can ever be recorded."""
        doc, documents = self._return_delivery_note(is_return=True)
        with patch.object(
            technical_procurement, "_technical_schema_ready", return_value=True
        ), patch.object(
            frappe_stub,
            "get_doc",
            side_effect=lambda doctype, name: documents[(doctype, name)],
            create=True,
        ), patch.object(technical_procurement, "_lock_document"), patch.object(
            technical_procurement, "_validate_revision"
        ), patch.object(
            technical_procurement, "_validate_source_line"
        ), patch.object(
            technical_procurement, "delivered_stock_qty", return_value={}
        ):
            technical_procurement.validate_procurement_document(doc)

    def test_forward_delivery_note_rows_still_reject_a_negative_quantity(self):
        doc, documents = self._return_delivery_note(is_return=False)
        with patch.object(
            technical_procurement, "_technical_schema_ready", return_value=True
        ), patch.object(
            frappe_stub,
            "get_doc",
            side_effect=lambda doctype, name: documents[(doctype, name)],
            create=True,
        ), patch.object(technical_procurement, "_lock_document"), patch.object(
            technical_procurement, "_validate_revision"
        ), patch.object(
            technical_procurement, "_validate_source_line"
        ), patch.object(
            technical_procurement, "delivered_stock_qty", return_value={}
        ):
            with self.assertRaisesRegex(ValueError, "must be greater than zero"):
                technical_procurement.validate_procurement_document(doc)

    def test_is_return_guard_precedes_the_row_loop(self):
        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        body = source.split("def validate_procurement_document", 1)[1].split("\ndef ", 1)[0]
        self.assertIn('if cint(_get(doc, "is_return")):', body)
        self.assertLess(
            body.index('if cint(_get(doc, "is_return")):'),
            body.index('rows = _get(doc, "items") or []'),
        )

    def test_delivered_totals_keep_counting_return_rows(self):
        """A return's negative rows must stay in the delivered pool: that is what
        credits the quantity back so the line can be delivered again."""
        source = (APP_ROOT / "orderlift_logistics" / "technical_allocation.py").read_text()
        delivered = source.split("def delivered_stock_qty", 1)[1].split("\ndef ", 1)[0]
        self.assertNotIn("parent_doc.is_return", delivered)
        self.assertNotIn("child.is_return", delivered)
        self.assertIn("credits the quantity back", delivered)

    def _shared_key_revision(self):
        """Two engineering additions of the same item, 3 each. No sales_order_item,
        so both collapse to the single allocation key "item::I-2"."""
        def line(name):
            return AttrDict(
                name=name,
                line_key=name,
                sales_order_item="",
                item_code="I-2",
                uom="Nos",
                conversion_factor=1,
                stock_uom="Nos",
                warehouse="WH - O",
                execution_relevant=1,
                execution_stock_qty=3,
            )

        return revision_stub(
            name="TLR-1",
            technical_list="TL-1",
            company="Orderlift",
            project="PROJ-1",
            sales_order="SO-1",
            approval_hash="abc",
            check_permission=lambda *args: None,
            items=[line("R1"), line("R2")],
        )

    def _delivery_note_for(self, revision, revision_items):
        rows = [
            AttrDict(
                item_code="I-2",
                qty=3,
                stock_qty=3,
                conversion_factor=1,
                uom="Nos",
                stock_uom="Nos",
                warehouse="WH - O",
                project="PROJ-1",
                custom_technical_list="TL-1",
                custom_technical_revision=revision.name,
                custom_technical_revision_item=revision_item,
                custom_technical_line_key=revision_item,
                custom_technical_approval_hash="abc",
                custom_technical_procurement_route="ROUTE-1",
                custom_technical_procurement_action="ACT-DN",
            )
            for revision_item in revision_items
        ]
        return AttrDict(
            doctype="Delivery Note",
            docstatus=0,
            is_return=0,
            name="DN-1",
            company="Orderlift",
            project="PROJ-1",
            items=rows,
        )

    def _run_delivery_validation(self, revision, doc, delivered):
        documents = {
            (technical_procurement.REVISION_DOCTYPE, revision.name): revision,
            (technical_procurement.TECHNICAL_LIST_DOCTYPE, "TL-1"): AttrDict(
                name="TL-1", check_permission=lambda *args: None
            ),
        }
        with patch.object(
            technical_procurement, "_technical_schema_ready", return_value=True
        ), patch.object(
            frappe_stub,
            "get_doc",
            side_effect=lambda doctype, name: documents[(doctype, name)],
            create=True,
        ), patch.object(technical_procurement, "_lock_document"), patch.object(
            technical_procurement, "_validate_revision"
        ), patch.object(
            technical_procurement, "_validate_source_line"
        ), patch.object(
            technical_procurement, "delivered_stock_qty", return_value=delivered
        ):
            technical_procurement.validate_procurement_document(doc)

    def test_shared_key_budget_does_not_shrink_when_deliveries_are_split(self):
        """Two additions of 3 approve 6 deliverable units. Summing the budget only
        over the rows present on this document made the second delivery see a budget
        of 3 against 3 already delivered, so splitting the delivery in two turned 6
        approved units into 3 deliverable ones."""
        revision = self._shared_key_revision()
        # First document: both lines together, nothing delivered yet.
        self._run_delivery_validation(
            revision, self._delivery_note_for(revision, ["R1", "R2"]), {}
        )
        # Second scenario: the same two lines delivered one document at a time.
        self._run_delivery_validation(
            revision, self._delivery_note_for(revision, ["R1"]), {}
        )
        self._run_delivery_validation(
            revision, self._delivery_note_for(revision, ["R2"]), {"item::I-2": 3}
        )

    def test_shared_key_budget_is_still_capped_at_the_approved_total(self):
        revision = self._shared_key_revision()
        with self.assertRaisesRegex(ValueError, "remaining delivery quantity"):
            self._run_delivery_validation(
                revision,
                self._delivery_note_for(revision, ["R2"]),
                {"item::I-2": 6},
            )

    def test_delivery_remaining_apportions_a_shared_bucket_across_its_lines(self):
        """The shared remainder must be handed out once, in revision order, not
        subtracted in full from every line sharing the key."""
        revision = self._shared_key_revision()
        with patch.object(
            technical_allocation, "delivered_stock_qty", return_value={"item::I-2": 3}
        ):
            remaining = technical_allocation.delivery_remaining_by_line(revision)

        self.assertEqual(remaining["R1"], 3)
        self.assertEqual(remaining["R2"], 0)
        self.assertEqual(sum(remaining.values()), 3)

        with patch.object(
            technical_allocation, "delivered_stock_qty", return_value={"item::I-2": 4}
        ):
            remaining = technical_allocation.delivery_remaining_by_line(revision)
        self.assertEqual(remaining["R1"], 2)
        self.assertEqual(remaining["R2"], 0)

    def test_delivery_budget_is_summed_over_the_whole_revision(self):
        revision = self._shared_key_revision()
        revision.items.append(
            AttrDict(
                name="R3",
                sales_order_item="",
                item_code="I-2",
                execution_relevant=0,
                execution_stock_qty=99,
            )
        )
        self.assertEqual(
            dict(technical_allocation.budget_by_key(revision)),
            {"item::I-2": 6},
        )

    def test_native_delivery_note_from_sales_order_is_blocked(self):
        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        body = source.split("def validate_procurement_document", 1)[1].split("\ndef ", 1)[0]
        self.assertIn(
            "create {1} from the approved Technical List instead of directly from the Sales Order.",
            body,
        )

    def test_pick_list_sourced_delivery_rows_are_not_blocked_yet(self):
        """delivery_note_reservation_guard forces the Pick List route for reserved
        stock, and Pick Lists carry no lineage until Plan 2, so blocking these rows
        would make reserved-stock delivery impossible."""
        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        body = source.split("def validate_procurement_document", 1)[1].split("\ndef ", 1)[0]
        self.assertIn('_text(_get(row, "pick_list_item"))', body)
        self.assertIn("Remove this skip in Plan 2.", body)

    def _project_check_row(self, *, row_meta):
        source_line = AttrDict(
            name="R1",
            line_key="SOI-1",
            sales_order_item="SOI-1",
            item_code="I-1",
            uom="Nos",
            conversion_factor=1,
            stock_uom="Nos",
            warehouse="",
            execution_relevant=1,
            execution_stock_qty=3,
        )
        revision = revision_stub(
            name="TLR-1",
            technical_list="TL-1",
            company="Orderlift",
            project="PROJ-1",
            sales_order="SO-1",
            approval_hash="abc",
            items=[source_line],
        )
        row = AttrDict(
            meta=row_meta,
            item_code="I-1",
            qty=3,
            stock_qty=3,
            conversion_factor=1,
            uom="Nos",
            stock_uom="Nos",
            warehouse="",
            project="",
        )
        doc = AttrDict(doctype="Material Request", company="Orderlift", project="")
        return doc, row, revision, source_line

    def test_cleared_project_is_still_rejected_when_the_target_has_the_field(self):
        """Tolerating any empty project relaxed the invariant for Material Request
        and Purchase Order, which both carry the field: a row whose project was
        cleared then passed a check it used to fail."""
        doc, row, revision, source_line = self._project_check_row(
            row_meta=FakeMeta({"project"})
        )
        with patch.object(technical_procurement, "_validate_source_line"):
            with self.assertRaisesRegex(ValueError, "Project does not match"):
                technical_procurement._validate_target_row(doc, row, revision, source_line)

    def test_project_check_is_skipped_only_when_the_field_is_absent(self):
        """The tolerance exists for doctypes with no project field at all, not for
        any empty value."""
        doc, row, revision, source_line = self._project_check_row(
            row_meta=FakeMeta({"item_code"})
        )
        with patch.object(technical_procurement, "_validate_source_line"), patch.object(
            technical_procurement, "_meta", return_value=None
        ):
            technical_procurement._validate_target_row(doc, row, revision, source_line)

    def test_procurement_cumulative_cap_stays_reachable_for_other_doctypes(self):
        """The delivery branch ends in `return`; the procurement pool below it must
        still run for Material Request and Purchase Order."""
        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        body = source.split("def validate_procurement_document", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("allocated_by_revision = {}", body)
        self.assertLess(body.index('if doctype == "Delivery Note":'), body.index("allocated_by_revision = {}"))

    def test_allocation_helpers_live_in_their_own_module(self):
        from orderlift.orderlift_logistics import technical_allocation

        for name in (
            "ALLOCATION_ITEM_DOCTYPES",
            "ADAPTER_POOLS",
            "allocation_key",
            "line_stock_qty",
            "row_stock_qty",
            "allocated_stock_qty",
            "delivered_stock_qty",
            "budget_by_key",
            "delivery_remaining_by_line",
            "picked_stock_qty",
            "picking_remaining_by_line",
            "remaining_by_line",
            "remaining_for_adapter",
        ):
            self.assertTrue(hasattr(technical_allocation, name), name)

    def test_pool_selection_is_expressed_once_for_every_adapter(self):
        """The UI payload and the adapter must agree on remaining quantity. Two
        separate expressions of the same choice is how they drift, and a mismatch
        offers the user a quantity the adapter then refuses."""
        allocation_source = (APP_ROOT / "orderlift_logistics" / "technical_allocation.py").read_text()
        procurement_source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        self.assertIn("def remaining_for_adapter(", allocation_source)
        # Exactly one definition (in technical_allocation) and two call sites (the
        # UI payload and the adapter, both in technical_procurement).
        self.assertEqual(allocation_source.count("remaining_for_adapter("), 1)
        self.assertEqual(procurement_source.count("remaining_for_adapter("), 2)

    def test_remaining_for_adapter_maps_each_adapter_to_its_pool(self):
        calls = []
        with patch.object(
            technical_allocation, "remaining_by_line",
            side_effect=lambda r: calls.append("procurement") or {"R1": 1},
        ), patch.object(
            technical_allocation, "delivery_remaining_by_line",
            side_effect=lambda r: calls.append("delivery") or {"R1": 2},
        ):
            revision = revision_stub(name="TLR-1", technical_list="TL-1", items=[])
            cache = {}
            self.assertEqual(
                technical_allocation.remaining_for_adapter(
                    "revision_to_delivery_note", revision, cache
                ),
                {"R1": 2},
            )
            self.assertEqual(
                technical_allocation.remaining_for_adapter(
                    "revision_to_material_request", revision, cache
                ),
                {"R1": 1},
            )
            # Cached: a second lookup must not re-run the SQL-backed pool.
            technical_allocation.remaining_for_adapter(
                "revision_to_delivery_note", revision, cache
            )
        self.assertEqual(calls, ["delivery", "procurement"])

    def test_delivery_route_step_is_seeded_ungated(self):
        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        self.assertIn("_ensure_delivery_route_step()", source)
        body = source.split("def _ensure_delivery_route_step", 1)[1].split("\ndef ", 1)[0]
        # Spec rule 7: delivery is not gated on procurement.
        self.assertIn('"required_previous_action": ""', body)
        self.assertIn('"enabled": 1', body)


if __name__ == "__main__":
    unittest.main()
