from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from orderlift.orderlift_crm.api.pipeline import get_party_defaults
from orderlift.orderlift_sales.utils.price_list_usage_guard import reprice_quotation_items_from_selected_price_lists
from orderlift.orderlift_sales.utils.price_list_scope import can_override_quotation_pricing, validate_visible_price_list
from orderlift.orderlift_sales.utils.tax_inclusive import (
    apply_quotation_sales_tax_template,
    sync_quotation_item_tax_inclusive_fields,
)
from orderlift.sales.utils.pricing_projection import calculate_agent_commission


OTHER_CHARGE_ITEM_CODE = "OTHER-CHARGES"
COMMISSION_ASSIGNMENT_MANAGER_ROLES = {
    "Orderlift Admin",
    "Orderlift Business Admin",
    "Sales Manager",
    "Pricing Manager",
    "System Manager",
}


@frappe.whitelist()
def get_other_charge_item(company: str | None = None) -> dict:
    if not frappe.has_permission("Quotation", "create") and not frappe.has_permission("Quotation", "write"):
        frappe.throw(_("Not permitted to add other charges."), frappe.PermissionError)

    if not frappe.db.exists("Item", OTHER_CHARGE_ITEM_CODE):
        item = frappe.new_doc("Item")
        item.item_code = OTHER_CHARGE_ITEM_CODE
        item.item_name = _("Other Charges")
        item.description = _("Other Charges")
        item.item_group = _default_service_item_group()
        item.stock_uom = _default_service_uom()
        item.is_stock_item = 0
        item.is_sales_item = 1
        item.is_purchase_item = 0
        if item.meta.get_field("include_item_in_manufacturing"):
            item.include_item_in_manufacturing = 0
        item.insert(ignore_permissions=True)

    values = frappe.db.get_value(
        "Item",
        OTHER_CHARGE_ITEM_CODE,
        ["name", "item_name", "description", "stock_uom"],
        as_dict=True,
    ) or {}
    return {
        "item_code": values.get("name") or OTHER_CHARGE_ITEM_CODE,
        "item_name": values.get("item_name") or _("Other Charges"),
        "description": values.get("description") or _("Other Charges"),
        "uom": values.get("stock_uom") or _default_service_uom(),
    }


@frappe.whitelist()
def get_transportation_charge_item(company: str | None = None) -> dict:
    return get_other_charge_item(company=company)


@frappe.whitelist()
def get_quotation_commission_assignment_context() -> dict:
    """Return only the current user's safe Quotation commission UI context."""
    return {
        "sales_person": _sales_person_for_user(frappe.session.user),
        "can_edit_sales_person": _can_assign_any_commission_salesperson(),
    }


def _default_service_item_group() -> str:
    for name in ("Services", "Service", "All Item Groups"):
        if frappe.db.exists("Item Group", name):
            return name
    row = frappe.get_all(
        "Item Group",
        filters={"is_group": 0} if frappe.db.has_column("Item Group", "is_group") else None,
        pluck="name",
        order_by="name asc",
        limit_page_length=1,
    )
    if row:
        return row[0]
    frappe.throw(_("Create an Item Group before adding transportation charges."))


def _default_service_uom() -> str:
    for name in ("Nos", "Unit", "Pce", "Service"):
        if frappe.db.exists("UOM", name):
            return name
    row = frappe.get_all("UOM", pluck="name", order_by="name asc", limit_page_length=1)
    if row:
        return row[0]
    frappe.throw(_("Create a UOM before adding transportation charges."))


def apply_quotation_party_defaults(doc, method=None) -> None:
    party_type = (doc.get("quotation_to") or "").strip()
    party_name = (doc.get("party_name") or "").strip()
    if party_type not in {"Customer", "Prospect", "Lead"} or not party_name:
        return

    defaults = get_party_defaults(party_type, party_name) or {}
    if doc.meta.get_field("customer_name") and not (doc.get("customer_name") or "").strip():
        doc.customer_name = defaults.get("display_name") or doc.get("customer_name") or party_name
    if doc.meta.get_field("custom_customer_tax_id"):
        doc.custom_customer_tax_id = (
            frappe.db.get_value("Customer", party_name, "tax_id") or ""
            if party_type == "Customer"
            else ""
        )
    _set_if_empty(doc, "territory", defaults.get("territory"))
    _set_if_empty(doc, "customer_address", defaults.get("address_name"))
    _set_if_empty(doc, "address_display", defaults.get("address"))
    _set_if_empty(doc, "contact_person", defaults.get("contact_name"))
    _set_if_empty(doc, "contact_display", defaults.get("contact_display") or defaults.get("email") or defaults.get("mobile"))
    _set_if_empty(doc, "contact_mobile", defaults.get("mobile") or defaults.get("phone"))
    _set_if_empty(doc, "contact_email", defaults.get("email"))
    _set_if_empty(doc, "shipping_address_name", defaults.get("address_name"))


def sync_quotation_pricing_snapshot_fields(doc, method=None) -> None:
    resolve_quotation_commission_context(doc)
    sync_quotation_item_price_input_fields(doc)
    reprice_quotation_items_from_selected_price_lists(doc)
    sync_quotation_item_price_input_fields(doc)
    apply_quotation_sales_tax_template(doc)
    sync_quotation_item_tax_inclusive_fields(doc)


def resolve_quotation_commission_context(doc, method=None) -> str:
    """Resolve one auditable salesperson/rate for Pricing Sheet and direct quotes."""
    source_pricing_sheet = (doc.get("source_pricing_sheet") or "").strip()
    selected = (doc.get("commission_sales_person") or "").strip()
    snapshot_people = {
        (row.get("source_sales_person") or "").strip()
        for row in (doc.get("items") or [])
        if (row.get("source_sales_person") or "").strip()
    }

    if source_pricing_sheet:
        sheet_sales_person = frappe.db.get_value("Pricing Sheet", source_pricing_sheet, "sales_person") or ""
        sales_person = sheet_sales_person or (next(iter(snapshot_people)) if len(snapshot_people) == 1 else "")
    elif _can_assign_any_commission_salesperson():
        # Managers explicitly choose the beneficiary. Blank is intentional and
        # means that this Quotation does not create a commission snapshot.
        sales_person = selected
    else:
        # A normal sales user cannot redirect commission through a crafted
        # request. Existing assignments remain immutable; a new Quotation is
        # attributed to its creator's Sales Person mapping when one exists.
        sales_person = _locked_direct_quotation_sales_person(doc)

    if sales_person and frappe.db.has_column("Sales Person", "enabled"):
        if not frappe.db.get_value("Sales Person", sales_person, "enabled"):
            frappe.throw(_("Commission Salesperson must be enabled."))

    if doc.meta.get_field("commission_sales_person"):
        doc.commission_sales_person = sales_person

    commission_rate = _agent_commission_rate(sales_person)
    for row in doc.get("items") or []:
        if row.meta.get_field("source_sales_person"):
            row.source_sales_person = sales_person
        if not source_pricing_sheet and row.meta.get_field("source_commission_rate"):
            row.source_commission_rate = commission_rate

    return sales_person


def _locked_direct_quotation_sales_person(doc) -> str:
    if not doc.is_new():
        before = doc.get_doc_before_save()
        if before:
            get = getattr(before, "get", None)
            previous = get("commission_sales_person") if callable(get) else getattr(before, "commission_sales_person", "")
            previous = (previous or "").strip()
            if previous:
                return previous
    creator = getattr(doc, "owner", None) or frappe.session.user
    return _sales_person_for_user(creator)


def _sales_person_for_user(user: str) -> str:
    if not user or not frappe.db.exists("DocType", "Sales Person") or not frappe.db.has_column("Sales Person", "user"):
        return ""
    filters = {"user": user}
    if frappe.db.has_column("Sales Person", "enabled"):
        filters["enabled"] = 1
    return frappe.db.get_value("Sales Person", filters, "name") or ""


def _agent_commission_rate(sales_person: str) -> float:
    if not sales_person:
        return 0.0
    rule = frappe.db.get_value("Agent Pricing Rules", {"sales_person": sales_person}, "name")
    return flt(frappe.db.get_value("Agent Pricing Rules", rule, "commission_rate") or 0) if rule else 0.0


def _can_assign_any_commission_salesperson() -> bool:
    if frappe.session.user == "Administrator":
        return True
    return bool(COMMISSION_ASSIGNMENT_MANAGER_ROLES.intersection(set(frappe.get_roles(frappe.session.user) or [])))


def sync_quotation_item_price_input_fields(doc, method=None) -> None:
    """Keep direct Quotation price-input fields consistent before validation.

    The browser lets users enter discount %, discount amount, PU HT, or PU TTC.
    ERPNext accounting remains HT-based, so the saved rate is authoritative and
    the helper fields are normalized from it server-side.
    """
    for row in doc.get("items") or []:
        gross_rate = flt(row.get("source_gross_sell_rate") or row.get("price_list_rate") or 0)
        current_rate = flt(row.get("rate") or 0)
        if gross_rate <= 0 or current_rate < 0:
            continue

        qty = flt(row.get("qty") or 1) or 1
        discount = max((1 - (current_rate / gross_rate)) * 100, 0)
        current_rate = flt(current_rate, row.precision("rate"))
        row.rate = current_rate
        row.amount = flt(current_rate * qty, row.precision("amount"))
        if row.meta.get_field("discount_percentage"):
            row.discount_percentage = flt(discount, row.precision("discount_percentage"))
        if row.meta.get_field("source_price_list_sell_rate") and not flt(row.get("source_price_list_sell_rate") or 0):
            row.source_price_list_sell_rate = flt(gross_rate, row.precision("source_price_list_sell_rate"))
        if row.meta.get_field("source_discount_percent"):
            row.source_discount_percent = flt(discount, row.precision("source_discount_percent"))
        if row.meta.get_field("source_discount_amount"):
            # Quotation input/display is a per-unit discount. Commission payout
            # totals are derived separately from rates and ordered quantity.
            row.source_discount_amount = flt(max(gross_rate - current_rate, 0), row.precision("source_discount_amount"))
        if row.meta.get_field("source_discounted_sell_rate"):
            row.source_discounted_sell_rate = flt(current_rate, row.precision("source_discounted_sell_rate"))
        if row.meta.get_field("source_commission_amount"):
            max_discount = flt(row.get("source_max_discount_percent") or 0)
            commission_rate = flt(row.get("source_commission_rate") or 0)
            try:
                commission = calculate_agent_commission(
                    price_list_unit_price=gross_rate,
                    actual_unit_price=current_rate,
                    qty=qty,
                    max_discount_percent=max_discount,
                    commission_rate=commission_rate,
                    enforce_discount_cap=not can_override_quotation_pricing(),
                )
            except ValueError:
                row.source_commission_amount = 0
                continue
            row.source_commission_amount = flt(
                commission.get("commission_amount") or 0,
                row.precision("source_commission_amount"),
            )


def populate_quotation_stock_snapshot(doc, method=None) -> None:
    """Compute the company warehouse stock snapshot server-side at save time.

    Replaces the old client-side refresh that rewrote the snapshot child table on
    every form open and dirtied the form (company-dependent — only companies with
    warehouse stock for the items were affected), which hid the Submit button.
    Computing here means the snapshot is a point-in-time value stored on save and
    never re-dirties the form when a draft is reopened.
    """
    has_table = bool(doc.meta.get_field("custom_warehouse_stock_snapshot"))
    item_meta = frappe.get_meta("Quotation Item")
    has_item_qty = bool(item_meta.get_field("custom_current_company_stock_qty"))
    if not has_table and not has_item_qty:
        return

    item_codes = sorted({
        (row.get("item_code") or "").strip()
        for row in (doc.get("items") or [])
        if (row.get("item_code") or "").strip()
    })
    company = (doc.get("company") or "").strip()

    if not item_codes or not company:
        if has_table:
            doc.set("custom_warehouse_stock_snapshot", [])
        if has_item_qty:
            for row in doc.get("items") or []:
                row.custom_current_company_stock_qty = 0
        return

    from orderlift.orderlift_sales.utils.item_price_tools import get_transaction_stock_snapshot

    snapshot = get_transaction_stock_snapshot(item_codes, company) or {}
    rows = snapshot.get("rows") or []
    totals = snapshot.get("totals") or {}

    if has_table:
        # IDEMPOTENT: only rebuild the child table when the stock data actually
        # changed. Rebuilding unconditionally assigns new child row names every
        # save, so the document is "modified" on every save and the form is
        # perpetually "Not Saved". Compare (item_code, warehouse, actual_qty).
        desired = [
            (r.get("item_code") or "", r.get("warehouse") or "", flt(r.get("actual_qty") or 0))
            for r in rows
        ]
        existing = [
            ((er.item_code or ""), (er.warehouse or ""), flt(er.actual_qty or 0))
            for er in (doc.get("custom_warehouse_stock_snapshot") or [])
        ]
        if desired != existing:
            doc.set("custom_warehouse_stock_snapshot", [])
            for row in rows:
                doc.append("custom_warehouse_stock_snapshot", {
                    "item_code": row.get("item_code") or "",
                    "item_name": row.get("item_name") or row.get("item_code") or "",
                    "warehouse": row.get("warehouse") or "",
                    "actual_qty": flt(row.get("actual_qty") or 0),
                })
    if has_item_qty:
        for row in doc.get("items") or []:
            new_qty = flt(totals.get((row.get("item_code") or "").strip(), 0))
            if flt(row.get("custom_current_company_stock_qty") or 0) != new_qty:
                row.custom_current_company_stock_qty = new_qty


def validate_quotation_item_discount_caps(doc, method=None) -> None:
    if can_override_quotation_pricing():
        return
    if not frappe.db.has_column("Quotation Item", "source_discount_percent"):
        return
    if not frappe.db.has_column("Quotation Item", "source_max_discount_percent"):
        return

    for row in doc.get("items") or []:
        discount = flt(row.get("source_discount_percent") or 0)
        max_discount = flt(row.get("source_max_discount_percent") or 0)
        if discount < 0:
            frappe.throw(
                _("Pricing Discount % cannot be negative on row {0}.").format(row.get("idx") or "-"),
            )
        if discount > max_discount + 0.000001:
            frappe.throw(
                _("Pricing Discount % cannot exceed {0}% for {1} on row {2}.").format(
                    max_discount,
                    row.get("item_code") or row.get("item_name") or "item",
                    row.get("idx") or "-",
                ),
            )
        _validate_row_rate_against_policy_snapshot(row, discount)


def _validate_row_rate_against_policy_snapshot(row, discount: float) -> None:
    gross_rate = flt(row.get("source_gross_sell_rate") or 0)
    if gross_rate <= 0:
        return
    expected_rate = gross_rate * (1 - (discount / 100.0))
    current_rate = flt(row.get("rate") or 0)
    if current_rate + 0.000001 >= expected_rate:
        return
    frappe.throw(
        _("Rate for {0} on row {1} is below the pricing policy net rate {2}.").format(
            row.get("item_code") or row.get("item_name") or "item",
            row.get("idx") or "-",
            _format_rate(expected_rate),
        )
    )


def _format_rate(value: float) -> str:
    return f"{flt(value):.2f}".rstrip("0").rstrip(".")


def protect_source_pricing_sheet_link(doc, method=None) -> None:
    if not doc.meta.get_field("source_pricing_sheet"):
        return
    if doc.is_new() or getattr(doc.flags, "allow_source_pricing_sheet_update", False):
        return
    old = (doc.get_doc_before_save().get("source_pricing_sheet") if doc.get_doc_before_save() else "") or ""
    current = (doc.get("source_pricing_sheet") or "").strip()
    if current != old:
        frappe.throw(
            "Pricing Sheet link is system-controlled. Open or create it from the Quotation action."
        )


def sync_quotation_selling_price_lists(doc, method=None) -> None:
    if not doc.meta.get_field("selected_selling_price_lists"):
        return

    company = (doc.get("company") or "").strip()
    rows = _valid_selection_rows(doc, company)
    if len(rows) != len([row for row in (doc.get("selected_selling_price_lists") or []) if (row.get("price_list") or "").strip()]):
        doc.set("selected_selling_price_lists", [])
        for row in rows:
            doc.append("selected_selling_price_lists", row)

    active_rows = [row for row in rows if int(row.get("is_active") or 0) == 1] or rows
    active_rows = sorted(active_rows, key=lambda row: (int(row.get("sequence") or 0) or 999999, row.get("idx") or 0))

    if not active_rows:
        if doc.meta.get_field("selling_price_list"):
            doc.selling_price_list = ""
        return

    primary_price_list = (active_rows[0].get("price_list") or "").strip()
    if doc.meta.get_field("selling_price_list"):
        doc.selling_price_list = primary_price_list


def _valid_selection_rows(doc, company: str) -> list[dict]:
    out = []
    seen = set()
    for row in doc.get("selected_selling_price_lists") or []:
        price_list = _visible_selling_price_list((row.get("price_list") or "").strip(), company)
        if not price_list or price_list in seen:
            continue
        seen.add(price_list)
        out.append(
            {
                "price_list": price_list,
                "sequence": int(row.get("sequence") or 10),
                "is_active": 1 if int(row.get("is_active") or 0) == 1 else 0,
            }
        )
    return out


def _visible_selling_price_list(price_list: str, company: str) -> str:
    if not price_list:
        return ""
    try:
        return validate_visible_price_list(price_list, kind="selling", required=False, company=company)
    except Exception:
        frappe.logger("orderlift").debug("Ignoring invalid Quotation selling price list %s", price_list)
        return ""


def _set_if_empty(doc, fieldname: str, value) -> None:
    if not value or not doc.meta.get_field(fieldname):
        return
    current = doc.get(fieldname)
    if isinstance(current, str):
        current = current.strip()
    if current not in (None, "", 0, 0.0):
        return
    doc.set(fieldname, value)
