import frappe
from frappe import _
from frappe.utils import cint

from orderlift.menu_access import resolve_current_company
from orderlift.role_capabilities import (
    CAPABILITY_PRIVILEGED_PRICING,
    CAPABILITY_PURCHASING_ACCESS,
    CAPABILITY_QUOTATION_OVERRIDE,
    role_capability_decision,
)


# Role sets for Item-form price visibility (tunable). Privileged users see every
# active-company price list; sales agents are limited to their allocated selling
# lists; buying (cost) prices are gated behind purchasing access.
PRIVILEGED_PRICE_ROLES = {
    "Orderlift Admin",
    "Orderlift Business Admin",
    "Pricing Manager",
    "Sales Manager",
    "Purchase Manager",
    "System Manager",
}
SALES_AGENT_ROLES = {"Sales User", "Orderlift Commercial"}
PURCHASING_ROLES = {"Purchase User", "Purchase Manager", "Purchasing User", "Stock Manager"}

QUOTATION_PRICE_OVERRIDE_ROLES = {
    "Orderlift Admin",
    "Orderlift Business Admin",
}


def can_override_quotation_pricing():
    user = frappe.session.user
    if user == "Administrator":
        return True
    try:
        roles = set(frappe.get_roles(user) or [])
    except (AttributeError, TypeError):
        return False
    legacy_allowed = bool(roles & (QUOTATION_PRICE_OVERRIDE_ROLES | {"System Manager"}))
    return role_capability_decision(
        CAPABILITY_QUOTATION_OVERRIDE,
        legacy_allowed,
        user=user,
        roles=roles,
        context="can_override_quotation_pricing",
    )

PRICE_LIST_TYPE_FIELD = "custom_price_list_type"
BUYING_PRICE_LIST = "Buying"
SELLING_PRICE_LIST = "Selling"
BENCHMARK_PRICE_LIST = "Benchmark"
KNOWN_PRICE_LIST_TYPES = {BUYING_PRICE_LIST, SELLING_PRICE_LIST, BENCHMARK_PRICE_LIST}


def current_company():
    return resolve_current_company(user=frappe.session.user)


def price_list_filters(kind=None, company=None):
    filters = {}
    if _has_column("Price List", "enabled"):
        filters["enabled"] = 1
    if kind and _has_column("Price List", PRICE_LIST_TYPE_FIELD):
        list_type = _list_type_for_kind(kind)
        if list_type:
            filters[PRICE_LIST_TYPE_FIELD] = list_type
    else:
        if kind == "buying" and _has_column("Price List", "buying"):
            filters["buying"] = 1
        if kind == "selling" and _has_column("Price List", "selling"):
            filters["selling"] = 1
    company = (company or current_company() or "").strip()
    if company and _has_column("Price List", "custom_company"):
        filters["custom_company"] = company
    return filters


def get_price_lists(kind=None, fields=None, company=None):
    fields = fields or ["name"]
    return frappe.get_all(
        "Price List",
        filters=price_list_filters(kind=kind, company=company),
        fields=fields,
        order_by="name asc",
        limit_page_length=0,
    )


def get_price_list_names(kind=None, company=None):
    return frappe.get_all(
        "Price List",
        filters=price_list_filters(kind=kind, company=company),
        pluck="name",
        order_by="name asc",
        limit_page_length=0,
    )


def validate_price_list_scope(price_list_name, kind=None, required=False, company=None):
    price_list_name = (price_list_name or "").strip()
    if not price_list_name:
        if required:
            frappe.throw(_("Price List is required."))
        return ""

    fields = ["name"]
    if _has_column("Price List", PRICE_LIST_TYPE_FIELD):
        fields.append(PRICE_LIST_TYPE_FIELD)
    if kind == "buying" and _has_column("Price List", "buying"):
        fields.append("buying")
    if kind == "selling" and _has_column("Price List", "selling"):
        fields.append("selling")
    if _has_column("Price List", "custom_company"):
        fields.append("custom_company")

    values = frappe.db.get_value("Price List", price_list_name, fields, as_dict=True)
    if not values:
        frappe.throw(_("Price List {0} does not exist.").format(price_list_name))

    if kind == "buying" and "buying" in fields and cint(values.get("buying")) != 1:
        frappe.throw(_("Price List {0} is not a buying price list.").format(price_list_name))
    if kind == "selling" and "selling" in fields and cint(values.get("selling")) != 1:
        frappe.throw(_("Price List {0} is not a selling price list.").format(price_list_name))
    expected_type = _list_type_for_kind(kind)
    actual_type = get_price_list_type(price_list_name, values=values)
    if expected_type and actual_type != expected_type:
        frappe.throw(_("Price List {0} is not a {1} price list.").format(price_list_name, expected_type))

    company = (company or current_company() or "").strip()
    if company and "custom_company" in fields and (values.get("custom_company") or "").strip() != company:
        frappe.throw(_("Price List {0} does not belong to company {1}.").format(price_list_name, company))
    return price_list_name


def apply_price_list_company(doc, company=None):
    company = (company or current_company() or "").strip()
    if company and _doc_has_field(doc, "custom_company"):
        setter = getattr(doc, "set", None)
        if callable(setter):
            setter("custom_company", company)
        else:
            setattr(doc, "custom_company", company)


def get_price_list_type(price_list_name=None, values=None):
    values = values or {}
    if not values and price_list_name:
        fields = ["buying", "selling"]
        if _has_column("Price List", PRICE_LIST_TYPE_FIELD):
            fields.append(PRICE_LIST_TYPE_FIELD)
        values = frappe.db.get_value("Price List", price_list_name, fields, as_dict=True) or {}
    explicit = (values.get(PRICE_LIST_TYPE_FIELD) or "").strip()
    if explicit in KNOWN_PRICE_LIST_TYPES:
        return explicit
    is_buying = cint(values.get("buying")) == 1
    is_selling = cint(values.get("selling")) == 1
    if is_buying:
        return BUYING_PRICE_LIST
    if is_selling:
        return SELLING_PRICE_LIST
    return BENCHMARK_PRICE_LIST if explicit == BENCHMARK_PRICE_LIST else "Unknown"


def normalize_price_list_type(doc):
    if not doc:
        return ""
    explicit = (getattr(doc, PRICE_LIST_TYPE_FIELD, "") or "").strip()
    if explicit not in KNOWN_PRICE_LIST_TYPES:
        explicit = get_price_list_type(values={
            "buying": getattr(doc, "buying", 0),
            "selling": getattr(doc, "selling", 0),
            PRICE_LIST_TYPE_FIELD: explicit,
        })
        if explicit == "Unknown":
            explicit = SELLING_PRICE_LIST if cint(getattr(doc, "selling", 0)) else BUYING_PRICE_LIST if cint(getattr(doc, "buying", 0)) else SELLING_PRICE_LIST
    setattr(doc, PRICE_LIST_TYPE_FIELD, explicit)
    if explicit == BUYING_PRICE_LIST:
        doc.buying = 1
        doc.selling = 0
    elif explicit == SELLING_PRICE_LIST:
        doc.buying = 0
        doc.selling = 1
    elif explicit == BENCHMARK_PRICE_LIST:
        # ERPNext rejects Price Lists that are neither buying nor selling.
        # Orderlift uses custom_price_list_type as the authoritative type, so a
        # Benchmark list stays out of selling filters while remaining saveable.
        doc.buying = 0
        doc.selling = 1
    return explicit


def validate_price_list_type(doc, method=None):
    explicit = normalize_price_list_type(doc)
    if explicit == BENCHMARK_PRICE_LIST:
        builder_name = (getattr(doc, "custom_pricing_builder", "") or "").strip()
        if builder_name and cint(getattr(doc, "custom_auto_rebuild_from_source_buying_prices", 0)):
            frappe.throw(_("Benchmark Price Lists cannot auto rebuild from source buying prices."))


def validate_price_list_unique_name_context(doc, method=None):
    target_name = (getattr(doc, "price_list_name", "") or getattr(doc, "name", "") or "").strip()
    if not target_name:
        return

    existing = _existing_price_list_by_name_or_title(target_name)
    if not existing:
        return
    current_name = (getattr(doc, "name", "") or "").strip()
    if current_name and existing.get("name") == current_name:
        return

    active_company = current_company()
    frappe.throw(
        _(
            "Price List {0} already exists under company {1}. Your active company is {2}. "
            "Price List names are global; switch company or use a unique name."
        ).format(
            existing.get("name") or target_name,
            existing.get("custom_company") or "-",
            active_company or "-",
        )
    )


def _existing_price_list_by_name_or_title(target_name: str) -> dict | None:
    fields = ["name"]
    if _has_column("Price List", "custom_company"):
        fields.append("custom_company")
    existing = frappe.db.get_value("Price List", target_name, fields, as_dict=True)
    if existing:
        return existing
    return frappe.db.get_value("Price List", {"price_list_name": target_name}, fields, as_dict=True)


def preserve_price_list_builder_stamp(doc, method=None):
    if not _doc_has_field(doc, "custom_pricing_builder"):
        return
    if (getattr(doc, "custom_pricing_builder", "") or "").strip():
        return

    price_list_name = (getattr(doc, "name", "") or getattr(doc, "price_list_name", "") or "").strip()
    builder_name = _previous_price_list_builder(doc)
    if not builder_name:
        if not price_list_name or not getattr(frappe, "db", None) or not frappe.db.exists("Price List", price_list_name):
            return
        builder_name = _single_item_price_builder(price_list_name)
    if not builder_name:
        return

    doc.custom_pricing_builder = builder_name
    if _doc_has_field(doc, "custom_source_buying_price_lists") and not (
        getattr(doc, "custom_source_buying_price_lists", "") or ""
    ).strip() and getattr(frappe, "db", None):
        doc.custom_source_buying_price_lists = _source_lists_for_builder_price_list(price_list_name, builder_name)


def _previous_price_list_builder(doc):
    before_getter = getattr(doc, "get_doc_before_save", None)
    before = before_getter() if callable(before_getter) else None
    if not before:
        return ""
    return (getattr(before, "custom_pricing_builder", "") or "").strip()


def _single_item_price_builder(price_list_name):
    rows = frappe.db.sql(
        """
        SELECT custom_pricing_builder AS builder_name, COUNT(*) AS row_count
        FROM `tabItem Price`
        WHERE price_list = %s AND IFNULL(custom_pricing_builder, '') != ''
        GROUP BY custom_pricing_builder
        ORDER BY row_count DESC
        LIMIT 2
        """,
        (price_list_name,),
        as_dict=True,
    )
    return (rows[0].builder_name or "").strip() if len(rows) == 1 else ""


def _source_lists_for_builder_price_list(price_list_name, builder_name):
    if not _has_column("Item Price", "custom_source_buying_price_list"):
        return ""
    rows = frappe.db.sql(
        """
        SELECT DISTINCT custom_source_buying_price_list AS source_list
        FROM `tabItem Price`
        WHERE price_list = %s
            AND custom_pricing_builder = %s
            AND IFNULL(custom_source_buying_price_list, '') != ''
        ORDER BY custom_source_buying_price_list ASC
        """,
        (price_list_name, builder_name),
        as_dict=True,
    )
    return "\n".join((row.source_list or "").strip() for row in rows if (row.source_list or "").strip())


def get_visible_price_lists(kind=None, company=None, user=None):
    user = user or frappe.session.user
    kind = (kind or "").strip().lower()
    company = (company or current_company() or "").strip()
    if not kind:
        visible = set()
        for list_kind in ("selling", "buying", "benchmark"):
            visible.update(get_visible_price_lists(list_kind, company=company, user=user))
        return sorted(visible)

    company_lists = set(get_price_list_names(kind, company=company))
    roles = set(frappe.get_roles(user) or [])
    privileged_allowed = user == "Administrator" or bool(roles & PRIVILEGED_PRICE_ROLES)
    if role_capability_decision(
        CAPABILITY_PRIVILEGED_PRICING,
        privileged_allowed,
        user=user,
        roles=roles,
        context="get_visible_price_lists",
    ):
        return sorted(company_lists)
    sales_person = _user_sales_person(user)
    if kind == "selling":
        return sorted(company_lists & _agent_selling_lists(sales_person))
    if kind == "benchmark":
        return sorted(company_lists & _agent_benchmark_lists(sales_person))
    if kind == "buying":
        purchasing_allowed = bool(roles & PURCHASING_ROLES)
        if not role_capability_decision(
            CAPABILITY_PURCHASING_ACCESS,
            purchasing_allowed,
            user=user,
            roles=roles,
            context="get_visible_price_lists.buying",
        ):
            return []
        buying_alloc = _agent_buying_lists(sales_person)
        if buying_alloc is not None:
            return sorted(company_lists & buying_alloc)
    return sorted(company_lists)


def validate_visible_price_list(price_list_name, kind=None, required=False, company=None, user=None):
    price_list_name = validate_price_list_scope(price_list_name, kind=kind, required=required, company=company)
    if not price_list_name:
        return ""
    user = user or frappe.session.user
    kind = (kind or _kind_for_price_list(price_list_name) or "").strip().lower()
    allowed = set(get_visible_price_lists(kind, company=company, user=user)) if kind else set(get_visible_price_lists(company=company, user=user))
    if price_list_name not in allowed:
        frappe.throw(_("Price List {0} is not allowed for your current company/access.").format(price_list_name))
    return price_list_name


def get_item_price_access(kind, company=None):
    """Resolve which Price Lists the current user may see on the Item form for a kind.

    Returns ``{"permitted", "restricted", "price_lists", "reason"}``:
      * permitted  — whether the grid is shown at all (buying needs purchasing access)
      * restricted — whether agent ruling narrowed the list (UI hint)
      * price_lists — allowed Price List names, active-company scoped
    """
    kind = (kind or "").strip().lower()
    user = frappe.session.user
    company = (company or current_company() or "").strip()
    company_lists = set(get_price_list_names(kind, company=company))

    if user == "Administrator":
        return _access(True, False, company_lists, "admin")
    roles = set(frappe.get_roles(user) or [])

    # Buying = supplier cost: only users with purchasing access may see it.
    purchasing_allowed = bool(roles & PURCHASING_ROLES)
    if kind == "buying" and not role_capability_decision(
        CAPABILITY_PURCHASING_ACCESS,
        purchasing_allowed,
        user=user,
        roles=roles,
        context="get_item_price_access.buying",
    ):
        return _access(False, False, set(), "no_purchasing_access")

    sales_person = _user_sales_person(user)

    if kind == "selling":
        return _access(True, True, company_lists & _agent_selling_lists(sales_person), "agent_selling")

    if kind == "benchmark":
        return _access(True, True, company_lists & _agent_benchmark_lists(sales_person), "agent_benchmark")

    # kind == "buying" and user has purchasing access: narrow to a dynamic agent
    # allocation when one exists; otherwise a normal purchaser sees all lists.
    buying_alloc = _agent_buying_lists(sales_person)
    if buying_alloc is not None:
        return _access(True, True, company_lists & buying_alloc, "agent_buying")
    return _access(True, False, company_lists, "buying")


def _access(permitted, restricted, price_lists, reason):
    return {
        "permitted": bool(permitted),
        "restricted": bool(restricted),
        "price_lists": sorted(price_lists),
        "reason": reason,
    }


def _agent_selling_lists(sales_person):
    if not sales_person:
        return set()
    # Lazy import: agent_pricing_rules imports from this module (avoid a cycle).
    from orderlift.orderlift_sales.doctype.agent_pricing_rules.agent_pricing_rules import (
        STATIC_MODE,
        build_static_context,
    )

    context = build_static_context(sales_person=sales_person)
    if (context.get("pricing_mode") or "") != STATIC_MODE:
        return set()
    return {pl for pl in (context.get("selling_price_lists") or []) if pl}


def _agent_buying_lists(sales_person):
    """Set of dynamically-allocated buying lists, or None when the user has no
    dynamic allocation (treated as unrestricted)."""
    if not sales_person:
        return None
    from orderlift.orderlift_sales.doctype.agent_pricing_rules.agent_pricing_rules import (
        DYNAMIC_MODE,
        build_dynamic_context,
    )

    context = build_dynamic_context(sales_person=sales_person)
    if (context.get("pricing_mode") or "") != DYNAMIC_MODE:
        return None
    return {pl for pl in (context.get("allowed_buying_price_lists") or []) if pl}


def _agent_benchmark_lists(sales_person):
    if not sales_person:
        return set()
    from orderlift.orderlift_sales.doctype.agent_pricing_rules.agent_pricing_rules import build_static_context

    context = build_static_context(sales_person=sales_person)
    return {pl for pl in (context.get("benchmark_price_lists") or []) if pl}


def _list_type_for_kind(kind):
    kind = (kind or "").strip().lower()
    return {
        "buying": BUYING_PRICE_LIST,
        "selling": SELLING_PRICE_LIST,
        "benchmark": BENCHMARK_PRICE_LIST,
    }.get(kind)


def _kind_for_price_list(price_list_name):
    values = frappe.db.get_value(
        "Price List",
        price_list_name,
        [PRICE_LIST_TYPE_FIELD, "buying", "selling"] if _has_column("Price List", PRICE_LIST_TYPE_FIELD) else ["buying", "selling"],
        as_dict=True,
    ) or {}
    list_type = get_price_list_type(values=values)
    if list_type == SELLING_PRICE_LIST:
        return "selling"
    if list_type == BUYING_PRICE_LIST:
        return "buying"
    if list_type == BENCHMARK_PRICE_LIST:
        return "benchmark"
    return ""


def _user_sales_person(user):
    if not frappe.db.exists("DocType", "Sales Person") or not _has_column("Sales Person", "user"):
        return ""
    filters = {"user": user}
    if _has_column("Sales Person", "enabled"):
        filters["enabled"] = 1
    return frappe.db.get_value("Sales Person", filters, "name") or ""


def _has_column(doctype, fieldname):
    checker = getattr(getattr(frappe, "db", None), "has_column", None)
    return bool(checker(doctype, fieldname)) if callable(checker) else False


def _doc_has_field(doc, fieldname):
    meta = getattr(doc, "meta", None)
    has_field = getattr(meta, "has_field", None)
    if callable(has_field):
        return bool(has_field(fieldname))
    return hasattr(doc, fieldname)
