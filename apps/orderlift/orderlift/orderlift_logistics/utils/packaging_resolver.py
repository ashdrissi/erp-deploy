from __future__ import annotations

import math

import frappe
from frappe import _
from frappe.utils import flt


def get_packaging_resolution(item_code, packaging_profile=None, qty=0, uom=None):
    """Resolve packaging metrics for an item.

    Priority:
    1. Explicitly selected packaging profile
    2. Active default packaging profile on item
    3. Item master fallback

    Args:
        item_code: Item name/code
        packaging_profile: Optional packaging profile dict or doc (selected by caller)
        qty: Requested quantity (interpreted in *uom* if given, else stock_uom)
        uom: UOM of the requested qty

    Returns:
        dict with resolved metrics (see implementation for keys)
    """
    item = frappe.get_cached_doc("Item", item_code)
    stock_uom = item.stock_uom or "Nos"
    input_qty = flt(qty)
    input_uom = uom or stock_uom
    warnings = []

    resolved_source = "item_fallback"
    resolved_profile = None
    resolved_profile_name = ""
    resolved_uom = stock_uom
    packaging_type = ""
    units_per_package = 1.0
    stock_qty = input_qty
    package_count = 1.0
    weight_kg = flt(getattr(item, "custom_weight_kg", 0) or 0)
    length_cm = flt(getattr(item, "custom_length_cm", 0) or 0)
    width_cm = flt(getattr(item, "custom_width_cm", 0) or 0)
    height_cm = flt(getattr(item, "custom_height_cm", 0) or 0)
    volume_m3 = flt(getattr(item, "custom_volume_m3", 0) or 0)
    customs_tariff_number = (getattr(item, "customs_tariff_number", "") or "").strip().upper()

    profiles = _get_active_profiles(item) if not packaging_profile else []

    profile_doc = None

    if packaging_profile:
        profile_doc = _ensure_profile_doc(packaging_profile, item_code)
        if profile_doc and flt(getattr(profile_doc, "is_active", 1)):
            resolved_source = "selected"
            resolved_profile = profile_doc
            resolved_profile_name = getattr(profile_doc, "name", "") or ""
            resolved_uom = profile_doc.uom or stock_uom
    elif profiles:
        default_profile = _find_default_profile(profiles)
        if default_profile:
            resolved_source = "default"
            resolved_profile = default_profile
            resolved_profile_name = getattr(default_profile, "name", "") or ""
            resolved_uom = default_profile.uom or stock_uom
            profile_doc = default_profile

    if profile_doc:
        tariff_override = (getattr(profile_doc, "customs_tariff_number_override", "") or "").strip().upper()
        if tariff_override:
            customs_tariff_number = tariff_override

        units_per_package = flt(getattr(profile_doc, "units_per_package", 1) or 1)
        if units_per_package <= 0:
            units_per_package = 1.0
            warnings.append(_("Units per package is invalid for profile {0}.").format(profile_doc.parentfield or profile_doc.idx))

        weight_kg = flt(getattr(profile_doc, "weight_kg", 0) or 0)
        packaging_type = (getattr(profile_doc, "packaging_type", "") or "").strip()
        length_cm = flt(getattr(profile_doc, "length_cm", 0) or 0)
        width_cm = flt(getattr(profile_doc, "width_cm", 0) or 0)
        height_cm = flt(getattr(profile_doc, "height_cm", 0) or 0)
        volume_m3 = flt(getattr(profile_doc, "volume_m3", 0) or 0)

        if length_cm > 0 and width_cm > 0 and height_cm > 0 and volume_m3 <= 0:
            volume_m3 = (length_cm * width_cm * height_cm) / 1000000.0

        stock_qty = _convert_to_stock_uom(item_code, input_qty, input_uom)
        package_count = math.ceil(stock_qty / units_per_package) if units_per_package > 0 else 0
    else:
        if input_uom and input_uom != stock_uom:
            stock_qty = _convert_to_stock_uom(item_code, input_qty, input_uom)
        else:
            stock_qty = input_qty
        package_count = input_qty

    if input_qty > 0 and flt(stock_qty) <= 0 and input_uom and input_uom != stock_uom:
        warnings.append(_("Could not convert {0} {1} to stock UOM {2}.").format(input_qty, input_uom, stock_uom))

    return {
        "item_code": item_code,
        "stock_uom": stock_uom,
        "input_qty": input_qty,
        "input_uom": input_uom,
        "resolved_source": resolved_source,
        "resolved_profile": resolved_profile,
        "resolved_profile_name": resolved_profile_name,
        "resolved_uom": resolved_uom,
        "packaging_type": packaging_type,
        "units_per_package": units_per_package,
        "stock_qty": stock_qty,
        "package_count": package_count,
        "weight_kg": weight_kg,
        "length_cm": length_cm,
        "width_cm": width_cm,
        "height_cm": height_cm,
        "volume_m3": volume_m3,
        "customs_tariff_number": customs_tariff_number,
        "warnings": warnings,
    }


def _get_active_profiles(item):
    """Return active packaging profiles for an item."""
    return [
        p for p in (item.custom_packaging_profiles or [])
        if cint_safe(getattr(p, "is_active", 1), 1)
    ]


def _find_default_profile(profiles):
    """Return the first active default profile, or None."""
    for p in profiles:
        if cint_safe(getattr(p, "is_default", 0), 0):
            return p
    return None


def _ensure_profile_doc(profile, item_code):
    """Convert packaging_profile input into a usable dict-like/doc-like object."""
    if isinstance(profile, dict):
        return frappe._dict(profile)
    if isinstance(profile, str):
        profile = profile.strip()
        if not profile:
            return None
        if frappe.db.exists("Item Packaging Profile", profile):
            return frappe.get_doc("Item Packaging Profile", profile)
        return None
    return profile


@frappe.whitelist()
def get_item_packaging_profiles(item_code):
    item_code = (item_code or "").strip()
    if not item_code:
        return []

    rows = frappe.get_all(
        "Item Packaging Profile",
        filters={"parent": item_code, "parenttype": "Item", "is_active": 1},
        fields=[
            "name",
            "uom",
            "packaging_type",
            "units_per_package",
            "weight_kg",
            "length_cm",
            "width_cm",
            "height_cm",
            "volume_m3",
            "is_default",
        ],
        order_by="is_default desc, idx asc",
        limit_page_length=0,
    )
    return rows


@frappe.whitelist()
def resolve_packaging(item_code, packaging_profile=None, qty=0, uom=None):
    resolution = get_packaging_resolution(
        item_code=(item_code or "").strip(),
        packaging_profile=packaging_profile,
        qty=qty,
        uom=uom,
    )

    return {
        "item_code": resolution["item_code"],
        "resolved_source": resolution["resolved_source"],
        "resolved_profile_name": resolution.get("resolved_profile_name") or "",
        "resolved_uom": resolution.get("resolved_uom") or "",
        "packaging_type": resolution.get("packaging_type") or "",
        "units_per_package": flt(resolution.get("units_per_package") or 0),
        "package_count": flt(resolution.get("package_count") or 0),
        "weight_kg": flt(resolution.get("weight_kg") or 0),
        "volume_m3": flt(resolution.get("volume_m3") or 0),
        "stock_qty": flt(resolution.get("stock_qty") or 0),
        "customs_tariff_number": resolution.get("customs_tariff_number") or "",
        "warnings": resolution.get("warnings") or [],
    }


def _convert_to_stock_uom(item_code, qty, uom):
    """Convert qty from given UOM to stock UOM using ERPNext conversions."""
    if uom is None:
        return flt(qty)
    item = frappe.get_cached_doc("Item", item_code)
    if uom == item.stock_uom:
        return flt(qty)
    conversion = _get_uom_conversion(item, uom)
    if conversion > 0:
        return flt(qty) * conversion
    frappe.throw(
        _("No UOM conversion found for {0} from {1} to {2}.").format(item_code, uom, item.stock_uom)
    )


def _get_uom_conversion(item, target_uom):
    """Return factor to convert 1 of target_uom into stock_uom."""
    for row in item.uoms or []:
        if row.uom == target_uom:
            return flt(row.conversion_factor or 1)
    return 1.0


def cint_safe(value, fallback=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback
