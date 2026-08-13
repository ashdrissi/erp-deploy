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
        self.assertEqual(company_scope.company_field_for("Supplier"), "custom_company")
        self.assertEqual(company_scope.company_field_for("Quotation"), "company")
        self.assertEqual(company_scope.company_field_for("Project"), "company")
        # Unknown doctypes fall back to the native company field.
        self.assertEqual(company_scope.company_field_for("Item"), "company")

    def test_supplier_is_company_scoped(self):
        self.assertIn("Supplier", company_scope.SCOPED_DOCTYPES)
        self.assertEqual(company_scope.company_field_for("Supplier"), "custom_company")
        self.assertIn("Supplier", company_access.COMPANY_SCOPED_DOCTYPES)
        self.assertIn('"Supplier": "orderlift.company_access.has_company_permission"', HOOKS)
        self.assertIn('"Supplier": "orderlift.company_access.supplier_query"', HOOKS)

        form_js = (APP_ROOT / "orderlift" / "public" / "js" / "company_scope_form_20260724a.js").read_text()
        list_js = (APP_ROOT / "orderlift" / "public" / "js" / "company_scope_list_focus_20260601a.js").read_text()
        self.assertIn('Supplier: { company: "custom_company"', form_js)
        self.assertIn('const COUNTERPARTY_FOCUS = new Set(["Customer", "Supplier"]);', list_js)
        self.assertIn("enforceCounterpartyFocus(listview, field)", list_js)
        self.assertIn("installCounterpartyFilterTranslation(listview, field)", list_js)
        self.assertIn("translateCounterpartyFilters", list_js)
        self.assertIn("return listview.filter_area.add([[listview.doctype, field, \"=\", company]], false);", list_js)
        self.assertNotIn("translated.push([doctype, internalField(doctype)", list_js)
        self.assertIn("_internal_party_represents_active_company", COMPANY_ACCESS_SRC)
        self.assertIn("and not ", COMPANY_ACCESS_SRC)

    def test_internal_parties_are_visible_to_allowed_companies(self):
        for token in [
            "Allowed To Transact With",
            "is_internal_customer",
            "is_internal_supplier",
            "_company_clause_for_doctype",
            "_internal_party_allowed_to_user_company",
        ]:
            self.assertIn(token, COMPANY_ACCESS_SRC)

    def test_company_change_button_is_limited_to_drafts(self):
        form_js = (APP_ROOT / "orderlift" / "public" / "js" / "company_scope_form_20260724a.js").read_text()

        self.assertIn("canOverride && Number(frm.doc.docstatus || 0) === 0", form_js)
        self.assertIn('frappe.session.user === "Administrator"', form_js)
        self.assertIn('frappe.user.has_role("System Manager")', form_js)

    def test_transaction_forms_follow_the_active_company(self):
        form_js = (APP_ROOT / "orderlift" / "public" / "js" / "company_scope_form_20260724a.js").read_text()
        transaction_doctypes = {
            "Delivery Note",
            "Material Request",
            "Payment Entry",
            "Purchase Invoice",
            "Purchase Order",
            "Purchase Receipt",
            "Quotation",
            "Request for Quotation",
            "Sales Invoice",
            "Sales Order",
            "Stock Entry",
        }

        for doctype in transaction_doctypes:
            self.assertIn(doctype, form_js)
            self.assertIn(doctype, company_scope.TRANSACTION_COMPANY_DOCTYPES)

        self.assertIn("frm.doc[field] !== activeCompany()", form_js)
        self.assertIn('"orderlift.company_scope.apply_transaction_company_scope"', HOOKS)

    def test_transaction_scope_defaults_new_document_to_active_company(self):
        doc = _CompanyDoc("Purchase Order")
        self._with_transaction_scope_stubs(lambda: company_scope.apply_transaction_company_scope(doc))

        self.assertEqual(doc.company, "Orderlift Maroc Distribution")

    def test_transaction_scope_rejects_other_company_for_business_user(self):
        doc = _CompanyDoc("Purchase Order", company="Orderlift Maroc Installation")

        with self.assertRaisesRegex(ValueError, "current Desk company"):
            self._with_transaction_scope_stubs(lambda: company_scope.apply_transaction_company_scope(doc))

    def test_transaction_scope_allows_system_manager_override(self):
        doc = _CompanyDoc("Purchase Order", company="Orderlift Maroc Installation")
        self._with_transaction_scope_stubs(
            lambda: company_scope.apply_transaction_company_scope(doc), roles=["System Manager"]
        )

        self.assertEqual(doc.company, "Orderlift Maroc Installation")

    def test_system_generated_documents_can_bypass_company_scope(self):
        doc = _CompanyDoc("Purchase Order", company="Orderlift Maroc Installation")
        doc.flags = {"ignore_orderlift_company_scope": True}

        company_scope.apply_transaction_company_scope(doc)
        company_scope.apply_company_scope(doc)

        self.assertEqual(doc.company, "Orderlift Maroc Installation")

    def test_interactive_multi_company_creation_requires_active_selection(self):
        doc = _CompanyDoc("Purchase Order", company="Orderlift Maroc Installation")
        originals = {
            "meta": company_scope._meta_has_field,
            "resolve": company_scope.resolve_current_company,
            "interactive": company_scope.has_interactive_company_session,
            "throw": getattr(company_scope.frappe, "throw", None),
            "roles": getattr(company_scope.frappe, "get_roles", None),
        }
        company_scope._meta_has_field = lambda doctype, fieldname: fieldname == "company"
        company_scope.resolve_current_company = lambda user=None: ""
        company_scope.has_interactive_company_session = lambda user=None: True
        company_scope.frappe.throw = lambda message: (_ for _ in ()).throw(ValueError(message))
        company_scope.frappe.get_roles = lambda user=None: []
        try:
            with self.assertRaisesRegex(ValueError, "Select an active Company"):
                company_scope.apply_transaction_company_scope(doc)
        finally:
            company_scope._meta_has_field = originals["meta"]
            company_scope.resolve_current_company = originals["resolve"]
            company_scope.has_interactive_company_session = originals["interactive"]
            if originals["throw"] is None:
                delattr(company_scope.frappe, "throw")
            else:
                company_scope.frappe.throw = originals["throw"]
            if originals["roles"] is None:
                delattr(company_scope.frappe, "get_roles")
            else:
                company_scope.frappe.get_roles = originals["roles"]

    def _with_transaction_scope_stubs(self, action, roles=None):
        original_meta = company_scope._meta_has_field
        original_resolve = company_scope.resolve_current_company
        original_throw = getattr(company_scope.frappe, "throw", None)
        original_roles = getattr(company_scope.frappe, "get_roles", None)
        original_interactive = company_scope.has_interactive_company_session
        try:
            company_scope._meta_has_field = lambda doctype, fieldname: fieldname == "company"
            company_scope.resolve_current_company = lambda user=None: "Orderlift Maroc Distribution"
            company_scope.frappe.throw = lambda message: (_ for _ in ()).throw(ValueError(message))
            company_scope.frappe.get_roles = lambda user=None: roles or []
            company_scope.has_interactive_company_session = lambda user=None: False
            action()
        finally:
            company_scope._meta_has_field = original_meta
            company_scope.resolve_current_company = original_resolve
            company_scope.has_interactive_company_session = original_interactive
            if original_throw is None:
                delattr(company_scope.frappe, "throw")
            else:
                company_scope.frappe.throw = original_throw
            if original_roles is None:
                delattr(company_scope.frappe, "get_roles")
            else:
                company_scope.frappe.get_roles = original_roles

    def test_registry_uses_supported_company_fields(self):
        for doctype, config in company_scope.SCOPED_DOCTYPES.items():
            self.assertIn(
                config["company_field"],
                {"company", "custom_company"},
                msg=f"{doctype} uses unexpected company field {config['company_field']}",
            )

    def test_every_scoped_doctype_is_wired_in_hooks(self):
        for doctype in BUSINESS_DOCTYPES:
            permission_hook = (
                '"Purchase Agent Rules": "orderlift.orderlift_logistics.doctype.purchase_agent_rules.purchase_agent_rules.has_purchase_agent_rules_permission"'
                if doctype == "Purchase Agent Rules"
                else f'"{doctype}": "orderlift.company_access.has_company_permission"'
            )
            self.assertIn(
                permission_hook,
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

class _CompanyDoc:
    def __init__(self, doctype, company=""):
        self.doctype = doctype
        self.company = company
        self.flags = {}

    def get(self, fieldname):
        return getattr(self, fieldname, "")

    def set(self, fieldname, value):
        setattr(self, fieldname, value)

    def is_new(self):
        return True


if __name__ == "__main__":
    unittest.main()
