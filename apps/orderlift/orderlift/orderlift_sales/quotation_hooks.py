from __future__ import annotations

from math import isfinite

import frappe
from frappe import _
from frappe.utils import add_days, flt, nowdate

try:
    from frappe.utils import cint
except ImportError:  # Unit tests may provide only a minimal frappe.utils stub.
    def cint(value=0):
        return int(value or 0)

from orderlift.orderlift_crm.party_propagation import apply_party_context_to_quotation, resolve_party_context
from orderlift.orderlift_sales.utils.sales_team import primary_sales_person
from orderlift.orderlift_sales.utils.price_list_usage_guard import reprice_quotation_items_from_selected_price_lists
from orderlift.orderlift_sales.utils.price_list_scope import can_override_quotation_pricing, validate_visible_price_list
from orderlift.orderlift_sales.utils.tax_inclusive import (
    apply_quotation_sales_tax_template,
    sync_quotation_item_tax_inclusive_fields,
)
from orderlift.role_capabilities import CAPABILITY_COMMISSION_ASSIGNMENT_MANAGEMENT, user_has_capability
from orderlift.sales.utils.pricing_projection import calculate_agent_commission


OTHER_CHARGE_ITEM_CODE = "OTHER-CHARGES"
CAPABILITY_PRIVILEGED_PRICING = "privileged_pricing"
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
def get_other_charge_template(other_charge: str, company: str | None = None) -> dict:
    if not frappe.has_permission("Quotation", "create") and not frappe.has_permission("Quotation", "write"):
        frappe.throw(_("Not permitted to add other charges."), frappe.PermissionError)

    other_charge = (other_charge or "").strip()
    if not other_charge:
        frappe.throw(_("Select an other charge."))
    if not frappe.db.exists("Orderlift Other Charge", other_charge):
        frappe.throw(_("Other charge {0} was not found.").format(other_charge))

    template = _other_charge_template_values(other_charge)
    item_defaults = get_other_charge_item(company=company)
    result = {
        "other_charge": other_charge,
        "description": template.get("description") or item_defaults.get("description") or other_charge,
        "uom": template.get("uom") or item_defaults.get("uom") or _default_service_uom(),
        "rate": flt(template.get("rate")),
        "item_code": template.get("item_code") or item_defaults.get("item_code") or OTHER_CHARGE_ITEM_CODE,
        "item_name": item_defaults.get("item_name") or _("Other Charges"),
    }
    if user_has_capability(CAPABILITY_PRIVILEGED_PRICING):
        result["expected_unit_cost"] = flt(template.get("expected_unit_cost"))
    return result


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
    if int(doc.get("docstatus") or 0) != 0:
        return
    if not doc.get("valid_till"):
        doc.valid_till = add_days(nowdate(), 15)

    party_type = (doc.get("quotation_to") or "").strip()
    party_name = (doc.get("party_name") or "").strip()
    if party_type not in {"Customer", "Prospect", "Lead"} or not party_name:
        return

    defaults = resolve_party_context(party_type, party_name, source_doc=doc) or {}
    apply_party_context_to_quotation(doc, defaults)
    if doc.meta.get_field("custom_customer_tax_id"):
        doc.custom_customer_tax_id = defaults.get("tax_id") or ""


def sync_quotation_opportunity_snapshot(doc, method=None) -> None:
    if not doc or not getattr(doc, "meta", None):
        return
    if not doc.meta.get_field("custom_opportunity_title") and not doc.meta.get_field("custom_opportunity_owner"):
        return

    opportunity = (doc.get("opportunity") or "").strip()
    values = {}
    if opportunity and frappe.db.exists("Opportunity", opportunity):
        values = frappe.db.get_value("Opportunity", opportunity, ["title", "opportunity_owner", "owner"], as_dict=True) or {}

    if doc.meta.get_field("custom_opportunity_title"):
        doc.custom_opportunity_title = values.get("title") or ""
    if doc.meta.get_field("custom_opportunity_owner"):
        doc.custom_opportunity_owner = values.get("opportunity_owner") or values.get("owner") or ""


def sync_quotation_other_charges(doc, method=None) -> None:
    if not doc or not getattr(doc, "meta", None) or not doc.meta.get_field("custom_other_charges"):
        return
    if not frappe.db.has_column("Quotation Item", "custom_orderlift_other_charge"):
        return

    charges = _normalized_other_charge_rows(doc)
    items = [row for row in (doc.get("items") or []) if not flt(row.get("custom_orderlift_other_charge"))]
    doc.set("items", items)
    if not charges:
        return

    item_defaults = get_other_charge_item(company=doc.get("company"))
    for charge in charges:
        item_code = charge.get("item_code") or item_defaults.get("item_code") or OTHER_CHARGE_ITEM_CODE
        description = charge.get("description") or item_defaults.get("description") or _("Other Charges")
        qty = flt(charge.get("qty") or 1) or 1
        rate = flt(charge.get("rate"))
        expected_unit_cost = flt(charge.get("expected_unit_cost"))
        amount = flt(qty * rate)
        row = doc.append(
            "items",
            {
                "item_code": item_code,
                "item_name": description,
                "description": description,
                "qty": qty,
                "stock_uom": charge.get("uom") or item_defaults.get("uom") or _default_service_uom(),
                "uom": charge.get("uom") or item_defaults.get("uom") or _default_service_uom(),
                "conversion_factor": 1,
                "price_list_rate": rate,
                "base_price_list_rate": rate,
                "rate": rate,
                "base_rate": rate,
                "amount": amount,
                "base_amount": amount,
                "net_rate": rate,
                "net_amount": amount,
                "base_net_rate": rate,
                "base_net_amount": amount,
                "discount_percentage": 0,
                "custom_presentation_role": "Print separately",
                "custom_orderlift_other_charge": 1,
            },
        )
        for fieldname, value in {
            "source_price_list_sell_rate": rate,
            "source_discount_percent": 0,
            "source_max_discount_percent": 0,
            "source_discount_amount": 0,
            "source_landed_cost": expected_unit_cost,
        }.items():
            if row.meta.get_field(fieldname):
                row.set(fieldname, value)
        if row.meta.get_field("ignore_pricing_rule"):
            row.ignore_pricing_rule = 1


def sync_quotation_pricing_snapshot_fields(doc, method=None) -> None:
    resolve_quotation_commission_context(doc)
    sync_quotation_item_price_input_fields(doc)
    reprice_quotation_items_from_selected_price_lists(doc)
    sync_quotation_item_price_input_fields(doc)
    apply_quotation_sales_tax_template(doc)
    sync_quotation_item_tax_inclusive_fields(doc)


def _normalized_other_charge_rows(doc) -> list[dict]:
    rows = []
    can_edit_cost = user_has_capability(CAPABILITY_PRIVILEGED_PRICING)
    previous = doc.get_doc_before_save() if hasattr(doc, "get_doc_before_save") else None
    previous_values = {
        row.get("name"): {
            "other_charge": (row.get("other_charge") or "").strip(),
            "expected_unit_cost": row.get("expected_unit_cost"),
        }
        for row in (previous.get("custom_other_charges") if previous else []) or []
        if row.get("name")
    }
    for charge in doc.get("custom_other_charges") or []:
        other_charge = (charge.get("other_charge") or "").strip()
        if not other_charge or not frappe.db.exists("Orderlift Other Charge", other_charge):
            frappe.throw(_("Select a valid saved Other Charge."))
        template = _other_charge_template_values(other_charge)
        description = (charge.get("description") or "").strip() or template.get("description") or _("Other Charges")
        qty = flt(charge.get("qty") or 0)
        rate = flt(charge.get("rate") if charge.get("rate") is not None else template.get("rate"))
        previous_value = previous_values.get(charge.get("name")) or {}
        template_changed = previous_value and previous_value.get("other_charge") != other_charge
        if can_edit_cost and not (
            template_changed
            and flt(charge.get("expected_unit_cost")) == flt(previous_value.get("expected_unit_cost"))
        ):
            raw_expected_cost = charge.get("expected_unit_cost")
        elif not template_changed and previous_value:
            raw_expected_cost = previous_value.get("expected_unit_cost")
        else:
            raw_expected_cost = template.get("expected_unit_cost")
        expected_unit_cost = flt(
            template.get("expected_unit_cost") if raw_expected_cost in (None, "") else raw_expected_cost
        )
        uom = (charge.get("uom") or "").strip() or template.get("uom")
        item_code = template.get("item_code") or OTHER_CHARGE_ITEM_CODE
        if qty <= 0:
            frappe.throw(_("Other charge quantity must be greater than zero: {0}").format(description))
        if rate < 0:
            frappe.throw(_("Other charge amount cannot be negative: {0}").format(description))
        if expected_unit_cost < 0:
            frappe.throw(_("Other charge expected cost cannot be negative: {0}").format(description))
        amount = flt(qty * rate)
        expected_cost = flt(qty * expected_unit_cost)
        charge.description = description
        charge.qty = qty
        charge.uom = uom
        charge.rate = rate
        charge.amount = amount
        charge.expected_unit_cost = expected_unit_cost
        charge.expected_cost = expected_cost
        charge.item_code = item_code
        rows.append(
            {
                "other_charge": other_charge,
                "description": description,
                "qty": qty,
                "uom": uom,
                "rate": rate,
                "amount": amount,
                "expected_unit_cost": expected_unit_cost,
                "expected_cost": expected_cost,
                "item_code": item_code,
            }
        )
    return rows


def _other_charge_template_values(other_charge: str | None) -> dict:
    other_charge = (other_charge or "").strip()
    if not other_charge or not frappe.db.exists("DocType", "Orderlift Other Charge"):
        return {}
    if not frappe.db.exists("Orderlift Other Charge", other_charge):
        return {}
    values = frappe.db.get_value(
        "Orderlift Other Charge",
        other_charge,
        ["description", "default_uom", "default_rate", "default_expected_unit_cost", "item_code", "disabled"],
        as_dict=True,
    ) or {}
    if values.get("disabled"):
        frappe.throw(_("Other charge {0} is disabled.").format(other_charge))
    return {
        "description": values.get("description") or other_charge,
        "uom": values.get("default_uom") or "",
        "rate": flt(values.get("default_rate")),
        "expected_unit_cost": flt(values.get("default_expected_unit_cost")),
        "item_code": values.get("item_code") or "",
    }


def resolve_quotation_commission_context(doc, method=None) -> str:
    """Resolve one auditable salesperson/rate for Pricing Sheet and direct quotes."""
    source_pricing_sheet = (doc.get("source_pricing_sheet") or "").strip()
    selected = (doc.get("commission_sales_person") or "").strip()
    team = doc.get("custom_sales_team") if doc.meta.get_field("custom_sales_team") else []
    snapshot_people = {
        (row.get("source_sales_person") or "").strip()
        for row in (doc.get("items") or [])
        if (row.get("source_sales_person") or "").strip()
    }

    if team:
        sales_person = primary_sales_person(team)
    elif source_pricing_sheet:
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
    if not rule:
        return 0.0
    rate = frappe.db.get_value("Agent Pricing Rules", rule, "commission_rate") or 0
    if frappe.db.has_column("Agent Pricing Rules", "commission_enabled") and not cint(
        frappe.db.get_value("Agent Pricing Rules", rule, "commission_enabled")
    ):
        return 0.0
    return flt(rate)


def _can_assign_any_commission_salesperson() -> bool:
    return user_has_capability(CAPABILITY_COMMISSION_ASSIGNMENT_MANAGEMENT)


def sync_quotation_item_price_input_fields(doc, method=None) -> None:
    """Keep direct Quotation price-input fields consistent before validation.

    Native rate/amount are the canonical HT values. Discount inputs are accepted
    on drafts and translated back to rate; TTC is always derived separately.
    """
    previous_rows = _quotation_item_rows_before_save(doc)
    for row in doc.get("items") or []:
        list_rate = flt(
            row.get("source_price_list_sell_rate")
            or row.get("price_list_rate")
            or 0
        )
        current_rate = flt(row.get("rate") or 0)
        if list_rate <= 0 and _is_valid_new_row_rate(row.get("rate")):
            list_rate = current_rate
        if list_rate <= 0:
            continue
        if row.meta.get_field("source_price_list_sell_rate"):
            list_rate = flt(list_rate, row.precision("source_price_list_sell_rate"))
            row.source_price_list_sell_rate = list_rate

        previous_row = previous_rows.get((row.get("name") or "").strip())
        current_rate = _resolve_changed_quotation_price_input(
            row,
            previous_row,
            list_rate,
            current_rate,
        )
        qty = flt(row.get("qty") or 0)
        current_rate = flt(max(current_rate, 0), row.precision("rate"))
        if current_rate >= list_rate:
            discount = 0.0
            discount_amount = 0.0
        else:
            discount_amount = max(list_rate - current_rate, 0)
            discount = (discount_amount / list_rate) * 100.0

        conversion_rate = flt(doc.get("conversion_rate") or 1) or 1
        row.rate = current_rate
        row.amount = flt(current_rate * qty, row.precision("amount"))
        _set_rounded_if_field(row, "price_list_rate", list_rate)
        _set_rounded_if_field(row, "base_price_list_rate", list_rate * conversion_rate)
        _set_rounded_if_field(row, "base_rate", current_rate * conversion_rate)
        _set_rounded_if_field(row, "net_rate", current_rate)
        _set_rounded_if_field(row, "base_net_rate", current_rate * conversion_rate)
        _set_rounded_if_field(row, "net_amount", current_rate * qty)
        _set_rounded_if_field(row, "base_amount", current_rate * qty * conversion_rate)
        _set_rounded_if_field(row, "base_net_amount", current_rate * qty * conversion_rate)
        _set_rounded_if_field(row, "discount_amount", discount_amount)
        if row.meta.get_field("discount_percentage"):
            row.discount_percentage = flt(discount, row.precision("discount_percentage"))
        if row.meta.get_field("source_discount_percent"):
            row.source_discount_percent = flt(discount, row.precision("source_discount_percent"))
        if row.meta.get_field("source_discount_amount"):
            row.source_discount_amount = flt(
                discount_amount,
                row.precision("source_discount_amount"),
            )
        if row.meta.get_field("source_commission_amount"):
            max_discount = flt(row.get("source_max_discount_percent") or 0)
            commission_rate = flt(row.get("source_commission_rate") or 0)
            try:
                commission = calculate_agent_commission(
                    price_list_unit_price=list_rate,
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


def _quotation_item_rows_before_save(doc) -> dict[str, object]:
    get_before = getattr(doc, "get_doc_before_save", None)
    if not callable(get_before):
        return {}
    before = get_before()
    if not before:
        return {}
    get = getattr(before, "get", None)
    items = get("items") if callable(get) else getattr(before, "items", None)
    return {
        (row.get("name") or "").strip(): row
        for row in (items or [])
        if (row.get("name") or "").strip()
    }


def _resolve_changed_quotation_price_input(row, previous_row, list_rate: float, current_rate: float) -> float:
    """Resolve the last changed canonical/helper input into native rate."""
    if not previous_row:
        discount_amount = max(flt(row.get("source_discount_amount") or 0), 0)
        if discount_amount > 0:
            return max(list_rate - discount_amount, 0)
        discount = max(flt(row.get("source_discount_percent") or 0), 0)
        if discount > 0:
            return max(list_rate * (1 - (discount / 100.0)), 0)
        if _is_valid_new_row_rate(row.get("rate")):
            return current_rate
        return list_rate

    changed_inputs = [
        fieldname
        for fieldname in ("rate", "source_discount_percent", "source_discount_amount")
        if _numeric_row_field_changed(row, previous_row, fieldname)
    ]
    if not changed_inputs:
        return current_rate
    if "rate" in changed_inputs and current_rate >= list_rate:
        return current_rate

    last_changed = changed_inputs[-1]
    if last_changed == "source_discount_amount":
        discount_amount = max(flt(row.get("source_discount_amount") or 0), 0)
        return max(list_rate - discount_amount, 0)
    if last_changed == "source_discount_percent":
        discount = max(flt(row.get("source_discount_percent") or 0), 0)
        return max(list_rate * (1 - (discount / 100.0)), 0)
    return max(current_rate, 0)


def _numeric_row_field_changed(row, previous_row, fieldname: str) -> bool:
    return (
        abs(flt(row.get(fieldname) or 0) - flt(previous_row.get(fieldname) or 0))
        > _field_tolerance(fieldname, row, previous_row)
    )


def _is_valid_new_row_rate(value) -> bool:
    try:
        return isfinite(float(value)) and float(value) > 0
    except (TypeError, ValueError):
        return False


def _field_tolerance(fieldname: str, *rows) -> float:
    precisions = []
    for row in rows:
        precision = getattr(row, "precision", None)
        if not callable(precision):
            continue
        try:
            precisions.append(int(precision(fieldname)))
        except (TypeError, ValueError):
            continue
    precision = max(precisions or [9])
    return min(1e-9, 10 ** (-precision))


def _set_rounded_if_field(row, fieldname: str, value: float) -> None:
    if not row.meta.get_field(fieldname):
        return
    rounded = flt(value, row.precision(fieldname))
    setter = getattr(row, "set", None)
    if callable(setter):
        setter(fieldname, rounded)
    else:
        setattr(row, fieldname, rounded)


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
        if discount > max_discount + _field_tolerance("source_discount_percent", row):
            frappe.throw(
                _("Pricing Discount % cannot exceed {0}% for {1} on row {2}.").format(
                    max_discount,
                    row.get("item_code") or row.get("item_name") or "item",
                    row.get("idx") or "-",
                ),
            )
        _validate_row_rate_against_policy_snapshot(row, discount)


def _validate_row_rate_against_policy_snapshot(row, discount: float) -> None:
    list_rate = flt(row.get("source_price_list_sell_rate") or 0)
    if list_rate <= 0:
        return
    expected_rate = list_rate * (1 - (discount / 100.0))
    current_rate = flt(row.get("rate") or 0)
    if current_rate + _field_tolerance("rate", row) >= expected_rate:
        return
    frappe.throw(
        _("Rate for {0} on row {1} is below the pricing policy rate {2}.").format(
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
