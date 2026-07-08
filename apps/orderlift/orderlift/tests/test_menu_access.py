import json
import sys
import types
import unittest
from pathlib import Path


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda value, *args, **kwargs: value
frappe_stub.session = types.SimpleNamespace(user="demo@example.com")
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
sys.modules["frappe"] = frappe_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(value or 0)
sys.modules["frappe.utils"] = utils_stub


from orderlift import company_access, menu_access, menu_registry
from orderlift.scripts import setup_startup_roles
from orderlift.startup_roles import OPPORTUNITY_ASSIGNER_ROLE, OPPORTUNITY_ALL_ACCESS_ROLE, STARTUP_ROLES


APP_ROOT = Path(__file__).resolve().parents[2]


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
        self.assertIn("items.item_category", keys)
        self.assertIn("items.item_group", keys)
        self.assertIn("items.static_pricing_builder", keys)
        self.assertIn("administration.currency", keys)
        self.assertIn("administration.currency_exchange", keys)
        self.assertIn("administration.currency_exchange_settings", keys)
        self.assertIn("stock.stock_entry", keys)
        self.assertIn("stock.warehouse_tree", keys)
        self.assertIn("stock.warehouse_report", keys)
        self.assertNotIn("items.pricing_builder", keys)
        self.assertNotIn("my_work.notifications", keys)

    def test_my_work_todo_uses_filtered_page(self):
        todo = menu_registry.menu_item_by_key("my_work.todo")

        self.assertEqual(todo["label"], "My ToDos")
        self.assertEqual(todo["link_type"], "Page")
        self.assertEqual(todo["link_to"], "my-todos")

    def test_company_filter_normalization_replaces_stale_report_filter(self):
        filters = [["Quotation", "company", "=", "Orderlift"]]

        normalized = company_access._normalized_company_filters(
            filters,
            "Quotation",
            "company",
            "Orderlift Maroc Distribution",
        )

        self.assertEqual(normalized, [["Quotation", "company", "=", "Orderlift Maroc Distribution"]])

    def test_company_filter_normalization_handles_dict_filter(self):
        filters = {"company": "Orderlift"}

        normalized = company_access._normalized_company_filters(
            filters,
            "Quotation",
            "company",
            "Orderlift Maroc Distribution",
        )

        self.assertEqual(normalized["company"], "Orderlift Maroc Distribution")

    def test_company_filter_normalization_is_registered_before_request(self):
        from orderlift import hooks

        self.assertIn(
            "orderlift.company_access.normalize_company_filters_for_request",
            hooks.before_request,
        )

    def test_menu_registry_includes_default_and_startup_business_roles(self):
        for role in [
            "Orderlift Admin",
            "Sales User",
            "Pricing Manager",
            "Logistics User",
            "Finance User",
            "Installation User",
            "Service User",
            "SAV Technician",
            "Commercial Agent",
            "Commercial Agent - Partner",
            "Marketing User",
            "Quotation Creator",
            "Opportunity All Access",
            "Stock Quantity Viewer",
        ]:
            self.assertIn(role, menu_registry.BUSINESS_ROLES)
        all_default_roles = {
            role
            for item in menu_registry.iter_menu_items()
            for role in item.get("roles", [])
            if role != menu_registry.ALL_USERS_ROLE
        }

        self.assertEqual(all_default_roles - set(menu_registry.BUSINESS_ROLES) - {"Administrator", "System Manager", "Developer"}, set())

    def test_campaign_pages_require_campaign_doctype_permission(self):
        manager = menu_registry.menu_item_by_key("crm.campaign_manager")
        builder = menu_registry.menu_item_by_key("crm.campaign_builder")

        self.assertEqual(manager.get("required_doctypes"), ["Partner Campaign"])
        self.assertEqual(builder.get("required_doctypes"), ["Partner Campaign"])
        self.assertIn("Marketing User", manager.get("roles"))
        self.assertNotIn("Sales User", manager.get("roles"))

    def test_page_link_target_requires_backing_doctype_permission(self):
        row = {"_menu_key": "crm.campaign_manager", "link_type": "Page", "link_to": "campaign-manager"}
        originals = {
            "user_can_access_page": menu_access.user_can_access_page,
            "has_permission": getattr(menu_access.frappe, "has_permission", None),
        }
        menu_access.user_can_access_page = lambda page_name, user=None, rules=None: True
        menu_access.frappe.has_permission = lambda doctype, ptype=None, user=None: False
        try:
            self.assertFalse(menu_access._link_target_allowed(row, user="sales@example.com", roles={"Sales User"}))
            menu_access.frappe.has_permission = lambda doctype, ptype=None, user=None: doctype == "Partner Campaign"
            self.assertTrue(menu_access._link_target_allowed(row, user="campaign@example.com", roles={"Marketing User"}))
        finally:
            menu_access.user_can_access_page = originals["user_can_access_page"]
            if originals["has_permission"] is None:
                delattr(menu_access.frappe, "has_permission")
            else:
                menu_access.frappe.has_permission = originals["has_permission"]

    def test_direct_campaign_page_requires_backing_doctype_permission_even_with_stale_menu_rule(self):
        class Rule(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        rules = {
            "crm.campaign_manager": Rule(
                enabled=1,
                allowed_roles_json=json.dumps(["Sales User"]),
                denied_roles_json=json.dumps([]),
            )
        }
        originals = {
            "get_roles": getattr(menu_access.frappe, "get_roles", None),
            "has_permission": getattr(menu_access.frappe, "has_permission", None),
            "page_roles": menu_access._page_roles,
        }
        menu_access.frappe.get_roles = lambda user=None: ["Sales User"]
        menu_access.frappe.has_permission = lambda doctype, ptype=None, user=None: False
        menu_access._page_roles = lambda page_name: set()
        try:
            self.assertFalse(menu_access.user_can_access_page("campaign-manager", user="sales@example.com", rules=rules))
            menu_access.frappe.has_permission = lambda doctype, ptype=None, user=None: doctype == "Partner Campaign"
            self.assertTrue(menu_access.user_can_access_page("campaign-manager", user="sales@example.com", rules=rules))
        finally:
            menu_access._page_roles = originals["page_roles"]
            if originals["get_roles"] is None:
                delattr(menu_access.frappe, "get_roles")
            else:
                menu_access.frappe.get_roles = originals["get_roles"]
            if originals["has_permission"] is None:
                delattr(menu_access.frappe, "has_permission")
            else:
                menu_access.frappe.has_permission = originals["has_permission"]

    def test_boot_menu_access_filters_page_by_backing_doctype_permission(self):
        class Rule(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        rules = {
            "crm.campaign_manager": Rule(
                enabled=1,
                allowed_roles_json=json.dumps(["Sales User"]),
                denied_roles_json=json.dumps([]),
            )
        }
        originals = {
            "get_roles": getattr(menu_access.frappe, "get_roles", None),
            "has_permission": getattr(menu_access.frappe, "has_permission", None),
            "menu_rule_map": menu_access._menu_rule_map,
            "page_roles": menu_access._page_roles,
        }
        menu_access.frappe.get_roles = lambda user=None: ["Sales User"]
        menu_access.frappe.has_permission = lambda doctype, ptype=None, user=None: False
        menu_access._menu_rule_map = lambda: rules
        menu_access._page_roles = lambda page_name: set()
        try:
            self.assertNotIn("crm.campaign_manager", menu_access.get_boot_menu_access("sales@example.com")["visible_menu_keys"])
            menu_access.frappe.has_permission = lambda doctype, ptype=None, user=None: doctype == "Partner Campaign"
            self.assertIn("crm.campaign_manager", menu_access.get_boot_menu_access("sales@example.com")["visible_menu_keys"])
        finally:
            menu_access._menu_rule_map = originals["menu_rule_map"]
            menu_access._page_roles = originals["page_roles"]
            if originals["get_roles"] is None:
                delattr(menu_access.frappe, "get_roles")
            else:
                menu_access.frappe.get_roles = originals["get_roles"]
            if originals["has_permission"] is None:
                delattr(menu_access.frappe, "has_permission")
            else:
                menu_access.frappe.has_permission = originals["has_permission"]

    def test_startup_roles_have_permission_or_menu_mapping(self):
        mapped_roles = set(setup_startup_roles.MENU_ROLE_MAP) | set(setup_startup_roles.DOCTYPE_PERMISSIONS)
        runtime_only_roles = {OPPORTUNITY_ASSIGNER_ROLE}

        self.assertFalse(set(STARTUP_ROLES) - mapped_roles - runtime_only_roles)

    def test_commercial_agent_can_create_quotation(self):
        permissions = setup_startup_roles.COMMERCIAL_AGENT_PERMISSIONS

        self.assertEqual(permissions["Quotation"]["create"], 1)
        self.assertEqual(permissions["Quotation"]["write"], 1)
        self.assertEqual(permissions["Price List"]["read"], 1)
        self.assertEqual(permissions["Price List"]["select"], 1)

    def test_stock_manager_has_explicit_stock_docperms(self):
        permissions = setup_startup_roles.DOCTYPE_PERMISSIONS["Stock Manager"]

        self.assertEqual(permissions["Stock Settings"]["read"], 1)
        self.assertEqual(permissions["Stock Settings"]["write"], 1)
        self.assertEqual(permissions["Bin"]["read"], 1)
        self.assertEqual(permissions["Bin"]["select"], 1)
        self.assertEqual(permissions["Stock Ledger Entry"]["report"], 1)
        self.assertEqual(permissions["Stock Entry"]["create"], 1)
        self.assertEqual(permissions["Stock Entry"]["submit"], 1)
        self.assertEqual(permissions["Pick List"]["create"], 1)
        self.assertEqual(permissions["Delivery Note"]["submit"], 1)
        self.assertEqual(permissions["Purchase Receipt"]["submit"], 1)
        self.assertEqual(permissions["Stock Entry Type"]["read"], 1)

    def test_logistics_user_has_full_operational_stock_permissions(self):
        permissions = setup_startup_roles.DOCTYPE_PERMISSIONS["Logistics User"]

        for doctype in ["Stock Entry", "Delivery Note", "Purchase Receipt", "Pick List", "Material Request", "Purchase Order"]:
            self.assertEqual(permissions[doctype]["read"], 1)
            self.assertEqual(permissions[doctype]["create"], 1)
            self.assertEqual(permissions[doctype]["submit"], 1)
            self.assertEqual(permissions[doctype]["cancel"], 1)
        self.assertEqual(permissions["Stock Settings"]["write"], 1)
        self.assertEqual(permissions["Bin"]["read"], 1)
        self.assertEqual(permissions["Stock Ledger Entry"]["report"], 1)
        self.assertEqual(permissions["Product Bundle"]["read"], 1)
        self.assertEqual(permissions["Item Price"]["read"], 1)
        self.assertEqual(permissions["Stock Entry Type"]["read"], 1)

    def test_base_business_roles_have_menu_backing_permissions(self):
        role_permissions = setup_startup_roles.DOCTYPE_PERMISSIONS

        self.assertEqual(role_permissions["Pricing Manager"]["Quotation"]["read"], 1)
        self.assertEqual(role_permissions["Pricing Manager"]["Agent Pricing Rules"]["create"], 1)
        self.assertEqual(role_permissions["Finance User"]["Payment Entry"]["create"], 1)
        self.assertEqual(role_permissions["Installation User"]["Project"]["create"], 1)
        self.assertEqual(role_permissions["Installation User"]["QC Checklist Template"]["create"], 1)
        self.assertEqual(role_permissions["Service User"]["SAV Ticket"]["create"], 1)
        self.assertEqual(role_permissions["SAV Technician"]["SAV Ticket"]["create"], 1)
        self.assertEqual(role_permissions["Sales User"]["Portal Quote Request"]["read"], 1)
        self.assertEqual(role_permissions["Sales User"]["Item Price"]["read"], 1)

    def test_stock_settings_link_fields_ignore_user_permissions(self):
        self.assertIn("default_warehouse", setup_startup_roles.STOCK_SETTINGS_USER_PERMISSION_EXEMPT_FIELDS)
        source = (APP_ROOT / "orderlift" / "scripts" / "setup_startup_roles.py").read_text()

        self.assertIn("_ensure_stock_settings_user_permission_exempt_fields(results)", source)
        self.assertIn('"ignore_user_permissions"', source)

    def test_warehouse_stock_menu_includes_core_stock_documents(self):
        warehouse = next(section for section in menu_registry.get_menu_sections() if section["key"] == "warehouse_stock")
        keys = {link["key"] for link in warehouse["links"]}

        self.assertIn("stock.delivery_note", keys)
        self.assertIn("stock.purchase_receipt", keys)
        self.assertIn("stock.pick_list", keys)
        self.assertIn("stock.bins", keys)
        self.assertIn("stock.stock_settings", keys)

    def test_startup_role_seed_does_not_overwrite_existing_docperms_by_default(self):
        source = (APP_ROOT / "orderlift" / "scripts" / "setup_startup_roles.py").read_text()

        self.assertIn("overwrite_existing_docperms: int = 0", source)
        self.assertIn("remove_stale_docperms: int = 0", source)
        self.assertIn('action = "exists"', source)

    def test_opportunity_all_access_is_manageable_capability_role(self):
        self.assertIn(OPPORTUNITY_ALL_ACCESS_ROLE, STARTUP_ROLES)
        self.assertEqual(
            setup_startup_roles.DOCTYPE_PERMISSIONS[OPPORTUNITY_ALL_ACCESS_ROLE]["Opportunity"]["read"],
            1,
        )

    def test_campaign_permissions_are_marketing_user_only(self):
        self.assertNotIn("Partner Campaign", setup_startup_roles.SALES_MANAGER_PERMISSIONS)
        self.assertNotIn("Partner Campaign Target", setup_startup_roles.SALES_MANAGER_PERMISSIONS)
        self.assertIn("Partner Campaign", setup_startup_roles.DOCTYPE_PERMISSIONS["Marketing User"])
        self.assertNotIn("Partner Campaign", setup_startup_roles.DOCTYPE_PERMISSIONS["Sales Distribution Manager"])
        self.assertNotIn("Partner Campaign", setup_startup_roles.DOCTYPE_PERMISSIONS["Sales Installation Manager"])
        self.assertEqual(
            setup_startup_roles.STALE_DOCTYPE_PERMISSIONS["Sales Distribution Manager"],
            ["Partner Campaign", "Partner Campaign Target"],
        )

    def test_startup_manager_roles_have_core_menu_access(self):
        self.assertIn("crm.opportunity_pipeline", setup_startup_roles.MENU_ROLE_MAP["Sales Distribution Manager"])
        self.assertIn("projects.project_pipeline", setup_startup_roles.MENU_ROLE_MAP["Sales Installation Manager"])
        self.assertIn("logistics.pipeline", setup_startup_roles.MENU_ROLE_MAP["Logistics Manager"])
        self.assertIn("finance.payments", setup_startup_roles.MENU_ROLE_MAP["Finance Admin"])

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

    def test_administration_menu_rule_sanitizer_keeps_only_selected_admin_roles(self):
        item = menu_registry.menu_item_by_key("administration.status_control")

        self.assertEqual(
            menu_access._sanitize_allowed_roles_for_item(item, ["Orderlift Admin", "Sales User", "System Manager"]),
            ["Orderlift Admin", "System Manager"],
        )

    def test_save_menu_access_can_remove_orderlift_admin_from_administration_item(self):
        class Rule(dict):
            def __init__(self, name, enabled, roles):
                super().__init__(name=name, enabled=enabled, allowed_roles_json=json.dumps(roles))
                self.name = name

            def get(self, key, default=None):
                return super().get(key, default)

        rules = {
            "administration.business_delivery": Rule(
                "administration.business_delivery",
                0,
                ["Orderlift Admin", "System Manager"],
            ),
            "administration.status_control": Rule(
                "administration.status_control",
                1,
                ["Orderlift Admin", "System Manager"],
            ),
        }
        updates = {}
        originals = {
            "sync_menu_access_rules": menu_access.sync_menu_access_rules,
            "_menu_rule_map": menu_access._menu_rule_map,
            "db": getattr(menu_access.frappe, "db", None),
            "clear_cache": getattr(menu_access.frappe, "clear_cache", None),
        }

        def set_value(_doctype, name, values):
            updates[name] = values

        menu_access.sync_menu_access_rules = lambda: None
        menu_access._menu_rule_map = lambda: rules
        menu_access.frappe.db = types.SimpleNamespace(
            exists=lambda doctype, name=None: doctype == "Role" and name == "Orderlift Admin",
            set_value=set_value,
        )
        menu_access.frappe.clear_cache = lambda *args, **kwargs: None
        try:
            result = menu_access.save_menu_access_for_role(
                "Orderlift Admin",
                ["administration.business_delivery"],
            )
        finally:
            menu_access.sync_menu_access_rules = originals["sync_menu_access_rules"]
            menu_access._menu_rule_map = originals["_menu_rule_map"]
            if originals["db"] is None:
                delattr(menu_access.frappe, "db")
            else:
                menu_access.frappe.db = originals["db"]
            if originals["clear_cache"] is None:
                delattr(menu_access.frappe, "clear_cache")
            else:
                menu_access.frappe.clear_cache = originals["clear_cache"]

        self.assertEqual(result["changed"], 2)
        self.assertEqual(updates["administration.business_delivery"]["enabled"], 1)
        self.assertEqual(
            json.loads(updates["administration.status_control"]["allowed_roles_json"]),
            ["System Manager"],
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

    def test_denied_role_overrides_all_role_menu_access(self):
        class Rule(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        rules = {
            "my_work.todo": Rule(
                enabled=1,
                allowed_roles_json=json.dumps(["All"]),
                denied_roles_json=json.dumps(["Orderlift Admin"]),
            )
        }

        self.assertFalse(
            menu_access.user_can_access_menu_key(
                "my_work.todo",
                user="orderlift.admin@example.com",
                roles={"Orderlift Admin"},
                rules=rules,
            )
        )
        self.assertTrue(
            menu_access.user_can_access_menu_key(
                "my_work.todo",
                user="sales@example.com",
                roles={"Sales User"},
                rules=rules,
            )
        )

    def test_save_menu_access_adds_denial_when_role_unchecks_all_item(self):
        class Rule(dict):
            def __init__(self, name, enabled, roles, denied_roles=None):
                super().__init__(
                    name=name,
                    enabled=enabled,
                    allowed_roles_json=json.dumps(roles),
                    denied_roles_json=json.dumps(denied_roles or []),
                )
                self.name = name

            def get(self, key, default=None):
                return super().get(key, default)

        rules = {"my_work.todo": Rule("my_work.todo", 1, ["All", "System Manager"])}
        updates = {}
        originals = {
            "sync_menu_access_rules": menu_access.sync_menu_access_rules,
            "_menu_rule_map": menu_access._menu_rule_map,
            "db": getattr(menu_access.frappe, "db", None),
            "clear_cache": getattr(menu_access.frappe, "clear_cache", None),
        }

        def set_value(_doctype, name, values):
            updates[name] = values

        menu_access.sync_menu_access_rules = lambda: None
        menu_access._menu_rule_map = lambda: rules
        menu_access.frappe.db = types.SimpleNamespace(
            exists=lambda doctype, name=None: doctype == "Role" and name == "Orderlift Admin",
            set_value=set_value,
        )
        menu_access.frappe.clear_cache = lambda *args, **kwargs: None
        try:
            result = menu_access.save_menu_access_for_role("Orderlift Admin", [])
        finally:
            menu_access.sync_menu_access_rules = originals["sync_menu_access_rules"]
            menu_access._menu_rule_map = originals["_menu_rule_map"]
            if originals["db"] is None:
                delattr(menu_access.frappe, "db")
            else:
                menu_access.frappe.db = originals["db"]
            if originals["clear_cache"] is None:
                delattr(menu_access.frappe, "clear_cache")
            else:
                menu_access.frappe.clear_cache = originals["clear_cache"]

        self.assertEqual(result["changed"], 1)
        self.assertEqual(json.loads(updates["my_work.todo"]["denied_roles_json"]), ["Orderlift Admin"])
        self.assertNotIn("allowed_roles_json", updates["my_work.todo"])

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
        self.assertIn("Item Category", labels)
        self.assertIn("Item Group", labels)
        self.assertIn("Selling Price Builder", labels)
        self.assertIn("Currency List", labels)
        self.assertIn("Currency Exchange", labels)
        self.assertIn("Currency Exchange Settings", labels)
        self.assertIn("Stock Entry", labels)
        self.assertIn("Warehouse Tree", labels)
        self.assertIn("Warehouse Report", labels)
        self.assertNotIn("Selling Price List Builder", labels)
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

    def test_company_access_payload_includes_company_currency_map(self):
        originals = {
            "all_companies": menu_access.user_can_access_all_companies,
            "allowed_companies": menu_access.get_allowed_companies,
            "user_default": menu_access.get_user_default_company,
            "doctype_available": menu_access._doctype_available,
            "get_all": getattr(menu_access.frappe, "get_all", None),
        }
        menu_access.user_can_access_all_companies = lambda user=None: False
        menu_access.get_allowed_companies = lambda user=None: ["Orderlift", "Orderlift Turkey"]
        menu_access.get_user_default_company = lambda user=None: "Orderlift Turkey"
        menu_access._doctype_available = lambda doctype: doctype == "Company"

        def get_all(doctype, filters=None, fields=None, **kwargs):
            self.assertEqual(doctype, "Company")
            return [
                {"name": "Orderlift", "default_currency": "MAD"},
                {"name": "Orderlift Turkey", "default_currency": "TRY"},
            ]

        menu_access.frappe.get_all = get_all
        try:
            payload = menu_access.get_company_access_payload("demo@example.com")
        finally:
            menu_access.user_can_access_all_companies = originals["all_companies"]
            menu_access.get_allowed_companies = originals["allowed_companies"]
            menu_access.get_user_default_company = originals["user_default"]
            menu_access._doctype_available = originals["doctype_available"]
            if originals["get_all"] is None:
                delattr(menu_access.frappe, "get_all")
            else:
                menu_access.frappe.get_all = originals["get_all"]

        self.assertEqual(payload["current_company"], "Orderlift Turkey")
        self.assertEqual(payload["company_currencies"]["Orderlift Turkey"], "TRY")
        self.assertEqual(payload["company_currencies"]["Orderlift"], "MAD")

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

    def test_company_query_focuses_selected_company_within_allowed_companies(self):
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
                "(`tabSales Order`.company = 'Orderlift')",
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
                "((`tabSales Commission`.company = 'Orderlift')) and (`tabSales Commission`.salesperson = 'Bilal')",
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

    def test_price_list_permission_allows_new_doc_for_allowed_company(self):
        original_all_companies = company_access.user_can_access_all_companies
        original_allowed = company_access.get_allowed_companies
        original_db = getattr(company_access.frappe, "db", None)
        company_access.user_can_access_all_companies = lambda user=None: False
        company_access.get_allowed_companies = lambda user=None: ["Orderlift"]
        company_access.frappe.db = types.SimpleNamespace(exists=lambda *args, **kwargs: False)

        def get_field(field):
            values = {"name": "new-price-list-1", "custom_company": "Orderlift", "buying": 0, "selling": 1}
            return values.get(field, "")

        doc = types.SimpleNamespace(doctype="Price List", name="new-price-list-1", get=get_field, is_new=lambda: True)
        try:
            self.assertTrue(company_access.has_company_permission(doc, user="admin@example.com", permission_type="create"))
        finally:
            company_access.user_can_access_all_companies = original_all_companies
            company_access.get_allowed_companies = original_allowed
            if original_db is None:
                delattr(company_access.frappe, "db")
            else:
                company_access.frappe.db = original_db

    def test_price_list_permission_denies_new_doc_for_disallowed_company(self):
        original_all_companies = company_access.user_can_access_all_companies
        original_allowed = company_access.get_allowed_companies
        original_db = getattr(company_access.frappe, "db", None)
        company_access.user_can_access_all_companies = lambda user=None: False
        company_access.get_allowed_companies = lambda user=None: ["Orderlift"]
        company_access.frappe.db = types.SimpleNamespace(exists=lambda *args, **kwargs: False)

        def get_field(field):
            values = {"name": "new-price-list-1", "custom_company": "Pivot", "buying": 0, "selling": 1}
            return values.get(field, "")

        doc = types.SimpleNamespace(doctype="Price List", name="new-price-list-1", get=get_field, is_new=lambda: True)
        try:
            self.assertFalse(company_access.has_company_permission(doc, user="admin@example.com", permission_type="create"))
        finally:
            company_access.user_can_access_all_companies = original_all_companies
            company_access.get_allowed_companies = original_allowed
            if original_db is None:
                delattr(company_access.frappe, "db")
            else:
                company_access.frappe.db = original_db

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

    def test_stock_entry_rate_guard_is_registered(self):
        from orderlift import hooks

        self.assertIn("Stock Entry", hooks.doctype_js)
        self.assertEqual(hooks.doctype_js["Stock Entry"], "public/js/stock_entry_rate_guard_20260706a.js")

    def test_stock_entry_rate_guard_hides_rate_fields(self):
        script = (APP_ROOT / "orderlift" / "public" / "js" / "stock_entry_rate_guard_20260706a.js").read_text()

        self.assertIn('"basic_rate"', script)
        self.assertIn('"basic_amount"', script)
        self.assertIn('"valuation_rate"', script)
        self.assertIn('"set_basic_rate_manually"', script)
        self.assertIn('"allow_zero_valuation_rate"', script)
        self.assertIn('"rates_section"', script)
        self.assertIn("userHasPrivilegedRole", script)
        self.assertIn("Orderlift Admin", script)


if __name__ == "__main__":
    unittest.main()
