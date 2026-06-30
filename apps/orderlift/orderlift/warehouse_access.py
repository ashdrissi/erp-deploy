from __future__ import annotations

import frappe
from frappe.utils import cint

from orderlift.menu_access import get_allowed_companies, user_can_access_all_companies


WAREHOUSE_DOCTYPE = "Warehouse"
USER_PERMISSION_DOCTYPE = "User Permission"


def get_visible_warehouses(user: str | None = None) -> list[dict]:
    if not hasattr(frappe, "get_all"):
        return []
    filters = {"is_group": 0}
    if _has_column(WAREHOUSE_DOCTYPE, "disabled"):
        filters["disabled"] = 0
    if not user_can_access_all_companies(user):
        companies = get_allowed_companies(user)
        if not companies:
            return []
        filters["company"] = ["in", companies]
    return frappe.get_all(
        WAREHOUSE_DOCTYPE,
        filters=filters,
        fields=["name", "warehouse_name", "company", "parent_warehouse"],
        order_by="company asc, warehouse_name asc, name asc",
        limit_page_length=0,
    )


def get_selected_warehouses(user: str | None = None) -> list[str]:
    user = user or frappe.session.user
    if not _doctype_available(USER_PERMISSION_DOCTYPE):
        return []
    rows = frappe.get_all(
        USER_PERMISSION_DOCTYPE,
        filters={"user": user, "allow": WAREHOUSE_DOCTYPE},
        fields=["for_value", "apply_to_all_doctypes", "applicable_for"],
        order_by="for_value asc",
        limit_page_length=0,
    )
    return [
        row.for_value
        for row in rows
        if cint(row.get("apply_to_all_doctypes")) and not (row.get("applicable_for") or "").strip()
    ]


def user_can_access_all_warehouses(user: str | None = None) -> bool:
    user = user or frappe.session.user
    if user_can_access_all_companies(user):
        return True
    # Opt-in: no selected warehouses means current company-scoped behavior.
    return not get_selected_warehouses(user)


def get_allowed_warehouses(user: str | None = None) -> list[str]:
    selected = set(get_selected_warehouses(user))
    visible = get_visible_warehouses(user)
    visible_names = [row.name for row in visible]
    if not selected:
        return visible_names
    return [name for name in visible_names if name in selected]


def user_can_access_warehouse(warehouse: str | None, user: str | None = None) -> bool:
    warehouse = (warehouse or "").strip()
    if not warehouse:
        return True
    return warehouse in set(get_allowed_warehouses(user))


def save_user_warehouse_access(user: str, warehouses: list[str] | str) -> dict:
    user = (user or "").strip()
    if not user or not frappe.db.exists("User", user):
        frappe.throw(f"User {user} was not found.")

    warehouse_names = _clean_list(warehouses)
    missing = [warehouse for warehouse in warehouse_names if not frappe.db.exists(WAREHOUSE_DOCTYPE, warehouse)]
    if missing:
        frappe.throw(f"Unknown warehouses: {', '.join(missing)}")

    visible = {row.name for row in get_visible_warehouses()}
    unavailable = [warehouse for warehouse in warehouse_names if warehouse not in visible]
    if unavailable:
        frappe.throw(f"Warehouses not available to your access scope: {', '.join(unavailable)}")

    existing = frappe.get_all(
        USER_PERMISSION_DOCTYPE,
        filters={"user": user, "allow": WAREHOUSE_DOCTYPE},
        fields=["name", "apply_to_all_doctypes", "applicable_for"],
        limit_page_length=0,
    )
    for row in existing:
        if cint(row.get("apply_to_all_doctypes")) and not (row.get("applicable_for") or "").strip():
            frappe.delete_doc(USER_PERMISSION_DOCTYPE, row.name, ignore_permissions=True)

    for warehouse in warehouse_names:
        doc = frappe.new_doc(USER_PERMISSION_DOCTYPE)
        doc.user = user
        doc.allow = WAREHOUSE_DOCTYPE
        doc.for_value = warehouse
        doc.apply_to_all_doctypes = 1
        doc.is_default = 0
        doc.insert(ignore_permissions=True)

    frappe.clear_cache(user=user)
    return {"user": user, "warehouses": warehouse_names}


def stock_warehouse_condition(field_sql: str, params: dict, user: str | None = None, key: str = "allowed_warehouses") -> str:
    warehouses = get_allowed_warehouses(user)
    if not warehouses:
        return " AND 1 = 0"
    if user_can_access_all_companies(user) and user_can_access_all_warehouses(user):
        return ""
    params[key] = tuple(warehouses)
    return f" AND {field_sql} IN %({key})s"


def warehouse_query(user: str | None = None) -> str | None:
    return _warehouse_field_query("name", user=user)


def bin_query(user: str | None = None) -> str | None:
    return _warehouse_field_query("warehouse", doctype="Bin", user=user)


def stock_ledger_entry_query(user: str | None = None) -> str | None:
    return _warehouse_field_query("warehouse", doctype="Stock Ledger Entry", user=user)


def item_reorder_query(user: str | None = None) -> str | None:
    return _warehouse_field_query("warehouse", doctype="Item Reorder", user=user)


def stock_entry_query_clause(user: str | None = None) -> str | None:
    warehouses = get_allowed_warehouses(user)
    if not warehouses:
        return "`tabStock Entry`.name is null"
    if user_can_access_all_companies(user) and user_can_access_all_warehouses(user):
        return None
    escaped = ", ".join(frappe.db.escape(warehouse) for warehouse in warehouses)
    return (
        f"(`tabStock Entry`.from_warehouse in ({escaped}) "
        f"or `tabStock Entry`.to_warehouse in ({escaped}) "
        "or exists (select 1 from `tabStock Entry Detail` _ol_sed "
        "where _ol_sed.parent = `tabStock Entry`.name "
        f"and (_ol_sed.s_warehouse in ({escaped}) or _ol_sed.t_warehouse in ({escaped}))))"
    )


def _warehouse_field_query(field: str, doctype: str = WAREHOUSE_DOCTYPE, user: str | None = None) -> str | None:
    warehouses = get_allowed_warehouses(user)
    table = f"`tab{doctype}`"
    if not warehouses:
        return f"{table}.name is null"
    if user_can_access_all_companies(user) and user_can_access_all_warehouses(user):
        return None
    escaped = ", ".join(frappe.db.escape(warehouse) for warehouse in warehouses)
    return f"{table}.{field} in ({escaped})"


def _doctype_available(doctype: str) -> bool:
    try:
        return bool(frappe.db.exists("DocType", doctype))
    except Exception:
        return False


def _has_column(doctype: str, fieldname: str) -> bool:
    try:
        return bool(frappe.db.has_column(doctype, fieldname))
    except Exception:
        return False


def _clean_list(value) -> list[str]:
    if isinstance(value, str):
        import json

        try:
            value = json.loads(value)
        except Exception:
            value = [value]
    result = []
    for item in value or []:
        clean = str(item or "").strip()
        if clean and clean not in result:
            result.append(clean)
    return result
