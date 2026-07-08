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
frappe_stub._ = lambda value, *args, **kwargs: value
frappe_stub.session = types.SimpleNamespace(user="demo@example.com")
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.db = types.SimpleNamespace(
    escape=_escape,
    exists=lambda *a, **k: True,
    get_value=lambda *a, **k: None,
    has_column=lambda *a, **k: False,
)
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
        menu_access.frappe = frappe_stub
        company_access.frappe = frappe_stub
        company_scope.frappe = frappe_stub

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

    def test_managed_docshare_is_blocked(self):
        original_throw = getattr(company_access.frappe, "throw", None)

        def throw(message):
            raise RuntimeError(message)

        company_access.frappe.throw = throw
        try:
            with self.assertRaisesRegex(RuntimeError, "Document sharing is disabled"):
                company_access.validate_managed_docshare(AttrDict({"share_doctype": "Opportunity"}))

            company_access.validate_managed_docshare(AttrDict({"share_doctype": "Event"}))
        finally:
            if original_throw is None:
                delattr(company_access.frappe, "throw")
            else:
                company_access.frappe.throw = original_throw

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
        ROLES.clear()
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
        ROLES.clear()
        self._orig = {
            "all_co": company_access.user_can_access_all_companies,
            "allowed_co": company_access.get_allowed_companies,
            "active_co": company_access._active_company_for_query,
            "all_bt": company_access.user_can_access_all_business_types,
            "allowed_bt": company_access.get_allowed_business_types,
            "has_field": company_access._has_company_field,
        }
        company_access.user_can_access_all_companies = lambda user=None: False
        company_access.get_allowed_companies = lambda user=None: ["Orderlift"]
        company_access._active_company_for_query = lambda user=None, allowed_companies=None: "Orderlift"
        company_access._has_company_field = lambda doctype, field="company": True
        company_access.get_allowed_business_types = lambda user=None: ["Distribution"]

    def tearDown(self):
        company_access.user_can_access_all_companies = self._orig["all_co"]
        company_access.get_allowed_companies = self._orig["allowed_co"]
        company_access._active_company_for_query = self._orig["active_co"]
        company_access.user_can_access_all_business_types = self._orig["all_bt"]
        company_access.get_allowed_business_types = self._orig["allowed_bt"]
        company_access._has_company_field = self._orig["has_field"]

    def test_query_unchanged_when_business_type_unrestricted(self):
        company_access.user_can_access_all_business_types = lambda user=None: True
        self.assertEqual(
            company_access._company_query("Opportunity", "demo@example.com"),
            "(`tabOpportunity`.company = 'Orderlift')",
        )

    def test_query_appends_business_type_when_restricted(self):
        company_access.user_can_access_all_business_types = lambda user=None: False
        self.assertEqual(
            company_access._company_query("Opportunity", "demo@example.com"),
            "(`tabOpportunity`.company = 'Orderlift') and "
            "((`tabOpportunity`.custom_crm_business_type in ('Distribution') "
            "or `tabOpportunity`.custom_crm_business_type is null "
            "or `tabOpportunity`.custom_crm_business_type = ''))",
        )

    def test_company_doctype_query_still_uses_allowed_companies(self):
        self.assertEqual(
            company_access._company_query("Company", "demo@example.com"),
            "`tabCompany`.name in ('Orderlift')",
        )

    def test_scoped_query_uses_selected_company_within_allowed_companies(self):
        company_access.get_allowed_companies = lambda user=None: ["Orderlift", "Orderlift Turkey"]
        company_access._active_company_for_query = lambda user=None, allowed_companies=None: "Orderlift Turkey"
        company_access.user_can_access_all_business_types = lambda user=None: True

        self.assertEqual(
            company_access._company_query("Opportunity", "demo@example.com"),
            "(`tabOpportunity`.company = 'Orderlift Turkey')",
        )

    def test_opportunity_query_matches_company_query(self):
        company_access.user_can_access_all_business_types = lambda user=None: True
        self.assertEqual(
            company_access.opportunity_query("demo@example.com"),
            company_access._company_query("Opportunity", "demo@example.com"),
        )


class TestOwnedOnlyAssignmentClause(unittest.TestCase):
    def setUp(self):
        self._orig = {
            "owned_flag": company_access._user_owned_documents_only,
            "has_field": company_access._has_company_field,
            "sales_person": company_access._sales_person_for_user,
        }
        company_access._user_owned_documents_only = lambda user=None: True
        company_access._has_company_field = lambda doctype, field="company": True

    def tearDown(self):
        company_access._user_owned_documents_only = self._orig["owned_flag"]
        company_access._has_company_field = self._orig["has_field"]
        company_access._sales_person_for_user = self._orig["sales_person"]

    def test_lead_owner_or_open_todo_assignment_grants_visibility(self):
        clause = company_access._owned_only_clause("Lead", "demo@example.com")

        self.assertIn("`tabLead`.lead_owner = 'demo@example.com'", clause)
        self.assertIn("exists (select 1 from `tabToDo` _todo_assignment", clause)
        self.assertIn("_todo_assignment.reference_type = 'Lead'", clause)
        self.assertIn("_todo_assignment.reference_name = `tabLead`.name", clause)
        self.assertIn("_todo_assignment.allocated_to = 'demo@example.com'", clause)
        self.assertIn("_todo_assignment.status = 'Open'", clause)

    def test_prospect_owner_or_open_todo_assignment_grants_visibility(self):
        clause = company_access._owned_only_clause("Prospect", "demo@example.com")

        self.assertIn("`tabProspect`.prospect_owner = 'demo@example.com'", clause)
        self.assertIn("_todo_assignment.reference_type = 'Prospect'", clause)
        self.assertIn("_todo_assignment.reference_name = `tabProspect`.name", clause)

    def test_customer_account_manager_or_open_todo_assignment_grants_visibility(self):
        company_access._sales_person_for_user = lambda user: "Sales Person A"

        clause = company_access._owned_only_clause("Customer", "demo@example.com")

        self.assertIn("`tabCustomer`.owner = 'demo@example.com'", clause)
        self.assertIn("`tabCustomer`.account_manager = 'Sales Person A'", clause)
        self.assertIn("`tabSales Team` _customer_sales_team", clause)
        self.assertIn("_customer_sales_team.sales_person = 'Sales Person A'", clause)
        self.assertIn("_todo_assignment.reference_type = 'Customer'", clause)
        self.assertIn("_todo_assignment.reference_name = `tabCustomer`.name", clause)

    def test_customer_open_todo_assignment_grants_visibility_without_sales_person(self):
        company_access._sales_person_for_user = lambda user: ""

        clause = company_access._owned_only_clause("Customer", "demo@example.com")

        self.assertIn("`tabCustomer`.owner = 'demo@example.com'", clause)
        self.assertNotIn("account_manager", clause)
        self.assertIn("_todo_assignment.reference_type = 'Customer'", clause)
        self.assertIn("_todo_assignment.allocated_to = 'demo@example.com'", clause)

    def test_unsaved_temp_named_doc_bypasses_db_owned_scope_lookup(self):
        doc = types.SimpleNamespace(
            doctype="Quotation",
            name="new-quotation-test",
            is_new=lambda: True,
            get=lambda key, default=None: {"name": "new-quotation-test", "company": ""}.get(key, default),
        )

        self.assertTrue(company_access._doc_company_allowed(doc, "demo@example.com", "read"))
        self.assertTrue(company_access._doc_owned_scope_allowed(doc, "demo@example.com"))

    def test_party_visibility_includes_owned_or_assigned_source_opportunity(self):
        clause = company_access._owned_only_clause("Prospect", "demo@example.com")

        self.assertIn("`tabOpportunity` _child_opp", clause)
        self.assertIn("_child_opp.opportunity_from = 'Prospect'", clause)
        self.assertIn("_child_opp.party_name = `tabProspect`.name", clause)
        self.assertIn("_child_opp.opportunity_owner = 'demo@example.com'", clause)
        self.assertIn("_opp_todo.reference_type = 'Opportunity'", clause)

    def test_quotation_visibility_includes_owned_or_assigned_source_opportunity(self):
        clause = company_access._owned_only_clause("Quotation", "demo@example.com")

        self.assertIn("`tabOpportunity` _quote_opp", clause)
        self.assertIn("_quote_opp.name = `tabQuotation`.opportunity", clause)
        self.assertIn("_quote_opp.opportunity_owner = 'demo@example.com'", clause)

    def test_sales_order_visibility_includes_quotation_source_opportunity(self):
        clause = company_access._owned_only_clause("Sales Order", "demo@example.com")

        self.assertIn("`tabSales Order Item` _so_item", clause)
        self.assertIn("`tabQuotation` _so_quote", clause)
        self.assertIn("`tabOpportunity` _so_opp", clause)
        self.assertIn("_so_item.parent = `tabSales Order`.name", clause)
        self.assertIn("_so_opp.name = _so_quote.opportunity", clause)

    def test_opportunity_visibility_uses_business_owner_not_native_owner(self):
        clause = company_access._owned_only_clause("Opportunity", "demo@example.com")

        self.assertIn("`tabOpportunity`.opportunity_owner = 'demo@example.com'", clause)
        self.assertNotIn("`tabOpportunity`.owner = 'demo@example.com'", clause)
        self.assertIn("_opp_todo.reference_type = 'Opportunity'", clause)


class TestOwnedOnlyStandardColumns(unittest.TestCase):
    def setUp(self):
        self._orig = {
            "owned_flag": company_access._user_owned_documents_only,
            "db": company_access.frappe.db,
            "get_meta": getattr(company_access.frappe, "get_meta", None),
        }
        company_access._user_owned_documents_only = lambda user=None: True
        company_access.frappe.get_meta = lambda doctype: types.SimpleNamespace(get_field=lambda field: None)
        company_access.frappe.db = types.SimpleNamespace(
            escape=_escape,
            has_column=lambda doctype, field: field == "owner",
        )

    def tearDown(self):
        company_access._user_owned_documents_only = self._orig["owned_flag"]
        company_access.frappe.db = self._orig["db"]
        if self._orig["get_meta"] is None:
            delattr(company_access.frappe, "get_meta")
        else:
            company_access.frappe.get_meta = self._orig["get_meta"]

    def test_standard_owner_column_is_detected_without_meta_field(self):
        self.assertTrue(company_access._has_company_field("Quotation", "owner"))

    def test_quotation_owned_only_uses_standard_owner_column(self):
        clause = company_access._owned_only_clause("Quotation", "demo@example.com")

        self.assertIn("`tabQuotation`.owner = 'demo@example.com'", clause)
        self.assertIn("_todo_assignment.reference_type = 'Quotation'", clause)
        self.assertIn("`tabOpportunity` _quote_opp", clause)

    def test_sales_order_owned_only_uses_standard_owner_column(self):
        clause = company_access._owned_only_clause("Sales Order", "demo@example.com")

        self.assertIn("`tabSales Order`.owner = 'demo@example.com'", clause)
        self.assertIn("_todo_assignment.reference_type = 'Sales Order'", clause)
        self.assertIn("`tabSales Order Item` _so_item", clause)

    def test_project_owned_only_uses_owner_and_assignment(self):
        clause = company_access._owned_only_clause("Project", "demo@example.com")

        self.assertIn("`tabProject`.owner = 'demo@example.com'", clause)
        self.assertIn("_todo_assignment.reference_type = 'Project'", clause)

    def test_sales_invoice_related_visibility_uses_sales_order_anchor(self):
        clause = company_access._owned_only_clause("Sales Invoice", "demo@example.com")

        self.assertIn("`tabSales Invoice`.owner = 'demo@example.com'", clause)
        self.assertIn("`tabSales Invoice Item` _si_item", clause)
        self.assertIn("_si_item.sales_order", clause)
        self.assertIn("_si_so.owner = 'demo@example.com'", clause)

    def test_delivery_note_related_visibility_uses_sales_order_anchor(self):
        clause = company_access._owned_only_clause("Delivery Note", "demo@example.com")

        self.assertIn("`tabDelivery Note`.owner = 'demo@example.com'", clause)
        self.assertIn("`tabDelivery Note Item` _dn_item", clause)
        self.assertIn("_dn_item.against_sales_order", clause)
        self.assertIn("_dn_so.owner = 'demo@example.com'", clause)


class TestOwnedOnlyOperationalChains(unittest.TestCase):
    def setUp(self):
        self._orig = {
            "owned_flag": company_access._user_owned_documents_only,
            "db": company_access.frappe.db,
            "get_meta": getattr(company_access.frappe, "get_meta", None),
            "sales_person": company_access._sales_person_for_user,
            "allowed_companies": company_access.get_allowed_companies,
            "active_company": company_access._active_company_for_query,
            "has_field": company_access._has_company_field,
        }
        company_access._user_owned_documents_only = lambda user=None: True
        company_access._sales_person_for_user = lambda user=None: "Sales Person A"
        company_access.frappe.get_meta = lambda doctype: types.SimpleNamespace(get_field=lambda field: None)
        company_access.frappe.db = types.SimpleNamespace(
            escape=_escape,
            has_column=lambda doctype, field: True,
        )

    def tearDown(self):
        company_access._user_owned_documents_only = self._orig["owned_flag"]
        company_access._sales_person_for_user = self._orig["sales_person"]
        company_access.get_allowed_companies = self._orig["allowed_companies"]
        company_access._active_company_for_query = self._orig["active_company"]
        company_access._has_company_field = self._orig["has_field"]
        company_access.frappe.db = self._orig["db"]
        if self._orig["get_meta"] is None:
            delattr(company_access.frappe, "get_meta")
        else:
            company_access.frappe.get_meta = self._orig["get_meta"]

    def test_material_request_links_to_sales_order_and_project(self):
        clause = company_access._owned_only_clause("Material Request", "demo@example.com")

        self.assertIn("`tabMaterial Request`.owner = 'demo@example.com'", clause)
        self.assertIn("`tabMaterial Request Item` _mr_item", clause)
        self.assertIn("_mr_item.sales_order", clause)
        self.assertIn("_mr_item.project", clause)

    def test_purchase_order_links_to_sales_order_material_request_and_project(self):
        clause = company_access._owned_only_clause("Purchase Order", "demo@example.com")

        self.assertIn("`tabPurchase Order`.owner = 'demo@example.com'", clause)
        self.assertIn("`tabPurchase Order Item` _po_item", clause)
        self.assertIn("_po_item.sales_order", clause)
        self.assertIn("_po_item.material_request", clause)
        self.assertIn("_po_item.project", clause)

    def test_purchase_receipt_links_to_purchase_order_material_request_sales_order_and_project(self):
        clause = company_access._owned_only_clause("Purchase Receipt", "demo@example.com")

        self.assertIn("`tabPurchase Receipt`.owner = 'demo@example.com'", clause)
        self.assertIn("`tabPurchase Receipt Item` _pr_item", clause)
        self.assertIn("_pr_item.purchase_order", clause)
        self.assertIn("_pr_item.material_request", clause)
        self.assertIn("_pr_item.sales_order", clause)
        self.assertIn("_pr_item.project", clause)

    def test_purchase_invoice_links_to_purchase_order_receipt_material_request_and_project(self):
        clause = company_access._owned_only_clause("Purchase Invoice", "demo@example.com")

        self.assertIn("`tabPurchase Invoice`.owner = 'demo@example.com'", clause)
        self.assertIn("`tabPurchase Invoice Item` _pi_item", clause)
        self.assertIn("_pi_item.purchase_order", clause)
        self.assertIn("_pi_item.purchase_receipt", clause)
        self.assertIn("_pi_item.material_request", clause)
        self.assertIn("_pi_item.project", clause)

    def test_payment_entry_links_to_sales_and_purchase_documents(self):
        clause = company_access._owned_only_clause("Payment Entry", "demo@example.com")

        self.assertIn("`tabPayment Entry`.owner = 'demo@example.com'", clause)
        self.assertIn("`tabPayment Entry Reference` _pe_ref", clause)
        self.assertIn("_pe_ref.reference_doctype = 'Sales Invoice'", clause)
        self.assertIn("_pe_ref.reference_doctype = 'Purchase Invoice'", clause)
        self.assertIn("_pe_ref.reference_doctype = 'Sales Order'", clause)
        self.assertIn("_pe_ref.reference_doctype = 'Purchase Order'", clause)

    def test_stock_entry_keeps_owner_assignment_and_source_links(self):
        clause = company_access._owned_only_clause("Stock Entry", "demo@example.com")

        self.assertIn("`tabStock Entry`.owner = 'demo@example.com'", clause)
        self.assertIn("`tabStock Entry Detail` _se_item", clause)
        self.assertIn("_se_item.material_request", clause)

    def test_forecast_load_plan_links_to_forecasted_documents(self):
        clause = company_access._owned_only_clause("Forecast Load Plan", "demo@example.com")

        self.assertIn("`tabForecast Load Plan`.owner = 'demo@example.com'", clause)
        self.assertIn("_flp_purchase_order.custom_forecast_plan", clause)
        self.assertIn("_flp_sales_order.custom_forecast_plan", clause)
        self.assertIn("_flp_delivery_note.custom_forecast_plan", clause)

    def test_partner_campaign_uses_person_in_charge_or_campaign_todo_only(self):
        clause = company_access._owned_only_clause("Partner Campaign", "demo@example.com")

        self.assertIn("`tabPartner Campaign`.campaign_owner = 'demo@example.com'", clause)
        self.assertIn("_todo_assignment.reference_type = 'Partner Campaign'", clause)
        self.assertIn("_todo_assignment.reference_name = `tabPartner Campaign`.name", clause)
        self.assertNotIn("`tabPartner Campaign Target`", clause)
        self.assertNotIn("_campaign_target", clause)

    def test_pricing_sheet_links_to_sales_person_opportunity_and_party(self):
        clause = company_access._owned_only_clause("Pricing Sheet", "demo@example.com")

        self.assertIn("`tabPricing Sheet`.owner = 'demo@example.com'", clause)
        self.assertIn("`tabPricing Sheet`.sales_person = 'Sales Person A'", clause)
        self.assertIn("_ps_opp", clause)
        self.assertIn("`tabCustomer` _ps_customer", clause)

    def test_portal_quote_request_links_to_portal_user_customer_and_quotation(self):
        clause = company_access._owned_only_clause("Portal Quote Request", "demo@example.com")

        self.assertIn("`tabPortal Quote Request`.owner = 'demo@example.com'", clause)
        self.assertIn("`tabPortal Quote Request`.portal_user = 'demo@example.com'", clause)
        self.assertIn("`tabCustomer` _pqr_customer", clause)
        self.assertIn("`tabQuotation` _pqr_quote", clause)

    def test_sav_ticket_links_to_assignment_and_origin_documents(self):
        clause = company_access._owned_only_clause("SAV Ticket", "demo@example.com")

        self.assertIn("`tabSAV Ticket`.owner = 'demo@example.com'", clause)
        self.assertIn("`tabSAV Ticket`.assigned_technician = 'demo@example.com'", clause)
        self.assertIn("`tabCustomer` _sav_customer", clause)
        self.assertIn("`tabSales Order` _sav_sales_order", clause)
        self.assertIn("`tabDelivery Note` _sav_delivery_note", clause)
        self.assertIn("`tabSales Invoice` _sav_sales_invoice", clause)
        self.assertIn("`tabPurchase Receipt` _sav_purchase_receipt", clause)
        self.assertIn("`tabProject` _sav_installation_project", clause)

    def test_sav_technician_query_is_limited_to_assigned_or_todo_tickets(self):
        ROLES["demo@example.com"] = ["SAV Technician"]
        company_access.get_allowed_companies = lambda user=None: ["Orderlift"]
        company_access._active_company_for_query = lambda user=None, allowed_companies=None: "Orderlift"
        company_access._has_company_field = lambda doctype, fieldname: True
        company_access._user_owned_documents_only = lambda user=None: False

        clause = company_access._sav_ticket_query("demo@example.com")

        self.assertIn("`tabSAV Ticket`.assigned_technician = 'demo@example.com'", clause)
        self.assertIn("_todo_assignment.reference_type = 'SAV Ticket'", clause)
        self.assertIn("_todo_assignment.allocated_to = 'demo@example.com'", clause)

    def test_service_user_sav_query_is_not_limited_to_assigned_tickets(self):
        ROLES["demo@example.com"] = ["Service User", "SAV Technician"]
        company_access.get_allowed_companies = lambda user=None: ["Orderlift"]
        company_access._active_company_for_query = lambda user=None, allowed_companies=None: "Orderlift"
        company_access._has_company_field = lambda doctype, fieldname: True
        company_access._user_owned_documents_only = lambda user=None: False

        clause = company_access._sav_ticket_query("demo@example.com")

        self.assertNotIn("`tabSAV Ticket`.assigned_technician = 'demo@example.com'", clause)


class TestSpecialScopeQueries(unittest.TestCase):
    def setUp(self):
        self._orig = {
            "visible_price_lists": company_access.get_visible_price_lists,
            "active_company": company_access._active_company_for_query,
            "company_query": company_access._company_query,
            "can_manage_commissions": company_access._can_manage_sales_commissions,
            "sales_person": company_access._sales_person_for_user,
        }
        company_access._active_company_for_query = lambda user=None, allowed_companies=None: "Orderlift"

    def tearDown(self):
        company_access.get_visible_price_lists = self._orig["visible_price_lists"]
        company_access._active_company_for_query = self._orig["active_company"]
        company_access._company_query = self._orig["company_query"]
        company_access._can_manage_sales_commissions = self._orig["can_manage_commissions"]
        company_access._sales_person_for_user = self._orig["sales_person"]

    def test_price_list_query_denies_when_no_visible_lists(self):
        company_access.get_visible_price_lists = lambda *args, **kwargs: []

        self.assertEqual(company_access.price_list_query("demo@example.com"), "`tabPrice List`.name is null")

    def test_price_list_query_allows_only_visible_lists(self):
        company_access.get_visible_price_lists = lambda *args, **kwargs: ["Sell A", "Buy A"]

        clause = company_access.price_list_query("demo@example.com")

        self.assertEqual(clause, "`tabPrice List`.name in ('Buy A', 'Sell A')")

    def test_price_list_query_uses_selected_company_focus(self):
        calls = []

        def visible(*args, **kwargs):
            calls.append(kwargs)
            return ["Sell TR"]

        company_access._active_company_for_query = lambda user=None, allowed_companies=None: "Orderlift Turkey"
        company_access.get_visible_price_lists = visible

        self.assertEqual(company_access.price_list_query("demo@example.com"), "`tabPrice List`.name in ('Sell TR')")
        self.assertEqual(calls, [{"company": "Orderlift Turkey", "user": "demo@example.com"}])

    def test_print_format_query_hides_shared_formats_for_turkey(self):
        company_access._active_company_for_query = lambda user=None, allowed_companies=None: "Orderlift Turkey"

        self.assertEqual(
            company_access.print_format_query("demo@example.com"),
            "`tabPrint Format`.custom_company = 'Orderlift Turkey'",
        )

    def test_print_format_query_uses_exact_active_company_for_non_turkey(self):
        company_access._active_company_for_query = lambda user=None, allowed_companies=None: "Orderlift"

        self.assertEqual(
            company_access.print_format_query("demo@example.com"),
            "`tabPrint Format`.custom_company = 'Orderlift'",
        )

    def test_item_price_query_denies_when_no_visible_lists(self):
        company_access.get_visible_price_lists = lambda *args, **kwargs: []

        self.assertEqual(company_access.item_price_query("demo@example.com"), "`tabItem Price`.name is null")

    def test_item_price_query_allows_only_visible_price_lists(self):
        company_access.get_visible_price_lists = lambda *args, **kwargs: ["Sell A", "Benchmark A"]

        clause = company_access.item_price_query("demo@example.com")

        self.assertEqual(clause, "`tabItem Price`.price_list in ('Benchmark A', 'Sell A')")

    def test_item_price_doc_permission_uses_visible_price_lists(self):
        company_access.get_visible_price_lists = lambda *args, **kwargs: ["Sell A"]

        self.assertTrue(company_access.has_item_price_permission(AttrDict(price_list="Sell A"), user="demo@example.com"))
        self.assertFalse(company_access.has_item_price_permission(AttrDict(price_list="Buy A"), user="demo@example.com"))

    def test_sales_commission_query_non_manager_is_limited_to_own_salesperson(self):
        company_access._company_query = lambda doctype, user=None: "`tabSales Commission`.company in ('Orderlift')"
        company_access._can_manage_sales_commissions = lambda user: False
        company_access._sales_person_for_user = lambda user: "Haitem"

        clause = company_access.sales_commission_query("demo@example.com")

        self.assertEqual(
            clause,
            "(`tabSales Commission`.company in ('Orderlift')) and (`tabSales Commission`.salesperson = 'Haitem')",
        )

    def test_sales_commission_query_without_salesperson_denies_rows(self):
        company_access._company_query = lambda doctype, user=None: "`tabSales Commission`.company in ('Orderlift')"
        company_access._can_manage_sales_commissions = lambda user: False
        company_access._sales_person_for_user = lambda user: ""

        clause = company_access.sales_commission_query("demo@example.com")

        self.assertEqual(
            clause,
            "(`tabSales Commission`.company in ('Orderlift')) and (`tabSales Commission`.name is null)",
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
            "active_co": company_access._active_company_for_query,
            "all_bt": company_access.user_can_access_all_business_types,
            "allowed_bt": company_access.get_allowed_business_types,
            "visible_price_lists": company_access.get_visible_price_lists,
            "db": company_access.frappe.db,
        }
        company_access.user_can_access_all_companies = lambda user=None: False
        company_access.get_allowed_companies = lambda user=None: ["Orderlift"]
        company_access._active_company_for_query = lambda user=None, allowed_companies=None: "Orderlift"
        company_access.user_can_access_all_business_types = lambda user=None: False
        company_access.get_allowed_business_types = lambda user=None: ["Distribution"]

    def tearDown(self):
        company_access.user_can_access_all_companies = self._orig["all_co"]
        company_access.get_allowed_companies = self._orig["allowed_co"]
        company_access._active_company_for_query = self._orig["active_co"]
        company_access.user_can_access_all_business_types = self._orig["all_bt"]
        company_access.get_allowed_business_types = self._orig["allowed_bt"]
        company_access.get_visible_price_lists = self._orig["visible_price_lists"]
        company_access.frappe.db = self._orig["db"]

    def test_sav_ticket_visible_when_any_linked_origin_company_allowed(self):
        original_db = company_access.frappe.db

        def get_value(doctype, name, fieldname, *args, **kwargs):
            values = {
                ("Customer", "CUST-1", "custom_company"): "Other Company",
                ("Sales Order", "SO-1", "company"): "Orderlift",
            }
            return values.get((doctype, name, fieldname))

        company_access.frappe.db = types.SimpleNamespace(
            escape=_escape,
            exists=lambda *a, **k: True,
            get_value=get_value,
            has_column=lambda *a, **k: False,
        )
        try:
            doc = FakeDoc("SAV Ticket", name="SAV-1", customer="CUST-1", sales_order="SO-1")

            self.assertTrue(company_access.has_company_permission(doc, "read", user="demo@example.com"))
        finally:
            company_access.frappe.db = original_db

    def test_sav_ticket_denied_when_no_linked_origin_company_allowed(self):
        original_db = company_access.frappe.db

        def get_value(doctype, name, fieldname, *args, **kwargs):
            values = {
                ("Customer", "CUST-1", "custom_company"): "Other Company",
                ("Sales Order", "SO-1", "company"): "Other Company",
            }
            return values.get((doctype, name, fieldname))

        company_access.frappe.db = types.SimpleNamespace(
            escape=_escape,
            exists=lambda *a, **k: True,
            get_value=get_value,
            has_column=lambda *a, **k: False,
        )
        try:
            doc = FakeDoc("SAV Ticket", name="SAV-1", customer="CUST-1", sales_order="SO-1")

            self.assertFalse(company_access.has_company_permission(doc, "read", user="demo@example.com"))
        finally:
            company_access.frappe.db = original_db

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

    def test_price_list_permission_uses_persisted_company_for_existing_doc(self):
        calls = []

        def get_value(doctype, name, fields, as_dict=False, **kwargs):
            self.assertEqual((doctype, name), ("Price List", "PRIX FOURNISSEUR MAD"))
            self.assertTrue(as_dict)
            return {
                "custom_company": "Orderlift",
                company_access.PRICE_LIST_TYPE_FIELD: company_access.BUYING_PRICE_LIST,
                "buying": 1,
                "selling": 0,
            }

        company_access.frappe.db = types.SimpleNamespace(
            escape=_escape,
            exists=lambda doctype, name=None: doctype == "Price List" and name == "PRIX FOURNISSEUR MAD",
            get_value=get_value,
            has_column=lambda doctype, field: field == company_access.PRICE_LIST_TYPE_FIELD,
        )

        def visible(kind=None, company=None, user=None):
            calls.append((kind, company, user))
            return ["PRIX FOURNISSEUR MAD"] if kind == "buying" and company == "Orderlift" else []

        company_access.get_visible_price_lists = visible

        doc = FakeDoc(
            "Price List",
            name="PRIX FOURNISSEUR MAD",
            custom_company="Other Company",
            custom_price_list_type="Buying",
            buying=1,
            selling=0,
        )

        self.assertTrue(company_access.has_company_permission(doc, "write", user="demo@example.com"))
        self.assertEqual(calls, [("buying", "Orderlift", "demo@example.com")])

    def test_price_list_permission_ignores_unsaved_type_change_for_existing_doc(self):
        calls = []

        def get_value(doctype, name, fields, as_dict=False, **kwargs):
            self.assertEqual((doctype, name), ("Price List", "PRIX FOURNISSEUR MAD"))
            self.assertTrue(as_dict)
            return {
                "custom_company": "Orderlift",
                company_access.PRICE_LIST_TYPE_FIELD: company_access.BUYING_PRICE_LIST,
                "buying": 1,
                "selling": 0,
            }

        company_access.frappe.db = types.SimpleNamespace(
            escape=_escape,
            exists=lambda doctype, name=None: doctype == "Price List" and name == "PRIX FOURNISSEUR MAD",
            get_value=get_value,
            has_column=lambda doctype, field: field == company_access.PRICE_LIST_TYPE_FIELD,
        )

        def visible(kind=None, company=None, user=None):
            calls.append((kind, company, user))
            return ["PRIX FOURNISSEUR MAD"] if kind == "buying" else []

        company_access.get_visible_price_lists = visible

        doc = FakeDoc(
            "Price List",
            name="PRIX FOURNISSEUR MAD",
            custom_company="Orderlift",
            custom_price_list_type="Selling",
            buying=0,
            selling=1,
        )

        self.assertTrue(company_access.has_company_permission(doc, "write", user="demo@example.com"))
        self.assertEqual(calls, [("buying", "Orderlift", "demo@example.com")])


if __name__ == "__main__":
    unittest.main()
