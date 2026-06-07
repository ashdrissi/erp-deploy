import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
frappe_stub.session = types.SimpleNamespace(user="demo@example.com")
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
sys.modules["frappe"] = frappe_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(value or 0)
sys.modules["frappe.utils"] = utils_stub


from orderlift import company_access, menu_access, menu_registry


class TestMenuAccessHelpers(unittest.TestCase):
    def test_menu_registry_has_stable_unique_keys(self):
        keys = [item["key"] for item in menu_registry.iter_menu_items()]

        self.assertEqual(len(keys), len(set(keys)))
        self.assertIn("hr.dashboard", keys)
        self.assertIn("training.center", keys)
        self.assertIn("training.leaderboard", keys)
        self.assertIn("training.performance_leaderboard", keys)
        self.assertIn("training.cycle_dashboard", keys)
        self.assertIn("training.programs", keys)
        self.assertIn("sales.pricing_sheets", keys)
        self.assertIn("logistics.pipeline", keys)
        self.assertNotIn("my_work.notifications", keys)

    def test_menu_registry_uses_seven_default_business_roles(self):
        self.assertEqual(
            menu_registry.BUSINESS_ROLES,
            [
                "Orderlift Admin",
                "Sales User",
                "Pricing Manager",
                "Logistics User",
                "Finance User",
                "Installation User",
                "Service User",
            ],
        )
        all_default_roles = {
            role
            for item in menu_registry.iter_menu_items()
            for role in item.get("roles", [])
            if role != menu_registry.ALL_USERS_ROLE
        }

        self.assertEqual(all_default_roles - set(menu_registry.BUSINESS_ROLES) - {"Administrator", "System Manager", "Developer"}, set())

    def test_administration_menu_includes_orderlift_admin_and_superadmins(self):
        status_control = menu_registry.menu_item_by_key("administration.status_control")
        document_templates = menu_registry.menu_item_by_key("administration.document_templates")
        access_center = menu_registry.menu_item_by_key("administration.access_command_center")
        menu_editor = menu_registry.menu_item_by_key("administration.menu_editor")

        self.assertIn("Orderlift Admin", status_control["roles"])
        self.assertIn("Administrator", status_control["roles"])
        self.assertIn("System Manager", status_control["roles"])
        self.assertIn("Developer", status_control["roles"])
        self.assertEqual(document_templates["link_to"], "document-template-manager")
        self.assertIn("Orderlift Admin", document_templates["roles"])
        self.assertIn("System Manager", document_templates["roles"])
        self.assertEqual(access_center["roles"], ["Orderlift Admin", "System Manager"])
        self.assertEqual(menu_editor["roles"], ["Orderlift Admin", "System Manager"])

    def test_document_template_targets_use_shipment_plan_label(self):
        from orderlift.document_templates import get_supported_document_template_targets

        targets = {row["doctype"]: row["label"] for row in get_supported_document_template_targets()}

        self.assertEqual(targets["Forecast Load Plan"], "Shipment Plan")
        self.assertIn("Opportunity", targets)
        self.assertIn("Project", targets)
        self.assertIn("Quotation", targets)
        self.assertIn("Sales Order", targets)

    def test_projects_menu_does_not_include_logistics_links(self):
        projects = next(section for section in menu_registry.get_menu_sections() if section["key"] == "projects")
        keys = {link["key"] for link in projects["links"]}

        self.assertNotIn("projects.logistics_dashboard", keys)
        self.assertNotIn("projects.container_planning", keys)

    def test_contract_menu_lives_under_projects(self):
        crm = next(section for section in menu_registry.get_menu_sections() if section["key"] == "crm_customers")
        projects = next(section for section in menu_registry.get_menu_sections() if section["key"] == "projects")

        self.assertNotIn("crm.contract", {link["key"] for link in crm["links"]})
        self.assertIn("projects.contract", {link["key"] for link in projects["links"]})

    def test_sales_menu_includes_order_and_project_pipelines(self):
        sales = next(section for section in menu_registry.get_menu_sections() if section["key"] == "sales")
        keys = {link["key"] for link in sales["links"]}

        self.assertIn("sales.sales_order_pipeline", keys)
        self.assertIn("sales.project_pipeline", keys)

    def test_administration_menu_rule_sanitizer_keeps_allowed_admin_roles(self):
        item = menu_registry.menu_item_by_key("administration.status_control")

        self.assertEqual(
            menu_access._sanitize_allowed_roles_for_item(item, ["Orderlift Admin", "Sales User", "System Manager"]),
            ["Orderlift Admin", "System Manager", "Administrator", "Developer"],
        )

    def test_page_menu_map_links_custom_pages_to_menu_keys(self):
        page_map = menu_registry.page_menu_map()

        self.assertIn("pricing-sheet-manager", page_map)
        self.assertIn("sales.pricing_sheets", page_map["pricing-sheet-manager"])
        self.assertIn("logistics-pipeline", page_map)

    def test_roles_allow_supports_all_role_and_specific_roles(self):
        self.assertTrue(menu_access._roles_allow([menu_registry.ALL_USERS_ROLE], {"Sales User"}))
        self.assertTrue(menu_access._roles_allow(["Sales User"], {"Sales User", "Employee"}))
        self.assertFalse(menu_access._roles_allow(["Logistics User"], {"Sales User"}))

    def test_legacy_default_roles_are_pruned_from_existing_menu_rules(self):
        roles = ["Sales Manager", "Sales User", "Custom Escalation Role", "System Manager"]

        self.assertEqual(
            menu_access._prune_legacy_default_roles(roles),
            ["Sales User", "Custom Escalation Role", "System Manager"],
        )

    def test_central_sidebar_removes_native_pricing_sheet_link(self):
        rows = menu_registry.build_sidebar_rows()
        labels = [row.get("label") for row in rows]

        self.assertIn("Pricing Sheets", labels)
        self.assertIn("HR & Performance", labels)
        self.assertIn("Pick List", labels)
        self.assertNotIn("Commisions", labels)
        self.assertNotIn("Delivey note", labels)

    def test_menu_rule_overrides_only_change_label_and_order(self):
        class Rule(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        rows = [
            {"type": "Section Break", "label": "Sales"},
            {"type": "Link", "label": "Quotation", "link_type": "DocType", "link_to": "Quotation"},
            {"type": "Link", "label": "Pricing Sheets", "link_type": "Page", "link_to": "pricing-sheet-manager"},
        ]
        original_map = menu_access._menu_rule_map
        menu_access._menu_rule_map = lambda: {
            "sales.quotation": Rule(label="Quotes", menu_order=20),
            "sales.pricing_sheets": Rule(label="Sheets", menu_order=10),
        }
        try:
            labels = [row.get("label") for row in menu_access.apply_menu_rule_overrides(rows)]
        finally:
            menu_access._menu_rule_map = original_map

        self.assertEqual(labels, ["Sales", "Sheets", "Quotes"])

    def test_menu_rule_overrides_can_reorder_sections(self):
        class Rule(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        rows = [
            {"type": "Section Break", "label": "Sales"},
            {"type": "Link", "label": "Quotation", "link_type": "DocType", "link_to": "Quotation"},
            {"type": "Section Break", "label": "Finance"},
            {"type": "Link", "label": "Sales Invoices", "link_type": "DocType", "link_to": "Sales Invoice"},
        ]
        original_map = menu_access._menu_rule_map
        menu_access._menu_rule_map = lambda: {
            "sales.quotation": Rule(label="Quotation", menu_order=20),
            "finance.sales_invoices": Rule(label="Sales Invoices", menu_order=10),
        }
        try:
            labels = [row.get("label") for row in menu_access.apply_menu_rule_overrides(rows)]
        finally:
            menu_access._menu_rule_map = original_map

        self.assertEqual(labels, ["Finance", "Sales Invoices", "Sales", "Quotation"])

    def test_menu_rule_overrides_uses_internal_key_for_duplicate_targets(self):
        class Rule(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        rows = menu_registry.build_sidebar_rows()
        original_map = menu_access._menu_rule_map
        menu_access._menu_rule_map = lambda: {
            "crm.projects_list": Rule(label="CRM Projects", menu_order=4),
            "sig.projects": Rule(label="SIG Projects", menu_order=57),
        }
        try:
            updated = menu_access.apply_menu_rule_overrides(rows)
        finally:
            menu_access._menu_rule_map = original_map

        project_rows = [
            row
            for row in updated
            if row.get("type") == "Link" and row.get("link_type") == "DocType" and row.get("link_to") == "Project"
        ]

        self.assertEqual([row["label"] for row in project_rows], ["CRM Projects", "SIG Projects"])
        self.assertTrue(all("_menu_key" not in row for row in updated))

    def test_business_user_bootinfo_keeps_only_main_dashboard_sidebar(self):
        class BootInfo(dict):
            def __getattr__(self, name):
                return self[name]

            def __setattr__(self, name, value):
                self[name] = value

        bootinfo = BootInfo({
            "workspace_sidebar_item": {
                "Main Dashboard": {"items": [{"type": "Link", "label": "Dashboard"}]},
                "HR": {"items": [{"type": "Link", "label": "HR Dashboard"}]},
                "Gestion de Projets": {"items": [{"type": "Link", "label": "Project Pipeline"}]},
            }
        })
        originals = {
            "get_boot_menu_access": menu_access.get_boot_menu_access,
            "get_company_access_payload": menu_access.get_company_access_payload,
            "filter_sidebar_rows": menu_access.filter_sidebar_rows,
            "_get_roles": menu_access._get_roles,
        }
        menu_access.get_boot_menu_access = lambda user=None: {"visible_menu_keys": []}
        menu_access.get_company_access_payload = lambda user=None: {"companies": []}
        menu_access.filter_sidebar_rows = lambda rows, user=None: rows
        menu_access._get_roles = lambda user=None: {"Orderlift Admin"}
        try:
            menu_access.apply_menu_access_to_bootinfo(bootinfo, user="orderlift.admin@example.com")
        finally:
            for name, value in originals.items():
                setattr(menu_access, name, value)

        self.assertEqual(list(bootinfo["workspace_sidebar_item"].keys()), ["main dashboard"])

    def test_system_manager_with_business_role_still_uses_main_sidebar_only(self):
        class BootInfo(dict):
            def __getattr__(self, name):
                return self[name]

            def __setattr__(self, name, value):
                self[name] = value

        bootinfo = BootInfo({
            "workspace_sidebar_item": {
                "Main Dashboard": {"items": [{"type": "Link", "label": "Dashboard"}]},
                "SIG": {"items": [{"type": "Link", "label": "Mobile QC"}]},
                "Stock": {"items": [{"type": "Link", "label": "Item"}]},
            }
        })
        originals = {
            "get_boot_menu_access": menu_access.get_boot_menu_access,
            "get_company_access_payload": menu_access.get_company_access_payload,
            "filter_sidebar_rows": menu_access.filter_sidebar_rows,
            "_get_roles": menu_access._get_roles,
        }
        menu_access.get_boot_menu_access = lambda user=None: {"visible_menu_keys": []}
        menu_access.get_company_access_payload = lambda user=None: {"companies": []}
        menu_access.filter_sidebar_rows = lambda rows, user=None: rows
        menu_access._get_roles = lambda user=None: {"Orderlift Admin", "System Manager"}
        try:
            menu_access.apply_menu_access_to_bootinfo(bootinfo, user="manager@example.com")
        finally:
            for name, value in originals.items():
                setattr(menu_access, name, value)

        self.assertEqual(list(bootinfo["workspace_sidebar_item"].keys()), ["main dashboard"])

    def test_administrator_uses_main_sidebar_only_without_losing_access(self):
        class BootInfo(dict):
            def __getattr__(self, name):
                return self[name]

            def __setattr__(self, name, value):
                self[name] = value

        bootinfo = BootInfo({
            "workspace_sidebar_item": {
                "Main Dashboard": {"items": [{"type": "Link", "label": "Dashboard"}]},
                "Stock": {"items": [{"type": "Link", "label": "Item"}]},
            }
        })
        originals = {
            "get_boot_menu_access": menu_access.get_boot_menu_access,
            "get_company_access_payload": menu_access.get_company_access_payload,
            "filter_sidebar_rows": menu_access.filter_sidebar_rows,
            "_get_roles": menu_access._get_roles,
        }
        menu_access.get_boot_menu_access = lambda user=None: {"visible_menu_keys": []}
        menu_access.get_company_access_payload = lambda user=None: {"companies": []}
        menu_access.filter_sidebar_rows = lambda rows, user=None: rows
        menu_access._get_roles = lambda user=None: {"Administrator", "System Manager"}
        try:
            menu_access.apply_menu_access_to_bootinfo(bootinfo, user="Administrator")
        finally:
            for name, value in originals.items():
                setattr(menu_access, name, value)

        self.assertEqual(list(bootinfo["workspace_sidebar_item"].keys()), ["main dashboard"])

    def test_company_query_denies_when_no_company_is_assigned(self):
        original_all_companies = company_access.user_can_access_all_companies
        original_allowed = company_access.get_allowed_companies
        original_db = getattr(company_access.frappe, "db", None)
        company_access.user_can_access_all_companies = lambda user=None: False
        company_access.get_allowed_companies = lambda user=None: []
        company_access.frappe.db = types.SimpleNamespace(escape=lambda value: repr(value))
        try:
            self.assertEqual(company_access.sales_order_query("demo@example.com"), "`tabSales Order`.name is null")
        finally:
            company_access.user_can_access_all_companies = original_all_companies
            company_access.get_allowed_companies = original_allowed
            if original_db is None:
                delattr(company_access.frappe, "db")
            else:
                company_access.frappe.db = original_db

    def test_company_query_filters_allowed_companies(self):
        original_all_companies = company_access.user_can_access_all_companies
        original_allowed = company_access.get_allowed_companies
        original_db = getattr(company_access.frappe, "db", None)
        original_get_meta = getattr(company_access.frappe, "get_meta", None)
        company_access.user_can_access_all_companies = lambda user=None: False
        company_access.get_allowed_companies = lambda user=None: ["Orderlift", "Pivot"]
        company_access.frappe.db = types.SimpleNamespace(escape=lambda value: repr(value))
        company_access.frappe.get_meta = lambda doctype: types.SimpleNamespace(get_field=lambda field: field == "company")
        try:
            self.assertEqual(
                company_access.sales_order_query("demo@example.com"),
                "`tabSales Order`.company in ('Orderlift', 'Pivot')",
            )
        finally:
            company_access.user_can_access_all_companies = original_all_companies
            company_access.get_allowed_companies = original_allowed
            if original_db is None:
                delattr(company_access.frappe, "db")
            else:
                company_access.frappe.db = original_db
            if original_get_meta is None:
                delattr(company_access.frappe, "get_meta")
            else:
                company_access.frappe.get_meta = original_get_meta

    def test_sales_commission_query_filters_sales_user_to_own_salesperson(self):
        original_all_companies = company_access.user_can_access_all_companies
        original_allowed = company_access.get_allowed_companies
        original_db = getattr(company_access.frappe, "db", None)
        original_get_meta = getattr(company_access.frappe, "get_meta", None)
        original_can_manage = company_access._can_manage_sales_commissions
        original_salesperson = company_access._sales_person_for_user
        company_access.user_can_access_all_companies = lambda user=None: False
        company_access.get_allowed_companies = lambda user=None: ["Orderlift"]
        company_access.frappe.db = types.SimpleNamespace(escape=lambda value: repr(value))
        company_access.frappe.get_meta = lambda doctype: types.SimpleNamespace(get_field=lambda field: field == "company")
        company_access._can_manage_sales_commissions = lambda user: False
        company_access._sales_person_for_user = lambda user: "Bilal"
        try:
            self.assertEqual(
                company_access.sales_commission_query("bilal@example.com"),
                "(`tabSales Commission`.company in ('Orderlift')) and (`tabSales Commission`.salesperson = 'Bilal')",
            )
        finally:
            company_access.user_can_access_all_companies = original_all_companies
            company_access.get_allowed_companies = original_allowed
            company_access._can_manage_sales_commissions = original_can_manage
            company_access._sales_person_for_user = original_salesperson
            if original_db is None:
                delattr(company_access.frappe, "db")
            else:
                company_access.frappe.db = original_db
            if original_get_meta is None:
                delattr(company_access.frappe, "get_meta")
            else:
                company_access.frappe.get_meta = original_get_meta

    def test_sales_commission_permission_is_read_only_for_own_salesperson(self):
        original_all_companies = company_access.user_can_access_all_companies
        original_allowed = company_access.get_allowed_companies
        original_can_manage = company_access._can_manage_sales_commissions
        original_salesperson = company_access._sales_person_for_user
        company_access.user_can_access_all_companies = lambda user=None: False
        company_access.get_allowed_companies = lambda user=None: ["Orderlift"]
        company_access._can_manage_sales_commissions = lambda user: False
        company_access._sales_person_for_user = lambda user: "Bilal"

        def get_field(field):
            values = {"salesperson": "Bilal", "company": "Orderlift"}
            return values.get(field, "")

        doc = types.SimpleNamespace(doctype="Sales Commission", name="SC-1", get=get_field, is_new=lambda: False)
        try:
            self.assertTrue(company_access.has_company_permission(doc, user="bilal@example.com", permission_type="read"))
            self.assertTrue(company_access.has_company_permission(doc, user="bilal@example.com", permission_type="print"))
            self.assertFalse(company_access.has_company_permission(doc, user="bilal@example.com", permission_type="write"))
        finally:
            company_access.user_can_access_all_companies = original_all_companies
            company_access.get_allowed_companies = original_allowed
            company_access._can_manage_sales_commissions = original_can_manage
            company_access._sales_person_for_user = original_salesperson

    def test_company_permission_allows_new_create_before_company_is_set(self):
        original_all_companies = company_access.user_can_access_all_companies
        original_allowed = company_access.get_allowed_companies
        company_access.user_can_access_all_companies = lambda user=None: False
        company_access.get_allowed_companies = lambda user=None: ["Orderlift"]
        doc = types.SimpleNamespace(doctype="Sales Order", name=None, get=lambda field: "", is_new=lambda: True)
        try:
            self.assertTrue(company_access.has_company_permission(doc, user="demo@example.com", permission_type="create"))
        finally:
            company_access.user_can_access_all_companies = original_all_companies
            company_access.get_allowed_companies = original_allowed

    def test_company_permission_still_denies_disallowed_company(self):
        original_all_companies = company_access.user_can_access_all_companies
        original_allowed = company_access.get_allowed_companies
        company_access.user_can_access_all_companies = lambda user=None: False
        company_access.get_allowed_companies = lambda user=None: ["Orderlift"]
        doc = types.SimpleNamespace(
            doctype="Sales Order",
            name="new-sales-order-1",
            get=lambda field: "Other Company" if field == "company" else "",
            is_new=lambda: True,
        )
        try:
            self.assertFalse(company_access.has_company_permission(doc, user="demo@example.com", permission_type="create"))
        finally:
            company_access.user_can_access_all_companies = original_all_companies
            company_access.get_allowed_companies = original_allowed


if __name__ == "__main__":
    unittest.main()
