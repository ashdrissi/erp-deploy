import frappe
from frappe.utils import cint


LEGACY_TYPE_MAP = {
    "installateur": "Installateur",
    "distributeur": "Distributeur",
    "promoteur": "Promoteur",
    "particulier": "Particulier",
}


def execute():
    _normalize_customer_tier_mode_fields()
    _normalize_scenario_rule_customer_group_values()
    _normalize_benchmark_rule_customer_group_values()


def _normalize_customer_tier_mode_fields():
    if not frappe.db.has_column("Customer", "enable_dynamic_segmentation"):
        return

    customers = frappe.get_all(
        "Customer",
        fields=["name", "tier", "manual_tier", "enable_dynamic_segmentation", "tier_source"],
        limit_page_length=0,
    )

    for cust in customers:
        values = {}

        enable_dynamic = cust.get("enable_dynamic_segmentation")
        if enable_dynamic is None:
            values["enable_dynamic_segmentation"] = 1
            enable_dynamic = 1

        if cint(enable_dynamic) == 0:
            manual_tier = (cust.get("manual_tier") or "").strip()
            tier = (cust.get("tier") or "").strip()
            if not manual_tier and tier:
                values["manual_tier"] = tier
            if not (cust.get("tier_source") or "").strip():
                values["tier_source"] = "Manual"

        if values:
            frappe.db.set_value("Customer", cust.get("name"), values, update_modified=False)


def _normalize_scenario_rule_customer_group_values():
    if not frappe.db.exists("DocType", "Pricing Scenario Assignment Rule"):
        return

    rules = frappe.get_all(
        "Pricing Scenario Assignment Rule",
        fields=["name", "customer_type"],
        limit_page_length=0,
    )
    for row in rules:
        group_name = _normalize_group_name(row.get("customer_type"))
        if not group_name:
            continue
        _ensure_customer_group(group_name)
        if group_name != (row.get("customer_type") or ""):
            frappe.db.set_value(
                "Pricing Scenario Assignment Rule",
                row.get("name"),
                "customer_type",
                group_name,
                update_modified=False,
            )


def _normalize_benchmark_rule_customer_group_values():
    if not frappe.db.exists("DocType", "Pricing Benchmark Rule"):
        return

    rules = frappe.get_all(
        "Pricing Benchmark Rule",
        fields=["name", "customer_type"],
        limit_page_length=0,
    )
    for row in rules:
        group_name = _normalize_group_name(row.get("customer_type"))
        if not group_name:
            continue
        _ensure_customer_group(group_name)
        if group_name != (row.get("customer_type") or ""):
            frappe.db.set_value(
                "Pricing Benchmark Rule",
                row.get("name"),
                "customer_type",
                group_name,
                update_modified=False,
            )


def _normalize_group_name(raw):
    value = (raw or "").strip()
    if not value:
        return ""
    mapped = LEGACY_TYPE_MAP.get(value.lower())
    return mapped or value


def _ensure_customer_group(group_name):
    if not group_name:
        return
    if frappe.db.exists("Customer Group", group_name):
        return

    doc = frappe.new_doc("Customer Group")
    doc.customer_group_name = group_name
    doc.parent_customer_group = frappe.db.get_value("Customer Group", {"is_group": 1}, "name") or "All Customer Groups"
    doc.is_group = 0
    doc.insert(ignore_permissions=True)
