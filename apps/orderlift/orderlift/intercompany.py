from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime, today


ORDERLIFT_PARENT_COMPANY = "Orderlift"
REPORTING_COMPANY_FIELD = "custom_orderlift_reporting_company"
INTERNAL_PARTY_TAG = "Orderlift Internal Party"


@frappe.whitelist()
def ensure_internal_orderlift_parties(dry_run: int = 1, companies=None, parent_company: str = ORDERLIFT_PARENT_COMPANY) -> dict:
    frappe.only_for(["System Manager", "Orderlift Admin"])
    dry_run = int(dry_run or 0)
    operating_companies = _operating_companies(companies=companies, parent_company=parent_company)
    summary = {
        "dry_run": bool(dry_run),
        "parent_company": parent_company,
        "companies": list(operating_companies),
        "customers_created": 0,
        "customers_updated": 0,
        "suppliers_created": 0,
        "suppliers_updated": 0,
        "tagged": 0,
        "skipped": [],
    }

    companies = summary["companies"]
    for represented_company in companies:
        allowed_companies = [company for company in companies if company != represented_company]
        _ensure_internal_customer(represented_company, allowed_companies, summary, dry_run=dry_run)
        _ensure_internal_supplier(represented_company, allowed_companies, summary, dry_run=dry_run)

    if not dry_run:
        frappe.db.commit()
        frappe.clear_cache(doctype="Customer")
        frappe.clear_cache(doctype="Supplier")
    return summary


def create_draft_sales_order_from_purchase_order(doc, method=None) -> str | None:
    if not doc or doc.doctype != "Purchase Order":
        return None
    # Runs from the Purchase Order's on_submit hook, so only a submitted PO
    # qualifies. The Sales Order it creates is still a draft in the other company.
    if int(doc.get("docstatus") or 0) != 1:
        return None
    if doc.get("inter_company_order_reference"):
        return doc.get("inter_company_order_reference")
    if not doc.get("supplier") or not int(doc.get("is_internal_supplier") or 0):
        return None

    source_company = (doc.get("company") or "").strip()
    target_company = (doc.get("represents_company") or "").strip()
    if not source_company or not target_company or source_company == target_company:
        return None
    if not _is_orderlift_operating_company(source_company) or not _is_orderlift_operating_company(target_company):
        return None
    if _existing_sales_order_for_purchase_order(doc.name):
        sales_order = _existing_sales_order_for_purchase_order(doc.name)
        doc.db_set("inter_company_order_reference", sales_order, update_modified=False)
        return sales_order

    customer = _internal_customer_for_company_pair(target_company, source_company)
    if not customer:
        frappe.throw(
            _(
                "Missing internal Customer in {0} representing {1}. Run setup_internal_orderlift_parties first."
            ).format(target_company, source_company)
        )
    if not _party_allowed_to_transact("Customer", customer, target_company):
        frappe.throw(
            _("Internal Customer {0} is not allowed to transact with {1}.").format(customer, target_company)
        )

    sales_order = frappe.new_doc("Sales Order")
    sales_order.flags.ignore_permissions = True
    sales_order.flags.ignore_orderlift_company_scope = True
    sales_order.company = target_company
    sales_order.customer = customer
    sales_order.is_internal_customer = 1
    sales_order.represents_company = source_company
    sales_order.inter_company_order_reference = doc.name
    sales_order.po_no = doc.name
    sales_order.transaction_date = doc.get("transaction_date") or today()
    _set_sales_order_currency_and_price_list(sales_order, doc)
    _copy_purchase_order_items(sales_order, doc)
    sales_order.run_method("set_missing_values")
    sales_order.insert(ignore_permissions=True)

    doc.db_set("inter_company_order_reference", sales_order.name, update_modified=False)
    sales_order.add_comment(
        "Comment",
        _("Draft Sales Order created automatically from internal Purchase Order {0}.").format(doc.name),
    )
    return sales_order.name


def _operating_companies(companies=None, parent_company: str = ORDERLIFT_PARENT_COMPANY) -> tuple[str, ...]:
    explicit = _parse_company_list(companies)
    if explicit:
        return _valid_operating_companies(explicit)

    fields = ["name", "is_group"]
    if _doctype_has_field("Company", "parent_company"):
        fields.append("parent_company")
    if _doctype_has_field("Company", REPORTING_COMPANY_FIELD):
        fields.append(REPORTING_COMPANY_FIELD)

    rows = frappe.get_all("Company", fields=fields, order_by="name", limit_page_length=0)
    parents = {row.name: (row.get("parent_company") or "") for row in rows}
    names = []
    for row in rows:
        if int(row.get("is_group") or 0):
            continue
        if row.name == parent_company:
            continue
        if row.get(REPORTING_COMPANY_FIELD) or _is_descendant_company(row.name, parent_company, parents):
            names.append(row.name)
    return tuple(dict.fromkeys(names))


def _is_orderlift_operating_company(company: str) -> bool:
    return company in set(_operating_companies())


def _parse_company_list(companies) -> list[str]:
    if not companies:
        return []
    if isinstance(companies, str):
        return [company.strip() for company in companies.split(",") if company.strip()]
    return [str(company).strip() for company in companies if str(company).strip()]


def _valid_operating_companies(companies: list[str]) -> tuple[str, ...]:
    valid = []
    for company in companies:
        if not frappe.db.exists("Company", company):
            frappe.throw(_("Company {0} was not found.").format(company))
        if int(frappe.db.get_value("Company", company, "is_group") or 0):
            frappe.throw(_("Company {0} is a group company and cannot be used for intercompany trading.").format(company))
        valid.append(company)
    return tuple(dict.fromkeys(valid))


def _is_descendant_company(company: str, parent_company: str, parents: dict[str, str]) -> bool:
    seen = set()
    current = parents.get(company)
    while current and current not in seen:
        if current == parent_company:
            return True
        seen.add(current)
        current = parents.get(current)
    return False


def _ensure_internal_customer(represented_company: str, allowed_companies: list[str], summary: dict, dry_run: int = 1) -> str | None:
    existing = _internal_customer_for_represented_company(represented_company)
    if dry_run:
        if existing:
            summary["customers_updated"] += 1
            return existing
        summary["customers_created"] += 1
        return None

    doc = frappe.get_doc("Customer", existing) if existing else frappe.new_doc("Customer")
    if not existing:
        doc.customer_name = _party_name(represented_company)
    doc.customer_type = "Company"
    doc.customer_group = _default_customer_group()
    doc.territory = _default_territory()
    _set_if_field(doc, "custom_company", represented_company)
    _set_if_field(doc, "is_internal_customer", 1)
    _set_if_field(doc, "represents_company", represented_company)
    _set_if_field(doc, "default_currency", _company_currency(represented_company))
    _remove_internal_company_access(doc, [represented_company])
    _ensure_internal_company_access(doc, allowed_companies)
    _ensure_allowed_companies(doc, allowed_companies)
    doc.flags.ignore_permissions = True
    doc.flags.ignore_orderlift_company_scope = True
    doc.save(ignore_permissions=True) if existing else doc.insert(ignore_permissions=True)
    doc = _ensure_canonical_internal_party_name("Customer", doc, represented_company, summary, dry_run=dry_run)
    _tag_internal_party("Customer", doc.name, summary)
    summary["customers_updated" if existing else "customers_created"] += 1
    return doc.name


def _ensure_internal_supplier(represented_company: str, allowed_companies: list[str], summary: dict, dry_run: int = 1) -> str | None:
    existing = _internal_supplier_for_represented_company(represented_company)
    if dry_run:
        if existing:
            summary["suppliers_updated"] += 1
            return existing
        summary["suppliers_created"] += 1
        return None

    doc = frappe.get_doc("Supplier", existing) if existing else frappe.new_doc("Supplier")
    if not existing:
        doc.supplier_name = _party_name(represented_company)
    doc.supplier_type = "Company"
    doc.supplier_group = _default_supplier_group()
    _set_if_field(doc, "custom_company", represented_company)
    _set_if_field(doc, "is_internal_supplier", 1)
    _set_if_field(doc, "represents_company", represented_company)
    _set_if_field(doc, "default_currency", _company_currency(represented_company))
    _remove_internal_company_access(doc, [represented_company])
    _ensure_internal_company_access(doc, allowed_companies)
    _ensure_allowed_companies(doc, allowed_companies)
    doc.flags.ignore_permissions = True
    doc.flags.ignore_orderlift_company_scope = True
    doc.save(ignore_permissions=True) if existing else doc.insert(ignore_permissions=True)
    doc = _ensure_canonical_internal_party_name("Supplier", doc, represented_company, summary, dry_run=dry_run)
    _tag_internal_party("Supplier", doc.name, summary)
    summary["suppliers_updated" if existing else "suppliers_created"] += 1
    return doc.name


def _internal_customer_for_company_pair(owner_company: str, represented_company: str) -> str | None:
    customer = _internal_customer_for_represented_company(represented_company)
    if customer and _party_allowed_to_transact("Customer", customer, owner_company):
        return customer
    return None


def _internal_customer_for_represented_company(represented_company: str) -> str | None:
    filters = {"is_internal_customer": 1, "represents_company": represented_company}
    return frappe.db.get_value("Customer", filters, "name")


def _internal_supplier_for_represented_company(represented_company: str) -> str | None:
    filters = {"is_internal_supplier": 1, "represents_company": represented_company}
    return frappe.db.get_value("Supplier", filters, "name")


def _existing_sales_order_for_purchase_order(purchase_order: str) -> str | None:
    return frappe.db.get_value(
        "Sales Order",
        {"inter_company_order_reference": purchase_order, "docstatus": ["<", 2]},
        "name",
    )


def _set_sales_order_currency_and_price_list(sales_order, purchase_order) -> None:
    currency = purchase_order.get("currency") or _company_currency(sales_order.company)
    if sales_order.meta.get_field("currency"):
        sales_order.currency = currency
    if sales_order.meta.get_field("conversion_rate"):
        sales_order.conversion_rate = 1 if currency == _company_currency(sales_order.company) else flt(purchase_order.get("conversion_rate")) or 1

    price_list = _selling_price_list_for_order(purchase_order, sales_order.company)
    if price_list and sales_order.meta.get_field("selling_price_list"):
        sales_order.selling_price_list = price_list
    if currency and sales_order.meta.get_field("price_list_currency"):
        sales_order.price_list_currency = currency


def _selling_price_list_for_order(purchase_order, company: str) -> str | None:
    buying_price_list = (purchase_order.get("buying_price_list") or "").strip()
    if buying_price_list:
        # A disabled list reused here fails the downstream enabled check in
        # validate_price_list_scope and surfaces as "unavailable or not permitted".
        values = frappe.db.get_value("Price List", buying_price_list, ["selling", "enabled"], as_dict=True) or {}
        if cint(values.get("selling")) and cint(values.get("enabled")):
            return buying_price_list

    filters = {"selling": 1, "enabled": 1}
    if _doctype_has_field("Price List", "custom_company"):
        company_list = frappe.db.get_value("Price List", {**filters, "custom_company": company}, "name")
        if company_list:
            return company_list
    return frappe.db.get_value("Price List", filters, "name")


def _copy_purchase_order_items(sales_order, purchase_order) -> None:
    for row in purchase_order.get("items") or []:
        if not row.get("item_code") or flt(row.get("qty")) <= 0:
            continue
        sales_order.append(
            "items",
            {
                "item_code": row.get("item_code"),
                "item_name": row.get("item_name"),
                "description": row.get("description"),
                "qty": row.get("qty"),
                "uom": row.get("uom"),
                "stock_uom": row.get("stock_uom"),
                "conversion_factor": row.get("conversion_factor") or 1,
                "rate": row.get("rate"),
                "delivery_date": row.get("schedule_date") or purchase_order.get("schedule_date") or today(),
                "purchase_order": purchase_order.name,
                "purchase_order_item": row.get("name"),
                "material_request": row.get("material_request"),
                "material_request_item": row.get("material_request_item"),
            },
        )


def _ensure_allowed_companies(doc, companies: list[str]) -> None:
    if not doc.meta.get_field("companies"):
        return
    for company in companies:
        _ensure_allowed_company(doc, company)


def _ensure_allowed_company(doc, company: str) -> None:
    for row in doc.get("companies") or []:
        if (row.get("company") or "").strip() == company:
            return
    doc.append("companies", {"company": company})


def _remove_internal_company_access(doc, companies: list[str]) -> None:
    if not doc.meta.get_field("custom_internal_company_access"):
        return
    remove = {company for company in companies if company}
    for row in list(doc.get("custom_internal_company_access") or []):
        if (row.get("company") or "").strip() in remove:
            doc.remove(row)


def _ensure_internal_company_access(doc, companies: list[str]) -> None:
    if not doc.meta.get_field("custom_internal_company_access"):
        return
    seen = {
        (row.get("company") or "").strip()
        for row in doc.get("custom_internal_company_access") or []
        if (row.get("company") or "").strip()
    }
    for company in dict.fromkeys(company for company in companies if company):
        if company in seen:
            continue
        doc.append(
            "custom_internal_company_access",
            {
                "company": company,
                "is_primary": 0,
                "approved_by": frappe.session.user,
                "approved_on": now_datetime(),
            },
        )
        seen.add(company)


def _ensure_canonical_internal_party_name(doctype: str, doc, represented_company: str, summary: dict, *, dry_run: int = 1):
    target_name = _party_name(represented_company)
    if doc.name == target_name:
        return doc
    if frappe.db.exists(doctype, target_name):
        summary.setdefault("skipped", []).append(
            {
                "doctype": doctype,
                "name": doc.name,
                "reason": "canonical_name_exists",
                "target_name": target_name,
            }
        )
        return doc
    if dry_run:
        return doc
    renamed = frappe.rename_doc(doctype, doc.name, target_name, force=True, merge=False, show_alert=False)
    return frappe.get_doc(doctype, renamed)


def _party_allowed_to_transact(doctype: str, party: str, company: str) -> bool:
    return bool(
        frappe.db.exists(
            "Allowed To Transact With",
            {"parenttype": doctype, "parent": party, "company": company},
        )
    )


def _tag_internal_party(doctype: str, name: str, summary: dict | None = None) -> None:
    from frappe.desk.doctype.tag.tag import add_tag

    add_tag(INTERNAL_PARTY_TAG, doctype, name)
    if summary is not None:
        summary["tagged"] = int(summary.get("tagged") or 0) + 1


def _set_if_field(doc, fieldname: str, value) -> None:
    if doc.meta.get_field(fieldname):
        doc.set(fieldname, value)


def _doctype_has_field(doctype: str, fieldname: str) -> bool:
    return bool(frappe.get_meta(doctype).get_field(fieldname))


def _party_name(represented_company: str) -> str:
    return represented_company


def _company_currency(company: str) -> str:
    return frappe.db.get_value("Company", company, "default_currency") or frappe.defaults.get_global_default("currency")


def _default_customer_group() -> str:
    if frappe.db.exists("Customer Group", "All Customer Groups") and not int(
        frappe.db.get_value("Customer Group", "All Customer Groups", "is_group") or 0
    ):
        return "All Customer Groups"
    return frappe.db.get_value("Customer Group", {"is_group": 0}, "name") or frappe.db.get_value("Customer Group", {}, "name")


def _default_supplier_group() -> str:
    return frappe.db.get_value("Supplier Group", {"is_group": 0}, "name") or frappe.db.get_value("Supplier Group", {}, "name")


def _default_territory() -> str:
    return frappe.db.get_value("Territory", {"is_group": 0}, "name") or frappe.db.get_value("Territory", {}, "name") or "All Territories"
