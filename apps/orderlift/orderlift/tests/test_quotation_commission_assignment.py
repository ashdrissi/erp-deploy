import importlib.util
import sys
import types
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = APP_ROOT / "orderlift_sales" / "quotation_hooks.py"


class Row(dict):
    def __init__(self, **values):
        super().__init__(values)
        self.meta = types.SimpleNamespace(get_field=lambda fieldname: True)

    def __getattr__(self, key):
        return self.get(key)

    def __setattr__(self, key, value):
        if key == "meta":
            object.__setattr__(self, key, value)
            return
        self[key] = value


class Quotation(dict):
    def __init__(self, *, owner="sales@example.com", is_new=True, before_sales_person="", **values):
        super().__init__(values)
        self.owner = owner
        self.name = values.get("name") or ("new-quotation" if is_new else "QTN-001")
        self._is_new = is_new
        self._before_sales_person = before_sales_person
        self.meta = types.SimpleNamespace(get_field=lambda fieldname: True)

    def __getattr__(self, key):
        return self.get(key)

    def __setattr__(self, key, value):
        if key.startswith("_") or key in {"owner", "name", "meta"}:
            object.__setattr__(self, key, value)
            return
        self[key] = value

    def is_new(self):
        return self._is_new

    def get_doc_before_save(self):
        if self._is_new:
            return None
        return types.SimpleNamespace(commission_sales_person=self._before_sales_person)


class DbStub:
    def __init__(self):
        self.user_sales_people = {
            "sales@example.com": "Haitem",
            "manager@example.com": "Manager Person",
        }
        self.sheet_sales_people = {"PS-001": "Yassine"}
        self.commission_rates = {"Haitem": 20, "Yassine": 15, "Manager Person": 10}

    def exists(self, doctype, name):
        return doctype == "DocType" and name == "Sales Person"

    def has_column(self, doctype, fieldname):
        return doctype == "Sales Person" and fieldname in {"user", "enabled"}

    def get_value(self, doctype, name_or_filters=None, fieldname=None, *args, **kwargs):
        if doctype == "Customer" and fieldname == "tax_id":
            return "ICE-001122334455667"
        if doctype == "Sales Person" and isinstance(name_or_filters, dict):
            return self.user_sales_people.get(name_or_filters.get("user"), "")
        if doctype == "Sales Person" and fieldname == "enabled":
            return 1
        if doctype == "Pricing Sheet" and fieldname == "sales_person":
            return self.sheet_sales_people.get(name_or_filters, "")
        if doctype == "Agent Pricing Rules" and isinstance(name_or_filters, dict):
            salesperson = name_or_filters.get("sales_person")
            return f"APR-{salesperson}" if salesperson in self.commission_rates else ""
        if doctype == "Agent Pricing Rules" and fieldname == "commission_rate":
            salesperson = str(name_or_filters or "").removeprefix("APR-")
            return self.commission_rates.get(salesperson, 0)
        return ""


def load_quotation_hooks():
    frappe = types.ModuleType("frappe")
    frappe._ = lambda message: message
    frappe.PermissionError = PermissionError
    frappe.session = types.SimpleNamespace(user="sales@example.com")
    frappe.db = DbStub()
    frappe.roles = {"sales@example.com": ["Sales User"], "manager@example.com": ["Sales User", "Sales Manager"]}
    frappe.get_roles = lambda user=None: frappe.roles.get(user or frappe.session.user, [])
    frappe.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(RuntimeError(message))
    frappe.whitelist = lambda *args, **kwargs: (lambda fn: fn)

    utils = types.ModuleType("frappe.utils")
    utils.flt = lambda value=0, *args, **kwargs: float(value or 0)

    dependencies = {
        "frappe": frappe,
        "frappe.utils": utils,
        "orderlift.orderlift_crm.api.pipeline": types.SimpleNamespace(get_party_defaults=lambda *args, **kwargs: {}),
        "orderlift.orderlift_sales.utils.price_list_usage_guard": types.SimpleNamespace(
            reprice_quotation_items_from_selected_price_lists=lambda *args, **kwargs: None
        ),
        "orderlift.orderlift_sales.utils.price_list_scope": types.SimpleNamespace(
            can_override_quotation_pricing=lambda: False,
            validate_visible_price_list=lambda *args, **kwargs: None,
        ),
        "orderlift.orderlift_sales.utils.tax_inclusive": types.SimpleNamespace(
            apply_quotation_sales_tax_template=lambda *args, **kwargs: None,
            sync_quotation_item_tax_inclusive_fields=lambda *args, **kwargs: None,
        ),
        "orderlift.sales.utils.pricing_projection": types.SimpleNamespace(
            calculate_agent_commission=lambda **kwargs: {"commission_amount": 0}
        ),
    }
    previous = {name: sys.modules.get(name) for name in dependencies}
    sys.modules.update(dependencies)
    try:
        spec = importlib.util.spec_from_file_location("quotation_hooks_assignment_test", MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, frappe
    finally:
        for name, value in previous.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


class TestQuotationCommissionAssignment(unittest.TestCase):
    def setUp(self):
        self.hooks, self.frappe = load_quotation_hooks()

    def quotation(self, **values):
        values.setdefault("source_pricing_sheet", "")
        values.setdefault("commission_sales_person", "")
        values.setdefault("items", [Row(source_sales_person="", source_commission_rate=0, price_list_rate=100)])
        return Quotation(**values)

    def test_sales_user_is_forced_to_their_own_sales_person(self):
        quotation = self.quotation(commission_sales_person="Yassine")

        resolved = self.hooks.resolve_quotation_commission_context(quotation)

        self.assertEqual(resolved, "Haitem")
        self.assertEqual(quotation.commission_sales_person, "Haitem")
        self.assertEqual(quotation.get("items")[0].source_sales_person, "Haitem")
        self.assertEqual(quotation.get("items")[0].source_commission_rate, 20)

    def test_existing_assignment_cannot_be_redirected_by_sales_user(self):
        quotation = self.quotation(
            is_new=False,
            before_sales_person="Haitem",
            commission_sales_person="Yassine",
            items=[Row(source_sales_person="Haitem", source_commission_rate=20, price_list_rate=100)],
        )

        resolved = self.hooks.resolve_quotation_commission_context(quotation)

        self.assertEqual(resolved, "Haitem")
        self.assertEqual(quotation.commission_sales_person, "Haitem")

    def test_unmapped_sales_user_can_submit_without_commission(self):
        self.frappe.db.user_sales_people.pop("sales@example.com")
        quotation = self.quotation(commission_sales_person="Yassine", _action="submit")

        resolved = self.hooks.resolve_quotation_commission_context(quotation)

        self.assertEqual(resolved, "")
        self.assertEqual(quotation.commission_sales_person, "")
        self.assertEqual(quotation.get("items")[0].source_sales_person, "")
        self.assertEqual(quotation.get("items")[0].source_commission_rate, 0)

    def test_manager_may_choose_any_enabled_sales_person(self):
        self.frappe.session.user = "manager@example.com"
        quotation = self.quotation(owner="manager@example.com", commission_sales_person="Yassine")

        resolved = self.hooks.resolve_quotation_commission_context(quotation)

        self.assertEqual(resolved, "Yassine")
        self.assertEqual(quotation.get("items")[0].source_commission_rate, 15)

    def test_manager_may_submit_without_commission(self):
        self.frappe.session.user = "manager@example.com"
        quotation = self.quotation(owner="manager@example.com", _action="submit")

        resolved = self.hooks.resolve_quotation_commission_context(quotation)

        self.assertEqual(resolved, "")
        self.assertEqual(quotation.commission_sales_person, "")
        self.assertEqual(quotation.get("items")[0].source_sales_person, "")

    def test_pricing_sheet_assignment_is_authoritative_and_non_blocking(self):
        self.frappe.session.user = "manager@example.com"
        quotation = self.quotation(
            owner="manager@example.com",
            source_pricing_sheet="PS-001",
            commission_sales_person="Haitem",
            _action="submit",
        )

        resolved = self.hooks.resolve_quotation_commission_context(quotation)

        self.assertEqual(resolved, "Yassine")
        self.assertEqual(quotation.commission_sales_person, "Yassine")
        self.assertEqual(quotation.get("items")[0].source_sales_person, "Yassine")

    def test_assignment_context_exposes_default_and_edit_permission(self):
        self.assertEqual(
            self.hooks.get_quotation_commission_assignment_context(),
            {"sales_person": "Haitem", "can_edit_sales_person": False},
        )

        self.frappe.session.user = "manager@example.com"
        self.assertEqual(
            self.hooks.get_quotation_commission_assignment_context(),
            {"sales_person": "Manager Person", "can_edit_sales_person": True},
        )

    def test_customer_tax_id_is_snapshotted_on_quotation(self):
        quotation = self.quotation(
            quotation_to="Customer",
            party_name="CUST-001",
            customer_name="Example Customer",
            custom_customer_tax_id="",
        )

        self.hooks.apply_quotation_party_defaults(quotation)

        self.assertEqual(quotation.custom_customer_tax_id, "ICE-001122334455667")


if __name__ == "__main__":
    unittest.main()
