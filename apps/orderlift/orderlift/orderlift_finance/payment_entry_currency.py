from __future__ import annotations

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import flt


SUPPORTED_SOURCE_DOCTYPES = frozenset(
    {"Sales Invoice", "Purchase Invoice", "Sales Order", "Purchase Order"}
)
SOURCE_CURRENCY_FIELD = "custom_source_document_currency"
SOURCE_AMOUNT_FIELD = "custom_source_payment_amount"
SOURCE_RATE_FIELD = "custom_source_to_company_exchange_rate"
COMPANY_AMOUNT_FIELD = "custom_converted_company_amount"


def after_migrate() -> None:
    create_custom_fields(
        {
            "Payment Entry": [
                {
                    "fieldname": "custom_source_payment_section",
                    "label": "Source Document Payment",
                    "fieldtype": "Section Break",
                    "insert_after": "references",
                    "depends_on": f"eval:doc.{SOURCE_CURRENCY_FIELD}",
                },
                {
                    "fieldname": SOURCE_CURRENCY_FIELD,
                    "label": "Source Document Currency",
                    "fieldtype": "Link",
                    "options": "Currency",
                    "insert_after": "custom_source_payment_section",
                    "read_only": 1,
                },
                {
                    "fieldname": SOURCE_AMOUNT_FIELD,
                    "label": "Payment Amount in Source Currency",
                    "fieldtype": "Currency",
                    "options": SOURCE_CURRENCY_FIELD,
                    "insert_after": SOURCE_CURRENCY_FIELD,
                },
                {
                    "fieldname": "custom_source_payment_column",
                    "fieldtype": "Column Break",
                    "insert_after": SOURCE_AMOUNT_FIELD,
                },
                {
                    "fieldname": SOURCE_RATE_FIELD,
                    "label": "Source to Company Exchange Rate",
                    "fieldtype": "Float",
                    "precision": 9,
                    "insert_after": "custom_source_payment_column",
                    "description": "Company currency received for one unit of source document currency.",
                },
                {
                    "fieldname": COMPANY_AMOUNT_FIELD,
                    "label": "Converted Amount in Company Currency",
                    "fieldtype": "Currency",
                    "options": "Company:company:default_currency",
                    "insert_after": SOURCE_RATE_FIELD,
                    "read_only": 1,
                },
            ]
        },
        update=True,
    )


@frappe.whitelist()
def get_payment_entry(
    dt,
    dn,
    party_amount=None,
    bank_account=None,
    bank_amount=None,
    party_type=None,
    payment_type=None,
    reference_date=None,
    created_from_payment_request=False,
):
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry as erpnext_get_payment_entry

    payment_entry = erpnext_get_payment_entry(
        dt,
        dn,
        party_amount=party_amount,
        bank_account=bank_account,
        bank_amount=bank_amount,
        party_type=party_type,
        payment_type=payment_type,
        reference_date=reference_date,
        created_from_payment_request=created_from_payment_request,
    )
    if dt in SUPPORTED_SOURCE_DOCTYPES:
        initialize_source_currency_payment(payment_entry, frappe.get_doc(dt, dn))
    return payment_entry


def initialize_source_currency_payment(payment_entry, source_doc) -> None:
    company_currency = _company_currency(payment_entry.company)
    source_currency = (source_doc.get("currency") or company_currency or "").strip()
    if source_currency == company_currency:
        return

    rate = _initial_source_rate(source_doc, source_currency, company_currency)
    company_amount = _party_company_amount(payment_entry)
    source_amount = _rounded(payment_entry, SOURCE_AMOUNT_FIELD, company_amount / rate if rate else 0)

    payment_entry.set(SOURCE_CURRENCY_FIELD, source_currency)
    payment_entry.set(SOURCE_AMOUNT_FIELD, source_amount)
    payment_entry.set(SOURCE_RATE_FIELD, rate)
    apply_source_currency_payment(payment_entry)


def apply_source_currency_payment(doc, method=None) -> None:
    source_currency = (doc.get(SOURCE_CURRENCY_FIELD) or "").strip()
    if not source_currency:
        return

    references = _supported_references(doc)
    if not references:
        frappe.throw(_("Source-currency payments require an invoice or order reference."))
    named_references = [row for row in doc.get("references") or [] if row.get("reference_name")]
    if len(named_references) != len(references):
        frappe.throw(_("Source-currency payments cannot mix invoice/order references with other references."))

    reference_currencies = {_reference_currency(row) for row in references}
    reference_currencies.discard("")
    if reference_currencies != {source_currency}:
        frappe.throw(
            _("All source documents must use the selected source currency {0}.").format(source_currency)
        )

    deductions = [
        row
        for row in doc.get("deductions") or []
        if flt(row.get("amount")) and not row.get("is_exchange_gain_loss")
    ]
    if deductions:
        frappe.throw(
            _("Source-currency payments do not support deductions. Record deductions separately.")
        )

    company_currency = _company_currency(doc.get("company"))
    amount = flt(doc.get(SOURCE_AMOUNT_FIELD))
    rate = flt(doc.get(SOURCE_RATE_FIELD))
    if amount <= 0:
        frappe.throw(_("Payment Amount in Source Currency must be greater than zero."))
    if source_currency == company_currency:
        rate = 1
        doc.set(SOURCE_RATE_FIELD, rate)
    elif rate <= 0:
        frappe.throw(_("Source to Company Exchange Rate must be greater than zero."))

    company_amount = _rounded(doc, COMPANY_AMOUNT_FIELD, amount * rate)
    doc.set(COMPANY_AMOUNT_FIELD, company_amount)
    _set_account_currency_amounts(doc, source_currency, company_currency, amount, company_amount, rate)
    _allocate_party_amount(doc, references)


@frappe.whitelist()
def preview_source_currency_payment(doc) -> dict:
    payload = frappe.parse_json(doc) if isinstance(doc, str) else doc
    payment_entry = frappe.get_doc(payload)
    apply_source_currency_payment(payment_entry)
    return {
        "paid_from_account_currency": payment_entry.get("paid_from_account_currency"),
        "paid_to_account_currency": payment_entry.get("paid_to_account_currency"),
        "source_exchange_rate": payment_entry.get("source_exchange_rate"),
        "target_exchange_rate": payment_entry.get("target_exchange_rate"),
        "paid_amount": payment_entry.get("paid_amount"),
        "received_amount": payment_entry.get("received_amount"),
        "base_paid_amount": payment_entry.get("base_paid_amount"),
        "base_received_amount": payment_entry.get("base_received_amount"),
        COMPANY_AMOUNT_FIELD: payment_entry.get(COMPANY_AMOUNT_FIELD),
        SOURCE_RATE_FIELD: payment_entry.get(SOURCE_RATE_FIELD),
        "references": [
            {"name": row.name, "allocated_amount": row.allocated_amount}
            for row in payment_entry.get("references") or []
        ],
    }


def _set_account_currency_amounts(
    doc,
    source_currency: str,
    company_currency: str,
    source_amount: float,
    company_amount: float,
    source_rate: float,
) -> None:
    from_currency = _account_currency(doc.get("paid_from"), doc.get("paid_from_account_currency"))
    to_currency = _account_currency(doc.get("paid_to"), doc.get("paid_to_account_currency"))
    from_rate = _account_to_company_rate(
        doc,
        from_currency,
        source_currency,
        company_currency,
        source_rate,
        "source_exchange_rate",
    )
    to_rate = _account_to_company_rate(
        doc,
        to_currency,
        source_currency,
        company_currency,
        source_rate,
        "target_exchange_rate",
    )

    paid_amount = _amount_in_account_currency(
        from_currency, source_currency, company_currency, source_amount, company_amount, from_rate
    )
    received_amount = _amount_in_account_currency(
        to_currency, source_currency, company_currency, source_amount, company_amount, to_rate
    )
    doc.set("paid_from_account_currency", from_currency)
    doc.set("paid_to_account_currency", to_currency)
    doc.set("source_exchange_rate", from_rate)
    doc.set("target_exchange_rate", to_rate)
    doc.set("paid_amount", _rounded(doc, "paid_amount", paid_amount))
    doc.set("received_amount", _rounded(doc, "received_amount", received_amount))
    doc.set("base_paid_amount", company_amount)
    doc.set("base_received_amount", company_amount)


def _allocate_party_amount(doc, references) -> None:
    payment_type = (doc.get("payment_type") or "").strip()
    party_amount = flt(doc.get("paid_amount") if payment_type == "Receive" else doc.get("received_amount"))
    tolerance = 1 / (10 ** _currency_precision())
    allocator = getattr(doc, "allocate_amount_to_references", None)
    if callable(allocator):
        allocator(party_amount, paid_amount_change=True, allocate_payment_amount=True)
    else:
        remaining = party_amount
        for row in references:
            available = abs(flt(row.get("outstanding_amount")))
            allocated = min(remaining, available)
            row.allocated_amount = _rounded(doc, "total_allocated_amount", allocated)
            remaining -= allocated

    if all(flt(row.get("outstanding_amount")) >= 0 for row in references):
        allocated = sum(flt(row.get("allocated_amount")) for row in references)
        if party_amount > allocated + tolerance:
            frappe.throw(
                _("Converted payment amount {0} exceeds the referenced outstanding amount {1}.").format(
                    party_amount,
                    allocated,
                )
            )


def _supported_references(doc) -> list:
    return [
        row
        for row in doc.get("references") or []
        if (row.get("reference_doctype") or "").strip() in SUPPORTED_SOURCE_DOCTYPES
        and (row.get("reference_name") or "").strip()
    ]


def _reference_currency(row) -> str:
    return (
        frappe.db.get_value(row.get("reference_doctype"), row.get("reference_name"), "currency") or ""
    ).strip()


def _initial_source_rate(source_doc, source_currency: str, company_currency: str) -> float:
    if source_currency == company_currency:
        return 1
    rate = flt(source_doc.get("conversion_rate") or source_doc.get("exchange_rate"))
    if rate > 0:
        return rate

    from erpnext.setup.utils import get_exchange_rate

    posting_date = source_doc.get("posting_date") or source_doc.get("transaction_date")
    return flt(get_exchange_rate(source_currency, company_currency, posting_date))


def _party_company_amount(payment_entry) -> float:
    if payment_entry.get("payment_type") == "Pay":
        return flt(payment_entry.get("base_received_amount"))
    return flt(payment_entry.get("base_paid_amount"))


def _account_currency(account: str, current_currency: str) -> str:
    if not account:
        return (current_currency or "").strip()
    return (frappe.db.get_value("Account", account, "account_currency") or current_currency or "").strip()


def _account_to_company_rate(
    doc,
    account_currency: str,
    source_currency: str,
    company_currency: str,
    source_rate: float,
    fieldname: str,
) -> float:
    if account_currency == company_currency:
        return 1
    if account_currency == source_currency:
        return source_rate

    current_rate = flt(doc.get(fieldname))
    if current_rate > 0:
        return current_rate

    from erpnext.setup.utils import get_exchange_rate

    return flt(get_exchange_rate(account_currency, company_currency, doc.get("posting_date")))


def _amount_in_account_currency(
    account_currency: str,
    source_currency: str,
    company_currency: str,
    source_amount: float,
    company_amount: float,
    account_rate: float,
) -> float:
    if account_currency == source_currency:
        return source_amount
    if account_currency == company_currency:
        return company_amount
    if account_rate <= 0:
        frappe.throw(_("An exchange rate is required for account currency {0}.").format(account_currency))
    return company_amount / account_rate


def _company_currency(company: str) -> str:
    return (frappe.get_cached_value("Company", company, "default_currency") or "").strip()


def _currency_precision() -> int:
    try:
        return int(frappe.get_system_settings("currency_precision") or 2)
    except Exception:
        return 2


def _rounded(doc, fieldname: str, value: float) -> float:
    try:
        precision = doc.precision(fieldname)
    except Exception:
        precision = _currency_precision()
    return flt(value, precision)
