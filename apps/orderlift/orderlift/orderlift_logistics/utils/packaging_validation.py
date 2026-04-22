from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt


def validate_item_packaging_profiles(item_doc, method=None):
    """Validate packaging profiles on an Item save.

    Enforces:
    - at most one active default profile
    - positive units_per_package on active profiles
    - no duplicate active profiles for same uom+packaging_type+units_per_package

    Weight and dimensions are intentionally not required here because many live
    items still depend on item-master fallback metrics during the rollout.
    """
    profiles = getattr(item_doc, "custom_packaging_profiles", []) or []
    active = [p for p in profiles if int(getattr(p, "is_active", 1) or 0)]

    _validate_single_default(item_doc.name, active)
    _validate_active_fields(item_doc.name, active)
    _validate_no_duplicates(item_doc.name, active)
    _derive_volume(active)


def _validate_single_default(item_code, active):
    defaults = [p for p in active if int(getattr(p, "is_default", 0) or 0)]
    if len(defaults) > 1:
        frappe.throw(
            _("Item {0} has {1} active default packaging profiles. Only one is allowed.").format(
                item_code, len(defaults)
            )
        )


def _validate_active_fields(item_code, active):
    for p in active:
        idx = getattr(p, "idx", "?")
        uom = getattr(p, "uom", "") or ""
        units = flt(getattr(p, "units_per_package", 0) or 0)

        if not uom:
            frappe.throw(
                _("Row {0}: UOM is required for Item {1} packaging profile.").format(idx, item_code)
            )

        if units <= 0:
            frappe.throw(
                _("Row {0}: Units per package must be > 0 for Item {1}.").format(idx, item_code)
            )


def _validate_no_duplicates(item_code, active):
    seen = set()
    for p in active:
        idx = getattr(p, "idx", "?")
        key = _dup_key(p)
        if key in seen:
            frappe.throw(
                _(
                    "Row {0}: Duplicate active packaging profile (UOM + Packaging Type + Units Per Package) "
                    "on Item {1}."
                ).format(idx, item_code)
            )
        seen.add(key)


def _dup_key(p):
    uom = (getattr(p, "uom", "") or "").strip().upper()
    ptype = (getattr(p, "packaging_type", "") or "").strip().upper()
    units = flt(getattr(p, "units_per_package", 0) or 0)
    return (uom, ptype, units)


def _derive_volume(active):
    """Auto-derive volume_m3 from dimensions when dimensions are present and volume is blank/0."""
    for p in active:
        length_cm = flt(getattr(p, "length_cm", 0) or 0)
        width_cm = flt(getattr(p, "width_cm", 0) or 0)
        height_cm = flt(getattr(p, "height_cm", 0) or 0)
        volume = flt(getattr(p, "volume_m3", 0) or 0)

        if length_cm > 0 and width_cm > 0 and height_cm > 0:
            derived = (length_cm * width_cm * height_cm) / 1000000.0
            if volume <= 0 or abs(volume - derived) > 0.000001:
                p.volume_m3 = derived
