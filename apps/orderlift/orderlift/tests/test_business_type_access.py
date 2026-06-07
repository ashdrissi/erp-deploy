import sys
import types
import unittest


class AttrDict(dict):
    def __getattr__(self, key):
        return self.get(key)

    def __setattr__(self, key, value):
        self[key] = value


# ---------------------------------------------------------------------------
# Minimal frappe stub so menu_access / company_access / company_scope import.
# ---------------------------------------------------------------------------
USER_PERMISSIONS: list[dict] = []
ROLES: dict[str, list[str]] = {}


def _escape(value):
    return "'" + str(value).replace("'", "''") + "'"


def _get_all(doctype, filters=None, fields=None, **kwargs):
    filters = filters or {}
    if doctype == "User Permission":
        rows = []
        for row in USER_PERMISSIONS:
            if all(row.get(key) == value for key, value in filters.items()):
                rows.append(AttrDict(row))
        return rows
    return []


frappe_stub = types.ModuleType("frappe")
frappe_stub.session = types.SimpleNamespace(user="demo@example.com")
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.db = types.SimpleNamespace(escape=_escape, exists=lambda *a, **k: True)
frappe_stub.get_all = _get_all
frappe_stub.get_roles = lambda user=None: ROLES.get(user, [])
sys.modules["frappe"] = frappe_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(value or 0)
sys.modules["frappe.utils"] = utils_stub


from orderlift import company_access, company_scope, menu_access


class TestBusinessTypeAccessHelpers(unittest.TestCase):
    def setUp(self):
        USER_PERMISSIONS.clear()
        ROLES.clear()
        frappe_stub.session.user = "demo@example.com"

    def _grant(self, user, business_type, apply_all=1, applicable_for=""):
        USER_PERMISSIONS.append(
            {
                "user": user,
                "allow": "CRM Business Type",
                "for_value": business_type,
                "apply_to_all_doctypes": apply_all,
                "applicable_for": applicable_for,
            }
        )

    def test_get_allowed_business_types_reads_apply_to_all_rows(self):
        self._grant("demo@example.com", "Distribution")
        self._grant("demo@example.com", "Installation", apply_all=0)  # ignored
        self._grant("demo@example.com", "Service", applicable_for="Opportunity")  # ignored
        self.assertEqual(menu_access.get_allowed_business_types("demo@example.com"), ["Distribution"])

    def test_empty_allow_list_is_unrestricted(self):
        self.assertTrue(menu_access.user_can_access_all_business_types("demo@example.com"))

    def test_configured_allow_list_is_restricted(self):
        self._grant("demo@example.com", "Distribution")
        self.assertFalse(menu_access.user_can_access_all_business_types("demo@example.com"))

    def test_admin_bypasses_business_type_restriction(self):
        self._grant("demo@example.com", "Distribution")
        ROLES["demo@example.com"] = ["System Manager"]
        self.assertTrue(menu_access.user_can_access_all_business_types("demo@example.com"))

    def test_user_can_access_business_type(self):
        self._grant("demo@example.com", "Distribution")
        self.assertTrue(menu_access.user_can_access_business_type("Distribution", "demo@example.com"))
        self.assertFalse(menu_access.user_can_access_business_type("Installation", "demo@example.com"))
        # Empty value is always allowed.
        self.assertTrue(menu_access.user_can_access_business_type("", "demo@example.com"))


class TestBusinessTypeClause(unittest.TestCase):
    def setUp(self):
        self._orig = {
            "all_bt": company_access.user_can_access_all_business_types,
            "allowed_bt": company_access.get_allowed_business_types,
            "has_field": company_access._has_company_field,
        }
        company_access.user_can_access_all_business_types = lambda user=None: False
        company_access.get_allowed_business_types = lambda user=None: ["Distribution"]
        company_access._has_company_field = lambda doctype, field="company": True

    def tearDown(self):
        company_access.user_can_access_all_business_types = self._orig["all_bt"]
        company_access.get_allowed_business_types = self._orig["allowed_bt"]
        company_access._has_company_field = self._orig["has_field"]

    def test_direct_field_clause(self):
        clause = company_access._business_type_clause("Opportunity", "demo@example.com")
        self.assertEqual(
            clause,
            "(`tabOpportunity`.custom_crm_business_type in ('Distribution') "
            "or `tabOpportunity`.custom_crm_business_type is null "
            "or `tabOpportunity`.custom_crm_business_type = '')",
        )

    def test_segment_doctype_clause(self):
        clause = company_access._business_type_clause("Customer", "demo@example.com")
        base = (
            "select 1 from `tabCRM Segment Assignment` _bt_seg "
            "where _bt_seg.parent = `tabCustomer`.name "
            "and _bt_seg.parenttype = 'Customer' "
            "and _bt_seg.parentfield = 'custom_crm_segments'"
        )
        self.assertEqual(
            clause,
            f"(not exists ({base}) or exists ({base} and _bt_seg.business_type in ('Distribution')))",
        )

    def test_no_business_type_doctype_returns_none(self):
        # Price List has neither a bt_field nor a segments_field.
        self.assertIsNone(company_access._business_type_clause("Price List", "demo@example.com"))

    def test_unrestricted_user_returns_none(self):
        company_access.user_can_access_all_business_types = lambda user=None: True
        self.assertIsNone(company_access._business_type_clause("Opportunity", "demo@example.com"))


class TestCompanyQueryCombination(unittest.TestCase):
    def setUp(self):
        self._orig = {
            "all_co": company_access.user_can_access_all_companies,
            "allowed_co": company_access.get_allowed_companies,
            "all_bt": company_access.user_can_access_all_business_types,
            "allowed_bt": company_access.get_allowed_business_types,
            "has_field": company_access._has_company_field,
        }
        company_access.user_can_access_all_companies = lambda user=None: False
        company_access.get_allowed_companies = lambda user=None: ["Orderlift"]
        company_access._has_company_field = lambda doctype, field="company": True
        company_access.get_allowed_business_types = lambda user=None: ["Distribution"]

    def tearDown(self):
        company_access.user_can_access_all_companies = self._orig["all_co"]
        company_access.get_allowed_companies = self._orig["allowed_co"]
        company_access.user_can_access_all_business_types = self._orig["all_bt"]
        company_access.get_allowed_business_types = self._orig["allowed_bt"]
        company_access._has_company_field = self._orig["has_field"]

    def test_query_unchanged_when_business_type_unrestricted(self):
        company_access.user_can_access_all_business_types = lambda user=None: True
        self.assertEqual(
            company_access._company_query("Opportunity", "demo@example.com"),
            "`tabOpportunity`.company in ('Orderlift')",
        )

    def test_query_appends_business_type_when_restricted(self):
        company_access.user_can_access_all_business_types = lambda user=None: False
        self.assertEqual(
            company_access._company_query("Opportunity", "demo@example.com"),
            "(`tabOpportunity`.company in ('Orderlift')) and "
            "((`tabOpportunity`.custom_crm_business_type in ('Distribution') "
            "or `tabOpportunity`.custom_crm_business_type is null "
            "or `tabOpportunity`.custom_crm_business_type = ''))",
        )


class FakeDoc(AttrDict):
    def __init__(self, doctype, **values):
        super().__init__(**values)
        self.doctype = doctype

    def is_new(self):
        return not self.get("name")


class TestHasPermissionBusinessType(unittest.TestCase):
    def setUp(self):
        self._orig = {
            "all_co": company_access.user_can_access_all_companies,
            "allowed_co": company_access.get_allowed_companies,
            "all_bt": company_access.user_can_access_all_business_types,
            "allowed_bt": company_access.get_allowed_business_types,
        }
        company_access.user_can_access_all_companies = lambda user=None: False
        company_access.get_allowed_companies = lambda user=None: ["Orderlift"]
        company_access.user_can_access_all_business_types = lambda user=None: False
        company_access.get_allowed_business_types = lambda user=None: ["Distribution"]

    def tearDown(self):
        company_access.user_can_access_all_companies = self._orig["all_co"]
        company_access.get_allowed_companies = self._orig["allowed_co"]
        company_access.user_can_access_all_business_types = self._orig["all_bt"]
        company_access.get_allowed_business_types = self._orig["allowed_bt"]

    def test_allowed_business_type_visible(self):
        doc = FakeDoc("Opportunity", name="OPP-1", company="Orderlift", custom_crm_business_type="Distribution")
        self.assertTrue(company_access.has_company_permission(doc, "read", user="demo@example.com"))

    def test_disallowed_business_type_denied(self):
        doc = FakeDoc("Opportunity", name="OPP-2", company="Orderlift", custom_crm_business_type="Installation")
        self.assertFalse(company_access.has_company_permission(doc, "read", user="demo@example.com"))

    def test_unclassified_record_visible(self):
        doc = FakeDoc("Opportunity", name="OPP-3", company="Orderlift", custom_crm_business_type="")
        self.assertTrue(company_access.has_company_permission(doc, "read", user="demo@example.com"))

    def test_segment_doc_visible_when_any_segment_allowed(self):
        doc = FakeDoc(
            "Customer",
            name="CUST-1",
            custom_company="Orderlift",
            custom_crm_segments=[{"business_type": "Installation"}, {"business_type": "Distribution"}],
        )
        self.assertTrue(company_access.has_company_permission(doc, "read", user="demo@example.com"))

    def test_segment_doc_denied_when_no_segment_allowed(self):
        doc = FakeDoc(
            "Customer",
            name="CUST-2",
            custom_company="Orderlift",
            custom_crm_segments=[{"business_type": "Installation"}],
        )
        self.assertFalse(company_access.has_company_permission(doc, "read", user="demo@example.com"))

    def test_segment_doc_visible_when_no_segments(self):
        doc = FakeDoc("Customer", name="CUST-3", custom_company="Orderlift", custom_crm_segments=[])
        self.assertTrue(company_access.has_company_permission(doc, "read", user="demo@example.com"))


if __name__ == "__main__":
    unittest.main()
