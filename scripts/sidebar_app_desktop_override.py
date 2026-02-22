"""Role-scoped persistent sidebar override for sidebar_app.

This replaces sidebar_app's default desktop override implementation.
"""

import frappe
from frappe.desk.desktop import get_workspace_sidebar_items as _original


@frappe.whitelist()
def get_workspace_sidebar_items():
    result = _original()
    _enrich_quick_link_fields(result)

    if not _is_feature_enabled() or not _user_matches_scope():
        return result

    workspace_name = _get_target_workspace_name()
    if not workspace_name:
        return result

    filtered_pages = _filter_pages_for_workspace(result.get("pages") or [], workspace_name)
    if filtered_pages:
        result["pages"] = filtered_pages

    return result


def _enrich_quick_link_fields(result):
    for page in result.get("pages", []):
        try:
            workspace_doc = frappe.get_cached_doc("Workspace", page["name"])
            page["display_label"] = workspace_doc.get("display_label") or ""
            page["is_quick_link"] = workspace_doc.get("is_quick_link") or 0
            page["quick_link_type"] = workspace_doc.get("quick_link_type")
            page["quick_link_to"] = workspace_doc.get("quick_link_to")
            page["quick_link_url"] = workspace_doc.get("quick_link_url")
            page["quick_link_open_new_tab"] = workspace_doc.get("quick_link_open_new_tab") or 0
        except Exception:
            continue


def _is_feature_enabled():
    value = frappe.conf.get("persistent_sidebar_enabled", 1)
    return _to_bool(value)


def _user_matches_scope():
    if frappe.session.user in (None, "", "Guest"):
        return False

    configured = frappe.conf.get("persistent_sidebar_roles", ["Orderlift Commercial"])
    allowed_roles = _normalize_roles(configured)
    if not allowed_roles:
        return False

    user_roles = set(frappe.get_roles(frappe.session.user))
    return bool(user_roles.intersection(allowed_roles))


def _get_target_workspace_name():
    return (frappe.conf.get("persistent_sidebar_workspace") or "Main Dashboard").strip()


def _normalize_roles(value):
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
        return {part for part in parts if part}

    if isinstance(value, (list, tuple, set)):
        out = set()
        for item in value:
            if item:
                out.add(str(item).strip())
        return {item for item in out if item}

    return set()


def _to_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _filter_pages_for_workspace(pages, workspace_name):
    if not pages:
        return pages

    def key(value):
        return (value or "").strip().lower()

    target_key = key(workspace_name)
    if not target_key:
        return pages

    root_name = None
    for page in pages:
        for field in ("name", "title", "label"):
            if key(page.get(field)) == target_key:
                root_name = page.get("name")
                break
        if root_name:
            break

    if not root_name:
        return pages

    selected = {root_name}
    changed = True
    while changed:
        changed = False
        for page in pages:
            parent = page.get("parent_page")
            name = page.get("name")
            if parent in selected and name not in selected:
                selected.add(name)
                changed = True

    filtered = [page for page in pages if page.get("name") in selected]
    return filtered or pages
