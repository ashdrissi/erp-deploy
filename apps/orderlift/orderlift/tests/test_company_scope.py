import sys
import types
import unittest
from pathlib import Path


# Minimal frappe stub so company_scope (and its company_access/menu_access imports) load.
frappe_stub = types.ModuleType("frappe")
frappe_stub.session = types.SimpleNamespace(user="demo@example.com")
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub._ = lambda message, *args, **kwargs: message
sys.modules["frappe"] = frappe_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(value or 0)
sys.modules["frappe.utils"] = utils_stub


from orderlift import company_access, company_scope


APP_ROOT = Path(__file__).resolve().parents[2]
HOOKS = (APP_ROOT / "orderlift" / "hooks.py").read_text()
COMPANY_ACCESS_SRC = (APP_ROOT / "orderlift" / "company_access.py").read_text()

# Doctypes the scope layer owns and must wire end-to-end (excludes child tables,
# which are scoped through their parent).
BUSINESS_DOCTYPES = sorted(company_scope.SCOPED_DOCTYPES)


class TestCompanyScopeRegistry(unittest.TestCase):
    def test_company_field_for_known_and_unknown(self):
        self.assertEqual(company_scope.company_field_for("Customer"), "custom_company")
        self.assertEqual(company_scope.company_field_for("Supplier"), "company")
        self.assertEqual(company_scope.company_field_for("Quotation"), "company")
        self.assertEqual(company_scope.company_field_for("Project"), "company")
        # Unknown doctypes fall back to the native company field.
        self.assertEqual(company_scope.company_field_for("Item"), "company")

    def test_supplier_is_a_shared_party_master_not_a_company_owned_record(self):
        self.assertNotIn("Supplier", company_scope.SCOPED_DOCTYPES)
        self.assertNotIn("Supplier", company_access.COMPANY_SCOPED_DOCTYPES)
        self.assertNotIn('"Supplier": "orderlift.company_access.has_company_permission"', HOOKS)
        self.assertNotIn('"Supplier": "orderlift.company_access.supplier_query"', HOOKS)

        form_js = (APP_ROOT / "orderlift" / "public" / "js" / "company_scope_form_20260607a.js").read_text()
        list_js = (APP_ROOT / "orderlift" / "public" / "js" / "company_scope_list_focus_20260601a.js").read_text()
        self.assertNotIn('Supplier: { company: "custom_company"', form_js)
        self.assertNotIn('Supplier: "custom_company"', list_js)

    def test_registry_uses_supported_company_fields(self):
        for doctype, config in company_scope.SCOPED_DOCTYPES.items():
            self.assertIn(
                config["company_field"],
                {"company", "custom_company"},
                msg=f"{doctype} uses unexpected company field {config['company_field']}",
            )

    def test_every_scoped_doctype_is_wired_in_hooks(self):
        for doctype in BUSINESS_DOCTYPES:
            self.assertIn(
                f'"{doctype}": "orderlift.company_access.has_company_permission"',
                HOOKS,
                msg=f"{doctype} missing from has_permission",
            )
            self.assertIn(
                f'"{doctype}": "orderlift.company_access.',
                HOOKS,
                msg=f"{doctype} missing from permission_query_conditions",
            )
            self.assertIn(
                doctype,
                HOOKS,
            )

    def test_company_access_has_query_for_each_scoped_doctype(self):
        # Each scoped doctype needs a permission-query function registered in hooks
        # that resolves to a real callable in company_access.
        for doctype in BUSINESS_DOCTYPES:
            slug = doctype.lower().replace(" ", "_")
            self.assertIn(
                f"def {slug}_query(",
                COMPANY_ACCESS_SRC,
                msg=f"company_access missing {slug}_query for {doctype}",
            )

    def test_validate_event_registered_for_each_scoped_doctype(self):
        for doctype in BUSINESS_DOCTYPES:
            # The doctype block must include the shared scope validator.
            block_marker = f'"{doctype}": {{'
            self.assertIn(block_marker, HOOKS, msg=f"{doctype} has no doc_events block")
        self.assertEqual(
            HOOKS.count('"orderlift.company_scope.apply_company_scope"'),
            len(BUSINESS_DOCTYPES),
            msg="apply_company_scope must be registered once per scoped doctype",
        )

    def test_managed_docperm_normalizer_is_wired_after_migrate(self):
        self.assertIn('"orderlift.company_access.normalize_managed_docperms"', HOOKS)


if __name__ == "__main__":
    unittest.main()
