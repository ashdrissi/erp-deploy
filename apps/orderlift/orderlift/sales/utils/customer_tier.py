import frappe
from frappe import _

DEFAULT_CUSTOMER_GROUP = "All Customer Groups"
DEFAULT_MANUAL_TIER = "New"


class CustomerGroupFallbackMixin:
    def validate_customer_group(self):
        if (self.customer_group or "").strip() == DEFAULT_CUSTOMER_GROUP:
            return
        return super().validate_customer_group()


def sync_customer_tier_mode(doc, method=None):
    if doc.meta.get_field("customer_group") and not (doc.get("customer_group") or "").strip():
        doc.customer_group = DEFAULT_CUSTOMER_GROUP

    if not all(doc.meta.get_field(fieldname) for fieldname in ["enable_dynamic_segmentation", "tier", "manual_tier"]):
        return

    is_dynamic = int(doc.get("enable_dynamic_segmentation") or 0) == 1

    if is_dynamic:
        doc.manual_tier = ""
        if doc.tier:
            _set_if_field(doc, "tier_source", doc.get("tier_source") or "Dynamic Segmentation")
        return

    manual_tier = (doc.get("tier") or doc.get("manual_tier") or "").strip() or DEFAULT_MANUAL_TIER

    allowed = _get_allowed_tiers()
    if allowed and manual_tier not in allowed:
        frappe.throw(
            _("Manual Tier {0} is not an active Pricing Tier.").format(
                manual_tier,
            )
        )

    doc.tier = manual_tier
    doc.manual_tier = manual_tier
    _set_if_field(doc, "tier_source", "Manual")
    _set_if_field(doc, "tier_last_calculated_on", None)


def apply_dynamic_customer_tier(doc, method=None):
    if not all(doc.meta.get_field(fieldname) for fieldname in ["enable_dynamic_segmentation", "tier"]):
        return
    if int(doc.get("enable_dynamic_segmentation") or 0) != 1:
        return
    if not doc.name:
        return

    from orderlift.orderlift_sales.doctype.customer_segmentation_engine.customer_segmentation_engine import (
        calculate_customer_dynamic_tier,
    )

    calculate_customer_dynamic_tier(customer=doc.name, apply=1)


def _set_if_field(doc, fieldname: str, value) -> None:
    if doc.meta.get_field(fieldname):
        doc.set(fieldname, value)


def _get_allowed_tiers():
    if not frappe.db.exists("DocType", "Pricing Tier"):
        return []

    return frappe.get_all(
        "Pricing Tier",
        filters={"is_active": 1},
        pluck="name",
        order_by="sequence asc, name asc",
        limit_page_length=0,
    )
