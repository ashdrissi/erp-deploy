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


from orderlift import company_access, menu_access, menu_registry, work_notifications
from orderlift.scripts import setup_startup_roles
from orderlift.startup_roles import (
    CANONICAL_BUSINESS_ROLES,
    OPPORTUNITY_ALL_ACCESS_ROLE,
    OPPORTUNITY_ASSIGNER_ROLE,
    PAYMENT_VALIDATOR_ROLE,
    STARTUP_ROLES,
)


APP_ROOT = Path(__file__).resolve().parents[2]


class TestMenuAccessHelpers(unittest.TestCase):
    def test_orderlift_admin_has_unrestricted_business_company_scope(self):
        original_get_roles = menu_access._get_roles
        menu_access._get_roles = lambda user=None: {"Orderlift Admin"}
        try:
            self.assertTrue(menu_access.user_can_access_all_companies("orderlift.admin@example.com"))
            self.assertTrue(menu_access.user_can_access_all_business_types("orderlift.admin@example.com"))
        finally:
            menu_access._get_roles = original_get_roles

    def test_current_company_prefers_browser_session_without_changing_last_selected(self):
        original_session_context = menu_access.get_session_company_context
        original_last_selected = menu_access.get_last_selected_company
        original_set_session = menu_access.set_session_current_company
        menu_access.get_session_company_context = lambda **kwargs: {
            "user": "demo@example.com",
            "company": "Orderlift Maroc Installation",
            "revision": 4,
        }
        menu_access.get_last_selected_company = lambda user=None: "Orderlift Maroc Distribution"
        menu_access.set_session_current_company = lambda company, user=None: self.fail(
            "Existing session context must not be rewritten"
        )
        try:
            current = menu_access.resolve_current_company(
                user="demo@example.com",
                allowed_companies=["Orderlift Maroc Distribution", "Orderlift Maroc Installation"],
            )
        finally:
            menu_access.get_session_company_context = original_session_context
            menu_access.get_last_selected_company = original_last_selected
            menu_access.set_session_current_company = original_set_session

        self.assertEqual(current, "Orderlift Maroc Installation")

    def test_multi_company_without_session_or_last_selected_requires_selection(self):
        original_session_context = menu_access.get_session_company_context
        original_last_selected = menu_access.get_last_selected_company
        original_sid = menu_access._interactive_session_sid
        menu_access.get_session_company_context = lambda **kwargs: {}
        menu_access.get_last_selected_company = lambda user=None: ""
        menu_access._interactive_session_sid = lambda user=None: "SID-A"
        try:
            current = menu_access.resolve_current_company(
                user="demo@example.com",
                allowed_companies=["Orderlift Maroc Distribution", "Orderlift Maroc Installation"],
            )
        finally:
            menu_access.get_session_company_context = original_session_context
            menu_access.get_last_selected_company = original_last_selected
            menu_access._interactive_session_sid = original_sid

        self.assertEqual(current, "")

    def test_new_interactive_session_uses_last_selected_and_seeds_sid(self):
        originals = {
            "context": menu_access.get_session_company_context,
            "last_selected": menu_access.get_last_selected_company,
            "session_set": menu_access.set_session_current_company,
            "sid": menu_access._interactive_session_sid,
        }
        seeded = []
        menu_access.get_session_company_context = lambda **kwargs: {}
        menu_access.get_last_selected_company = lambda user=None: "Orderlift Maroc Installation"
        menu_access.set_session_current_company = lambda company, user=None: seeded.append((company, user)) or {"company": company}
        menu_access._interactive_session_sid = lambda user=None: "SID-NEW"
        try:
            current = menu_access.resolve_current_company(
                user="demo@example.com",
                allowed_companies=["Orderlift Maroc Distribution", "Orderlift Maroc Installation"],
            )
        finally:
            menu_access.get_session_company_context = originals["context"]
            menu_access.get_last_selected_company = originals["last_selected"]
            menu_access.set_session_current_company = originals["session_set"]
            menu_access._interactive_session_sid = originals["sid"]

        self.assertEqual(current, "Orderlift Maroc Installation")
        self.assertEqual(seeded, [("Orderlift Maroc Installation", "demo@example.com")])

    def test_single_allowed_company_is_automatic_without_last_selected(self):
        original_session_context = menu_access.get_session_company_context
        original_last_selected = menu_access.get_last_selected_company
        original_sid = menu_access._interactive_session_sid
        menu_access.get_session_company_context = lambda **kwargs: {}
        menu_access.get_last_selected_company = lambda user=None: ""
        menu_access._interactive_session_sid = lambda user=None: ""
        try:
            current = menu_access.resolve_current_company(
                user="demo@example.com",
                allowed_companies=["Orderlift Maroc Installation"],
            )
        finally:
            menu_access.get_session_company_context = original_session_context
            menu_access.get_last_selected_company = original_last_selected
            menu_access._interactive_session_sid = original_sid

        self.assertEqual(current, "Orderlift Maroc Installation")

    def test_resolving_another_user_never_uses_current_browser_sid(self):
        original_session = menu_access.frappe.session
        original_request = getattr(menu_access.frappe, "request", None)
        menu_access.frappe.session = types.SimpleNamespace(user="operator@example.com", sid="SID-A")
        menu_access.frappe.request = types.SimpleNamespace(cookies={"sid": "SID-A"})
        try:
            self.assertEqual(menu_access._interactive_session_sid("target@example.com"), "")
            self.assertEqual(menu_access._interactive_session_sid("operator@example.com"), "SID-A")
        finally:
            menu_access.frappe.session = original_session
            if original_request is None:
                delattr(menu_access.frappe, "request")
            else:
                menu_access.frappe.request = original_request

    def test_unbound_request_proxy_is_treated_as_noninteractive(self):
        original_session = menu_access.frappe.session
        original_request = getattr(menu_access.frappe, "request", None)
        original_local = getattr(menu_access.frappe, "local", None)

        class UnboundRequest:
            @property
            def cookies(self):
                raise RuntimeError("object is not bound")

        menu_access.frappe.session = types.SimpleNamespace(user="worker@example.com", sid="worker")
        menu_access.frappe.local = types.SimpleNamespace(request=UnboundRequest())
        menu_access.frappe.request = UnboundRequest()
        try:
            self.assertEqual(menu_access._interactive_session_sid("worker@example.com"), "")
        finally:
            menu_access.frappe.session = original_session
            if original_request is None:
                delattr(menu_access.frappe, "request")
            else:
                menu_access.frappe.request = original_request
            if original_local is None:
                delattr(menu_access.frappe, "local")
            else:
                menu_access.frappe.local = original_local

    def test_same_user_has_independent_company_context_per_sid(self):
        originals = {
            "session": menu_access.frappe.session,
            "request": getattr(menu_access.frappe, "request", None),
            "local": getattr(menu_access.frappe, "local", None),
            "cache": getattr(menu_access.frappe, "cache", None),
            "all_companies": menu_access.user_can_access_all_companies,
            "get_all_companies": menu_access.get_all_companies,
        }

        class Cache:
            def __init__(self):
                self.values = {}

            def get_value(self, key, **kwargs):
                return self.values.get(key)

            def set_value(self, key, value, **kwargs):
                self.values[key] = value

            def delete_value(self, key):
                self.values.pop(key, None)

        cache = Cache()
        menu_access.frappe.cache = cache
        menu_access.frappe.local = types.SimpleNamespace()
        menu_access.user_can_access_all_companies = lambda user=None: True
        menu_access.get_all_companies = lambda: [
            "Orderlift Maroc Distribution",
            "Orderlift Maroc Installation",
        ]
        try:
            menu_access.frappe.session = types.SimpleNamespace(user="demo@example.com", sid="SID-A")
            menu_access.frappe.request = types.SimpleNamespace(cookies={"sid": "SID-A"})
            menu_access.set_session_current_company("Orderlift Maroc Distribution")

            menu_access.frappe.local = types.SimpleNamespace()
            menu_access.frappe.session = types.SimpleNamespace(user="demo@example.com", sid="SID-B")
            menu_access.frappe.request = types.SimpleNamespace(cookies={"sid": "SID-B"})
            menu_access.set_session_current_company("Orderlift Maroc Installation")

            menu_access.frappe.local = types.SimpleNamespace()
            menu_access.frappe.session = types.SimpleNamespace(user="demo@example.com", sid="SID-A")
            menu_access.frappe.request = types.SimpleNamespace(cookies={"sid": "SID-A"})
            context_a = menu_access.get_session_company_context()

            menu_access.frappe.local = types.SimpleNamespace()
            menu_access.frappe.session = types.SimpleNamespace(user="demo@example.com", sid="SID-B")
            menu_access.frappe.request = types.SimpleNamespace(cookies={"sid": "SID-B"})
            context_b = menu_access.get_session_company_context()
        finally:
            menu_access.frappe.session = originals["session"]
            for name in ("request", "local", "cache"):
                value = originals[name]
                if value is None:
                    delattr(menu_access.frappe, name)
                else:
                    setattr(menu_access.frappe, name, value)
            menu_access.user_can_access_all_companies = originals["all_companies"]
            menu_access.get_all_companies = originals["get_all_companies"]

        self.assertEqual(context_a["company"], "Orderlift Maroc Distribution")
        self.assertEqual(context_b["company"], "Orderlift Maroc Installation")

    def test_last_selected_company_uses_only_namespaced_default(self):
        original_defaults = getattr(menu_access.frappe, "defaults", None)
        calls = []

        class Defaults:
            @staticmethod
            def get_user_default(key, user=None):
                calls.append((key, user))
                return {
                    menu_access.LAST_SELECTED_COMPANY_DEFAULT_KEY: "Orderlift Maroc Installation",
                    "Company": "Orderlift Maroc Distribution",
                    menu_access.LEGACY_PREFERRED_COMPANY_DEFAULT_KEY: "Orderlift Turkey",
                }.get(key)

        menu_access.frappe.defaults = Defaults()
        try:
            company = menu_access.get_last_selected_company("demo@example.com")
        finally:
            if original_defaults is None:
                delattr(menu_access.frappe, "defaults")
            else:
                menu_access.frappe.defaults = original_defaults

        self.assertEqual(company, "Orderlift Maroc Installation")
        self.assertEqual(calls, [(menu_access.LAST_SELECTED_COMPANY_DEFAULT_KEY, "demo@example.com")])

    def test_noninteractive_multi_company_resolution_ignores_last_selected(self):
        originals = {
            "context": menu_access.get_session_company_context,
            "last_selected": menu_access.get_last_selected_company,
            "sid": menu_access._interactive_session_sid,
        }
        menu_access.get_session_company_context = lambda **kwargs: {}
        menu_access.get_last_selected_company = lambda user=None: "Orderlift Maroc Installation"
        menu_access._interactive_session_sid = lambda user=None: ""
        try:
            current = menu_access.resolve_current_company(
                user="demo@example.com",
                allowed_companies=["Orderlift Maroc Distribution", "Orderlift Maroc Installation"],
            )
        finally:
            menu_access.get_session_company_context = originals["context"]
            menu_access.get_last_selected_company = originals["last_selected"]
            menu_access._interactive_session_sid = originals["sid"]

        self.assertEqual(current, "")

    def test_explicit_company_switch_persists_last_selected(self):
        originals = {
            "access": menu_access.user_can_access_company,
            "request": menu_access._current_request,
            "session_set": menu_access.set_session_current_company,
            "last_set": menu_access._set_last_selected_company,
            "payload": menu_access.get_company_access_payload,
        }
        calls = []
        menu_access.user_can_access_company = lambda company, user=None: True
        menu_access._current_request = lambda: types.SimpleNamespace(method="POST")
        menu_access.set_session_current_company = lambda company, user=None: {"company": company}
        menu_access._set_last_selected_company = lambda company, user=None: calls.append((company, user))
        menu_access.get_company_access_payload = lambda **kwargs: {"current_company": kwargs.get("requested_company")}
        try:
            result = menu_access.set_current_company("Orderlift Maroc Installation")
        finally:
            menu_access.user_can_access_company = originals["access"]
            menu_access._current_request = originals["request"]
            menu_access.set_session_current_company = originals["session_set"]
            menu_access._set_last_selected_company = originals["last_set"]
            menu_access.get_company_access_payload = originals["payload"]

        self.assertEqual(result["current_company"], "Orderlift Maroc Installation")
        self.assertEqual(calls, [("Orderlift Maroc Installation", "demo@example.com")])

    def test_company_access_change_clears_disallowed_last_selected(self):
        originals = {
            "db": getattr(menu_access.frappe, "db", None),
            "get_all": getattr(menu_access.frappe, "get_all", None),
            "new_doc": getattr(menu_access.frappe, "new_doc", None),
            "delete_doc": getattr(menu_access.frappe, "delete_doc", None),
            "clear_cache": getattr(menu_access.frappe, "clear_cache", None),
            "last_selected": menu_access.get_last_selected_company,
            "all_access": menu_access.user_can_access_all_companies,
        }
        deleted_defaults = []
        inserted_permissions = []

        class Db:
            @staticmethod
            def exists(doctype, name):
                return True

            @staticmethod
            def delete(doctype, filters):
                deleted_defaults.append((doctype, filters))

        class Permission:
            def insert(self, ignore_permissions=False):
                inserted_permissions.append(self.for_value)

        menu_access.frappe.db = Db()
        menu_access.frappe.get_all = lambda *args, **kwargs: []
        menu_access.frappe.new_doc = lambda doctype: Permission()
        menu_access.frappe.delete_doc = lambda *args, **kwargs: None
        menu_access.frappe.clear_cache = lambda **kwargs: None
        menu_access.get_last_selected_company = lambda user=None: "Orderlift Maroc Distribution"
        menu_access.user_can_access_all_companies = lambda user=None: False
        try:
            result = menu_access.save_user_company_access(
                "demo@example.com",
                ["Orderlift Maroc Installation"],
            )
        finally:
            for name in ("db", "get_all", "new_doc", "delete_doc", "clear_cache"):
                value = originals[name]
                if value is None:
                    delattr(menu_access.frappe, name)
                else:
                    setattr(menu_access.frappe, name, value)
            menu_access.get_last_selected_company = originals["last_selected"]
            menu_access.user_can_access_all_companies = originals["all_access"]

        self.assertEqual(inserted_permissions, ["Orderlift Maroc Installation"])
        self.assertEqual(result["last_selected_company"], "")
        self.assertEqual(
            deleted_defaults,
            [
                (
                    "DefaultValue",
                    {
                        "parent": "demo@example.com",
                        "defkey": menu_access.LAST_SELECTED_COMPANY_DEFAULT_KEY,
                    },
                )
            ],
        )

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
        self.assertIn("my_work.notifications", keys)

    def test_my_work_todo_uses_filtered_page(self):
        todo = menu_registry.menu_item_by_key("my_work.todo")

        self.assertEqual(todo["label"], "My ToDos")
        self.assertEqual(todo["link_type"], "Page")
        self.assertEqual(todo["link_to"], "my-todos")

    def test_my_work_notifications_link_and_personal_counts(self):
        notifications = menu_registry.menu_item_by_key("my_work.notifications")
        self.assertEqual(notifications["link_type"], "DocType")
        self.assertEqual(notifications["link_to"], "Notification Log")

        calls = []
        original_db = getattr(work_notifications.frappe, "db", None)
        work_notifications.frappe.db = types.SimpleNamespace(
            count=lambda doctype, filters: calls.append((doctype, filters)) or (4 if doctype == "ToDo" else 7)
        )
        try:
            counts = work_notifications.get_work_counts()
        finally:
            if original_db is None:
                delattr(work_notifications.frappe, "db")
            else:
                work_notifications.frappe.db = original_db

        self.assertEqual(counts, {"open_todos": 4, "unread_notifications": 7})
        self.assertEqual(calls[0], ("ToDo", {"status": "Open", "allocated_to": "demo@example.com"}))
        self.assertEqual(calls[1], ("Notification Log", {"read": 0, "for_user": "demo@example.com"}))

    def test_sidebar_work_badges_use_routes_and_realtime_state_updates(self):
        source = (
            APP_ROOT / "orderlift" / "public" / "js" / "orderlift_sidebar_tune_20260423e.js"
        ).read_text()

        self.assertIn('renderWorkCount("my-todos", "My ToDos"', source)
        self.assertIn('renderWorkCount("Notification Log", "Notifications"', source)
        self.assertIn('anchor.insertBefore(badge, control || null)', source)
        self.assertIn('(count ? "" : " is-empty")', source)
        self.assertIn('badge.textContent = String(count)', source)
        self.assertIn('findSidebarItemByLabel("ToDo")', source)
        self.assertIn('frappe.realtime.doctype_subscribe("ToDo")', source)
        self.assertIn('frappe.realtime.doctype_subscribe("Notification Log")', source)
        self.assertIn('data.doctype === "ToDo" || data.doctype === "Notification Log"', source)
        self.assertIn('notification_log.notification_log.mark_as_read', source)

    def test_company_switcher_is_sid_scoped_and_replaces_native_session_defaults(self):
        hooks = (APP_ROOT / "orderlift" / "hooks.py").read_text()
        menu_access_source = (APP_ROOT / "orderlift" / "menu_access.py").read_text()
        switcher = (
            APP_ROOT / "orderlift" / "public" / "js" / "orderlift_company_switcher_20260803d.js"
        ).read_text()

        self.assertIn("orderlift_company_switcher_20260803d.js", hooks)
        self.assertNotIn("orderlift_change_company_label_20260519a.js", hooks)
        self.assertIn('"orderlift.menu_access.clear_session_company_context"', hooks)
        self.assertIn("SESSION_COMPANY_CACHE_PREFIX", menu_access_source)
        self.assertIn("_interactive_session_sid", menu_access_source)
        self.assertIn('method: "orderlift.menu_access.set_current_company"', switcher)
        self.assertNotIn("setup_session_defaults = function", switcher)
        self.assertIn("BroadcastChannel", switcher)
        self.assertIn("window.orderlift.setActiveCompany", switcher)
        self.assertIn("requires_company_selection", switcher)
        self.assertIn("MutationObserver", switcher)
        self.assertIn(":scope > .sidebar-header", switcher)
        self.assertIn("text-overflow:ellipsis", switcher)
        self.assertIn("host.dataset.companyLabel", switcher)
        self.assertIn("frappe.boot.desk_settings.view_switcher = 1", switcher)
        self.assertIn(".header-subtitle{display:none!important}", switcher)

        list_focus = (
            APP_ROOT / "orderlift" / "public" / "js" / "company_scope_list_focus_20260601a.js"
        ).read_text()
        self.assertIn("refreshOnceForCompany", list_focus)
        self.assertIn("__orderlift_initial_refresh_complete", list_focus)
        self.assertIn("listview.last_args = null", list_focus)
        self.assertIn("Promise.resolve(frappe.call", list_focus)
        self.assertNotIn("orderlift_company=", switcher)

        setter = menu_access_source.split("def set_current_company(company: str)", 1)[1].split(
            "def resolve_current_company", 1
        )[0]
        self.assertIn('upper() != "POST"', setter)
        self.assertIn("set_session_current_company", setter)
        self.assertIn("_set_last_selected_company", setter)
        session_setter = menu_access_source.split("def set_session_current_company(", 1)[1].split(
            "def clear_session_company_context", 1
        )[0]
        self.assertNotIn("_set_last_selected_company", session_setter)
        boot = (APP_ROOT / "orderlift" / "boot.py").read_text()
        self.assertIn('defaults["Company"] = company', boot)
        self.assertIn('sysdefaults["Company"] = company', boot)
        self.assertIn('desk_settings["view_switcher"] = 1', boot)

        patch = (
            APP_ROOT / "orderlift" / "patches" / "v1_0" / "backfill_session_company_context.py"
        ).read_text()
        self.assertIn("LEGACY_PREFERRED_COMPANY_DEFAULT_KEY", patch)
        self.assertIn('row.get("ref_doctype") != "Company"', patch)
        self.assertNotIn("delete_doc", patch)
        retire_patch = (
            APP_ROOT / "orderlift" / "patches" / "v1_0" / "retire_preferred_company_default.py"
        ).read_text()
        self.assertIn("LEGACY_PREFERRED_COMPANY_DEFAULT_KEY", retire_patch)
        self.assertIn('frappe.db.delete(', retire_patch)
        self.assertNotIn("set_user_default", retire_patch)

    def test_company_context_consumers_fail_closed_without_shared_default(self):
        campaign = (APP_ROOT / "orderlift" / "orderlift_crm" / "api" / "campaign.py").read_text()
        portal_api = (APP_ROOT / "orderlift" / "client_portal" / "api.py").read_text()
        portal_request = (
            APP_ROOT
            / "orderlift"
            / "client_portal"
            / "doctype"
            / "portal_quote_request"
            / "portal_quote_request.py"
        ).read_text()
        status_control = (
            APP_ROOT / "orderlift" / "orderlift_crm" / "api" / "status_control.py"
        ).read_text()

        self.assertNotIn('frappe.defaults.get_user_default("Company")', campaign)
        self.assertIn("Select an active Company before using Campaign Manager", campaign)
        self.assertIn("campaign_company == company", campaign)
        self.assertIn("request.custom_company", portal_api)
        self.assertIn('getattr(self, "custom_company", "")', portal_request)
        self.assertIn('user_can_access_menu_key("administration.status_control"', status_control)

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

    def test_menu_registry_exposes_only_canonical_business_roles(self):
        self.assertEqual(menu_registry.BUSINESS_ROLES, CANONICAL_BUSINESS_ROLES)
        self.assertFalse(set(STARTUP_ROLES).intersection(menu_registry.BUSINESS_ROLES))
        all_default_roles = {
            role
            for item in menu_registry.iter_menu_items()
            for role in item.get("roles", [])
            if role != menu_registry.ALL_USERS_ROLE
        }

        self.assertEqual(all_default_roles - set(menu_registry.BUSINESS_ROLES) - {"System Manager"}, set())

    def test_campaign_pages_require_campaign_doctype_permission(self):
        manager = menu_registry.menu_item_by_key("crm.campaign_manager")
        builder = menu_registry.menu_item_by_key("crm.campaign_builder")

        self.assertEqual(manager.get("required_doctypes"), ["Partner Campaign"])
        self.assertEqual(builder.get("required_doctypes"), ["Partner Campaign"])
        self.assertIn("Sales User", manager.get("roles"))
        self.assertIn("Sales Manager", manager.get("roles"))

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
        self.assertEqual(permissions["Quotation"]["submit"], 1)
        self.assertEqual(permissions["Price List"]["read"], 1)
        self.assertEqual(permissions["Price List"]["select"], 1)

    def test_dimensioning_configuration_access_is_narrow(self):
        feature_roles = set(setup_startup_roles.DIMENSIONING_FEATURE_ROLES)
        builder_roles = set(setup_startup_roles.PRICING_SHEET_BUILDER_ROLES)

        self.assertEqual(feature_roles, {"Orderlift Admin", "Pricing Configuration"})
        self.assertEqual(builder_roles, {"Orderlift Admin", "Sales Manager", "Sales User"})
        self.assertEqual(
            set(setup_startup_roles.DIMENSIONING_SET_BUILDER_ROLES),
            {"Orderlift Admin", "System Manager", "Pricing Configuration"},
        )
        self.assertEqual(
            set(setup_startup_roles.DIMENSIONING_SET_FULL_ACCESS_ROLES),
            {"Orderlift Admin", "Pricing Configuration"},
        )
        self.assertEqual(setup_startup_roles.DIMENSIONING_SET_ADMIN_PERMISSION["delete"], 1)

    def test_after_migrate_does_not_reapply_dimensioning_or_permissions(self):
        source = (APP_ROOT / "orderlift" / "scripts" / "setup_startup_roles.py").read_text()

        self.assertIn("return run(seed_roles_only=1)", source)
        self.assertNotIn("_ensure_dimensioning_feature_access(results)", source)

    def test_stock_manager_has_explicit_stock_docperms(self):
        permissions = setup_startup_roles.DOCTYPE_PERMISSIONS["Stock Manager"]

        self.assertEqual(permissions["Stock Settings"]["read"], 1)
        self.assertEqual(permissions["Stock Settings"]["write"], 1)
        self.assertEqual(permissions["Bin"]["read"], 1)
        self.assertEqual(permissions["Bin"]["read"], 1)
        self.assertEqual(permissions["Stock Ledger Entry"]["report"], 1)
        self.assertEqual(permissions["Stock Entry"]["create"], 1)
        self.assertEqual(permissions["Stock Entry"]["submit"], 1)
        self.assertEqual(permissions["Pick List"]["create"], 1)
        self.assertEqual(permissions["Delivery Note"]["submit"], 1)
        self.assertEqual(permissions["Purchase Receipt"]["submit"], 1)
        self.assertEqual(permissions["Stock Entry Type"]["read"], 1)

    def test_menu_report_roles_are_synced_from_allowed_menu_roles(self):
        source = (APP_ROOT / "orderlift" / "scripts" / "setup_startup_roles.py").read_text()

        self.assertIn("def _ensure_allowed_menu_link_roles", source)
        self.assertIn("_ensure_allowed_menu_link_roles(results, roles=roles)", source)
        self.assertIn('not frappe.db.exists("Role", role)', source)

    def test_logistics_user_has_operational_stock_and_read_only_purchase_order(self):
        permissions = setup_startup_roles.DOCTYPE_PERMISSIONS["Logistics User"]

        for doctype in ["Stock Entry", "Delivery Note", "Purchase Receipt", "Pick List", "Material Request"]:
            self.assertEqual(permissions[doctype]["read"], 1)
            self.assertEqual(permissions[doctype]["create"], 1)
            self.assertEqual(permissions[doctype]["submit"], 1)
            self.assertEqual(permissions[doctype].get("cancel", 0), 0)
        self.assertEqual(permissions["Purchase Order"]["read"], 1)
        self.assertEqual(permissions["Purchase Order"].get("create", 0), 0)
        self.assertNotIn("Request for Quotation", permissions)
        self.assertEqual(permissions["Supplier"]["read"], 1)
        self.assertEqual(permissions["Supplier"].get("write", 0), 0)
        self.assertEqual(permissions["Supplier Group"]["read"], 1)
        self.assertEqual(permissions["Stock Settings"]["write"], 1)
        self.assertEqual(permissions["Bin"]["read"], 1)
        self.assertEqual(permissions["Stock Ledger Entry"]["report"], 1)
        self.assertEqual(permissions["Product Bundle"]["read"], 1)
        self.assertNotIn("Item Price", permissions)
        self.assertEqual(permissions["Stock Entry Type"]["read"], 1)

    def test_base_business_roles_have_menu_backing_permissions(self):
        role_permissions = setup_startup_roles.DOCTYPE_PERMISSIONS

        self.assertEqual(role_permissions["Desk User"]["Report"]["read"], 1)
        self.assertEqual(role_permissions["Desk User"]["Report"].get("write", 0), 0)
        self.assertEqual(setup_startup_roles.WORKFLOW_PERMISSION_SCOPE["Desk User"], {"Report"})
        self.assertNotIn("Quotation", role_permissions["Pricing Configuration"])
        self.assertEqual(role_permissions["Pricing Configuration"]["Agent Pricing Rules"]["create"], 1)
        self.assertEqual(role_permissions["Finance User"]["Payment Entry"]["create"], 1)
        self.assertEqual(role_permissions["Finance User"]["Payment Entry"]["submit"], 1)
        self.assertEqual(role_permissions["Finance User"]["Sales Invoice"]["submit"], 1)
        self.assertEqual(role_permissions["Finance User"]["Purchase Invoice"]["submit"], 1)
        self.assertEqual(role_permissions["Finance User"]["Buying Settings"]["read"], 1)
        self.assertEqual(role_permissions["Finance User"]["Supplier Group"]["read"], 1)
        self.assertEqual(role_permissions["Finance User"]["Bank Account"]["read"], 1)
        self.assertEqual(role_permissions["Finance Admin"]["Payment Entry"]["cancel"], 1)
        self.assertEqual(
            role_permissions[PAYMENT_VALIDATOR_ROLE]["Payment Entry"]["submit"],
            1,
        )
        self.assertEqual(role_permissions["Installation User"]["Project"]["create"], 1)
        self.assertEqual(role_permissions["Installation User"]["QC Checklist Template"]["create"], 1)
        self.assertEqual(role_permissions["Service User"]["SAV Ticket"]["create"], 1)
        self.assertEqual(role_permissions["SAV Technician"]["SAV Ticket"]["create"], 1)
        self.assertEqual(role_permissions["Sales User"]["Portal Quote Request"]["read"], 1)
        self.assertNotIn("Item Price", role_permissions["Sales User"])
        self.assertEqual(role_permissions["Sales User"]["Quotation"]["submit"], 1)
        self.assertEqual(role_permissions["Sales User"]["Sales Order"]["submit"], 1)
        self.assertEqual(role_permissions["Sales User"]["Sales Order"]["cancel"], 1)
        self.assertEqual(role_permissions["Sales User"]["Sales Order"]["amend"], 1)
        self.assertEqual(role_permissions["Sales Manager"]["Sales Order"]["cancel"], 1)

    def test_native_purchase_roles_own_procurement_workflow(self):
        purchase_user = setup_startup_roles.DOCTYPE_PERMISSIONS["Purchase User"]
        purchase_manager = setup_startup_roles.DOCTYPE_PERMISSIONS["Purchase Manager"]

        for doctype in [
            "Request for Quotation",
            "Supplier Quotation",
        ]:
            self.assertEqual(purchase_user[doctype]["create"], 1)
            self.assertEqual(purchase_user[doctype]["submit"], 1)
            self.assertEqual(purchase_user[doctype].get("cancel", 0), 0)
            self.assertEqual(purchase_manager[doctype]["cancel"], 1)
            self.assertEqual(purchase_manager[doctype]["amend"], 1)
        self.assertEqual(purchase_user["Purchase Order"]["create"], 1)
        self.assertEqual(purchase_user["Purchase Order"].get("submit", 0), 0)
        self.assertEqual(purchase_user["Purchase Order"].get("cancel", 0), 0)
        self.assertEqual(purchase_manager["Purchase Order"]["submit"], 1)
        self.assertEqual(purchase_manager["Purchase Order"]["cancel"], 1)
        self.assertEqual(purchase_user["Material Request"]["read"], 1)
        self.assertEqual(purchase_user["Material Request"].get("create", 0), 0)
        self.assertEqual(purchase_manager["Material Request"]["cancel"], 1)
        self.assertEqual(purchase_user["Purchase Receipt"]["read"], 1)
        self.assertEqual(purchase_user["Purchase Receipt"].get("submit", 0), 0)
        self.assertNotIn("Buying Settings", purchase_user)
        self.assertNotIn("Item Price", purchase_user)
        self.assertEqual(purchase_manager["Supplier Group"]["write"], 1)

    def test_purchasing_and_finance_menu_roles_match_workflow_owners(self):
        purchasing = next(
            section
            for section in menu_registry.get_menu_sections()
            if section["key"] == "purchasing"
        )
        finance_report = menu_registry.menu_item_by_key(
            "finance.sales_payment_follow_up"
        )

        self.assertIn("Purchase User", purchasing["roles"])
        self.assertIn("Purchase Manager", purchasing["roles"])
        self.assertNotIn("Logistics User", purchasing["roles"])
        self.assertIn("Finance User", finance_report["roles"])
        self.assertIn("Finance Admin", finance_report["roles"])
        self.assertNotIn("Payment Validator", finance_report["roles"])
        self.assertEqual(
            menu_registry.menu_item_by_key("items.dimensioning_sets")["roles"],
            menu_registry.PRICING_CONFIGURATION_ROLES,
        )
        rate_review = menu_registry.menu_item_by_key("stock.rate_review")
        self.assertEqual(rate_review["link_to"], "stock-rate-review")
        self.assertNotIn("Purchase User", rate_review["roles"])
        self.assertIn("Pricing Configuration", rate_review["roles"])
        self.assertNotIn("Logistics User", rate_review["roles"])

    def test_financial_detail_is_guarded_by_dashboard_menu_access(self):
        self.assertEqual(
            menu_access.SUPPORTING_PAGE_MENU_KEYS["sale-financial-workspace"],
            "finance.sale_financial_dashboard",
        )
        dashboard = menu_registry.menu_item_by_key("finance.sale_financial_dashboard")
        self.assertEqual(
            dashboard["roles"],
            ["Orderlift Admin", "Finance User", "Finance Admin"],
        )
        self.assertNotIn(
            "finance.sale_financial_dashboard",
            setup_startup_roles.MENU_ROLE_MAP["Orderlift Executive"],
        )

        rule = {
            "enabled": 1,
            "allowed_roles_json": json.dumps(dashboard["roles"]),
            "denied_roles_json": "[]",
        }
        original_get_roles = menu_access._get_roles
        original_page_roles = menu_access._page_roles
        menu_access._get_roles = lambda user=None: {"Finance User"} if user == "finance@example.com" else {"Sales User"}
        menu_access._page_roles = lambda page_name: {
            "Orderlift Admin", "System Manager", "Finance User", "Finance Admin"
        }
        try:
            rules = {"finance.sale_financial_dashboard": rule}
            self.assertTrue(
                menu_access.user_can_access_page(
                    "sale-financial-workspace", user="finance@example.com", rules=rules
                )
            )
            self.assertFalse(
                menu_access.user_can_access_page(
                    "sale-financial-workspace", user="sales@example.com", rules=rules
                )
            )
        finally:
            menu_access._get_roles = original_get_roles
            menu_access._page_roles = original_page_roles

    def test_permission_setup_exposes_a_non_mutating_dry_run(self):
        source = (
            APP_ROOT / "orderlift" / "scripts" / "setup_startup_roles.py"
        ).read_text()
        hooks_source = (APP_ROOT / "orderlift" / "hooks.py").read_text()

        self.assertIn("dry_run: int = 0", source)
        self.assertIn('"permission_diff": [] if seed_roles_only else _permission_diff(exact_normalization=exact_normalization)', source)
        self.assertIn("exact_normalization: int = 0", source)
        self.assertIn("def after_migrate() -> dict:", source)
        self.assertIn("return run(seed_roles_only=1)", source)
        self.assertIn(
            '"orderlift.scripts.setup_startup_roles.after_migrate"',
            hooks_source,
        )

    def test_stock_settings_link_fields_ignore_user_permissions(self):
        self.assertIn("default_warehouse", setup_startup_roles.STOCK_SETTINGS_USER_PERMISSION_EXEMPT_FIELDS)
        source = (APP_ROOT / "orderlift" / "scripts" / "setup_startup_roles.py").read_text()

        self.assertNotIn("_ensure_stock_settings_user_permission_exempt_fields(results)", source)
        self.assertIn('"ignore_user_permissions"', source)

    def test_warehouse_stock_menu_includes_core_stock_documents(self):
        warehouse = next(section for section in menu_registry.get_menu_sections() if section["key"] == "warehouse_stock")
        keys = {link["key"] for link in warehouse["links"]}

        self.assertIn("stock.delivery_note", keys)
        self.assertIn("stock.purchase_receipt", keys)
        self.assertIn("stock.pick_list", keys)
        self.assertIn("stock.bins", keys)
        self.assertIn("stock.stock_settings", keys)
        self.assertIn("stock.planning_settings", keys)
        self.assertIn("stock.demand_plan", keys)

        planning_settings = menu_registry.menu_item_by_key("stock.planning_settings")
        self.assertEqual(planning_settings["link_type"], "Page")
        self.assertEqual(planning_settings["link_to"], "stock-planning-settings-control")

    def test_startup_role_seed_does_not_overwrite_existing_docperms_by_default(self):
        source = (APP_ROOT / "orderlift" / "scripts" / "setup_startup_roles.py").read_text()

        self.assertIn("exact_normalization: int = 0", source)
        self.assertIn("overwrite_existing=exact_normalization", source)
        self.assertIn('action = "exists"', source)

    def test_opportunity_all_access_is_manageable_capability_role(self):
        self.assertIn(OPPORTUNITY_ALL_ACCESS_ROLE, STARTUP_ROLES)
        self.assertEqual(
            setup_startup_roles.DOCTYPE_PERMISSIONS[OPPORTUNITY_ALL_ACCESS_ROLE]["Opportunity"]["read"],
            1,
        )

    def test_campaign_permissions_are_in_canonical_sales_roles(self):
        for role in ("Sales User", "Sales Manager", "Orderlift Admin"):
            self.assertIn("Partner Campaign", setup_startup_roles.DOCTYPE_PERMISSIONS[role])
            self.assertIn("Partner Campaign Target", setup_startup_roles.DOCTYPE_PERMISSIONS[role])

    def test_startup_manager_roles_have_core_menu_access(self):
        self.assertIn("crm.opportunity_pipeline", setup_startup_roles.MENU_ROLE_MAP["Sales Distribution Manager"])
        self.assertIn("projects.project_pipeline", setup_startup_roles.MENU_ROLE_MAP["Sales Installation Manager"])
        self.assertIn("logistics.pipeline", setup_startup_roles.MENU_ROLE_MAP["Logistics Manager"])
        self.assertIn("finance.payments", setup_startup_roles.MENU_ROLE_MAP["Finance Admin"])
        self.assertIn(
            "finance.sales_payment_follow_up",
            setup_startup_roles.MENU_ROLE_MAP["Finance Admin"],
        )
        self.assertNotIn(
            "finance.sales_payment_summary",
            setup_startup_roles.MENU_ROLE_MAP["Finance Admin"],
        )
        self.assertIn(
            "purchasing.purchase_order",
            setup_startup_roles.MENU_ROLE_MAP["Purchase User"],
        )
        self.assertNotIn(
            "purchasing.purchase_order",
            setup_startup_roles.MENU_ROLE_MAP["Logistics User"],
        )

    def test_administration_menu_includes_orderlift_admin_and_superadmins(self):
        status_control = menu_registry.menu_item_by_key("administration.status_control")
        document_templates = menu_registry.menu_item_by_key("administration.document_templates")
        access_center = menu_registry.menu_item_by_key("administration.access_command_center")
        menu_editor = menu_registry.menu_item_by_key("administration.menu_editor")

        self.assertIn("Orderlift Admin", status_control["roles"])
        self.assertIn("System Manager", status_control["roles"])
        self.assertNotIn("Developer", status_control["roles"])
        self.assertEqual(document_templates["link_to"], "document-template-manager")
        self.assertIn("Orderlift Admin", document_templates["roles"])
        self.assertIn("System Manager", document_templates["roles"])
        self.assertEqual(access_center["roles"], ["Orderlift Admin", "System Manager"])
        self.assertEqual(menu_editor["roles"], ["Orderlift Admin", "System Manager"])

    def test_document_template_targets_are_loaded_from_active_configuration(self):
        source = (APP_ROOT / "orderlift" / "document_templates.py").read_text()

        body = source.split("def get_supported_document_template_targets", 1)[1].split("\ndef ", 1)[0]
        self.assertIn('"Orderlift Document Template Target"', body)
        self.assertIn('filters={"parent": ["in", active_templates]}', body)
        self.assertNotIn("Forecast Load Plan", body)

    def test_projects_menu_does_not_include_logistics_links(self):
        projects = next(section for section in menu_registry.get_menu_sections() if section["key"] == "projects")
        keys = {link["key"] for link in projects["links"]}

        self.assertIn("projects.projects", keys)
        self.assertEqual(menu_registry.menu_item_by_key("projects.projects")["link_to"], "Project")
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

    def test_managed_sales_manager_is_preserved_when_legacy_roles_are_pruned(self):
        roles = ["Sales Manager", "Sales User", "Custom Escalation Role", "System Manager"]

        self.assertEqual(
            menu_access._prune_legacy_default_roles(roles),
            [
                "Sales Manager",
                "Sales User",
                "Custom Escalation Role",
                "System Manager",
            ],
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

        # Three menu entries target DocType Project: crm.projects_list and
        # sig.projects (both overridden above) plus the un-overridden
        # projects.projects entry, which keeps its registry label. What this test
        # guards is that overrides key off the internal _menu_key rather than the
        # shared link target, so same-target rows get distinct labels.
        self.assertEqual(
            [row["label"] for row in project_rows],
            ["CRM Projects", "SIG Projects", "Projects"],
        )
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

    def test_business_user_bootinfo_injects_main_dashboard_when_frappe_omits_it(self):
        class BootInfo(dict):
            def __getattr__(self, name):
                return self[name]

            def __setattr__(self, name, value):
                self[name] = value

        bootinfo = BootInfo({"workspace_sidebar_item": {"buying": {"items": []}}})
        originals = {
            "get_boot_menu_access": menu_access.get_boot_menu_access,
            "get_company_access_payload": menu_access.get_company_access_payload,
            "filter_sidebar_rows": menu_access.filter_sidebar_rows,
            "_get_roles": menu_access._get_roles,
            "build_central_sidebar_rows": menu_access.build_central_sidebar_rows,
        }
        menu_access.get_boot_menu_access = lambda user=None: {"visible_menu_keys": ["purchasing.purchase_order"]}
        menu_access.get_company_access_payload = lambda user=None: {"companies": ["Orderlift Maroc Distribution"]}
        menu_access.filter_sidebar_rows = lambda rows, user=None: rows[:1]
        menu_access._get_roles = lambda user=None: {"Purchase User"}
        menu_access.build_central_sidebar_rows = lambda: [
            {"type": "Link", "label": "Purchase Order", "link_type": "DocType", "link_to": "Purchase Order"}
        ]
        try:
            menu_access.apply_menu_access_to_bootinfo(bootinfo, user="buyer@example.com")
        finally:
            for name, value in originals.items():
                setattr(menu_access, name, value)

        self.assertEqual(list(bootinfo["workspace_sidebar_item"].keys()), ["main dashboard"])
        self.assertEqual(bootinfo["workspace_sidebar_item"]["main dashboard"]["items"][0]["label"], "Purchase Order")

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
            "last_selected": menu_access.get_last_selected_company,
            "session_context": menu_access.get_session_company_context,
            "session_set": menu_access.set_session_current_company,
            "sid": menu_access._interactive_session_sid,
            "doctype_available": menu_access._doctype_available,
            "get_all": getattr(menu_access.frappe, "get_all", None),
        }
        menu_access.user_can_access_all_companies = lambda user=None: False
        menu_access.get_allowed_companies = lambda user=None: ["Orderlift", "Orderlift Turkey"]
        menu_access.get_last_selected_company = lambda user=None: "Orderlift Turkey"
        menu_access.get_session_company_context = lambda **kwargs: {}
        menu_access.set_session_current_company = lambda company, user=None: {"company": company}
        menu_access._interactive_session_sid = lambda user=None: "SID-A"
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
            menu_access.get_last_selected_company = originals["last_selected"]
            menu_access.get_session_company_context = originals["session_context"]
            menu_access.set_session_current_company = originals["session_set"]
            menu_access._interactive_session_sid = originals["sid"]
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
        original_resolve = company_access.resolve_current_company
        original_interactive = company_access.has_interactive_company_session
        original_db = getattr(company_access.frappe, "db", None)
        original_get_meta = getattr(company_access.frappe, "get_meta", None)
        company_access.user_can_access_all_companies = lambda user=None: False
        company_access.get_allowed_companies = lambda user=None: ["Orderlift", "Pivot"]
        company_access.resolve_current_company = lambda **kwargs: "Orderlift"
        company_access.has_interactive_company_session = lambda user=None: True
        company_access.frappe.db = types.SimpleNamespace(escape=lambda value: repr(value))
        company_access.frappe.get_meta = lambda doctype: types.SimpleNamespace(get_field=lambda field: field == "company")
        try:
            self.assertEqual(
                company_access.sales_order_query("demo@example.com"),
                "(`tabSales Order`.company in ('Orderlift'))",
            )
        finally:
            company_access.user_can_access_all_companies = original_all_companies
            company_access.get_allowed_companies = original_allowed
            company_access.resolve_current_company = original_resolve
            company_access.has_interactive_company_session = original_interactive
            if original_db is None:
                delattr(company_access.frappe, "db")
            else:
                company_access.frappe.db = original_db
            if original_get_meta is None:
                delattr(company_access.frappe, "get_meta")
            else:
                company_access.frappe.get_meta = original_get_meta

    def test_noninteractive_company_query_uses_all_allowed_companies(self):
        originals = {
            "allowed": company_access.get_allowed_companies,
            "interactive": company_access.has_interactive_company_session,
            "db": getattr(company_access.frappe, "db", None),
            "meta": getattr(company_access.frappe, "get_meta", None),
        }
        company_access.get_allowed_companies = lambda user=None: ["Distribution", "Installation"]
        company_access.has_interactive_company_session = lambda user=None: False
        company_access.frappe.db = types.SimpleNamespace(escape=lambda value: repr(value))
        company_access.frappe.get_meta = lambda doctype: types.SimpleNamespace(
            get_field=lambda field: field == "company"
        )
        try:
            clause = company_access.purchase_order_query("demo@example.com")
        finally:
            company_access.get_allowed_companies = originals["allowed"]
            company_access.has_interactive_company_session = originals["interactive"]
            if originals["db"] is None:
                delattr(company_access.frappe, "db")
            else:
                company_access.frappe.db = originals["db"]
            if originals["meta"] is None:
                delattr(company_access.frappe, "get_meta")
            else:
                company_access.frappe.get_meta = originals["meta"]

        self.assertEqual(clause, "(`tabPurchase Order`.company in ('Distribution', 'Installation'))")

    def test_sales_commission_query_filters_sales_user_to_own_salesperson(self):
        original_all_companies = company_access.user_can_access_all_companies
        original_allowed = company_access.get_allowed_companies
        original_db = getattr(company_access.frappe, "db", None)
        original_get_meta = getattr(company_access.frappe, "get_meta", None)
        original_can_manage = company_access._can_manage_sales_commissions
        original_salesperson = company_access._sales_person_for_user
        original_interactive = company_access.has_interactive_company_session
        company_access.user_can_access_all_companies = lambda user=None: False
        company_access.get_allowed_companies = lambda user=None: ["Orderlift"]
        company_access.frappe.db = types.SimpleNamespace(escape=lambda value: repr(value))
        company_access.frappe.get_meta = lambda doctype: types.SimpleNamespace(get_field=lambda field: field == "company")
        company_access._can_manage_sales_commissions = lambda user: False
        company_access._sales_person_for_user = lambda user: "Bilal"
        company_access.has_interactive_company_session = lambda user=None: True
        try:
            self.assertEqual(
                company_access.sales_commission_query("bilal@example.com"),
                "((`tabSales Commission`.company in ('Orderlift'))) and (`tabSales Commission`.salesperson = 'Bilal')",
            )
        finally:
            company_access.user_can_access_all_companies = original_all_companies
            company_access.get_allowed_companies = original_allowed
            company_access._can_manage_sales_commissions = original_can_manage
            company_access._sales_person_for_user = original_salesperson
            company_access.has_interactive_company_session = original_interactive
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
        self.assertIn("public/js/stock_rate_guard_20260721c.js", hooks.doctype_js["Stock Entry"])
        self.assertIn("public/js/stock_rate_guard_20260721c.js", hooks.doctype_js["Purchase Receipt"])

    def test_stock_entry_rate_guard_hides_rate_fields(self):
        script = (APP_ROOT / "orderlift" / "public" / "js" / "stock_rate_guard_20260721c.js").read_text()

        self.assertIn('"basic_rate"', script)
        self.assertIn('"basic_amount"', script)
        self.assertIn('"valuation_rate"', script)
        self.assertIn('"set_basic_rate_manually"', script)
        self.assertIn('"allow_zero_valuation_rate"', script)
        self.assertIn('"rate"', script)
        self.assertIn("stock_rate_access", script)
        self.assertIn("grid.update_docfield_property", script)
        self.assertIn("get_stock_entry_rate_suggestion", script)
        self.assertIn('basic_rate: scheduleScopedStockRate', script)

    def test_data_import_shows_native_child_row_guidance(self):
        from orderlift import hooks

        self.assertEqual(
            hooks.doctype_js["Data Import"],
            "public/js/data_import_child_rows_help_20260723a.js",
        )
        script = (APP_ROOT / "orderlift" / "public" / "js" / "data_import_child_rows_help_20260723a.js").read_text()
        self.assertIn('frappe.ui.form.on("Data Import"', script)
        self.assertIn("frm.set_intro", script)
        self.assertIn("Any value in a parent field starts a new document", script)
        self.assertIn("orderlift.data_import_access.get_importable_doctypes", script)
        self.assertIn('frappe.ui.form.off("Data Import", "show_report_error_button")', script)
        self.assertIn('frappe.model.can_read("Error Log")', script)

    def test_sales_order_list_uses_short_status_and_fetches_owner(self):
        from orderlift import hooks

        self.assertEqual(hooks.doctype_list_js["Sales Order"], "public/js/sales_order_list_20260803a.js")
        script = (APP_ROOT / "orderlift" / "public" / "js" / "sales_order_list_20260803a.js").read_text()
        self.assertIn('"owner"', script)
        self.assertIn("shortStatus", script)
        self.assertIn("<span>${frappe.utils.escape_html", script)
        self.assertIn("custom_orderlift_order_status", script)


if __name__ == "__main__":
    unittest.main()
