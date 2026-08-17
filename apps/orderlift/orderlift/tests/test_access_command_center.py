import sys
import types
import unittest
from pathlib import Path


frappe_stub = types.ModuleType("frappe")
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.PermissionError = PermissionError
frappe_stub.session = types.SimpleNamespace(user="Administrator")
frappe_stub.conf = types.SimpleNamespace(orderlift_use_role_capabilities=0)
frappe_stub._ = lambda value: value
frappe_stub.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(ValueError(message))
frappe_stub.get_roles = lambda user=None: []
frappe_stub.log_error = lambda *args, **kwargs: None
sys.modules["frappe"] = frappe_stub

frappe_model_stub = types.ModuleType("frappe.model")
frappe_rename_doc_stub = types.ModuleType("frappe.model.rename_doc")
frappe_rename_doc_stub.rename_doc = lambda *args, **kwargs: None
sys.modules["frappe.model"] = frappe_model_stub
sys.modules["frappe.model.rename_doc"] = frappe_rename_doc_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(value or 0)
utils_stub.flt = lambda value=0, precision=None: round(float(value or 0), precision) if precision is not None else float(value or 0)
utils_stub.getdate = lambda value=None: value or "2026-04-27"
utils_stub.date_diff = lambda end, start: 0
utils_stub.nowdate = lambda: "2026-04-27"
utils_stub.now_datetime = lambda: "2026-04-27 00:00:00"
utils_stub.validate_email_address = lambda value, throw=False: value if "@" in (value or "") else None
sys.modules["frappe.utils"] = utils_stub

background_jobs_stub = types.ModuleType("frappe.utils.background_jobs")
background_jobs_stub.get_redis_conn = lambda: None
sys.modules["frappe.utils.background_jobs"] = background_jobs_stub


from orderlift.orderlift.page.access_command_center import access_command_center
from orderlift import role_capabilities
from orderlift.orderlift_sales import other_charge_permissions


APP_ROOT = Path(__file__).resolve().parents[2]


class Row(dict):
    def __getattr__(self, key):
        return self.get(key)


class TestAccessCommandCenterHelpers(unittest.TestCase):
    def setUp(self):
        self._session_user = frappe_stub.session.user
        self._get_roles = frappe_stub.get_roles
        self._role_capabilities_frappe = role_capabilities.frappe
        self._other_charge_frappe = other_charge_permissions.frappe
        self._other_charge_user_has_capability = other_charge_permissions.user_has_capability
        role_capabilities.frappe = frappe_stub
        other_charge_permissions.frappe = frappe_stub

    def tearDown(self):
        frappe_stub.session.user = self._session_user
        frappe_stub.get_roles = self._get_roles
        frappe_stub.conf.orderlift_use_role_capabilities = 0
        role_capabilities.frappe = self._role_capabilities_frappe
        other_charge_permissions.frappe = self._other_charge_frappe
        other_charge_permissions.user_has_capability = self._other_charge_user_has_capability

    def test_coerce_permission_flags_normalizes_supported_flags(self):
        flags = access_command_center._coerce_permission_flags(
            {"read": "1", "write": 1, "delete": 0, "export": None, "unknown": 1}
        )

        self.assertEqual(flags["read"], 1)
        self.assertEqual(flags["write"], 1)
        self.assertEqual(flags["delete"], 0)
        self.assertEqual(flags["export"], 0)
        self.assertNotIn("unknown", flags)

    def test_native_if_owner_is_hidden_from_permission_matrix(self):
        self.assertNotIn("if_owner", access_command_center.PERMISSION_FIELDS)
        self.assertIn("if_owner", access_command_center.HIDDEN_PERMISSION_FIELDS)

        flags = access_command_center._coerce_permission_flags({"read": 1, "if_owner": 1})

        self.assertEqual(flags["read"], 1)
        self.assertNotIn("if_owner", flags)

    def test_share_is_forced_off_for_managed_doctypes(self):
        flags = access_command_center._coerce_permission_flags({"read": 1, "share": 1}, "Opportunity")

        self.assertEqual(flags["read"], 1)
        self.assertEqual(flags["share"], 0)
        self.assertEqual(access_command_center._disabled_permission_fields("Opportunity"), ("share",))
        self.assertEqual(access_command_center._disabled_permission_fields("Partner Campaign Target"), ("share",))

    def test_share_stays_available_for_unmanaged_doctypes(self):
        flags = access_command_center._coerce_permission_flags({"read": 1, "share": 1}, "Event")

        self.assertEqual(flags["share"], 1)

    def test_orderlift_admin_cannot_edit_base_permissions(self):
        frappe_stub.session.user = "business-admin@example.com"
        frappe_stub.get_roles = lambda user=None: ["Orderlift Admin"]

        with self.assertRaisesRegex(ValueError, "Only superadmins can edit base permissions"):
            access_command_center._assert_permission_role_scope(access_command_center.BASE_PERMISSION_ROLE)
        self.assertEqual(access_command_center._disabled_permission_fields("Event"), ())

    def test_startup_roles_do_not_seed_owner_only_permissions(self):
        source = (APP_ROOT / "orderlift" / "scripts" / "setup_startup_roles.py").read_text()

        self.assertNotIn("OWNER_ONLY_READ_WRITE_CREATE", source)
        self.assertNotIn('"if_owner": 1', source)

    def test_legacy_broad_access_scripts_require_confirmation(self):
        for path in [
            APP_ROOT / "orderlift" / "admin_access.py",
            APP_ROOT / "orderlift" / "scripts" / "grant_full_business_access.py",
            APP_ROOT / "orderlift" / "scripts" / "fix_business_access.py",
        ]:
            source = path.read_text()
            self.assertIn("confirm_legacy_access_reset", source)
            self.assertIn("legacy broad-access", source.lower())

    def test_access_level_prioritizes_admin_roles(self):
        self.assertEqual(access_command_center._access_level(["Sales User", "System Manager"]), "Admin Level")
        self.assertEqual(access_command_center._access_level(["Orderlift Admin"]), "High Access")
        self.assertEqual(access_command_center._access_level(["Sales User"]), "Managed Access")
        self.assertEqual(access_command_center._access_level([]), "No Access")

    def test_clean_list_deduplicates_json_role_payload(self):
        roles = access_command_center._clean_list('["Sales User", "Sales User", "System Manager", ""]')

        self.assertEqual(roles, ["Sales User", "System Manager"])

    def test_role_capability_serialization_filters_unknown_values(self):
        value = role_capabilities.serialize_capabilities([
            role_capabilities.CAPABILITY_PRIVILEGED_PRICING,
            "unknown",
            role_capabilities.CAPABILITY_PURCHASING_ACCESS,
        ])

        self.assertEqual(
            value,
            "\n".join([
                role_capabilities.CAPABILITY_PRIVILEGED_PRICING,
                role_capabilities.CAPABILITY_PURCHASING_ACCESS,
            ]),
        )

    def test_role_capabilities_include_grouped_saved_other_charge_management(self):
        options = {option["value"]: option for option in role_capabilities.capability_options()}

        self.assertEqual(options[role_capabilities.CAPABILITY_TODO_ALL_ACCESS]["label"], "All ToDos Access")
        self.assertEqual(
            options[role_capabilities.CAPABILITY_SAVED_OTHER_CHARGE_MANAGEMENT]["label"],
            "Manage Saved Other Charges",
        )
        self.assertEqual(options[role_capabilities.CAPABILITY_SAVED_OTHER_CHARGE_MANAGEMENT]["group"], "sales_pricing")
        self.assertIn("Other Charge", options[role_capabilities.CAPABILITY_SAVED_OTHER_CHARGE_MANAGEMENT]["description"])
        self.assertIn(role_capabilities.CAPABILITY_TODO_ALL_ACCESS, role_capabilities.DEFAULT_ROLE_CAPABILITIES["Orderlift Admin"])
        self.assertIn(
            role_capabilities.CAPABILITY_DELETE_SUBMITTED_BLOCKERS,
            role_capabilities.DEFAULT_ROLE_CAPABILITIES["Orderlift Admin"],
        )
        self.assertIn(
            role_capabilities.CAPABILITY_SAVED_OTHER_CHARGE_MANAGEMENT,
            role_capabilities.DEFAULT_ROLE_CAPABILITIES["Orderlift Admin"],
        )
        self.assertEqual(
            role_capabilities.DEFAULT_CAPABILITY_UPGRADES,
            {"Orderlift Admin": [role_capabilities.CAPABILITY_PURCHASE_AGENT_RULES_MANAGEMENT]},
        )

    def test_default_role_capability_matrix_matches_business_roles(self):
        matrix = role_capabilities.DEFAULT_ROLE_CAPABILITIES

        self.assertEqual(
            set(matrix["Orderlift Admin"]),
            set(role_capabilities.ROLE_CAPABILITIES),
        )
        self.assertEqual(
            set(matrix["Purchase Manager"]),
            {role_capabilities.CAPABILITY_PURCHASING_ACCESS},
        )
        self.assertEqual(
            matrix["Purchase User"],
            [role_capabilities.CAPABILITY_PURCHASING_ACCESS],
        )
        self.assertEqual(
            matrix["Pricing Configuration"],
            [
                role_capabilities.CAPABILITY_PRIVILEGED_PRICING,
                role_capabilities.CAPABILITY_PURCHASING_ACCESS,
                role_capabilities.CAPABILITY_SAVED_OTHER_CHARGE_MANAGEMENT,
            ],
        )
        self.assertEqual(matrix["Sales User"], [])

    def test_managed_role_boundary_is_not_native_role_access(self):
        source = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.py").read_text()

        self.assertIn('role.insert(ignore_permissions=True)', source)
        self.assertIn('role.save(ignore_permissions=True)', source)
        self.assertIn('role.delete(ignore_permissions=True)', source)
        self.assertIn("ORDERLIFT_MANAGED_ROLE_FIELD", source)
        self.assertIn("_apply_managed_role_baseline", source)
        self.assertNotIn('role.insert(ignore_permissions=False)', source)
        self.assertNotIn('role.save(ignore_permissions=False)', source)
        self.assertNotIn('role.delete(ignore_permissions=False)', source)

    def test_managed_role_delete_cleans_compiled_access_after_blocker_check(self):
        source = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.py").read_text()
        delete_body = source.split("def delete_role(", 1)[1].split("def bulk_update_user_roles(", 1)[0]

        self.assertIn("_role_blocking_dependency_summary(role_name)", delete_body)
        self.assertIn("_remove_managed_role_access(role_name)", delete_body)
        self.assertLess(
            delete_body.index("_role_blocking_dependency_summary(role_name)"),
            delete_body.index("_remove_managed_role_access(role_name)"),
        )
        self.assertLess(delete_body.index("_remove_managed_role_access(role_name)"), delete_body.index("role.delete"))

    def test_pipeline_business_rows_do_not_bind_assignment_capabilities(self):
        source = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.py").read_text()
        js = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.js").read_text()

        for key in (
            '"crm.opportunity_pipeline"',
            '"sales.project_pipeline"',
            '"sales.sales_order_pipeline"',
        ):
            self.assertIn(key, source)
        self.assertNotIn("BUSINESS_FEATURE_CAPABILITIES", source)
        self.assertNotIn("sync_business_feature_capabilities_from_page_roles", source)
        self.assertIn("_compile_target_feature_access(role, feature_grants)", source)
        self.assertNotIn('["menu", "Menu Access"]', js)

    def test_opportunity_pipeline_grants_runtime_backing_doctypes(self):
        backing = access_command_center.BUSINESS_FEATURE_BACKING_DOCTYPES["crm.opportunity_pipeline"]

        for doctype in ("Opportunity", "Sales Stage", "Quotation", "Sales Order", "Project", "ToDo"):
            self.assertIn(doctype, backing)

    def test_pipeline_pages_grant_status_and_assignment_backing_doctypes(self):
        expected = {
            "sales.sales_order_pipeline": ("Sales Order", "Orderlift Order Status", "ToDo"),
            "sales.project_pipeline": ("Project", "Project Status", "ToDo"),
            "projects.sales_order_pipeline": ("Sales Order", "Orderlift Order Status", "ToDo"),
            "projects.project_pipeline": ("Project", "Project Status", "ToDo"),
            "logistics.pipeline": ("Forecast Load Plan", "Logistics Pipeline Status", "ToDo"),
        }

        for key, doctypes in expected.items():
            backing = access_command_center.BUSINESS_FEATURE_BACKING_DOCTYPES[key]
            for doctype in doctypes:
                self.assertIn(doctype, backing)

    def test_technical_list_manager_exposes_operational_permissions(self):
        item = {
            "key": "projects.technical_list_manager",
            "link_type": "Page",
            "link_to": "technical-list-manager",
        }

        self.assertEqual(
            access_command_center._business_feature_actions(item),
            ("open", "view", "create_edit", "approve_cancel", "delete", "export"),
        )
        backing = access_command_center.BUSINESS_FEATURE_BACKING_DOCTYPES[item["key"]]
        for doctype in (
            "Sales Order",
            "Sales Order Technical List",
            "Sales Order Technical List Revision",
            "Orderlift Annex Document",
        ):
            self.assertIn(doctype, backing)

    def test_technical_list_approval_only_manages_revision_submit_permissions(self):
        item = {
            "key": "projects.technical_list_manager",
            "link_type": "Page",
            "link_to": "technical-list-manager",
        }

        self.assertEqual(
            access_command_center.BUSINESS_FEATURE_ACTION_BACKING_DOCTYPES[item["key"]]["approve_cancel"],
            ("Sales Order Technical List Revision",),
        )
        self.assertNotIn(
            "Sales Order",
            access_command_center.BUSINESS_FEATURE_ACTION_BACKING_DOCTYPES[item["key"]]["create_edit"],
        )

    def test_workflow_documents_grant_hidden_workflow_state_backing_doctype(self):
        for key in ("sales.quotation", "sales.sales_order", "purchasing.purchase_order"):
            self.assertIn("Workflow State", access_command_center.BUSINESS_FEATURE_BACKING_DOCTYPES[key])

    def test_sales_order_grants_reference_backing_doctypes(self):
        backing = access_command_center.BUSINESS_FEATURE_BACKING_DOCTYPES["sales.sales_order"]

        for doctype in ("CRM Business Type", "CRM Segment", "Orderlift Order Status", "Quotation", "Opportunity"):
            self.assertIn(doctype, backing)

    def test_stock_dashboard_grants_read_only_backing_doctypes(self):
        backing = access_command_center.BUSINESS_FEATURE_BACKING_DOCTYPES["stock.dashboard"]

        for doctype in ("Bin", "Item", "Warehouse", "Stock Ledger Entry", "Stock Entry"):
            self.assertIn(doctype, backing)

    def test_business_permission_dependencies_are_not_rendered(self):
        js = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.js").read_text()

        self.assertNotIn("feature.includes", js)
        self.assertIn("intentionally hidden from permission UIs", js)

    def test_other_charge_management_requires_capability_for_write(self):
        other_charge_permissions.user_has_capability = lambda capability, user=None: False
        frappe_stub.session.user = "sales@example.com"
        frappe_stub.has_permission = lambda doctype, ptype=None, user=None: doctype == "Quotation" and ptype in {"read", "create", "write"}

        self.assertTrue(other_charge_permissions.has_other_charge_permission(ptype="read", user="sales@example.com"))
        self.assertTrue(other_charge_permissions.has_other_charge_permission(ptype="select", user="sales@example.com"))
        self.assertFalse(other_charge_permissions.has_other_charge_permission(ptype="write", user="sales@example.com"))
        self.assertFalse(other_charge_permissions.has_other_charge_permission(ptype="create", user="sales@example.com"))

        source = (APP_ROOT / "orderlift" / "scripts" / "setup_startup_roles.py").read_text()
        sales_user_permissions = source.split("SALES_USER_PERMISSIONS = {", 1)[1].split("SALES_MANAGER_PERMISSIONS", 1)[0]
        self.assertIn('"Orderlift Other Charge": READ_SELECT', sales_user_permissions)
        self.assertIn('"Workflow State": READ_SELECT', source)

        other_charge_permissions.user_has_capability = (
            lambda capability, user=None: capability == role_capabilities.CAPABILITY_SAVED_OTHER_CHARGE_MANAGEMENT
        )
        self.assertTrue(other_charge_permissions.has_other_charge_permission(ptype="write", user="manager@example.com"))

    def test_role_capability_decision_ignores_legacy_result(self):
        original_user_has_capability = role_capabilities.user_has_capability
        role_capabilities.user_has_capability = lambda *args, **kwargs: True
        try:
            self.assertTrue(
                role_capabilities.role_capability_decision(
                    role_capabilities.CAPABILITY_PRIVILEGED_PRICING,
                    False,
                    user="demo@example.com",
                    roles={"Sales User"},
                    context="test",
                )
            )
        finally:
            role_capabilities.user_has_capability = original_user_has_capability

    def test_role_capability_decision_is_always_authoritative(self):
        original_user_has_capability = role_capabilities.user_has_capability
        role_capabilities.user_has_capability = lambda *args, **kwargs: True
        try:
            self.assertTrue(
                role_capabilities.role_capability_decision(
                    role_capabilities.CAPABILITY_PRIVILEGED_PRICING,
                    False,
                    user="demo@example.com",
                    roles={"Sales User"},
                    context="test",
                )
            )
        finally:
            role_capabilities.user_has_capability = original_user_has_capability

    def test_capability_decision_does_not_log_legacy_mismatch(self):
        original_user_has_capability = role_capabilities.user_has_capability
        original_log_error = frappe_stub.log_error
        logs = []
        role_capabilities.user_has_capability = lambda *args, **kwargs: True
        frappe_stub.log_error = lambda *args, **kwargs: logs.append((args, kwargs))
        try:
            self.assertTrue(
                role_capabilities.role_capability_decision(
                    role_capabilities.CAPABILITY_PURCHASING_ACCESS,
                    False,
                    user="matrix@example.com",
                    roles={"Orderlift Admin"},
                    context="capability_matrix_test",
                )
            )
            self.assertEqual(logs, [])
        finally:
            role_capabilities.user_has_capability = original_user_has_capability
            frappe_stub.log_error = original_log_error

    def test_enabled_capability_mode_enforces_role_matrix_without_user_hardcoding(self):
        original_get_role_capabilities = role_capabilities.get_role_capabilities
        frappe_stub.conf.orderlift_use_role_capabilities = 1
        role_capabilities.get_role_capabilities = lambda role: role_capabilities.DEFAULT_ROLE_CAPABILITIES.get(role, [])
        cases = [
            ({"Orderlift Admin"}, role_capabilities.CAPABILITY_PURCHASING_ACCESS, True),
            ({"Purchase Manager"}, role_capabilities.CAPABILITY_PURCHASING_ACCESS, True),
            ({"Purchase User"}, role_capabilities.CAPABILITY_PURCHASING_ACCESS, True),
            ({"Stock Manager"}, role_capabilities.CAPABILITY_PURCHASING_ACCESS, False),
            ({"Sales User"}, role_capabilities.CAPABILITY_PURCHASING_ACCESS, False),
            ({"Pricing Configuration"}, role_capabilities.CAPABILITY_PRIVILEGED_PRICING, True),
            ({"Sales Manager"}, role_capabilities.CAPABILITY_QUOTATION_OVERRIDE, True),
        ]
        try:
            for roles, capability, expected in cases:
                with self.subTest(roles=roles, capability=capability):
                    self.assertEqual(
                        role_capabilities.role_capability_decision(
                            capability,
                            legacy_allowed=not expected,
                            user="role-matrix@example.com",
                            roles=roles,
                            context="role_matrix_test",
                        ),
                        expected,
                    )
        finally:
            role_capabilities.get_role_capabilities = original_get_role_capabilities

    def test_role_payload_includes_capabilities(self):
        payload = access_command_center._role_payload(
            "Pricing Configuration",
            Row({
                "name": "Pricing Configuration",
                "role_name": "Pricing Configuration",
                "desk_access": 1,
                "disabled": 0,
                "is_custom": 1,
                role_capabilities.ROLE_CAPABILITY_FIELD: "privileged_pricing\nunknown",
            }),
            {"Pricing Configuration": 2},
        )

        self.assertEqual(payload["capabilities"], [role_capabilities.CAPABILITY_PRIVILEGED_PRICING])

    def test_permission_levels_include_zero_and_custom_levels(self):
        levels = access_command_center._permission_levels_for_matrix({1: {"read": 1}}, {2: {"write": 1}})

        self.assertEqual(levels, [0, 1, 2])

    def test_permission_levels_include_base_permission_levels(self):
        levels = access_command_center._permission_levels_for_matrix(
            {1: {"read": 1}},
            {},
            {3: {"write": 1}},
            {2: {"create": 1}},
        )

        self.assertEqual(levels, [0, 1, 2, 3])

    def test_role_permission_inherits_base_permissions(self):
        row = access_command_center._resolve_permission_matrix_row(
            "ToDo",
            "Sales User",
            standard={},
            custom={},
            base_standard={},
            base_custom={"read": 1, "write": 1, "create": 1},
        )

        self.assertEqual(row["source"], "base")
        self.assertEqual(row["source_role"], access_command_center.BASE_PERMISSION_ROLE)
        self.assertEqual(row["effective"]["read"], 1)
        self.assertEqual(row["effective"]["write"], 1)
        self.assertEqual(row["effective"]["create"], 1)
        self.assertFalse(row["can_reset"])

    def test_neutralized_base_permission_does_not_show_as_inherited_access(self):
        row = access_command_center._resolve_permission_matrix_row(
            "ToDo",
            "Sales User",
            standard={},
            custom={},
            base_standard={},
            base_custom={field: 0 for field in access_command_center.PERMISSION_FIELDS},
        )

        self.assertEqual(row["source"], "none")
        self.assertFalse(row["has_base_permission"])
        self.assertFalse(any(row["effective"].values()))

    def test_role_permission_merges_base_and_direct_permissions(self):
        row = access_command_center._resolve_permission_matrix_row(
            "ToDo",
            "Sales User",
            standard={"export": 1},
            custom={},
            base_standard={},
            base_custom={"read": 1, "write": 1},
        )

        self.assertEqual(row["source"], "mixed")
        self.assertEqual(row["direct"]["export"], 1)
        self.assertEqual(row["base"]["read"], 1)
        self.assertEqual(row["effective"]["read"], 1)
        self.assertEqual(row["effective"]["write"], 1)
        self.assertEqual(row["effective"]["export"], 1)

    def test_custom_direct_permission_is_resettable(self):
        row = access_command_center._resolve_permission_matrix_row(
            "Opportunity",
            "Sales User",
            standard={"read": 1},
            custom={"read": 1, "write": 1},
            base_standard={},
            base_custom={},
        )

        self.assertEqual(row["source"], "direct")
        self.assertTrue(row["has_custom_override"])
        self.assertTrue(row["can_reset"])

    def test_permission_matrix_sort_key_prioritizes_active_permissions(self):
        inactive = {
            "doctype": "Inactive Doc",
            "module": "Z Module",
            "permlevel": 0,
            "source": "none",
            "risk": "low",
            "effective": {field: 0 for field in access_command_center.PERMISSION_FIELDS},
        }
        active = {
            "doctype": "Active Doc",
            "module": "Z Module",
            "permlevel": 0,
            "source": "standard",
            "risk": "low",
            "effective": {field: 0 for field in access_command_center.PERMISSION_FIELDS} | {"read": 1},
        }

        rows = [inactive, active]
        rows.sort(key=access_command_center._permission_matrix_sort_key)

        self.assertEqual([row["doctype"] for row in rows], ["Active Doc", "Inactive Doc"])

    def test_permission_matrix_includes_permission_doctypes_outside_initial_limit(self):
        doctypes = [{"name": "Accounting Ledger"}, {"name": "Address"}]
        permission_names = {"Opportunity", "Address", "Quotation"}

        missing = access_command_center._missing_permission_doctype_names(doctypes, permission_names)

        self.assertEqual(missing, ["Opportunity", "Quotation"])

    def test_critical_user_detection_protects_administrator(self):
        self.assertTrue(access_command_center._is_critical_user("Administrator"))
        self.assertTrue(access_command_center._is_critical_user("Guest"))
        self.assertFalse(access_command_center._is_critical_user("demo@example.com"))

    def test_role_name_validation_requires_name(self):
        with self.assertRaises(ValueError):
            access_command_center._validate_role_name("   ")

    def test_business_admin_visible_roles_exclude_superadmin_roles(self):
        frappe_stub.session.user = "orderlift.admin@example.com"
        frappe_stub.get_roles = lambda user=None: ["Orderlift Admin"]

        roles = access_command_center._visible_role_names()

        self.assertIn("Sales User", roles)
        self.assertNotIn("System Manager", roles)
        self.assertNotIn("Developer", roles)

    def test_business_admin_visible_roles_include_custom_business_roles(self):
        frappe_stub.session.user = "orderlift.admin@example.com"
        frappe_stub.get_roles = lambda user=None: ["Orderlift Admin"]
        original_custom_roles = access_command_center._custom_business_role_names
        access_command_center._custom_business_role_names = lambda: ["testt"]
        try:
            roles = access_command_center._visible_role_names()
        finally:
            access_command_center._custom_business_role_names = original_custom_roles

        self.assertIn("Sales User", roles)
        self.assertIn("testt", roles)
        self.assertNotIn("System Manager", roles)

    def test_superadmin_visible_roles_include_superadmin_roles(self):
        frappe_stub.session.user = "manager@example.com"
        frappe_stub.get_roles = lambda user=None: ["System Manager"]

        roles = access_command_center._visible_role_names()

        self.assertIn("System Manager", roles)
        self.assertNotIn("Developer", roles)

    def test_business_admin_role_scope_rejects_superadmin_roles(self):
        frappe_stub.session.user = "orderlift.admin@example.com"
        frappe_stub.get_roles = lambda user=None: ["Orderlift Admin"]

        with self.assertRaises(ValueError):
            access_command_center._assert_role_scope(["Sales User", "System Manager"])

    def test_business_admin_role_scope_allows_custom_business_roles(self):
        frappe_stub.session.user = "orderlift.admin@example.com"
        frappe_stub.get_roles = lambda user=None: ["Orderlift Admin"]
        original_custom_roles = access_command_center._custom_business_role_names
        access_command_center._custom_business_role_names = lambda: ["testt"]
        try:
            access_command_center._assert_role_scope(["Sales User", "testt"])
        finally:
            access_command_center._custom_business_role_names = original_custom_roles

    def test_business_admin_cannot_see_backend_finance_permission_doctypes(self):
        frappe_stub.session.user = "orderlift.admin@example.com"
        frappe_stub.get_roles = lambda user=None: ["Orderlift Admin"]

        self.assertFalse(access_command_center._permission_doctype_visible("Account", "Orderlift Admin"))
        self.assertFalse(access_command_center._permission_doctype_visible("Cost Center", "Finance User"))
        self.assertTrue(access_command_center._permission_doctype_visible("Sales Invoice", "Finance User"))

    def test_stock_settings_is_visible_single_doctype_in_permission_matrix(self):
        self.assertIn("Stock Settings", access_command_center.MATRIX_SINGLE_DOCTYPES)
        group = access_command_center._permission_matrix_group("Stock Settings", "Stock", 0, {})

        self.assertEqual(group["group_key"], "stock_warehouse")
        self.assertTrue(access_command_center._permission_doctype_visible("Stock Settings", "Stock Manager"))

    def test_error_log_is_hidden_from_orderlift_admin_matrix(self):
        group = access_command_center._permission_matrix_group("Error Log", "Core", 0, {})

        self.assertEqual(group["group_key"], "access_admin")
        self.assertFalse(access_command_center._permission_doctype_visible("Error Log", "Orderlift Admin"))

    def test_user_is_matrix_managed_for_all_permission_roles(self):
        self.assertEqual(access_command_center.MATRIX_MANAGED_DOCTYPES, {"User"})
        group = access_command_center._permission_matrix_group("User", "Core", 0, {})

        self.assertEqual(group["group_key"], "access_admin")
        self.assertEqual(group["group_label"], "Access & Administration")
        for role in ("Orderlift Admin", "Sales User", access_command_center.BASE_PERMISSION_ROLE):
            with self.subTest(role=role):
                self.assertTrue(access_command_center._permission_doctype_visible("User", role))

    def test_orderlift_admin_permission_matrix_includes_user(self):
        original_get_all = getattr(frappe_stub, "get_all", None)

        def get_all(doctype, **kwargs):
            if doctype == "DocType":
                return [Row({"name": "User", "module": "Core", "custom": 0, "istable": 0, "issingle": 0})]
            return []

        frappe_stub.get_all = get_all
        try:
            matrix = access_command_center._get_permission_matrix("Orderlift Admin")
        finally:
            if original_get_all is None:
                delattr(frappe_stub, "get_all")
            else:
                frappe_stub.get_all = original_get_all

        user_rows = [row for row in matrix["rows"] if row["doctype"] == "User"]
        self.assertEqual(len(user_rows), 1)
        self.assertEqual(user_rows[0]["group_key"], "access_admin")
        self.assertTrue(user_rows[0]["is_protected"])

    def test_save_custom_docperms_writes_user_override(self):
        class FakeDoc(types.SimpleNamespace):
            def insert(self, ignore_permissions=False):
                self.name = "USER-ORDERLIFT-ADMIN"

            def save(self, ignore_permissions=False):
                return None

        class FakeDB:
            committed = False

            @staticmethod
            def exists(doctype, value=None):
                if doctype in {"Role", "DocType"}:
                    return True
                return False

            def commit(self):
                self.committed = True

        originals = {
            "db": getattr(frappe_stub, "db", None),
            "get_all": getattr(frappe_stub, "get_all", None),
            "get_doc": getattr(frappe_stub, "get_doc", None),
            "clear_cache": getattr(frappe_stub, "clear_cache", None),
            "get_permission_matrix": access_command_center._get_permission_matrix,
            "add_audit_note": access_command_center._add_audit_note,
        }
        created = []
        fake_db = FakeDB()
        frappe_stub.session.user = "orderlift.admin@example.com"
        frappe_stub.get_roles = lambda user=None: ["Orderlift Admin"]
        frappe_stub.db = fake_db
        frappe_stub.get_all = lambda *args, **kwargs: []

        def get_doc(value, name=None):
            doc = FakeDoc(**value) if isinstance(value, dict) else FakeDoc(doctype=value, name=name)
            created.append(doc)
            return doc

        frappe_stub.get_doc = get_doc
        frappe_stub.clear_cache = lambda **kwargs: None
        access_command_center._get_permission_matrix = lambda role: {"role": role, "rows": []}
        access_command_center._add_audit_note = lambda *args, **kwargs: None
        try:
            result = access_command_center.save_custom_docperms(
                "Orderlift Admin",
                [{"doctype": "User", "read": 1, "write": 1}],
            )
        finally:
            for key in ("db", "get_all", "get_doc", "clear_cache"):
                if originals[key] is None:
                    delattr(frappe_stub, key)
                else:
                    setattr(frappe_stub, key, originals[key])
            access_command_center._get_permission_matrix = originals["get_permission_matrix"]
            access_command_center._add_audit_note = originals["add_audit_note"]

        self.assertEqual(result["saved"], ["USER-ORDERLIFT-ADMIN"])
        self.assertTrue(fake_db.committed)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].parent, "User")
        self.assertEqual(created[0].role, "Orderlift Admin")
        self.assertEqual((created[0].read, created[0].write), (1, 1))
        self.assertEqual(created[0].create, 0)

    def test_item_implementation_doctypes_are_hidden_from_permission_matrix(self):
        hidden = {
            "Item",
            "Item Variant Attribute",
            "Item Tax",
            "Item Customer Detail",
            "Item Reorder",
            "Item Barcode",
            "Item Supplier",
            "UOM Conversion Detail",
            "Item Default",
            "Orderlift Item Warehouse Stock",
            "Orderlift Item Selling Price",
            "Orderlift Item Buying Price",
            "Item Specification Value",
            "Item Packaging Profile",
            "Data Import",
            "Data Import Log",
        }

        self.assertEqual(access_command_center.HIDDEN_PERMISSION_DOCTYPES, hidden)
        for doctype_name in hidden:
            with self.subTest(doctype_name=doctype_name):
                self.assertFalse(access_command_center._permission_doctype_visible(doctype_name, "Sales User"))

    def test_business_permissions_use_an_explicit_main_dashboard_toggle(self):
        source = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.js").read_text()

        self.assertIn('data-business-menu="${escapeHtml(feature.key)}"', source)
        self.assertIn("function updateBusinessMenuDraft(featureKey, enabled)", source)
        self.assertIn('"menu_visible" in data', (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.py").read_text())

    def test_access_command_center_is_a_high_access_business_permission_bundle(self):
        item = {
            "key": "administration.access_command_center",
            "link_type": "Page",
            "link_to": "access-command-center",
        }

        self.assertNotIn(item["key"], access_command_center.BUSINESS_PERMISSION_EXCLUDED_KEYS)
        self.assertEqual(
            access_command_center._business_feature_actions(item),
            ("open", "create_edit", "delete", "export"),
        )
        self.assertEqual(access_command_center.BUSINESS_FEATURE_BACKING_DOCTYPES[item["key"]], ("User",))
        self.assertTrue(access_command_center._business_feature_available_for_role(item, "Orderlift Admin"))
        self.assertTrue(access_command_center._business_feature_available_for_role(item, "System Manager"))
        self.assertFalse(access_command_center._business_feature_available_for_role(item, "Sales User"))

    def test_access_command_center_business_row_is_rendered_only_for_high_access_roles(self):
        item = {
            "key": "administration.access_command_center",
            "label": "Access Command Center",
            "section_key": "administration",
            "section": "Administration",
            "link_type": "Page",
            "link_to": "access-command-center",
        }
        originals = {
            "iter_menu_items": access_command_center.iter_menu_items,
            "get_menu_access": access_command_center._get_menu_access,
            "action_state": access_command_center._business_feature_action_state,
            "includes": access_command_center._business_feature_includes,
        }
        access_command_center.iter_menu_items = lambda: [item]
        access_command_center._get_menu_access = lambda: []
        access_command_center._business_feature_action_state = lambda feature, role, actions: [
            {"key": action, "enabled": 0} for action in actions
        ]
        access_command_center._business_feature_includes = lambda feature: []
        try:
            admin_matrix = access_command_center._get_business_permission_matrix("Orderlift Admin")
            sales_matrix = access_command_center._get_business_permission_matrix("Sales User")
        finally:
            access_command_center.iter_menu_items = originals["iter_menu_items"]
            access_command_center._get_menu_access = originals["get_menu_access"]
            access_command_center._business_feature_action_state = originals["action_state"]
            access_command_center._business_feature_includes = originals["includes"]

        self.assertEqual(admin_matrix["groups"][0]["features"][0]["key"], item["key"])
        self.assertEqual(sales_matrix["groups"], [])

    def test_access_command_center_business_actions_reflect_user_permissions(self):
        item = {
            "key": "administration.access_command_center",
            "link_type": "Page",
            "link_to": "access-command-center",
        }
        originals = {
            "native": access_command_center._native_target_role_state,
            "backing": access_command_center._business_backing_doctypes,
            "resolved": access_command_center._business_doctype_resolved,
        }
        access_command_center._native_target_role_state = lambda *args: {
            "effective": 1,
            "inherited": 0,
        }
        access_command_center._business_backing_doctypes = lambda feature: ("User",)
        access_command_center._business_doctype_resolved = lambda doctype, role: {
            "direct": {"read": 1, "write": 1, "create": 1, "delete": 1, "export": 1},
            "base": {},
            "effective": {"read": 1, "write": 1, "create": 1, "delete": 1, "export": 1},
        }
        try:
            states = access_command_center._business_feature_action_state(
                item,
                "Orderlift Admin",
                ("open", "create_edit", "delete", "export"),
            )
        finally:
            access_command_center._native_target_role_state = originals["native"]
            access_command_center._business_backing_doctypes = originals["backing"]
            access_command_center._business_doctype_resolved = originals["resolved"]

        self.assertEqual([state["key"] for state in states], ["open", "create_edit", "delete", "export"])
        self.assertTrue(all(state["enabled"] for state in states))

    def test_page_backed_select_does_not_require_page_access(self):
        item = {
            "key": "items.dimensioning_sets",
            "link_type": "Page",
            "link_to": "dimensioning-set-manager",
        }
        originals = {
            "native": access_command_center._native_target_role_state,
            "backing": access_command_center._business_backing_doctypes,
            "resolved": access_command_center._business_doctype_resolved,
        }
        access_command_center._native_target_role_state = lambda *args: {
            "effective": 0,
            "inherited": 0,
        }
        access_command_center._business_backing_doctypes = lambda feature: ("Dimensioning Set",)
        access_command_center._business_doctype_resolved = lambda doctype, role: {
            "direct": {"select": 1, "read": 0},
            "base": {},
            "effective": {"select": 1, "read": 0},
        }
        try:
            states = access_command_center._business_feature_action_state(
                item,
                "Sales User",
                ("select", "open"),
            )
        finally:
            access_command_center._native_target_role_state = originals["native"]
            access_command_center._business_backing_doctypes = originals["backing"]
            access_command_center._business_doctype_resolved = originals["resolved"]

        self.assertEqual(
            {state["key"]: state["enabled"] for state in states},
            {"select": 1, "open": 0},
        )

    def test_access_command_center_business_bundle_compiles_user_permissions(self):
        item = {
            "key": "administration.access_command_center",
            "link_type": "Page",
            "link_to": "access-command-center",
        }
        originals = {
            "iter_menu_items": access_command_center.iter_menu_items,
            "backing": access_command_center._business_backing_doctypes,
            "save_docperm": access_command_center._save_managed_docperm_fields,
            "set_target": access_command_center._set_native_target_role,
            "set_menu": access_command_center.set_menu_key_access_for_role,
        }
        saved = []
        page_access = []
        menu_access = []
        access_command_center.iter_menu_items = lambda: [item]
        access_command_center._business_backing_doctypes = lambda feature: ("User",)
        access_command_center._save_managed_docperm_fields = (
            lambda role, doctype, fields, desired: saved.append((role, doctype, set(fields), dict(desired)))
        )
        access_command_center._set_native_target_role = (
            lambda target_type, target, role, enabled: page_access.append((target_type, target, role, enabled))
        )
        access_command_center.set_menu_key_access_for_role = (
            lambda role, key, enabled: menu_access.append((role, key, enabled))
        )
        try:
            access_command_center._compile_target_feature_access(
                "Orderlift Admin",
                {
                    item["key"]: {
                        "actions": {"open": 1, "create_edit": 1, "delete": 1, "export": 1},
                        "menu_visible": 1,
                    }
                },
            )
        finally:
            access_command_center.iter_menu_items = originals["iter_menu_items"]
            access_command_center._business_backing_doctypes = originals["backing"]
            access_command_center._save_managed_docperm_fields = originals["save_docperm"]
            access_command_center._set_native_target_role = originals["set_target"]
            access_command_center.set_menu_key_access_for_role = originals["set_menu"]

        user_save = next(row for row in saved if row[1] == "User")
        self.assertEqual(
            user_save[2],
            {"read", "select", "write", "create", "delete", "report", "print", "export"},
        )
        self.assertTrue(all(user_save[3].get(field) for field in user_save[2]))
        self.assertIn(("Page", "access-command-center", "Orderlift Admin", True), page_access)
        self.assertEqual(menu_access, [("Orderlift Admin", item["key"], True)])

    def test_import_compiles_hidden_data_import_tool_dependencies(self):
        original_scope = access_command_center._business_scope_role_set
        original_target = access_command_center._role_has_business_import_target
        original_save = access_command_center._save_managed_docperm_fields
        original_db = getattr(frappe_stub, "db", None)
        saved = []
        frappe_stub.db = types.SimpleNamespace(exists=lambda *args, **kwargs: True)
        access_command_center._business_scope_role_set = lambda: {"Purchase User"}
        access_command_center._save_managed_docperm_fields = (
            lambda role, doctype, fields, desired: saved.append((role, doctype, fields, desired))
        )
        try:
            access_command_center._role_has_business_import_target = lambda role: True
            access_command_center._sync_business_import_support_permissions("Purchase User")
            self.assertEqual(
                sorted((row[1], tuple(sorted(row[2])), row[3]) for row in saved),
                [
                    ("Data Import", ("create", "read", "write"), {"create": 1, "read": 1, "write": 1}),
                    ("Data Import Log", ("read",), {"read": 1}),
                ],
            )

            saved.clear()
            access_command_center._role_has_business_import_target = lambda role: False
            access_command_center._sync_business_import_support_permissions("Purchase User")
            self.assertEqual(
                sorted((row[1], row[3]) for row in saved),
                [
                    ("Data Import", {"create": 0, "read": 0, "write": 0}),
                    ("Data Import Log", {"read": 0}),
                ],
            )
        finally:
            access_command_center._business_scope_role_set = original_scope
            access_command_center._role_has_business_import_target = original_target
            access_command_center._save_managed_docperm_fields = original_save
            if original_db is None:
                delattr(frappe_stub, "db")
            else:
                frappe_stub.db = original_db

    def test_import_support_sync_is_wired_to_save_and_migrate(self):
        access_source = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.py").read_text()
        pricing_source = (APP_ROOT / "orderlift" / "sales" / "utils" / "pricing_setup.py").read_text()
        sync_source = (APP_ROOT / "orderlift" / "scripts" / "sync_page_roles_from_menu_registry.py").read_text()

        self.assertIn("_sync_business_import_support_permissions(role)", access_source)
        self.assertIn("sync_business_import_support_permissions()", pricing_source)
        self.assertIn("sync_business_import_support_permissions()", sync_source)

    def test_all_role_is_preserved_in_scoped_menu_payloads(self):
        original_user = frappe_stub.session.user
        original_get_roles = frappe_stub.get_roles
        frappe_stub.session.user = "orderlift.admin@example.com"
        frappe_stub.get_roles = lambda user=None: ["Orderlift Admin"]
        try:
            self.assertEqual(
                access_command_center._filter_roles_for_session(["All", "Sales User", "System Manager"]),
                ["All", "Sales User"],
            )
        finally:
            frappe_stub.session.user = original_user
            frappe_stub.get_roles = original_get_roles

    def test_access_command_center_ui_exposes_role_capabilities(self):
        source = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.js").read_text()

        self.assertIn("role_capabilities", source)
        self.assertIn("Orderlift Capabilities", source)
        self.assertIn("grouped by business responsibility", source)
        self.assertIn("recommended capability for purchase and stock-rate reviewers", source)
        self.assertIn("either Privileged Pricing or Purchasing Access", source)
        self.assertIn("All ToDos Access", source)
        self.assertIn("Manage Saved Other Charges", source)
        self.assertIn("selectedDialogCapabilities", source)
        self.assertIn("groupedCapabilityOptions", source)

    def test_access_command_center_matrix_keeps_direct_and_effective_toggle_state_separate(self):
        source = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.js").read_text()

        self.assertIn("function rowDirectPermissionValues", source)
        self.assertIn("const direct = STATE.matrixDraft[rowKey] || row.direct || {};", source)
        self.assertIn("((row.base || {})[field]) || direct[field]", source)
        self.assertIn("STATE.matrixDraft[rowKey] || row.direct || {}", source)

    def test_business_permission_action_state_uses_native_effective_flags(self):
        resolved = {
            "direct": {"select": 1, "read": 1, "write": 1, "create": 1},
            "base": {},
            "effective": {"select": 1, "read": 1, "write": 1, "create": 1},
        }

        select = access_command_center._business_doc_action_payload("select", resolved)
        view = access_command_center._business_doc_action_payload("view", resolved)
        create_edit = access_command_center._business_doc_action_payload("create_edit", resolved)
        approve = access_command_center._business_doc_action_payload("approve_cancel", resolved)

        self.assertTrue(select["enabled"])
        self.assertTrue(view["enabled"])
        self.assertTrue(create_edit["enabled"])
        self.assertFalse(create_edit["mixed"])
        self.assertFalse(approve["enabled"])

    def test_business_permission_select_action_reads_only_native_select(self):
        resolved = {
            "direct": {"select": 1, "read": 0},
            "base": {},
            "effective": {"select": 1, "read": 0},
        }

        select = access_command_center._business_doc_action_payload("select", resolved)
        view = access_command_center._business_doc_action_payload("view", resolved)

        self.assertTrue(select["enabled"])
        self.assertFalse(view["enabled"])
        self.assertEqual(access_command_center.BUSINESS_ACTION_LABELS["select"], "Use in Fields")
        self.assertEqual(access_command_center.BUSINESS_ACTION_PERMISSION_FIELDS["select"], ("select",))
        self.assertNotIn("select", access_command_center.BUSINESS_ACTION_PERMISSION_FIELDS["view"])
        self.assertNotIn("select", access_command_center.BUSINESS_ACTION_PERMISSION_FIELDS["create_edit"])

    def test_business_permission_action_state_locks_inherited_base_access(self):
        resolved = {
            "direct": {"read": 0},
            "base": {"read": 1},
            "effective": {"read": 1},
        }

        view = access_command_center._business_doc_action_payload("view", resolved)

        self.assertTrue(view["enabled"])
        self.assertTrue(view["inherited"])
        self.assertTrue(view["locked"])

    def test_stock_ledger_business_bundle_is_view_export_only(self):
        original_exists = getattr(frappe_stub, "db", None)
        frappe_stub.db = types.SimpleNamespace(exists=lambda *args, **kwargs: True)
        try:
            actions = access_command_center._business_feature_actions({
                "key": "stock.ledger",
                "link_type": "Report",
                "link_to": "Stock Ledger",
            })
        finally:
            if original_exists is None:
                delattr(frappe_stub, "db")
            else:
                frappe_stub.db = original_exists

        self.assertEqual(actions, ("view", "export"))

    def test_business_select_is_offered_only_for_doctypes_and_comes_first(self):
        original_db = getattr(frappe_stub, "db", None)
        original_get_meta = getattr(frappe_stub, "get_meta", None)
        frappe_stub.db = types.SimpleNamespace(exists=lambda *args, **kwargs: True)
        frappe_stub.get_meta = lambda doctype: types.SimpleNamespace(issingle=0, is_submittable=1)
        try:
            doctype_actions = access_command_center._business_feature_actions({
                "key": "crm.customers",
                "link_type": "DocType",
                "link_to": "Customer",
            })
            overridden_doctype_actions = access_command_center._business_feature_actions({
                "key": "stock.bins",
                "link_type": "DocType",
                "link_to": "Bin",
            })
            page_actions = access_command_center._business_feature_actions({"key": "test.page", "link_type": "Page"})
            dimensioning_actions = access_command_center._business_feature_actions({
                "key": "items.dimensioning_sets",
                "link_type": "Page",
            })
            report_actions = access_command_center._business_feature_actions({"key": "test.report", "link_type": "Report"})
            dashboard_actions = access_command_center._business_feature_actions({"key": "test.dashboard", "link_type": "Dashboard"})
        finally:
            if original_db is None:
                delattr(frappe_stub, "db")
            else:
                frappe_stub.db = original_db
            if original_get_meta is None:
                delattr(frappe_stub, "get_meta")
            else:
                frappe_stub.get_meta = original_get_meta

        self.assertEqual(doctype_actions[:2], ("select", "view"))
        self.assertEqual(overridden_doctype_actions, ("select", "view", "export"))
        self.assertEqual(page_actions, ("open",))
        self.assertEqual(dimensioning_actions, ("select", "open"))
        self.assertEqual(report_actions, ("view", "export"))
        self.assertEqual(dashboard_actions, ("open",))

    def test_status_control_exposes_edit_and_delete_actions(self):
        actions = access_command_center._business_feature_actions({
            "key": "administration.status_control",
            "link_type": "Page",
            "link_to": "status-control",
        })

        self.assertEqual(actions, ("open", "create_edit", "delete"))

    def test_business_actions_normalize_select_view_and_stronger_dependencies(self):
        select_only = access_command_center._normalize_business_actions({
            "select": 1,
            "view": 0,
            "create_edit": 0,
            "approve_cancel": 0,
            "delete": 0,
            "import": 0,
            "export": 0,
        })
        view = access_command_center._normalize_business_actions({"select": 0, "view": 1, "create_edit": 0})
        page_open = access_command_center._normalize_business_actions({"select": 0, "open": 1})
        stronger = access_command_center._normalize_business_actions({"select": 0, "view": 0, "delete": 1})
        approve = access_command_center._normalize_business_actions({
            "select": 0,
            "view": 0,
            "create_edit": 0,
            "approve_cancel": 1,
            "import": 0,
        })
        import_actions = access_command_center._normalize_business_actions({
            "select": 0,
            "view": 0,
            "create_edit": 0,
            "import": 1,
        })
        view_removed = access_command_center._normalize_business_actions({
            "select": 1,
            "view": 0,
            "create_edit": 0,
            "approve_cancel": 0,
            "delete": 0,
        })
        select_removed = access_command_center._normalize_business_actions({
            "select": 0,
            "view": 0,
            "create_edit": 0,
            "delete": 0,
        })

        self.assertEqual(select_only["select"], 1)
        self.assertFalse(any(value for key, value in select_only.items() if key != "select"))
        self.assertEqual((view["select"], view["view"]), (1, 1))
        self.assertEqual((page_open["select"], page_open["open"]), (1, 1))
        self.assertEqual((stronger["select"], stronger["view"], stronger["delete"]), (1, 1, 1))
        self.assertEqual((approve["select"], approve["view"], approve["create_edit"]), (1, 1, 1))
        self.assertEqual((import_actions["select"], import_actions["view"], import_actions["create_edit"]), (1, 1, 1))
        self.assertEqual(view_removed["select"], 1)
        self.assertFalse(any(value for key, value in view_removed.items() if key != "select"))
        self.assertFalse(any(select_removed.values()))

    def test_business_permission_save_writes_exact_managed_flags_for_select_only(self):
        originals = {
            "db": getattr(frappe_stub, "db", None),
            "ensure": access_command_center._ensure_custom_permission_matrix,
            "perm_rows": access_command_center._perm_rows,
            "save": access_command_center._save_custom_docperm_record,
        }
        saved = {}
        frappe_stub.db = types.SimpleNamespace(exists=lambda *args, **kwargs: True)
        access_command_center._ensure_custom_permission_matrix = lambda doctype: None
        access_command_center._perm_rows = lambda source, doctype, role: {
            0: {field: 1 for field in access_command_center.PERMISSION_FIELDS}
        }
        access_command_center._save_custom_docperm_record = (
            lambda role, doctype, flags, permlevel, **kwargs: saved.update(flags=flags.copy())
        )
        allowed_actions = ("select", "view", "create_edit", "approve_cancel", "delete", "import", "export")
        try:
            access_command_center._apply_business_doctype_actions(
                "Event",
                "Sales User",
                {action: int(action == "select") for action in allowed_actions},
                allowed_actions=allowed_actions,
            )
        finally:
            if originals["db"] is None:
                delattr(frappe_stub, "db")
            else:
                frappe_stub.db = originals["db"]
            access_command_center._ensure_custom_permission_matrix = originals["ensure"]
            access_command_center._perm_rows = originals["perm_rows"]
            access_command_center._save_custom_docperm_record = originals["save"]

        managed_fields = {
            field
            for action in allowed_actions
            for field in access_command_center.BUSINESS_ACTION_PERMISSION_FIELDS[action]
        }
        self.assertEqual(saved["flags"]["select"], 1)
        self.assertFalse(any(saved["flags"][field] for field in managed_fields if field != "select"))
        self.assertEqual(saved["flags"]["email"], 1)

    def test_business_permission_ui_hides_native_permission_structure(self):
        source = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.js").read_text()
        api = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.py").read_text()

        self.assertIn('["matrix", "Business Permissions"]', source)
        self.assertIn("data-business-action", source)
        self.assertIn("business_permissions", source)
        self.assertIn("save_business_permissions", source)
        self.assertIn("Grant Full Business Access", source)
        self.assertIn('"stock.ledger": ("view", "export")', api)
        self.assertIn('_set_native_target_role("Report"', api)

    def test_business_matrix_role_switch_loads_targeted_context_with_feedback(self):
        source = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.js").read_text()
        api = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.py").read_text()

        for token in [
            "requestRoleChange",
            "loadRoleAccessContext",
            "get_role_access_context",
            "matrixLoading",
            "businessMatrixLoadingMarkup",
            "data-retry-role-matrix",
            "Discard unsaved business permission changes",
            'role="status" aria-live="polite"',
            "acc-business-matrix-error",
        ]:
            self.assertIn(token, source)
        self.assertNotIn(
            'page.main.find("[data-role-selector]").on("change", function () { STATE.selectedRole = $(this).val(); clearMatrixDraft(); load(page); });',
            source,
        )
        self.assertIn("def get_role_access_context(role: str) -> dict:", api)
        self.assertIn('"business_permissions": _get_business_permission_matrix(role)', api)
        role_context = api.split("def get_role_access_context(role: str) -> dict:", 1)[1].split("@frappe.whitelist()", 1)[0]
        self.assertNotIn("_get_permission_matrix(role)", role_context)
        self.assertIn('STATE.activeTab === "reports" && STATE.permissionMatrixRole !== STATE.selectedRole', source)

    def test_business_permission_ui_has_select_column_and_immediate_dependencies(self):
        source = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.js").read_text()

        for token in [
            '<th>${__("Use in Fields")}</th><th>${__("Open / View")}</th>',
            'businessActionCell(feature, actions.get("select"), "select")',
            'if (enabled && actionKey !== "select" && hasSelect) actions.select = 1;',
            'if (!enabled && actionKey === "select")',
            'if (key !== "select") actions[key] = 0;',
            "repeat(8,minmax(48px,.7fr))",
            "Array.from({ length: 8 }",
        ]:
            self.assertIn(token, source)
        for removed in [
            "SUPPORTING_ACCESS_HELP",
            "supportingAccessHelpButton",
            "showSupportingAccessHelp",
            "data-supporting-access-help",
            "acc-supporting-access-info",
            "acc-supporting-access-dialog",
            "ICONS.info",
        ]:
            self.assertNotIn(removed, source)

    def test_business_permission_draft_clears_server_mixed_state(self):
        source = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.js").read_text()

        self.assertIn("const hasDraftAction = Boolean(draft && draft.actions", source)
        self.assertIn("const mixed = hasDraftAction ? false : Boolean(action.mixed);", source)
        self.assertIn('data-mixed="${mixed ? 1 : 0}"', source)

    def test_permissions_ui_prompts_desk_reload_after_native_permission_changes(self):
        source = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.js").read_text()

        for token in [
            "showNativePermissionReloadNotice",
            "Reload Desk to apply permissions",
            "Native ERPNext buttons, Create menus, and search permissions use Desk boot data",
            "window.location.reload()",
        ]:
            self.assertIn(token, source)
        self.assertGreaterEqual(source.count("showNativePermissionReloadNotice();"), 3)

    def test_orderlift_admin_user_details_support_email_and_password_updates(self):
        source = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.js").read_text()
        api = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.py").read_text()

        for token in [
            'data-user-field="email"',
            'data-user-password="new_password"',
            'data-user-password="confirm_password"',
            "Passwords do not match",
            "payload.new_password = newPassword",
            "STATE.selectedUser = response.message.name",
            "Email Change Queued",
        ]:
            self.assertIn(token, source)
        save_user = api.split("def save_user_basic_info(payload: str | dict) -> dict:", 1)[1].split("@frappe.whitelist()", 1)[0]
        for token in [
            "_require_access_manager()",
            "_assert_user_scope(user_name)",
            "validate_email_address",
            "frappe.enqueue(",
            "rename_user_email",
            'queue="long"',
            "timeout=USER_RENAME_JOB_TIMEOUT",
            "enqueue_after_commit=True",
            "user_name=user_name",
            "email=email",
            "user.new_password = new_password",
        ]:
            self.assertIn(token, save_user)
        self.assertIn("def rename_user_email(user_name: str, email: str", api)
        self.assertIn('"Notification Settings",', api)
        self.assertIn('"User",', api)
        self.assertGreaterEqual(api.count("ignore_permissions=True"), 2)
        self.assertIn("rebuild_search=False", api)

    def test_user_email_rename_status_uses_shared_cache(self):
        class FakeRedis:
            def __init__(self):
                self.values = {}

            def setex(self, key, ttl, value):
                self.values[key] = value

            def get(self, key):
                return self.values.get(key)

            def delete(self, key):
                self.values.pop(key, None)

        original_get_redis_conn = access_command_center.get_redis_conn
        redis = FakeRedis()
        access_command_center.get_redis_conn = lambda: redis
        try:
            access_command_center._set_user_email_rename_status(
                "old@example.com",
                "new@example.com",
                "started",
                requested_by="admin@example.com",
            )
            status = access_command_center._get_user_email_rename_status("old@example.com")
            self.assertEqual(status["target_email"], "new@example.com")
            self.assertEqual(status["status"], "started")
            self.assertEqual(status["requested_by"], "admin@example.com")

            access_command_center._clear_user_email_rename_status("old@example.com")
            self.assertEqual(access_command_center._get_user_email_rename_status("old@example.com"), {})
        finally:
            access_command_center.get_redis_conn = original_get_redis_conn

    def test_user_list_shows_and_polls_active_email_rename_status(self):
        source = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.js").read_text()
        api = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.py").read_text()

        for token in [
            '"email_rename": _get_user_email_rename_status(row.name)',
            "def _queue_user_email_rename(",
            '_set_user_email_rename_status(user_name, email, "queued"',
            '_set_user_email_rename_status(user_name, email, "started"',
            '_set_user_email_rename_status(user_name, email, "failed"',
        ]:
            self.assertIn(token, api)
        for token in [
            "userRenamePollTimer",
            "scheduleUserRenamePoll(page)",
            "Renaming to {0}",
            "New login active",
            "Rename failed: {0}",
            "email_rename",
        ]:
            self.assertIn(token, source)

    def test_email_change_activates_new_login_alias_before_background_rename(self):
        source = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.js").read_text()
        api = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.py").read_text()

        self.assertGreaterEqual(api.count("_prepare_user_email_login_alias(user, user_name, email)"), 2)
        for token in [
            "def _prepare_user_email_login_alias(",
            'frappe.db.set_single_value("System Settings", "allow_login_using_user_name", 1)',
            '_set_if_field(user, "username", email)',
            '"login_ready":',
        ]:
            self.assertIn(token, api)
        self.assertIn("The new login {0} is available now", source)
        self.assertIn("linked records continue updating in the background", source)

    def test_user_settings_open_in_modal_without_lateral_panel(self):
        source = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.js").read_text()

        for token in [
            "userSettingsOpen: false",
            "function userSettingsModalMarkup",
            'role="dialog" aria-modal="true"',
            "data-close-user-settings",
            "openUserSettings(page",
            "closeUserSettings(page)",
            'data-view-user="${escapeHtml(user.name)}"',
            'renameActive ? __("View Progress") : __("User Settings")',
            'page.main.find(".acc-detail-panel")',
            "acc-user-settings-backdrop",
            "acc-user-settings-dialog",
        ]:
            self.assertIn(token, source)
        self.assertNotIn('<aside class="acc-detail-panel">', source)
        self.assertNotIn('page.main.find("[data-view-user], [data-user-row]")', source)

    def test_user_settings_use_one_atomic_save_and_explicit_user_type(self):
        source = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.js").read_text()
        api = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.py").read_text()

        for token in [
            "Save All User Settings",
            "data-save-user-configuration",
            "saveUserConfiguration(page)",
            "save_user_configuration",
            '<select data-user-field="user_type">',
            "System Users require at least one assigned Desk Access role",
            "Password fields are cleared after every save for security",
        ]:
            self.assertIn(token, source)
        for obsolete in [
            "data-save-user-roles",
            "data-save-user-companies",
            "data-save-user-warehouses",
            "data-save-user-business-types",
        ]:
            self.assertNotIn(obsolete, source)
        unified = api.split("def save_user_configuration(payload: str | dict) -> dict:", 1)[1].split("@frappe.whitelist()", 1)[0]
        for token in [
            "_require_access_manager()",
            "_assert_user_scope(user_name)",
            "_merge_scoped_roles",
            "_save_user_company_access",
            "_save_user_business_type_access",
            "_save_user_warehouse_access",
            "_assert_user_type_matches_roles(user_type, role_names)",
            '_set_if_field(user, "user_type", user_type)',
            "user.new_password = new_password",
            "_queue_user_email_rename(user_name, email, frappe.session.user)",
            "frappe.db.commit()",
        ]:
            self.assertIn(token, unified)
        queue_helper = api.split("def _queue_user_email_rename(", 1)[1].split("def _user_email_rename_status_key", 1)[0]
        for token in [
            "rename_user_email",
            'queue="long"',
            "timeout=USER_RENAME_JOB_TIMEOUT",
            "enqueue_after_commit=True",
            "user_name=user_name",
            "email=email",
        ]:
            self.assertIn(token, queue_helper)

    def test_company_access_does_not_manage_a_default_company(self):
        source = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.js").read_text()
        api = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.py").read_text()

        for obsolete in [
            "userDefaultCompanyDraft",
            "data-make-default-company",
            "Make Default",
            "acc-default-company-btn",
            "default_company",
        ]:
            self.assertNotIn(obsolete, source)
        company_save = api.split("def save_user_companies(", 1)[1].split("@frappe.whitelist()", 1)[0]
        self.assertNotIn("default_company", company_save)
        self.assertIn("_save_user_company_access(user_name, companies)", company_save)

    def test_user_type_requires_roles_that_match_manual_selection(self):
        original_get_all = getattr(frappe_stub, "get_all", None)
        frappe_stub.get_all = lambda *args, **kwargs: ["Sales User"] if "Sales User" in kwargs.get("filters", {}).get("name", [None, []])[1] else []
        try:
            access_command_center._assert_user_type_matches_roles("System User", ["Sales User"])
            with self.assertRaises(ValueError):
                access_command_center._assert_user_type_matches_roles("System User", [])
            with self.assertRaises(ValueError):
                access_command_center._assert_user_type_matches_roles("Website User", ["Sales User"])
            access_command_center._assert_user_type_matches_roles("Website User", [])
        finally:
            if original_get_all is None:
                del frappe_stub.get_all
            else:
                frappe_stub.get_all = original_get_all

    def test_native_role_form_uses_capability_checkbox_picker(self):
        source = (APP_ROOT / "orderlift" / "public" / "js" / "role_capability_picker_20260721a.js").read_text()

        self.assertIn('frappe.ui.form.on("Role"', source)
        self.assertIn("data-orderlift-capability", source)
        self.assertIn("get_capability_options", source)
        self.assertIn("renderCapabilityGroups", source)
        self.assertIn("ol-role-capability-group", source)
        self.assertIn('frm.set_df_property(STORAGE_FIELD, "hidden", 1)', source)

    def test_role_capability_hook_normalizes_storage_keys(self):
        class Meta:
            @staticmethod
            def get_field(fieldname):
                return fieldname == role_capabilities.ROLE_CAPABILITY_FIELD

        class RoleDoc(dict):
            meta = Meta()

            def set(self, fieldname, value):
                self[fieldname] = value

        doc = RoleDoc(custom_orderlift_capabilities="purchasing_access,unknown\nprivileged_pricing")

        role_capabilities.normalize_role_capabilities(doc)

        self.assertEqual(doc[role_capabilities.ROLE_CAPABILITY_FIELD], "purchasing_access\nprivileged_pricing")

    def test_superadmin_sees_backend_finance_permissions_only_for_superadmin_roles(self):
        frappe_stub.session.user = "manager@example.com"
        frappe_stub.get_roles = lambda user=None: ["System Manager"]

        self.assertTrue(access_command_center._permission_doctype_visible("Account", "System Manager"))
        self.assertFalse(access_command_center._permission_doctype_visible("Cost Center", "Developer"))
        self.assertFalse(access_command_center._permission_doctype_visible("Account", "Orderlift Admin"))

    def test_business_admin_can_manage_user_but_not_other_protected_permission_doctypes(self):
        frappe_stub.session.user = "orderlift.admin@example.com"
        frappe_stub.get_roles = lambda user=None: ["Orderlift Admin"]

        self.assertTrue(access_command_center._permission_doctype_visible("User", "Orderlift Admin"))
        self.assertFalse(access_command_center._permission_doctype_visible("Custom DocPerm", "Sales User"))
        self.assertFalse(access_command_center._permission_doctype_visible("Custom Field", "Orderlift Admin"))
        self.assertFalse(access_command_center._permission_doctype_visible("Workflow", "Orderlift Admin"))

        access_command_center._validate_permission_edit("Orderlift Admin", "User", {"read": 1, "write": 1})
        with self.assertRaises(ValueError):
            access_command_center._validate_permission_edit("Orderlift Admin", "Role", {"read": 1, "write": 1})

    def test_superadmin_sees_protected_permissions_only_for_superadmin_roles(self):
        frappe_stub.session.user = "manager@example.com"
        frappe_stub.get_roles = lambda user=None: ["System Manager"]

        self.assertTrue(access_command_center._permission_doctype_visible("User", "System Manager"))
        self.assertTrue(access_command_center._permission_doctype_visible("User", "Orderlift Admin"))
        self.assertFalse(access_command_center._permission_doctype_visible("Role", "Orderlift Admin"))

    def test_business_role_permission_edit_rejects_backend_finance_doctypes(self):
        frappe_stub.session.user = "manager@example.com"
        frappe_stub.get_roles = lambda user=None: ["System Manager"]

        with self.assertRaises(ValueError):
            access_command_center._validate_permission_edit("Finance User", "Cost Center", {"read": 1})

    def test_business_admin_page_access_target_is_menu_allowlisted(self):
        frappe_stub.session.user = "orderlift.admin@example.com"
        frappe_stub.get_roles = lambda user=None: ["Orderlift Admin"]

        self.assertTrue(access_command_center._page_access_target_visible("pricing-dashboard"))
        self.assertFalse(access_command_center._page_access_target_visible("access-command-center"))
        self.assertFalse(access_command_center._page_access_target_visible("role-permission-manager"))

    def test_business_admin_report_access_target_is_menu_allowlisted(self):
        frappe_stub.session.user = "orderlift.admin@example.com"
        frappe_stub.get_roles = lambda user=None: ["Orderlift Admin"]

        self.assertTrue(access_command_center._report_access_target_visible("Stock Balance", "Bin"))
        self.assertFalse(access_command_center._report_access_target_visible("General Ledger", "GL Entry"))
        self.assertFalse(access_command_center._report_access_target_visible("User Activity", "User"))

    def test_role_profile_scope_rejects_protected_roles_for_business_admin(self):
        frappe_stub.session.user = "orderlift.admin@example.com"
        frappe_stub.get_roles = lambda user=None: ["Orderlift Admin"]
        original_role_profile_roles = access_command_center._role_profile_roles
        access_command_center._role_profile_roles = lambda role_profile: ["Sales User", "System Manager"]
        try:
            with self.assertRaises(ValueError):
                access_command_center._assert_role_profile_scope("Escalation Profile")
        finally:
            access_command_center._role_profile_roles = original_role_profile_roles

    def test_company_assignment_scope_rejects_unavailable_company(self):
        frappe_stub.session.user = "orderlift.admin@example.com"
        frappe_stub.get_roles = lambda user=None: ["Orderlift Admin"]
        originals = {
            "user_can_access_all_companies": access_command_center.user_can_access_all_companies,
            "get_allowed_companies": access_command_center.get_allowed_companies,
        }
        access_command_center.user_can_access_all_companies = lambda user=None: False
        access_command_center.get_allowed_companies = lambda user=None: ["Orderlift Maroc Distribution"]
        try:
            with self.assertRaises(ValueError):
                access_command_center._assert_company_assignment_scope(["Orderlift Maroc Installation"])
        finally:
            access_command_center.user_can_access_all_companies = originals["user_can_access_all_companies"]
            access_command_center.get_allowed_companies = originals["get_allowed_companies"]

    def test_user_permission_scope_limits_managed_doctypes(self):
        with self.assertRaises(ValueError):
            access_command_center._validate_user_permission_scope("Role", "System Manager")

    def test_user_permission_scope_allows_warehouse(self):
        original_db = getattr(frappe_stub, "db", None)
        original_visible = access_command_center.get_visible_warehouses
        frappe_stub.db = types.SimpleNamespace(exists=lambda doctype, value=None: True)
        access_command_center.get_visible_warehouses = lambda: [types.SimpleNamespace(name="Stores - OMD")]
        try:
            access_command_center._validate_user_permission_scope("Warehouse", "Stores - OMD")
        finally:
            frappe_stub.db = original_db
            access_command_center.get_visible_warehouses = original_visible

    def test_business_admin_warehouse_assignment_scope_rejects_unavailable_warehouse(self):
        frappe_stub.session.user = "orderlift.admin@example.com"
        frappe_stub.get_roles = lambda user=None: ["Orderlift Admin"]
        original_visible = access_command_center.get_visible_warehouses
        access_command_center.get_visible_warehouses = lambda: [types.SimpleNamespace(name="Stores - OMD")]
        try:
            with self.assertRaises(ValueError):
                access_command_center._assert_warehouse_assignment_scope(["Hidden - OMI"])
        finally:
            access_command_center.get_visible_warehouses = original_visible

    def test_visible_user_filters_exclude_hidden_users(self):
        original_hidden_users = access_command_center._hidden_users_for_session
        access_command_center._hidden_users_for_session = lambda: {"Administrator", "Guest"}
        try:
            filters = access_command_center._visible_user_filters({"enabled": 1})
        finally:
            access_command_center._hidden_users_for_session = original_hidden_users

        hidden_filter = next(row for row in filters if row[:3] == ["User", "name", "not in"])
        self.assertEqual(set(hidden_filter[3]), {"Administrator", "Guest"})
        self.assertIn(["User", "enabled", "=", 1], filters)

    def test_business_admin_user_scope_rejects_hidden_users(self):
        frappe_stub.session.user = "orderlift.admin@example.com"
        frappe_stub.get_roles = lambda user=None: ["Orderlift Admin"]
        original_hidden_users = access_command_center._hidden_users_for_session
        access_command_center._hidden_users_for_session = lambda: {"Administrator", "Guest"}
        try:
            with self.assertRaises(ValueError):
                access_command_center._assert_user_scope("Guest")
        finally:
            access_command_center._hidden_users_for_session = original_hidden_users

    def test_superadmin_still_cannot_manage_guest_from_access_command_center(self):
        frappe_stub.session.user = "Administrator"
        frappe_stub.get_roles = lambda user=None: ["System Manager"]

        self.assertIn("Guest", access_command_center._hidden_users_for_session())
        with self.assertRaises(ValueError):
            access_command_center._assert_user_scope("Guest")

    def test_business_admin_summary_treats_visible_roles_as_custom(self):
        frappe_stub.session.user = "orderlift.admin@example.com"
        frappe_stub.get_roles = lambda user=None: ["Orderlift Admin"]
        originals = {
            "count_visible_users": access_command_center._count_visible_users,
            "summary_roles": access_command_center._summary_roles,
            "count_visible_admin_users": access_command_center._count_visible_admin_users,
            "has_field": access_command_center._has_field,
        }
        original_db = getattr(frappe_stub, "db", None)
        access_command_center._count_visible_users = lambda extra=None: 4 if not extra else (3 if extra.get("enabled") else 1)
        access_command_center._summary_roles = lambda: [{"name": "Orderlift Admin", "is_custom": 0}, {"name": "Sales User", "is_custom": 1}]
        access_command_center._count_visible_admin_users = lambda: 1
        access_command_center._has_field = lambda doctype, fieldname: True
        frappe_stub.db = types.SimpleNamespace(exists=lambda *args, **kwargs: False)
        try:
            summary = access_command_center._get_summary()
        finally:
            access_command_center._count_visible_users = originals["count_visible_users"]
            access_command_center._summary_roles = originals["summary_roles"]
            access_command_center._count_visible_admin_users = originals["count_visible_admin_users"]
            access_command_center._has_field = originals["has_field"]
            if original_db is None:
                delattr(frappe_stub, "db")
            else:
                frappe_stub.db = original_db

        self.assertEqual(summary["system_roles"], 0)
        self.assertEqual(summary["custom_roles"], 2)

    def test_business_admin_audit_filter_hides_superadmin_activity(self):
        originals = {
            "is_superadmin_session": access_command_center._is_superadmin_session,
            "hidden_users_for_session": access_command_center._hidden_users_for_session,
        }
        access_command_center._is_superadmin_session = lambda: False
        access_command_center._hidden_users_for_session = lambda: {"ashdrissi@gmail.com", "Administrator", "Guest"}
        try:
            self.assertFalse(access_command_center._audit_event_visible({"actor": "ashdrissi@gmail.com", "target_type": "User", "target": "orderlift.admin@ecomepivot.com"}))
            self.assertFalse(access_command_center._audit_event_visible({"actor": "orderlift.admin@ecomepivot.com", "target_type": "User", "target": "Administrator"}))
            self.assertFalse(access_command_center._audit_event_visible({"actor": "orderlift.admin@ecomepivot.com", "target_type": "Role", "target": "System Manager"}))
            self.assertTrue(access_command_center._audit_event_visible({"actor": "orderlift.admin@ecomepivot.com", "target_type": "Role", "target": "Sales User"}))
        finally:
            access_command_center._is_superadmin_session = originals["is_superadmin_session"]
            access_command_center._hidden_users_for_session = originals["hidden_users_for_session"]


if __name__ == "__main__":
    unittest.main()
