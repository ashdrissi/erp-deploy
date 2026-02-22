import frappe
from frappe.utils import flt


def execute():
    if not frappe.db.exists("DocType", "Pricing Scenario"):
        return

    logger = frappe.logger("pricing")
    migrated = 0
    skipped = 0

    scenario_names = frappe.get_all("Pricing Scenario", pluck="name", limit_page_length=0)
    for name in scenario_names:
        doc = frappe.get_doc("Pricing Scenario", name)
        if doc.get("expenses"):
            skipped += 1
            continue

        rows = _legacy_rows(doc)
        if not rows:
            rows = _default_rows()

        for row in rows:
            doc.append("expenses", row)

        doc.save(ignore_permissions=True)
        migrated += 1

    logger.info("Pricing scenario migration complete: migrated=%s skipped=%s", migrated, skipped)


def _legacy_rows(doc):
    rows = []
    sequence = 10

    customs_pct = _get_legacy_float(doc, "customs_percent_default")
    if customs_pct:
        rows.append(_mk(sequence, "Customs", "Percentage", customs_pct, "Base Price"))
        sequence += 10

    taxes_pct = _get_legacy_float(doc, "taxes_percent_of_buy")
    if taxes_pct:
        rows.append(_mk(sequence, "Taxes", "Percentage", taxes_pct, "Running Total"))
        sequence += 10

    margin_pct = _get_legacy_float(doc, "margin_percent_of_buy")
    if margin_pct:
        rows.append(_mk(sequence, "Margin", "Percentage", margin_pct, "Running Total"))
        sequence += 10

    transport_total = _legacy_sum(
        doc,
        [
            "price_container_usd",
            "price_truck_ttc",
            "loading_cost",
            "unloading_cost",
            "transport_risk_alea",
        ],
    )
    if transport_total:
        rows.append(_mk(sequence, "Transport", "Fixed", transport_total, "Running Total", scope="Per Sheet"))
        sequence += 10

    team_total = _legacy_sum(
        doc,
        ["cars_amortization", "hr_cost", "rent_office_stock", "accountant_other"],
    )
    if team_total:
        rows.append(_mk(sequence, "Team Office Charges", "Fixed", team_total, "Running Total", scope="Per Sheet"))

    return rows


def _default_rows():
    return [
        _mk(10, "Freight", "Percentage", 8, "Base Price"),
        _mk(20, "Handling", "Fixed", 12, "Running Total"),
        _mk(30, "Commercial Margin", "Percentage", 15, "Running Total"),
    ]


def _mk(sequence, label, expense_type, value, applies_to, scope="Per Unit"):
    return {
        "sequence": sequence,
        "label": label,
        "type": expense_type,
        "value": flt(value),
        "applies_to": applies_to,
        "scope": scope,
        "is_active": 1,
    }


def _legacy_sum(doc, fieldnames):
    return sum(_get_legacy_float(doc, fieldname) for fieldname in fieldnames)


def _get_legacy_float(doc, fieldname):
    if not frappe.db.has_column("Pricing Scenario", fieldname):
        return 0.0
    return flt(doc.get(fieldname))
