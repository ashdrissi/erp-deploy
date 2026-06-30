from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint

from orderlift.company_scope import business_type_field_for, company_field_for, segments_field_for
from orderlift.menu_access import (
    get_all_companies,
    get_allowed_business_types,
    get_allowed_companies,
    resolve_current_company,
    user_can_access_all_business_types,
    user_can_access_all_companies,
)
from orderlift.orderlift_sales.utils.price_list_scope import (
    BENCHMARK_PRICE_LIST,
    BUYING_PRICE_LIST,
    PRICE_LIST_TYPE_FIELD,
    SELLING_PRICE_LIST,
    get_price_list_type,
    get_visible_price_lists,
)
from orderlift.startup_roles import COMMISSION_MANAGER_ROLE


SEGMENT_ASSIGNMENT_DOCTYPE = "CRM Segment Assignment"


COMPANY_SCOPED_DOCTYPES = [
    "Company",
    "Opportunity",
    "Quotation",
    "Sales Order",
    "Sales Invoice",
    "Purchase Order",
    "Purchase Receipt",
    "Purchase Invoice",
    "Delivery Note",
    "Payment Entry",
    "Stock Entry",
    "Material Request",
    "Request for Quotation",
    "Project",
    "Sales Commission",
    "SAV Ticket",
    "Forecast Load Plan",
    # Company-owned masters / operational records (see orderlift.company_scope).
    "Customer",
    "Supplier",
    "Price List",
    "Prospect",
    "Lead",
    "Pricing Sheet",
    "Pricing Scenario",
    "Pricing Benchmark Policy",
    "Pricing Customs Policy",
    "Customer Segmentation Engine",
    "Partner Campaign",
    "Portal Customer Group Policy",
    "Portal Quote Request",
]
ORDERLIFT_MANAGED_PERMISSION_DOCTYPES = tuple(COMPANY_SCOPED_DOCTYPES)
ORDERLIFT_MANAGED_SHARE_DISABLED_DOCTYPES = tuple(
    dict.fromkeys((*ORDERLIFT_MANAGED_PERMISSION_DOCTYPES, "Partner Campaign Target"))
)

READ_ONLY_PERMISSION_TYPES = {"read", "report", "print", "email"}
OWNED_ONLY_USER_FIELD = "custom_owned_documents_only"


def has_company_permission(
    doc,
    ptype: str | None = None,
    user: str | None = None,
    permission_type: str | None = None,
) -> bool | None:
    permission_type = permission_type or ptype
    user = user or frappe.session.user
    if user_can_access_all_companies(user):
        return True
    if not doc:
        return None

    if getattr(doc, "doctype", None) == "Price List":
        if not _price_list_shared_edit_allowed(doc, user, permission_type):
            return False
        return True if _price_list_doc_allowed(doc, user, permission_type=permission_type) else False

    if getattr(doc, "doctype", None) == "Sales Commission" and not _can_manage_sales_commissions(user):
        if permission_type and permission_type not in READ_ONLY_PERMISSION_TYPES:
            return False
        salesperson = _sales_person_for_user(user)
        if not salesperson or doc.get("salesperson") != salesperson:
            return False

    if getattr(doc, "doctype", None) == "SAV Ticket":
        if not _sav_ticket_company_allowed(doc, user, permission_type):
            return False
    elif not _doc_company_allowed(doc, user, permission_type):
        return False
    if not _doc_business_type_allowed(doc, user):
        return False
    if not _doc_owned_scope_allowed(doc, user):
        return False
    # Frappe document-level controller hooks must return True when custom
    # checks pass; role permissions are still evaluated after this hook.
    return True


def company_query(user: str | None = None) -> str | None:
    return _company_query("Company", user=user)


def opportunity_query(user: str | None = None) -> str | None:
    return _company_query("Opportunity", user=user)


def quotation_query(user: str | None = None) -> str | None:
    return _company_query("Quotation", user=user)


def sales_order_query(user: str | None = None) -> str | None:
    return _company_query("Sales Order", user=user)


def sales_invoice_query(user: str | None = None) -> str | None:
    return _company_query("Sales Invoice", user=user)


def purchase_order_query(user: str | None = None) -> str | None:
    return _company_query("Purchase Order", user=user)


def purchase_receipt_query(user: str | None = None) -> str | None:
    return _company_query("Purchase Receipt", user=user)


def purchase_invoice_query(user: str | None = None) -> str | None:
    return _company_query("Purchase Invoice", user=user)


def delivery_note_query(user: str | None = None) -> str | None:
    return _company_query("Delivery Note", user=user)


def payment_entry_query(user: str | None = None) -> str | None:
    return _company_query("Payment Entry", user=user)


def stock_entry_query(user: str | None = None) -> str | None:
    company_clause = _company_query("Stock Entry", user=user)
    from orderlift.warehouse_access import stock_entry_query_clause

    warehouse_clause = stock_entry_query_clause(user=user)
    if company_clause and warehouse_clause:
        return f"({company_clause}) and ({warehouse_clause})"
    return company_clause or warehouse_clause


def material_request_query(user: str | None = None) -> str | None:
    return _company_query("Material Request", user=user)


def request_for_quotation_query(user: str | None = None) -> str | None:
    return _company_query("Request for Quotation", user=user)


def project_query(user: str | None = None) -> str | None:
    return _company_query("Project", user=user)


def pricing_sheet_query(user: str | None = None) -> str | None:
    return _company_query("Pricing Sheet", user=user)


def customer_query(user: str | None = None) -> str | None:
    return _company_query("Customer", user=user)


def supplier_query(user: str | None = None) -> str | None:
    return _company_query("Supplier", user=user)


def price_list_query(user: str | None = None) -> str | None:
    user = user or frappe.session.user
    table = _table_name("Price List")
    visible = get_visible_price_lists(company=_active_company_for_query(user), user=user)
    if not visible:
        return f"{table}.name is null"
    escaped = ", ".join(frappe.db.escape(name) for name in sorted(visible))
    return f"{table}.name in ({escaped})"


def item_price_query(user: str | None = None) -> str | None:
    user = user or frappe.session.user
    table = _table_name("Item Price")
    visible = get_visible_price_lists(company=_active_company_for_query(user), user=user)
    if not visible:
        return f"{table}.name is null"
    escaped = ", ".join(frappe.db.escape(name) for name in sorted(visible))
    return f"{table}.price_list in ({escaped})"


def has_item_price_permission(
    doc,
    ptype: str | None = None,
    user: str | None = None,
    permission_type: str | None = None,
) -> bool | None:
    user = user or frappe.session.user
    if user == "Administrator":
        return True
    price_list = (doc.get("price_list") if hasattr(doc, "get") else getattr(doc, "price_list", "")) or ""
    if not price_list:
        return None
    visible = set(get_visible_price_lists(company=_active_company_for_query(user), user=user))
    if price_list not in visible:
        return False
    if permission_type and permission_type not in READ_ONLY_PERMISSION_TYPES:
        if _price_list_is_shared(price_list):
            return False
    return True


def prospect_query(user: str | None = None) -> str | None:
    return _company_query("Prospect", user=user)


def lead_query(user: str | None = None) -> str | None:
    return _company_query("Lead", user=user)


def pricing_scenario_query(user: str | None = None) -> str | None:
    return _company_query("Pricing Scenario", user=user)


def pricing_benchmark_policy_query(user: str | None = None) -> str | None:
    return _company_query("Pricing Benchmark Policy", user=user)


def pricing_customs_policy_query(user: str | None = None) -> str | None:
    return _company_query("Pricing Customs Policy", user=user)


def customer_segmentation_engine_query(user: str | None = None) -> str | None:
    return _company_query("Customer Segmentation Engine", user=user)


def partner_campaign_query(user: str | None = None) -> str | None:
    return _company_query("Partner Campaign", user=user)


def portal_customer_group_policy_query(user: str | None = None) -> str | None:
    return _company_query("Portal Customer Group Policy", user=user)


def portal_quote_request_query(user: str | None = None) -> str | None:
    return _company_query("Portal Quote Request", user=user)


def sales_commission_query(user: str | None = None) -> str | None:
    user = user or frappe.session.user
    base_query = _company_query("Sales Commission", user=user)
    if _can_manage_sales_commissions(user):
        return base_query

    salesperson = _sales_person_for_user(user)
    table = _table_name("Sales Commission")
    if not salesperson:
        own_query = f"{table}.name is null"
    else:
        own_query = f"{table}.salesperson = {frappe.db.escape(salesperson)}"
    return f"({base_query}) and ({own_query})" if base_query else own_query


def sav_ticket_query(user: str | None = None) -> str | None:
    return _sav_ticket_query(user=user)


def forecast_load_plan_query(user: str | None = None) -> str | None:
    return _company_query("Forecast Load Plan", user=user)


def project_workflow_case_query(user: str | None = None) -> str | None:
    return _company_query("Project Workflow Case", user=user)


def print_format_query(user: str | None = None) -> str | None:
    user = user or frappe.session.user
    active_company = _active_company_for_query(user)
    if not active_company:
        return "`tabPrint Format`.name is null"
    return f"`tabPrint Format`.custom_company = {frappe.db.escape(active_company)}"


def _company_query(doctype: str, user: str | None = None) -> str | None:
    user = user or frappe.session.user
    allowed_companies = get_allowed_companies(user)
    table = _table_name(doctype)
    if not allowed_companies:
        return f"{table}.name is null"

    if doctype == "Company":
        escaped = ", ".join(frappe.db.escape(company) for company in allowed_companies)
        return f"{table}.name in ({escaped})"

    field = company_field_for(doctype)
    if not _has_company_field(doctype, field):
        return f"{table}.name is null"

    active_company = _active_company_for_query(user, allowed_companies=allowed_companies)
    if not active_company:
        return f"{table}.name is null"
    company_clause = f"{table}.{field} = {frappe.db.escape(active_company)}"

    bt_clause = _business_type_clause(doctype, user)
    owned_clause = _owned_only_clause(doctype, user)
    clauses = [company_clause]
    if bt_clause:
        clauses.append(bt_clause)
    if owned_clause:
        clauses.append(owned_clause)
    return " and ".join(f"({clause})" for clause in clauses if clause)


def _sav_ticket_query(user: str | None = None) -> str | None:
    user = user or frappe.session.user
    allowed_companies = get_allowed_companies(user)
    table = _table_name("SAV Ticket")
    if not allowed_companies:
        return f"{table}.name is null"

    active_company = _active_company_for_query(user, allowed_companies=allowed_companies)
    if not active_company:
        return f"{table}.name is null"

    escaped = frappe.db.escape(active_company)
    company_checks = []
    for doctype, fieldname, company_field in (
        ("Customer", "customer", "custom_company"),
        ("Sales Order", "sales_order", "company"),
        ("Delivery Note", "delivery_note", "company"),
        ("Sales Invoice", "sales_invoice", "company"),
        ("Purchase Receipt", "purchase_receipt", "company"),
        ("Project", "installation_project", "company"),
    ):
        if not _has_company_field("SAV Ticket", fieldname) or not _has_company_field(doctype, company_field):
            continue
        alias = "_sav_company_" + fieldname
        company_checks.append(
            f"exists (select 1 from {_table_name(doctype)} {alias} "
            f"where {alias}.name = {table}.{fieldname} "
            f"and {alias}.{company_field} = {escaped})"
        )
    if not company_checks:
        return f"{table}.name is null"

    clauses = ["(" + " or ".join(company_checks) + ")"]
    owned_clause = _owned_only_clause("SAV Ticket", user)
    if owned_clause:
        clauses.append(owned_clause)
    return " and ".join(f"({clause})" for clause in clauses if clause)


def _business_type_clause(doctype: str, user: str) -> str | None:
    """SQL fragment restricting a scoped doctype to the user's allowed business types.

    Returns ``None`` when the user is business-type-unrestricted (so company-only
    output is unchanged). Records with no business type set stay visible.
    """
    if user_can_access_all_business_types(user):
        return None
    allowed = get_allowed_business_types(user)
    if not allowed:
        return None

    table = _table_name(doctype)
    escaped = ", ".join(frappe.db.escape(bt) for bt in allowed)

    bt_field = business_type_field_for(doctype)
    if bt_field and _has_company_field(doctype, bt_field):
        column = f"{table}.{bt_field}"
        return f"({column} in ({escaped}) or {column} is null or {column} = '')"

    segments_field = segments_field_for(doctype)
    if segments_field and _has_company_field(doctype, segments_field):
        seg = _table_name(SEGMENT_ASSIGNMENT_DOCTYPE)
        escaped_dt = frappe.db.escape(doctype)
        escaped_field = frappe.db.escape(segments_field)
        base = (
            f"select 1 from {seg} _bt_seg "
            f"where _bt_seg.parent = {table}.name "
            f"and _bt_seg.parenttype = {escaped_dt} "
            f"and _bt_seg.parentfield = {escaped_field}"
        )
        return (
            f"(not exists ({base}) "
            f"or exists ({base} and _bt_seg.business_type in ({escaped})))"
        )

    return None


def _doc_business_type_allowed(doc, user: str) -> bool:
    if user_can_access_all_business_types(user):
        return True
    allowed = set(get_allowed_business_types(user))
    doctype = getattr(doc, "doctype", None)

    bt_field = business_type_field_for(doctype)
    if bt_field:
        value = (doc.get(bt_field) or "").strip() if hasattr(doc, "get") else ""
        return (not value) or value in allowed

    segments_field = segments_field_for(doctype)
    if segments_field and hasattr(doc, "get"):
        business_types = [
            (row.get("business_type") or "").strip()
            for row in (doc.get(segments_field) or [])
        ]
        business_types = [bt for bt in business_types if bt]
        if not business_types:
            return True
        return any(bt in allowed for bt in business_types)

    return True


def _price_list_doc_allowed(doc, user: str, permission_type: str | None = None) -> bool:
    if user == "Administrator":
        return True
    name = (doc.get("name") if hasattr(doc, "get") else getattr(doc, "name", "")) or ""
    values = _price_list_permission_values(doc, name)
    company = (values.get("custom_company") or "").strip()
    if company and company not in set(get_allowed_companies(user)) and not user_can_access_all_companies(user):
        return False
    if _is_new_doc(doc):
        return True
    if not name:
        return False
    kind = _price_list_kind(values=values)
    focus_company = company or _active_company_for_query(user)
    visible = set(get_visible_price_lists(kind, company=focus_company, user=user)) if kind else set(get_visible_price_lists(company=focus_company, user=user))
    return name in visible


def _active_company_for_query(user: str | None = None, allowed_companies: list[str] | None = None) -> str:
    user = user or frappe.session.user
    if allowed_companies is None:
        allowed_companies = get_all_companies() if user_can_access_all_companies(user) else get_allowed_companies(user)
    return resolve_current_company(user=user, allowed_companies=allowed_companies)


def _price_list_shared_edit_allowed(doc, user: str, permission_type: str | None = None) -> bool:
    """Block write operations on shared (mirrored) price lists."""
    if user == "Administrator":
        return True
    if not permission_type or permission_type in READ_ONLY_PERMISSION_TYPES:
        return True
    shared_from = None
    try:
        shared_from = (doc.get("custom_is_shared_from") if hasattr(doc, "get") else getattr(doc, "custom_is_shared_from", "")) or ""
    except (AttributeError, TypeError):
        pass
    if not shared_from:
        try:
            if frappe.db.has_column("Price List", "custom_is_shared_from"):
                shared_from = frappe.db.get_value("Price List", doc.name, "custom_is_shared_from") or ""
        except Exception:
            pass
    if shared_from:
        return False
    return True


def _price_list_is_shared(price_list_name: str) -> bool:
    try:
        if not frappe.db.has_column("Price List", "custom_is_shared_from"):
            return False
        val = frappe.db.get_value("Price List", price_list_name, "custom_is_shared_from") or ""
        return bool(val.strip())
    except Exception:
        return False


def _price_list_kind_for_doc(doc) -> str:
    return _price_list_kind(values={
        PRICE_LIST_TYPE_FIELD: (doc.get(PRICE_LIST_TYPE_FIELD) if hasattr(doc, "get") else getattr(doc, PRICE_LIST_TYPE_FIELD, "")) or "",
        "buying": doc.get("buying") if hasattr(doc, "get") else getattr(doc, "buying", 0),
        "selling": doc.get("selling") if hasattr(doc, "get") else getattr(doc, "selling", 0),
    })


def _price_list_kind(values: dict | None = None) -> str:
    values = values or {}
    list_type = get_price_list_type(values=values)
    if list_type == SELLING_PRICE_LIST:
        return "selling"
    if list_type == BUYING_PRICE_LIST:
        return "buying"
    if list_type == BENCHMARK_PRICE_LIST:
        return "benchmark"
    return ""


def _price_list_permission_values(doc, name: str) -> dict:
    if frappe.db.exists("Price List", name):
        fields = ["custom_company", "buying", "selling"]
        if getattr(frappe.db, "has_column", None) and frappe.db.has_column("Price List", PRICE_LIST_TYPE_FIELD):
            fields.insert(0, PRICE_LIST_TYPE_FIELD)
        values = frappe.db.get_value("Price List", name, fields, as_dict=True) or {}
        if values:
            return values
    values = {
        PRICE_LIST_TYPE_FIELD: (doc.get(PRICE_LIST_TYPE_FIELD) if hasattr(doc, "get") else getattr(doc, PRICE_LIST_TYPE_FIELD, "")) or "",
        "custom_company": (doc.get("custom_company") if hasattr(doc, "get") else getattr(doc, "custom_company", "")) or "",
        "buying": doc.get("buying") if hasattr(doc, "get") else getattr(doc, "buying", 0),
        "selling": doc.get("selling") if hasattr(doc, "get") else getattr(doc, "selling", 0),
    }
    return values


def _company_from_doc(doc) -> str:
    if getattr(doc, "doctype", None) == "Company":
        return doc.name
    if getattr(doc, "doctype", None) == "SAV Ticket":
        return _sav_ticket_company_from_doc(doc)
    field = company_field_for(getattr(doc, "doctype", None))
    if hasattr(doc, "get"):
        return doc.get(field) or ""
    return getattr(doc, field, "") or ""


def _doc_company_allowed(doc, user: str, permission_type: str | None = None) -> bool:
    company = _company_from_doc(doc)
    if not company:
        return _is_new_doc(doc)
    return company in set(get_allowed_companies(user))


def _sav_ticket_company_allowed(doc, user: str, permission_type: str | None = None) -> bool:
    companies = _sav_ticket_companies_from_doc(doc)
    if not companies:
        return bool(permission_type == "create" and _is_new_doc(doc))
    return bool(set(companies).intersection(set(get_allowed_companies(user))))


def _sav_ticket_company_from_doc(doc) -> str:
    companies = _sav_ticket_companies_from_doc(doc)
    return companies[0] if companies else ""


def _sav_ticket_companies_from_doc(doc) -> list[str]:
    if not hasattr(doc, "get"):
        return []
    companies = []
    for doctype, fieldname, company_field in (
        ("Customer", "customer", "custom_company"),
        ("Sales Order", "sales_order", "company"),
        ("Delivery Note", "delivery_note", "company"),
        ("Sales Invoice", "sales_invoice", "company"),
        ("Purchase Receipt", "purchase_receipt", "company"),
        ("Project", "installation_project", "company"),
    ):
        linked_name = (doc.get(fieldname) or "").strip()
        if not linked_name:
            continue
        try:
            company = frappe.db.get_value(doctype, linked_name, company_field)
        except Exception:
            company = ""
        if company and company not in companies:
            companies.append(company)
    return companies


def _table_name(doctype: str) -> str:
    return f"`tab{doctype.replace('`', '')}`"


def _has_company_field(doctype: str, field: str = "company") -> bool:
    try:
        if frappe.get_meta(doctype).get_field(field):
            return True
    except Exception:
        pass
    try:
        return bool(frappe.db.has_column(doctype, field))
    except Exception:
        return False


def _owned_only_clause(doctype: str, user: str) -> str | None:
    if not _user_owned_documents_only(user):
        return None
    table = _table_name(doctype)
    if doctype == "Opportunity" and _has_company_field(doctype, "opportunity_owner"):
        return _opportunity_user_clause(table, user)
    if doctype == "Project":
        return _project_user_clause(table, user)
    if doctype == "Sales Order":
        return _sales_order_user_clause(table, user)
    if doctype == "Purchase Order":
        return _purchase_order_user_clause(table, user)
    if doctype == "Purchase Receipt":
        return _purchase_receipt_user_clause(table, user)
    if doctype == "Purchase Invoice":
        return _purchase_invoice_user_clause(table, user)
    if doctype == "Material Request":
        return _material_request_user_clause(table, user)
    if doctype == "Request for Quotation":
        return _request_for_quotation_user_clause(table, user)
    if doctype == "Payment Entry":
        return _payment_entry_user_clause(table, user)
    if doctype == "Stock Entry":
        return _stock_entry_user_clause(table, user)
    if doctype == "Forecast Load Plan":
        return _forecast_load_plan_user_clause(table, user)
    if doctype == "Lead" and _has_company_field(doctype, "lead_owner"):
        return _lead_user_clause(table, user)
    if doctype == "Prospect" and _has_company_field(doctype, "prospect_owner"):
        return _prospect_user_clause(table, user)
    if doctype == "Customer":
        return _customer_user_clause(table, user)
    if doctype == "Quotation":
        return _quotation_user_clause(table, user)
    if doctype == "Sales Invoice":
        return _sales_invoice_user_clause(table, user)
    if doctype == "Delivery Note":
        return _delivery_note_user_clause(table, user)
    if doctype == "Partner Campaign":
        return _partner_campaign_user_clause(table, user)
    if doctype == "Pricing Sheet":
        return _pricing_sheet_user_clause(table, user)
    if doctype == "Portal Quote Request":
        return _portal_quote_request_user_clause(table, user)
    if doctype == "SAV Ticket":
        return _sav_ticket_user_clause(table, user)
    return None


def _doc_owned_scope_allowed(doc, user: str) -> bool:
    if not _user_owned_documents_only(user):
        return True
    doctype = getattr(doc, "doctype", None)
    name = (doc.get("name") if hasattr(doc, "get") else getattr(doc, "name", "")) or ""
    if not doctype or not name:
        return True
    if _is_new_doc(doc):
        return True
    clause = _owned_only_clause(doctype, user)
    if not clause:
        return True
    table = _table_name(doctype)
    return bool(
        frappe.db.sql(
            f"select {table}.name from {table} where {table}.name = %(name)s and ({clause}) limit 1",
            {"name": name},
        )
    )


def _owned_or_opportunity_child_clause(owner_clause: str, child_clause: str) -> str:
    clauses = [clause for clause in (owner_clause, child_clause) if clause]
    return "(" + " or ".join(f"({clause})" for clause in clauses) + ")"


def _opportunity_user_clause(opportunity_ref: str, user: str) -> str:
    escaped = frappe.db.escape(user)
    checks = []
    if _has_company_field("Opportunity", "opportunity_owner"):
        checks.append(f"{opportunity_ref}.opportunity_owner = {escaped}")
    elif _has_company_field("Opportunity", "owner"):
        checks.append(f"{opportunity_ref}.owner = {escaped}")
    checks.append(
        f"exists (select 1 from {_table_name('ToDo')} _opp_todo "
        f"where _opp_todo.reference_type = 'Opportunity' "
        f"and _opp_todo.reference_name = {opportunity_ref}.name "
        f"and _opp_todo.allocated_to = {escaped} "
        f"and _opp_todo.status = 'Open')"
    )
    return "(" + " or ".join(checks) + ")"


@frappe.whitelist()
def normalize_managed_docperms(dry_run: int | bool = 0) -> dict:
    """Clear native owner/share bypass permissions for Orderlift-managed business doctypes."""
    frappe.only_for(["System Manager", "Orderlift Admin"])
    dry_run = bool(cint(dry_run))
    doctypes = _existing_managed_permission_doctypes()
    result = {"dry_run": dry_run, "doctypes": doctypes, "updated": 0, "rows": []}
    if not doctypes:
        return result

    for perm_doctype in ("DocPerm", "Custom DocPerm"):
        if not _doctype_exists(perm_doctype):
            continue
        for fieldname in ("if_owner", "share"):
            if not _has_company_field(perm_doctype, fieldname):
                continue
            rows = frappe.get_all(
                perm_doctype,
                filters={"parent": ["in", doctypes], fieldname: 1},
                fields=["name", "parent", "role", "permlevel"],
                limit_page_length=0,
            )
            for row in rows:
                result["rows"].append(
                    {
                        "permission_doctype": perm_doctype,
                        "name": row.name,
                        "doctype": row.parent,
                        "role": row.role,
                        "permlevel": cint(row.get("permlevel")),
                        "fieldname": fieldname,
                    }
                )
                if not dry_run:
                    frappe.db.set_value(perm_doctype, row.name, fieldname, 0, update_modified=False)
                    result["updated"] += 1

    if not dry_run and result["updated"]:
        frappe.clear_cache()
        frappe.db.commit()
    return result


@frappe.whitelist()
def cleanup_managed_docshares(dry_run: int | bool = 0) -> dict:
    """Remove DocShare rows that would bypass the central Orderlift access model."""
    frappe.only_for(["System Manager", "Orderlift Admin"])
    dry_run = bool(cint(dry_run))
    doctypes = _existing_managed_permission_doctypes()
    result = {"dry_run": dry_run, "doctypes": doctypes, "deleted": 0, "rows": []}
    if not doctypes or not _doctype_exists("DocShare"):
        return result

    rows = frappe.get_all(
        "DocShare",
        filters={"share_doctype": ["in", doctypes]},
        fields=["name", "share_doctype", "share_name", "user", "read", "write", "share", "everyone"],
        order_by="creation asc",
        limit_page_length=0,
    )
    for row in rows:
        result["rows"].append(dict(row))
        if not dry_run:
            frappe.delete_doc("DocShare", row.name, ignore_permissions=True, force=True)
            result["deleted"] += 1

    if not dry_run and result["deleted"]:
        frappe.clear_cache()
        frappe.db.commit()
    return result


def validate_managed_docshare(doc, method: str | None = None) -> None:
    share_doctype = (doc.get("share_doctype") if hasattr(doc, "get") else getattr(doc, "share_doctype", "")) or ""
    if share_doctype not in set(_existing_managed_permission_doctypes()):
        return
    frappe.throw(
        _(
            "Document sharing is disabled for Orderlift-managed business documents. "
            "Use Access Command Center roles and pipeline assignments instead."
        )
    )


def _existing_managed_permission_doctypes() -> list[str]:
    return [
        doctype
        for doctype in ORDERLIFT_MANAGED_SHARE_DISABLED_DOCTYPES
        if _doctype_exists(doctype)
    ]


def _doctype_exists(doctype: str) -> bool:
    try:
        return bool(frappe.db.exists("DocType", doctype))
    except Exception:
        return False


def _project_user_clause(project_ref: str, user: str) -> str:
    checks = _owner_assignment_checks("Project", project_ref, user, extra_owner_fields=("project_owner",))
    if _has_company_field("Project", "custom_source_opportunity"):
        opp = "_project_opp"
        checks.append(
            f"exists (select 1 from {_table_name('Opportunity')} {opp} "
            f"where {opp}.name = {project_ref}.custom_source_opportunity "
            f"and {_opportunity_user_clause(opp, user)})"
        )
    return "(" + " or ".join(checks) + ")"


def _quotation_user_clause(quotation_ref: str, user: str) -> str:
    checks = _owner_assignment_checks("Quotation", quotation_ref, user)
    checks.append(_quotation_opportunity_child_clause(quotation_ref, user))
    return "(" + " or ".join(checks) + ")"


def _sales_order_user_clause(sales_order_ref: str, user: str) -> str:
    checks = _owner_assignment_checks("Sales Order", sales_order_ref, user)
    checks.append(_sales_order_opportunity_child_clause(sales_order_ref, user))
    return "(" + " or ".join(checks) + ")"


def _sales_invoice_user_clause(invoice_ref: str, user: str) -> str:
    checks = _owner_assignment_checks("Sales Invoice", invoice_ref, user)
    checks.append(_sales_invoice_sales_order_child_clause(invoice_ref, user))
    return "(" + " or ".join(checks) + ")"


def _delivery_note_user_clause(delivery_note_ref: str, user: str) -> str:
    checks = _owner_assignment_checks("Delivery Note", delivery_note_ref, user)
    checks.append(_delivery_note_sales_order_child_clause(delivery_note_ref, user))
    return "(" + " or ".join(checks) + ")"


def _customer_user_clause(customer_ref: str, user: str) -> str:
    escaped = frappe.db.escape(user)
    clauses = [f"{customer_ref}.owner = {escaped}"]
    sales_person = _sales_person_for_user(user)
    if sales_person and _has_company_field("Customer", "account_manager"):
        clauses.append(f"{customer_ref}.account_manager = {frappe.db.escape(sales_person)}")
        clauses.append(_customer_sales_team_clause(customer_ref, sales_person))
    clauses.append(_open_todo_assignment_clause("Customer", user, table_ref=customer_ref))
    return _owned_or_opportunity_child_clause(
        "(" + " or ".join(clauses) + ")",
        _party_opportunity_child_clause("Customer", customer_ref, user),
    )


def _customer_sales_team_clause(customer_ref: str, sales_person: str) -> str:
    return (
        f"exists (select 1 from {_table_name('Sales Team')} _customer_sales_team "
        f"where _customer_sales_team.parenttype = 'Customer' "
        f"and _customer_sales_team.parent = {customer_ref}.name "
        f"and _customer_sales_team.sales_person = {frappe.db.escape(sales_person)})"
    )


def _lead_user_clause(lead_ref: str, user: str) -> str:
    escaped = frappe.db.escape(user)
    clauses = []
    if _has_company_field("Lead", "lead_owner"):
        clauses.append(f"{lead_ref}.lead_owner = {escaped}")
    clauses.append(_open_todo_assignment_clause("Lead", user, table_ref=lead_ref))
    return _owned_or_opportunity_child_clause(
        "(" + " or ".join(clauses) + ")",
        _party_opportunity_child_clause("Lead", lead_ref, user),
    )


def _prospect_user_clause(prospect_ref: str, user: str) -> str:
    escaped = frappe.db.escape(user)
    clauses = []
    if _has_company_field("Prospect", "prospect_owner"):
        clauses.append(f"{prospect_ref}.prospect_owner = {escaped}")
    clauses.append(_open_todo_assignment_clause("Prospect", user, table_ref=prospect_ref))
    return _owned_or_opportunity_child_clause(
        "(" + " or ".join(clauses) + ")",
        _party_opportunity_child_clause("Prospect", prospect_ref, user),
    )


def _material_request_user_clause(material_request_ref: str, user: str) -> str:
    checks = _owner_assignment_checks("Material Request", material_request_ref, user)
    item = "_mr_item"
    if _has_company_field("Material Request Item", "sales_order"):
        so = "_mr_so"
        checks.append(
            f"exists (select 1 from {_table_name('Material Request Item')} {item} "
            f"inner join {_table_name('Sales Order')} {so} on {so}.name = {item}.sales_order "
            f"where {item}.parent = {material_request_ref}.name "
            f"and {_sales_order_user_clause(so, user)})"
        )
    if _has_company_field("Material Request Item", "project"):
        project = "_mr_project"
        checks.append(
            f"exists (select 1 from {_table_name('Material Request Item')} {item} "
            f"inner join {_table_name('Project')} {project} on {project}.name = {item}.project "
            f"where {item}.parent = {material_request_ref}.name "
            f"and {_project_user_clause(project, user)})"
        )
    return "(" + " or ".join(checks) + ")"


def _request_for_quotation_user_clause(rfq_ref: str, user: str) -> str:
    checks = _owner_assignment_checks("Request for Quotation", rfq_ref, user)
    if _has_company_field("Request for Quotation", "opportunity"):
        opp = "_rfq_opp"
        checks.append(
            f"exists (select 1 from {_table_name('Opportunity')} {opp} "
            f"where {opp}.name = {rfq_ref}.opportunity "
            f"and {_opportunity_user_clause(opp, user)})"
        )
    if _has_company_field("Request for Quotation Item", "material_request"):
        item = "_rfq_item"
        mr = "_rfq_mr"
        checks.append(
            f"exists (select 1 from {_table_name('Request for Quotation Item')} {item} "
            f"inner join {_table_name('Material Request')} {mr} on {mr}.name = {item}.material_request "
            f"where {item}.parent = {rfq_ref}.name "
            f"and {_material_request_user_clause(mr, user)})"
        )
    return "(" + " or ".join(checks) + ")"


def _purchase_order_user_clause(purchase_order_ref: str, user: str) -> str:
    checks = _owner_assignment_checks("Purchase Order", purchase_order_ref, user)
    if _has_company_field("Purchase Order", "project"):
        project = "_po_project"
        checks.append(
            f"exists (select 1 from {_table_name('Project')} {project} "
            f"where {project}.name = {purchase_order_ref}.project "
            f"and {_project_user_clause(project, user)})"
        )
    item = "_po_item"
    if _has_company_field("Purchase Order Item", "sales_order"):
        so = "_po_so"
        checks.append(
            f"exists (select 1 from {_table_name('Purchase Order Item')} {item} "
            f"inner join {_table_name('Sales Order')} {so} on {so}.name = {item}.sales_order "
            f"where {item}.parent = {purchase_order_ref}.name "
            f"and {_sales_order_user_clause(so, user)})"
        )
    if _has_company_field("Purchase Order Item", "material_request"):
        mr = "_po_mr"
        checks.append(
            f"exists (select 1 from {_table_name('Purchase Order Item')} {item} "
            f"inner join {_table_name('Material Request')} {mr} on {mr}.name = {item}.material_request "
            f"where {item}.parent = {purchase_order_ref}.name "
            f"and {_material_request_user_clause(mr, user)})"
        )
    if _has_company_field("Purchase Order Item", "project"):
        child_project = "_po_item_project"
        checks.append(
            f"exists (select 1 from {_table_name('Purchase Order Item')} {item} "
            f"inner join {_table_name('Project')} {child_project} on {child_project}.name = {item}.project "
            f"where {item}.parent = {purchase_order_ref}.name "
            f"and {_project_user_clause(child_project, user)})"
        )
    return "(" + " or ".join(checks) + ")"


def _purchase_receipt_user_clause(purchase_receipt_ref: str, user: str) -> str:
    checks = _owner_assignment_checks("Purchase Receipt", purchase_receipt_ref, user)
    if _has_company_field("Purchase Receipt", "project"):
        project = "_pr_project"
        checks.append(
            f"exists (select 1 from {_table_name('Project')} {project} "
            f"where {project}.name = {purchase_receipt_ref}.project "
            f"and {_project_user_clause(project, user)})"
        )
    item = "_pr_item"
    if _has_company_field("Purchase Receipt Item", "purchase_order"):
        po = "_pr_po"
        checks.append(
            f"exists (select 1 from {_table_name('Purchase Receipt Item')} {item} "
            f"inner join {_table_name('Purchase Order')} {po} on {po}.name = {item}.purchase_order "
            f"where {item}.parent = {purchase_receipt_ref}.name "
            f"and {_purchase_order_user_clause(po, user)})"
        )
    if _has_company_field("Purchase Receipt Item", "material_request"):
        mr = "_pr_mr"
        checks.append(
            f"exists (select 1 from {_table_name('Purchase Receipt Item')} {item} "
            f"inner join {_table_name('Material Request')} {mr} on {mr}.name = {item}.material_request "
            f"where {item}.parent = {purchase_receipt_ref}.name "
            f"and {_material_request_user_clause(mr, user)})"
        )
    if _has_company_field("Purchase Receipt Item", "sales_order"):
        so = "_pr_so"
        checks.append(
            f"exists (select 1 from {_table_name('Purchase Receipt Item')} {item} "
            f"inner join {_table_name('Sales Order')} {so} on {so}.name = {item}.sales_order "
            f"where {item}.parent = {purchase_receipt_ref}.name "
            f"and {_sales_order_user_clause(so, user)})"
        )
    if _has_company_field("Purchase Receipt Item", "project"):
        child_project = "_pr_item_project"
        checks.append(
            f"exists (select 1 from {_table_name('Purchase Receipt Item')} {item} "
            f"inner join {_table_name('Project')} {child_project} on {child_project}.name = {item}.project "
            f"where {item}.parent = {purchase_receipt_ref}.name "
            f"and {_project_user_clause(child_project, user)})"
        )
    return "(" + " or ".join(checks) + ")"


def _purchase_invoice_user_clause(purchase_invoice_ref: str, user: str) -> str:
    checks = _owner_assignment_checks("Purchase Invoice", purchase_invoice_ref, user)
    if _has_company_field("Purchase Invoice", "project"):
        project = "_pi_project"
        checks.append(
            f"exists (select 1 from {_table_name('Project')} {project} "
            f"where {project}.name = {purchase_invoice_ref}.project "
            f"and {_project_user_clause(project, user)})"
        )
    item = "_pi_item"
    if _has_company_field("Purchase Invoice Item", "purchase_order"):
        po = "_pi_po"
        checks.append(
            f"exists (select 1 from {_table_name('Purchase Invoice Item')} {item} "
            f"inner join {_table_name('Purchase Order')} {po} on {po}.name = {item}.purchase_order "
            f"where {item}.parent = {purchase_invoice_ref}.name "
            f"and {_purchase_order_user_clause(po, user)})"
        )
    if _has_company_field("Purchase Invoice Item", "purchase_receipt"):
        pr = "_pi_pr"
        checks.append(
            f"exists (select 1 from {_table_name('Purchase Invoice Item')} {item} "
            f"inner join {_table_name('Purchase Receipt')} {pr} on {pr}.name = {item}.purchase_receipt "
            f"where {item}.parent = {purchase_invoice_ref}.name "
            f"and {_purchase_receipt_user_clause(pr, user)})"
        )
    if _has_company_field("Purchase Invoice Item", "material_request"):
        mr = "_pi_mr"
        checks.append(
            f"exists (select 1 from {_table_name('Purchase Invoice Item')} {item} "
            f"inner join {_table_name('Material Request')} {mr} on {mr}.name = {item}.material_request "
            f"where {item}.parent = {purchase_invoice_ref}.name "
            f"and {_material_request_user_clause(mr, user)})"
        )
    if _has_company_field("Purchase Invoice Item", "project"):
        child_project = "_pi_item_project"
        checks.append(
            f"exists (select 1 from {_table_name('Purchase Invoice Item')} {item} "
            f"inner join {_table_name('Project')} {child_project} on {child_project}.name = {item}.project "
            f"where {item}.parent = {purchase_invoice_ref}.name "
            f"and {_project_user_clause(child_project, user)})"
        )
    return "(" + " or ".join(checks) + ")"


def _payment_entry_user_clause(payment_entry_ref: str, user: str) -> str:
    checks = _owner_assignment_checks("Payment Entry", payment_entry_ref, user)
    ref = "_pe_ref"
    reference_checks = {
        "Sales Invoice": _sales_invoice_user_clause,
        "Purchase Invoice": _purchase_invoice_user_clause,
        "Sales Order": _sales_order_user_clause,
        "Purchase Order": _purchase_order_user_clause,
        "Purchase Receipt": _purchase_receipt_user_clause,
    }
    for doctype, clause_fn in reference_checks.items():
        alias = "_pe_" + doctype.lower().replace(" ", "_")
        checks.append(
            f"exists (select 1 from {_table_name('Payment Entry Reference')} {ref} "
            f"inner join {_table_name(doctype)} {alias} on {alias}.name = {ref}.reference_name "
            f"where {ref}.parent = {payment_entry_ref}.name "
            f"and {ref}.reference_doctype = {frappe.db.escape(doctype)} "
            f"and {clause_fn(alias, user)})"
        )
    return "(" + " or ".join(checks) + ")"


def _stock_entry_user_clause(stock_entry_ref: str, user: str) -> str:
    checks = _owner_assignment_checks("Stock Entry", stock_entry_ref, user)
    if _has_company_field("Stock Entry", "project"):
        project = "_se_project"
        checks.append(
            f"exists (select 1 from {_table_name('Project')} {project} "
            f"where {project}.name = {stock_entry_ref}.project "
            f"and {_project_user_clause(project, user)})"
        )
    if _has_company_field("Stock Entry Detail", "material_request"):
        item = "_se_item"
        mr = "_se_mr"
        checks.append(
            f"exists (select 1 from {_table_name('Stock Entry Detail')} {item} "
            f"inner join {_table_name('Material Request')} {mr} on {mr}.name = {item}.material_request "
            f"where {item}.parent = {stock_entry_ref}.name "
            f"and {_material_request_user_clause(mr, user)})"
        )
    if _has_company_field("Stock Entry Detail", "project"):
        item = "_se_project_item"
        child_project = "_se_item_project"
        checks.append(
            f"exists (select 1 from {_table_name('Stock Entry Detail')} {item} "
            f"inner join {_table_name('Project')} {child_project} on {child_project}.name = {item}.project "
            f"where {item}.parent = {stock_entry_ref}.name "
            f"and {_project_user_clause(child_project, user)})"
        )
    return "(" + " or ".join(checks) + ")"


def _forecast_load_plan_user_clause(plan_ref: str, user: str) -> str:
    checks = _owner_assignment_checks("Forecast Load Plan", plan_ref, user)
    for doctype, fieldname, clause_fn in (
        ("Purchase Order", "custom_forecast_plan", _purchase_order_user_clause),
        ("Sales Order", "custom_forecast_plan", _sales_order_user_clause),
        ("Delivery Note", "custom_forecast_plan", _delivery_note_user_clause),
    ):
        if _has_company_field(doctype, fieldname):
            alias = "_flp_" + doctype.lower().replace(" ", "_")
            checks.append(
                f"exists (select 1 from {_table_name(doctype)} {alias} "
                f"where {alias}.{fieldname} = {plan_ref}.name "
                f"and {clause_fn(alias, user)})"
            )
    return "(" + " or ".join(checks) + ")"


def _partner_campaign_user_clause(campaign_ref: str, user: str) -> str:
    escaped = frappe.db.escape(user)
    checks = []
    if _has_company_field("Partner Campaign", "campaign_owner"):
        checks.append(f"{campaign_ref}.campaign_owner = {escaped}")
    elif _has_company_field("Partner Campaign", "owner"):
        checks.append(f"{campaign_ref}.owner = {escaped}")
    checks.append(_open_todo_assignment_clause("Partner Campaign", user, table_ref=campaign_ref))
    return "(" + " or ".join(checks) + ")"


def _campaign_target_link_clause(campaign_ref: str, doctype: str, target_field: str, clause_fn, user: str) -> str:
    target = "_campaign_target_" + target_field
    linked = "_campaign_linked_" + target_field
    return (
        f"exists (select 1 from {_table_name('Partner Campaign Target')} {target} "
        f"inner join {_table_name(doctype)} {linked} on {linked}.name = {target}.{target_field} "
        f"where {target}.parent = {campaign_ref}.name "
        f"and {clause_fn(linked, user)})"
    )


def _pricing_sheet_user_clause(sheet_ref: str, user: str) -> str:
    checks = _owner_assignment_checks("Pricing Sheet", sheet_ref, user)
    sales_person = _sales_person_for_user(user)
    if sales_person and _has_company_field("Pricing Sheet", "sales_person"):
        checks.append(f"{sheet_ref}.sales_person = {frappe.db.escape(sales_person)}")
    if _has_company_field("Pricing Sheet", "opportunity"):
        opp = "_ps_opp"
        checks.append(
            f"exists (select 1 from {_table_name('Opportunity')} {opp} "
            f"where {opp}.name = {sheet_ref}.opportunity "
            f"and {_opportunity_user_clause(opp, user)})"
        )
    for party_type in ("Lead", "Prospect", "Customer"):
        party = "_ps_" + party_type.lower()
        clause_fn = {"Lead": _lead_user_clause, "Prospect": _prospect_user_clause, "Customer": _customer_user_clause}[party_type]
        checks.append(
            f"exists (select 1 from {_table_name(party_type)} {party} "
            f"where {party}.name = {sheet_ref}.party_name "
            f"and {sheet_ref}.party_type = {frappe.db.escape(party_type)} "
            f"and {clause_fn(party, user)})"
        )
    return "(" + " or ".join(checks) + ")"


def _portal_quote_request_user_clause(request_ref: str, user: str) -> str:
    checks = _owner_assignment_checks("Portal Quote Request", request_ref, user)
    if _has_company_field("Portal Quote Request", "portal_user"):
        checks.append(f"{request_ref}.portal_user = {frappe.db.escape(user)}")
    if _has_company_field("Portal Quote Request", "customer"):
        customer = "_pqr_customer"
        checks.append(
            f"exists (select 1 from {_table_name('Customer')} {customer} "
            f"where {customer}.name = {request_ref}.customer "
            f"and {_customer_user_clause(customer, user)})"
        )
    if _has_company_field("Portal Quote Request", "linked_quotation"):
        quotation = "_pqr_quote"
        checks.append(
            f"exists (select 1 from {_table_name('Quotation')} {quotation} "
            f"where {quotation}.name = {request_ref}.linked_quotation "
            f"and {_quotation_user_clause(quotation, user)})"
        )
    return "(" + " or ".join(checks) + ")"


def _sav_ticket_user_clause(ticket_ref: str, user: str) -> str:
    checks = _owner_assignment_checks("SAV Ticket", ticket_ref, user, extra_owner_fields=("assigned_technician",))
    links = (
        ("Customer", "customer", _customer_user_clause),
        ("Sales Order", "sales_order", _sales_order_user_clause),
        ("Delivery Note", "delivery_note", _delivery_note_user_clause),
        ("Sales Invoice", "sales_invoice", _sales_invoice_user_clause),
        ("Purchase Receipt", "purchase_receipt", _purchase_receipt_user_clause),
        ("Project", "installation_project", _project_user_clause),
    )
    for doctype, fieldname, clause_fn in links:
        if _has_company_field("SAV Ticket", fieldname):
            alias = "_sav_" + fieldname
            checks.append(
                f"exists (select 1 from {_table_name(doctype)} {alias} "
                f"where {alias}.name = {ticket_ref}.{fieldname} "
                f"and {clause_fn(alias, user)})"
            )
    return "(" + " or ".join(checks) + ")"


def _owner_assignment_checks(doctype: str, table_ref: str, user: str, extra_owner_fields: tuple[str, ...] = ()) -> list[str]:
    escaped = frappe.db.escape(user)
    checks = []
    for field in ("owner", *extra_owner_fields):
        if _has_company_field(doctype, field):
            checks.append(f"{table_ref}.{field} = {escaped}")
    checks.append(_open_todo_assignment_clause(doctype, user, table_ref=table_ref))
    return checks


def _party_opportunity_child_clause(party_type: str, table: str, user: str) -> str:
    opp = "_child_opp"
    return (
        f"exists (select 1 from {_table_name('Opportunity')} {opp} "
        f"where {opp}.opportunity_from = {frappe.db.escape(party_type)} "
        f"and {opp}.party_name = {table}.name "
        f"and {_opportunity_user_clause(opp, user)})"
    )


def _quotation_opportunity_child_clause(table: str, user: str) -> str:
    opp = "_quote_opp"
    return (
        f"exists (select 1 from {_table_name('Opportunity')} {opp} "
        f"where {opp}.name = {table}.opportunity "
        f"and {_opportunity_user_clause(opp, user)})"
    )


def _sales_order_opportunity_child_clause(table: str, user: str) -> str:
    opp = "_so_opp"
    quote = "_so_quote"
    item = "_so_item"
    return (
        f"exists (select 1 from {_table_name('Sales Order Item')} {item} "
        f"inner join {_table_name('Quotation')} {quote} on {quote}.name = {item}.prevdoc_docname "
        f"inner join {_table_name('Opportunity')} {opp} on {opp}.name = {quote}.opportunity "
        f"where {item}.parent = {table}.name "
        f"and {_opportunity_user_clause(opp, user)})"
    )


def _sales_invoice_sales_order_child_clause(table: str, user: str) -> str:
    so = "_si_so"
    item = "_si_item"
    return (
        f"exists (select 1 from {_table_name('Sales Invoice Item')} {item} "
        f"inner join {_table_name('Sales Order')} {so} on {so}.name = {item}.sales_order "
        f"where {item}.parent = {table}.name "
        f"and {_sales_order_user_clause(so, user)})"
    )


def _delivery_note_sales_order_child_clause(table: str, user: str) -> str:
    so = "_dn_so"
    item = "_dn_item"
    return (
        f"exists (select 1 from {_table_name('Delivery Note Item')} {item} "
        f"inner join {_table_name('Sales Order')} {so} on {so}.name = {item}.against_sales_order "
        f"where {item}.parent = {table}.name "
        f"and {_sales_order_user_clause(so, user)})"
    )


def _owned_or_assigned_clause(doctype: str, owner_clause: str, user: str) -> str:
    return f"({owner_clause} or {_open_todo_assignment_clause(doctype, user)})"


def _open_todo_assignment_clause(doctype: str, user: str, table_ref: str | None = None) -> str:
    table = table_ref or _table_name(doctype)
    todo = _table_name("ToDo")
    return (
        f"exists (select 1 from {todo} _todo_assignment "
        f"where _todo_assignment.reference_type = {frappe.db.escape(doctype)} "
        f"and _todo_assignment.reference_name = {table}.name "
        f"and _todo_assignment.allocated_to = {frappe.db.escape(user)} "
        f"and _todo_assignment.status = 'Open')"
    )


def _user_owned_documents_only(user: str) -> bool:
    if not user or user == "Administrator":
        return False
    if not _has_company_field("User", OWNED_ONLY_USER_FIELD):
        return False
    return bool(cint(frappe.db.get_value("User", user, OWNED_ONLY_USER_FIELD) or 0))


def _price_list_type_clause(table: str, expected_type: str) -> str:
    if _has_company_field("Price List", PRICE_LIST_TYPE_FIELD):
        return f"{table}.{PRICE_LIST_TYPE_FIELD} = {frappe.db.escape(expected_type)}"
    if expected_type == BUYING_PRICE_LIST:
        return f"ifnull({table}.buying, 0) = 1"
    if expected_type == SELLING_PRICE_LIST:
        return f"ifnull({table}.selling, 0) = 1"
    if expected_type == BENCHMARK_PRICE_LIST:
        return f"ifnull({table}.buying, 0) = 0 and ifnull({table}.selling, 0) = 0"
    return f"{table}.name is null"


def _is_new_doc(doc) -> bool:
    try:
        return bool(doc.is_new())
    except Exception:
        return not bool(getattr(doc, "name", None))


def _can_manage_sales_commissions(user: str) -> bool:
    manager_roles = {"Orderlift Admin", "Sales Manager", "Orderlift Accountant", "System Manager", "Administrator", COMMISSION_MANAGER_ROLE}
    return bool(manager_roles.intersection(set(frappe.get_roles(user))))


def _sales_person_for_user(user: str) -> str:
    if not frappe.db.exists("DocType", "Sales Person") or not frappe.db.has_column("Sales Person", "user"):
        return ""
    filters = {"user": user}
    if frappe.db.has_column("Sales Person", "enabled"):
        filters["enabled"] = 1
    return frappe.db.get_value("Sales Person", filters, "name") or ""
