from __future__ import annotations

from dataclasses import dataclass

import frappe
from frappe import _


SUPERADMIN_ROLES = frozenset({"Administrator", "System Manager", "Developer"})


@dataclass(frozen=True)
class AccountDefinition:
    key: str
    account_name: str
    root_type: str
    report_type: str
    account_type: str
    parent_hints: tuple[str, ...]
    default_field: str = ""


ACCOUNT_DEFINITIONS: tuple[AccountDefinition, ...] = (
    AccountDefinition("receivable", "Accounts Receivable", "Asset", "Balance Sheet", "Receivable", ("Accounts Receivable", "Receivable", "Current Asset"), "default_receivable_account"),
    AccountDefinition("payable", "Accounts Payable", "Liability", "Balance Sheet", "Payable", ("Accounts Payable", "Payable", "Current Liability"), "default_payable_account"),
    AccountDefinition("bank", "Bank", "Asset", "Balance Sheet", "Bank", ("Bank", "Cash and Bank", "Current Asset"), "default_bank_account"),
    AccountDefinition("cash", "Cash", "Asset", "Balance Sheet", "Cash", ("Cash", "Cash In Hand", "Current Asset"), "default_cash_account"),
    AccountDefinition("sales_revenue", "Sales Revenue", "Income", "Profit and Loss", "Income Account", ("Direct Income", "Income", "Revenue"), "default_income_account"),
    AccountDefinition("purchases", "Purchases / COGS", "Expense", "Profit and Loss", "Expense Account", ("Cost of Goods Sold", "Direct Expenses", "Expenses")),
    AccountDefinition("operating_expenses", "Operating Expenses", "Expense", "Profit and Loss", "Expense Account", ("Indirect Expenses", "Expenses"), "default_expense_account"),
    AccountDefinition("salary_expense", "Salary Expense", "Expense", "Profit and Loss", "Expense Account", ("Indirect Expenses", "Expenses")),
    AccountDefinition("payroll_payable", "Payroll Payable", "Liability", "Balance Sheet", "Payable", ("Current Liabilities", "Payable")),
    AccountDefinition("vat_input", "VAT Input", "Asset", "Balance Sheet", "Tax", ("Duties and Taxes", "Current Asset")),
    AccountDefinition("vat_output", "VAT Output", "Liability", "Balance Sheet", "Tax", ("Duties and Taxes", "Current Liability")),
    AccountDefinition("rounding", "Rounding / Write Off", "Expense", "Profit and Loss", "Expense Account", ("Indirect Expenses", "Expenses"), "round_off_account"),
)

ACCOUNT_DEFINITION_BY_KEY = {definition.key: definition for definition in ACCOUNT_DEFINITIONS}
COMPANY_DEFAULT_FIELDS = {
    "receivable": ("default_receivable_account",),
    "payable": ("default_payable_account",),
    "bank": ("default_bank_account",),
    "cash": ("default_cash_account",),
    "sales_revenue": ("default_income_account",),
    "operating_expenses": ("default_expense_account",),
    "rounding": ("round_off_account", "write_off_account"),
}

PARENT_ACCOUNT_FIELDS = {
    "Sales Invoice": {"debit_to": "receivable"},
    "Purchase Invoice": {"credit_to": "payable"},
}
CHILD_ACCOUNT_FIELDS = {
    "Sales Invoice": {"items": {"income_account": "sales_revenue", "expense_account": "purchases"}},
    "Purchase Invoice": {"items": {"expense_account": "purchases"}},
}
ACCOUNT_FIELD_TABLES = {
    "Sales Invoice": {"items": ("income_account", "expense_account"), "taxes": ("account_head",)},
    "Purchase Invoice": {"items": ("expense_account",), "taxes": ("account_head",)},
    "Payment Entry": {"deductions": ("account",)},
}
COST_CENTER_FIELD_TABLES = {
    "Sales Order": {"items": ("cost_center",)},
    "Sales Invoice": {"items": ("cost_center",), "taxes": ("cost_center",)},
    "Purchase Invoice": {"items": ("cost_center",), "taxes": ("cost_center",)},
    "Payment Entry": {"deductions": ("cost_center",)},
}


def is_account_superadmin(user: str | None = None) -> bool:
    user = user or getattr(frappe.session, "user", None)
    if user == "Administrator":
        return True
    try:
        roles = set(frappe.get_roles(user))
    except Exception:
        roles = set()
    return bool(roles.intersection(SUPERADMIN_ROLES))


def has_account_permission(doc=None, ptype: str | None = None, user: str | None = None, permission_type: str | None = None) -> bool | None:
    permission_type = permission_type or ptype or "read"
    if permission_type in {"read", "select", "report", "export", "print", "email"}:
        return True
    return is_account_superadmin(user)


def has_cost_center_permission(doc=None, ptype: str | None = None, user: str | None = None, permission_type: str | None = None) -> bool | None:
    permission_type = permission_type or ptype or "read"
    if permission_type in {"read", "select", "report", "export", "print", "email"}:
        return True
    return is_account_superadmin(user)


def ensure_company_finance_defaults(doc, method=None) -> dict:
    company = _doc_name(doc)
    if not company or not _doctype_exists("Company") or not _doctype_exists("Account"):
        return {"skipped": True, "reason": "missing Company or Account doctype"}
    if _company_is_group(company):
        return {"skipped": True, "reason": "group company"}

    cost_center = get_company_cost_center(company, create_missing=True)
    account_map = get_company_account_map(company, create_missing=True)
    updated_fields = set_company_default_accounts(company, account_map)
    return {
        "company": company,
        "accounts": account_map,
        "cost_center": cost_center,
        "missing": sorted(set(ACCOUNT_DEFINITION_BY_KEY) - set(account_map)),
        "updated_fields": updated_fields,
    }


def after_migrate() -> dict:
    return ensure_all_company_finance_defaults()


@frappe.whitelist()
def ensure_all_company_finance_defaults() -> dict:
    if not _doctype_exists("Company") or not _doctype_exists("Account"):
        return {"skipped": True, "reason": "missing Company or Account doctype"}

    rows = frappe.get_all(
        "Company",
        filters=_company_setup_filters(),
        pluck="name",
        order_by="name asc",
        limit_page_length=0,
    )
    results = {"companies": [], "missing": {}, "updated_fields": {}}
    for company in rows:
        result = ensure_company_finance_defaults(company)
        results["companies"].append(company)
        if result.get("missing"):
            results["missing"][company] = result.get("missing")
        if result.get("updated_fields"):
            results["updated_fields"][company] = result.get("updated_fields")
    return results


def get_company_account_map(company: str, create_missing: bool = False) -> dict[str, str]:
    account_map: dict[str, str] = {}
    for definition in ACCOUNT_DEFINITIONS:
        account = _company_default_account(company, definition.key)
        if not account:
            account = _find_company_account(company, definition)
        if not account and create_missing:
            account = _create_company_account(company, definition)
        if account:
            account_map[definition.key] = account
    _apply_minimal_account_fallbacks(account_map)
    return account_map


def get_company_cost_center(company: str, create_missing: bool = False) -> str:
    if not company or not _doctype_exists("Cost Center"):
        return ""
    abbr = (frappe.db.get_value("Company", company, "abbr") or "").strip()
    preferred = f"Main - {abbr}" if abbr else ""
    if preferred and _cost_center_belongs_to_company(preferred, company):
        _set_company_default_cost_center(company, preferred)
        return preferred

    existing = _first_cost_center(company)
    if existing:
        _set_company_default_cost_center(company, existing)
        return existing

    if not create_missing:
        return ""

    created = _create_company_cost_center(company)
    if created:
        _set_company_default_cost_center(company, created)
    return created


def _apply_minimal_account_fallbacks(account_map: dict[str, str]) -> None:
    # Keep the chart minimal: if ERPNext cannot create dedicated cost accounts
    # under a child company, reuse the company operating expense account.
    operating_expense = account_map.get("operating_expenses")
    if operating_expense:
        account_map.setdefault("purchases", operating_expense)
        account_map.setdefault("salary_expense", operating_expense)


def set_company_default_accounts(company: str, account_map: dict[str, str]) -> list[str]:
    updated_fields: list[str] = []
    if not _doctype_exists("Company"):
        return updated_fields
    for key, fieldnames in COMPANY_DEFAULT_FIELDS.items():
        account = account_map.get(key)
        if not account:
            continue
        for fieldname in fieldnames:
            if not _has_field("Company", fieldname):
                continue
            if frappe.db.get_value("Company", company, fieldname) == account:
                continue
            frappe.db.set_value("Company", company, fieldname, account, update_modified=False)
            updated_fields.append(fieldname)
    return updated_fields


def apply_document_account_defaults(doc, method=None) -> None:
    company = _document_company(doc)
    if not company:
        return
    account_map: dict[str, str] = {}
    if _doctype_exists("Account"):
        account_map = get_company_account_map(company, create_missing=False)
        _apply_parent_account_defaults(doc, company, account_map)
        _apply_child_account_defaults(doc, company, account_map)
    if getattr(doc, "doctype", "") == "Payment Entry":
        _apply_payment_entry_defaults(doc, company, account_map)
    _apply_cost_center_defaults(doc, company)


def validate_finance_account_setup(doc, method=None) -> None:
    company = _document_company(doc)
    if not company:
        return
    account_map = get_company_account_map(company, create_missing=False) if _doctype_exists("Account") else {}
    required = _required_account_keys(doc) if _doctype_exists("Account") else ()
    missing = [key for key in required if not account_map.get(key)]
    if missing:
        labels = ", ".join(ACCOUNT_DEFINITION_BY_KEY[key].account_name for key in missing)
        frappe.throw(
            _("Company accounting setup is incomplete for {0}. Missing: {1}. Contact Superadmin.").format(
                company,
                labels,
            )
        )

    if _requires_cost_center(doc) and not get_company_cost_center(company, create_missing=False):
        frappe.throw(
            _("Company accounting setup is incomplete for {0}. Missing: Cost Center. Contact Superadmin.").format(
                company,
            )
        )


def protect_account_fields(doc, method=None) -> None:
    if is_account_superadmin():
        return
    before = _doc_before_save(doc)
    if not before:
        return
    changed = sorted(_changed_account_fields(doc, before))
    if changed:
        frappe.throw(
            _("Only superadmin roles can edit backend account or cost center fields. Changed fields: {0}").format(
                ", ".join(changed[:6]),
            )
        )


def validate_finance_document(doc, method=None) -> None:
    validate_finance_account_setup(doc, method=method)
    protect_account_fields(doc, method=method)


def _apply_parent_account_defaults(doc, company: str, account_map: dict[str, str]) -> None:
    for fieldname, key in PARENT_ACCOUNT_FIELDS.get(getattr(doc, "doctype", ""), {}).items():
        _set_account_if_needed(doc, fieldname, account_map.get(key), company)


def _apply_child_account_defaults(doc, company: str, account_map: dict[str, str]) -> None:
    table_map = CHILD_ACCOUNT_FIELDS.get(getattr(doc, "doctype", ""), {})
    for table_field, field_map in table_map.items():
        for row in _child_rows(doc, table_field):
            for fieldname, key in field_map.items():
                _set_account_if_needed(row, fieldname, account_map.get(key), company)


def _apply_payment_entry_defaults(doc, company: str, account_map: dict[str, str]) -> None:
    payment_type = (doc.get("payment_type") or "").strip()
    party_type = (doc.get("party_type") or "").strip()
    cash_bank = _cash_or_bank_account(doc, account_map)
    if payment_type == "Receive":
        if party_type == "Customer":
            _set_account_if_needed(doc, "paid_from", account_map.get("receivable"), company)
        _set_account_if_needed(doc, "paid_to", cash_bank, company)
    elif payment_type == "Pay":
        _set_account_if_needed(doc, "paid_from", cash_bank, company)
        if party_type == "Supplier":
            _set_account_if_needed(doc, "paid_to", account_map.get("payable"), company)


def _apply_cost_center_defaults(doc, company: str) -> None:
    cost_center = get_company_cost_center(company, create_missing=False)
    if not cost_center:
        return
    table_map = COST_CENTER_FIELD_TABLES.get(getattr(doc, "doctype", ""), {})
    for table_field, fieldnames in table_map.items():
        for row in _child_rows(doc, table_field):
            for fieldname in fieldnames:
                _set_cost_center_if_needed(row, fieldname, cost_center, company)


def _required_account_keys(doc) -> tuple[str, ...]:
    doctype = getattr(doc, "doctype", "")
    if doctype == "Sales Invoice":
        return ("receivable", "sales_revenue")
    if doctype == "Purchase Invoice":
        return ("payable", "purchases")
    if doctype == "Payment Entry":
        payment_type = (doc.get("payment_type") or "").strip()
        party_type = (doc.get("party_type") or "").strip()
        if payment_type == "Receive" and party_type == "Customer":
            return ("receivable", "bank")
        if payment_type == "Pay" and party_type == "Supplier":
            return ("payable", "bank")
        return ("bank",)
    return ()


def _changed_account_fields(doc, before) -> set[str]:
    changed: set[str] = set()
    for fieldname in _parent_account_fieldnames(getattr(doc, "doctype", "")):
        if _value(doc, fieldname) != _value(before, fieldname):
            changed.add(fieldname)

    table_map = ACCOUNT_FIELD_TABLES.get(getattr(doc, "doctype", ""), {})
    for table_field, fieldnames in table_map.items():
        current_rows = _rows_by_identity(_child_rows(doc, table_field))
        before_rows = _rows_by_identity(_child_rows(before, table_field))
        for identity, row in current_rows.items():
            old = before_rows.get(identity)
            if not old:
                continue
            for fieldname in fieldnames:
                if _value(row, fieldname) != _value(old, fieldname):
                    changed.add(f"{table_field}.{fieldname}")
    cost_center_table_map = COST_CENTER_FIELD_TABLES.get(getattr(doc, "doctype", ""), {})
    for table_field, fieldnames in cost_center_table_map.items():
        current_rows = _rows_by_identity(_child_rows(doc, table_field))
        before_rows = _rows_by_identity(_child_rows(before, table_field))
        for identity, row in current_rows.items():
            old = before_rows.get(identity)
            if not old:
                continue
            for fieldname in fieldnames:
                if _value(row, fieldname) != _value(old, fieldname):
                    changed.add(f"{table_field}.{fieldname}")
    return changed


def _parent_account_fieldnames(doctype: str) -> tuple[str, ...]:
    if doctype == "Payment Entry":
        return ("paid_from", "paid_to")
    return tuple(PARENT_ACCOUNT_FIELDS.get(doctype, {}))


def _rows_by_identity(rows) -> dict[str, object]:
    out = {}
    for idx, row in enumerate(rows, start=1):
        identity = str(_value(row, "name") or _value(row, "idx") or idx)
        out[identity] = row
    return out


def _set_account_if_needed(target, fieldname: str, account: str | None, company: str) -> None:
    if not account or not _target_has_field(target, fieldname):
        return
    current = _value(target, fieldname)
    force_company_default = not is_account_superadmin() and current != account
    if force_company_default or not current or not _account_belongs_to_company(current, company):
        setattr(target, fieldname, account)


def _set_cost_center_if_needed(target, fieldname: str, cost_center: str | None, company: str) -> None:
    if not cost_center or not _target_has_field(target, fieldname):
        return
    current = _value(target, fieldname)
    force_company_default = not is_account_superadmin() and current != cost_center
    if force_company_default or not current or not _cost_center_belongs_to_company(current, company):
        setattr(target, fieldname, cost_center)


def _cash_or_bank_account(doc, account_map: dict[str, str]) -> str:
    mode = (doc.get("mode_of_payment") or "").lower()
    if "cash" in mode or "espèce" in mode or "espece" in mode:
        return account_map.get("cash") or account_map.get("bank") or ""
    return account_map.get("bank") or account_map.get("cash") or ""


def _company_default_account(company: str, key: str) -> str:
    fieldnames = COMPANY_DEFAULT_FIELDS.get(key, ())
    for fieldname in fieldnames:
        if not _has_field("Company", fieldname):
            continue
        account = frappe.db.get_value("Company", company, fieldname) or ""
        if account and _account_belongs_to_company(account, company):
            return account
    return ""


def _find_company_account(company: str, definition: AccountDefinition) -> str:
    filters = {"company": company, "is_group": 0, "account_name": definition.account_name, "root_type": definition.root_type}
    account = _first_account(filters)
    if account:
        return account
    if definition.account_type:
        return _first_account(
            {
                "company": company,
                "is_group": 0,
                "root_type": definition.root_type,
                "account_type": definition.account_type,
            }
        )
    return ""


def _create_company_account(company: str, definition: AccountDefinition) -> str:
    parent = _parent_account(company, definition.root_type, definition.parent_hints)
    if not parent:
        return ""
    try:
        doc = frappe.new_doc("Account")
        doc.account_name = definition.account_name
        doc.company = company
        doc.parent_account = parent
        doc.root_type = definition.root_type
        doc.report_type = definition.report_type
        if definition.account_type and _target_has_field(doc, "account_type"):
            doc.account_type = definition.account_type
        doc.insert(ignore_permissions=True)
        return doc.name
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"Orderlift finance account setup skipped: {company} / {definition.account_name}",
        )
        return ""


def _parent_account(company: str, root_type: str, hints: tuple[str, ...]) -> str:
    for hint in hints:
        account = _first_account(
            {
                "company": company,
                "is_group": 1,
                "root_type": root_type,
                "account_name": ["like", f"%{hint}%"],
            },
            order_by="lft asc",
        )
        if account:
            return account
    return _first_account({"company": company, "is_group": 1, "root_type": root_type}, order_by="lft asc")


def _first_account(filters: dict, order_by: str = "name asc") -> str:
    if not _doctype_exists("Account"):
        return ""
    rows = frappe.get_all("Account", filters=filters, pluck="name", order_by=order_by, limit_page_length=1)
    return rows[0] if rows else ""


def _first_cost_center(company: str) -> str:
    if not _doctype_exists("Cost Center"):
        return ""
    rows = frappe.get_all(
        "Cost Center",
        filters={"company": company, "is_group": 0, "disabled": 0},
        pluck="name",
        order_by="name asc",
        limit_page_length=1,
    )
    return rows[0] if rows else ""


def _create_company_cost_center(company: str) -> str:
    parent = _parent_cost_center(company)
    try:
        doc = frappe.new_doc("Cost Center")
        doc.cost_center_name = "Main"
        doc.company = company
        doc.is_group = 0
        if parent and _target_has_field(doc, "parent_cost_center"):
            doc.parent_cost_center = parent
        doc.insert(ignore_permissions=True)
        return doc.name
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"Orderlift finance cost center setup skipped: {company}",
        )
        return ""


def _parent_cost_center(company: str) -> str:
    if not _doctype_exists("Cost Center"):
        return ""
    rows = frappe.get_all(
        "Cost Center",
        filters={"company": company, "is_group": 1},
        pluck="name",
        order_by="lft desc",
        limit_page_length=1,
    )
    return rows[0] if rows else ""


def _account_belongs_to_company(account: str, company: str) -> bool:
    if not account or not company:
        return False
    account_company = frappe.db.get_value("Account", account, "company")
    return account_company == company


def _cost_center_belongs_to_company(cost_center: str, company: str) -> bool:
    if not cost_center or not company or not _doctype_exists("Cost Center"):
        return False
    row = frappe.db.get_value("Cost Center", cost_center, ["company", "is_group", "disabled"], as_dict=True)
    if not row:
        return False
    return row.company == company and not bool(row.is_group) and not bool(row.disabled)


def _set_company_default_cost_center(company: str, cost_center: str) -> None:
    if not cost_center or not _has_field("Company", "cost_center"):
        return
    if frappe.db.get_value("Company", company, "cost_center") == cost_center:
        return
    frappe.db.set_value("Company", company, "cost_center", cost_center, update_modified=False)


def _requires_cost_center(doc) -> bool:
    return bool(COST_CENTER_FIELD_TABLES.get(getattr(doc, "doctype", "")))


def _company_is_group(company: str) -> bool:
    if not _has_field("Company", "is_group"):
        return False
    return bool(frappe.db.get_value("Company", company, "is_group"))


def _company_setup_filters() -> dict:
    filters = {}
    if _has_field("Company", "is_group"):
        filters["is_group"] = 0
    if _has_field("Company", "disabled"):
        filters["disabled"] = 0
    return filters


def _document_company(doc) -> str:
    return (doc.get("company") if hasattr(doc, "get") else getattr(doc, "company", "")) or ""


def _doc_name(doc) -> str:
    if isinstance(doc, str):
        return doc
    if getattr(doc, "doctype", None) == "Company":
        return getattr(doc, "name", "") or doc.get("name")
    return getattr(doc, "name", "") or (doc.get("name") if hasattr(doc, "get") else "")


def _doc_before_save(doc):
    try:
        return doc.get_doc_before_save()
    except Exception:
        return None


def _child_rows(doc, fieldname: str) -> list:
    rows = doc.get(fieldname) if hasattr(doc, "get") else getattr(doc, fieldname, None)
    return list(rows or [])


def _target_has_field(target, fieldname: str) -> bool:
    meta = getattr(target, "meta", None)
    if meta and hasattr(meta, "get_field"):
        return bool(meta.get_field(fieldname))
    return hasattr(target, fieldname)


def _value(target, fieldname: str):
    if hasattr(target, "get"):
        return target.get(fieldname)
    return getattr(target, fieldname, None)


def _doctype_exists(doctype: str) -> bool:
    try:
        return bool(frappe.db.exists("DocType", doctype))
    except Exception:
        return True


def _has_field(doctype: str, fieldname: str) -> bool:
    try:
        return bool(frappe.get_meta(doctype).get_field(fieldname))
    except Exception:
        return False
