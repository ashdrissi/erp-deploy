from __future__ import annotations


def execute() -> None:
    from orderlift.orderlift.page.access_command_center.access_command_center import (
        ensure_managed_role_baselines,
        ensure_managed_role_grant_snapshots,
        reconcile_business_menu_access,
        sync_business_import_support_permissions,
    )
    from orderlift.role_capabilities import (
        seed_default_role_capabilities,
        sync_purchase_agent_rule_permissions,
        upgrade_canonical_role_capabilities,
    )
    from orderlift.scripts.sync_page_roles_from_menu_registry import run

    ensure_managed_role_baselines()
    seed_default_role_capabilities()
    upgrade_canonical_role_capabilities()
    sync_business_import_support_permissions()
    ensure_managed_role_grant_snapshots()
    reconcile_business_menu_access()
    sync_purchase_agent_rule_permissions()
    run()
