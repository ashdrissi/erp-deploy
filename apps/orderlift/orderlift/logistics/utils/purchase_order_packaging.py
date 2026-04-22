from __future__ import annotations

from frappe.utils import flt

from orderlift.orderlift_logistics.utils.packaging_resolver import get_packaging_resolution


def validate_purchase_order_packaging(doc, method=None):
    # Keep submitted Purchase Orders immutable. Older submitted rows may not have
    # packaging snapshot fields populated yet, but they should not be mutated on
    # update-after-submit saves because Frappe blocks those child-row changes.
    if getattr(doc, "docstatus", 0) == 1:
        return

    for row in doc.items or []:
        item_code = (getattr(row, "item_code", "") or "").strip()
        if not item_code:
            continue

        selected_profile = (getattr(row, "custom_packaging_profile", "") or "").strip() or None
        source_hint = (getattr(row, "custom_packaging_profile_source", "") or "").strip()

        resolution = get_packaging_resolution(
            item_code=item_code,
            packaging_profile=selected_profile,
            qty=getattr(row, "qty", 0),
            uom=getattr(row, "uom", None),
        )

        resolved_profile_name = resolution.get("resolved_profile_name") or ""
        if not selected_profile and resolved_profile_name:
            row.custom_packaging_profile = resolved_profile_name

        row.custom_packaging_profile_source = _resolve_source(source_hint, resolution.get("resolved_source") or "item_fallback")
        row.custom_packaging_uom = resolution.get("resolved_uom") or ""
        if hasattr(row, "custom_packaging_type"):
            row.custom_packaging_type = resolution.get("packaging_type") or ""
        row.custom_units_per_package = flt(resolution.get("units_per_package") or 0)
        row.custom_package_count = flt(resolution.get("package_count") or 0)
        row.custom_package_weight_kg = flt(resolution.get("weight_kg") or 0)
        row.custom_package_volume_m3 = flt(resolution.get("volume_m3") or 0)


def _resolve_source(source_hint, resolved_source):
    if source_hint == "selected":
        return "selected"
    if resolved_source in {"selected", "default", "item_fallback"}:
        return resolved_source
    return "item_fallback"
