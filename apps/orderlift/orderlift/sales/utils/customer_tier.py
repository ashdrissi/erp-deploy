import frappe
from frappe import _


def sync_customer_tier_mode(doc, method=None):
    is_dynamic = int(doc.get("enable_dynamic_segmentation") or 0) == 1

    if is_dynamic:
        doc.manual_tier = ""
        if doc.tier:
            doc.tier_source = doc.tier_source or "Dynamic Segmentation"
        return

    manual_tier = (doc.get("manual_tier") or "").strip()
    if not manual_tier:
        doc.tier = ""
        doc.tier_source = "Manual"
        doc.tier_last_calculated_on = None
        return

    allowed = _get_allowed_tiers((doc.get("customer_group") or "").strip())
    if allowed and manual_tier not in allowed:
        frappe.throw(
            _("Manual Tier {0} is not allowed for Customer Group {1}.").format(
                manual_tier,
                doc.get("customer_group") or "-",
            )
        )

    doc.tier = manual_tier
    doc.tier_source = "Manual"
    doc.tier_last_calculated_on = None


def _get_allowed_tiers(customer_group):
    if not customer_group:
        return []

    engines = frappe.get_all(
        "Customer Segmentation Engine",
        filters={"is_active": 1, "target_customer_type": customer_group},
        pluck="name",
        limit_page_length=0,
    )

    if not engines:
        engines = frappe.get_all(
            "Customer Segmentation Engine",
            filters={"is_active": 1, "target_customer_type": ["in", ["", None]]},
            pluck="name",
            limit_page_length=0,
        )

    tiers = set()
    for engine_name in engines:
        rows = frappe.get_all(
            "Customer Segmentation Rule",
            filters={"parent": engine_name, "is_active": 1},
            fields=["designated_segment"],
            limit_page_length=0,
        )
        for row in rows:
            value = (row.get("designated_segment") or "").strip()
            if value:
                tiers.add(value)

    return sorted(tiers)
