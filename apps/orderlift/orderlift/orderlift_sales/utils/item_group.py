import frappe
from frappe.utils import cint


def is_item_group_node(item_group_name):
    return cint(frappe.db.get_value("Item Group", item_group_name, "is_group") or 0) == 1


def descendant_leaf_item_groups(item_group_name):
    node = frappe.db.get_value("Item Group", item_group_name, ["lft", "rgt"], as_dict=True) or {}
    lft = cint(node.get("lft") or 0)
    rgt = cint(node.get("rgt") or 0)
    if not lft or not rgt:
        return []

    return frappe.get_all(
        "Item Group",
        filters={
            "lft": [">=", lft],
            "rgt": ["<=", rgt],
            "is_group": 0,
        },
        pluck="name",
        limit_page_length=0,
    )
