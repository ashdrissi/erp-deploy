import frappe


def execute():
    _recalculate_pricing_sheet_lines()
    for doctype in ("Quotation Item", "Sales Order Item"):
        _recalculate_transaction_items(doctype)


def _recalculate_pricing_sheet_lines() -> None:
    required = {
        "sell_unit_price",
        "sell_total",
        "discount_amount_per_unit",
        "discount_percent",
        "max_discount_percent_allowed",
        "commission_rate",
        "commission_amount",
        "static_list_price",
        "projected_unit_price",
        "qty",
    }
    if not all(frappe.db.has_column("Pricing Sheet Item", fieldname) for fieldname in required):
        return

    reference = "COALESCE(NULLIF(static_list_price, 0), NULLIF(projected_unit_price, 0), sell_unit_price, 0)"
    used_discount = f"""
        CASE
            WHEN ({reference}) > 0 AND sell_unit_price < ({reference})
                THEN (({reference}) - sell_unit_price) / ({reference}) * 100
            ELSE 0
        END
    """
    frappe.db.sql(
        f"""
        UPDATE `tabPricing Sheet Item`
        SET
            sell_total = COALESCE(sell_unit_price, 0) * COALESCE(qty, 0),
            discount_amount_per_unit = GREATEST(({reference}) - COALESCE(sell_unit_price, 0), 0),
            discount_percent = ({used_discount}),
            commission_amount = COALESCE(sell_unit_price, 0)
                * COALESCE(qty, 0)
                * GREATEST(COALESCE(max_discount_percent_allowed, 0) - ({used_discount}), 0) / 100
                * COALESCE(commission_rate, 0) / 100
        """
    )


def _recalculate_transaction_items(doctype: str) -> None:
    required = {
        "source_price_list_sell_rate",
        "source_discount_percent",
        "source_max_discount_percent",
        "source_discount_amount",
        "source_commission_rate",
        "source_commission_amount",
        "rate",
        "amount",
        "qty",
    }
    if not all(frappe.db.has_column(doctype, fieldname) for fieldname in required):
        return

    reference = "COALESCE(source_price_list_sell_rate, 0)"
    actual = "COALESCE(rate, 0)"
    used_discount = f"""
        CASE
            WHEN ({reference}) > 0 AND ({actual}) < ({reference})
                THEN (({reference}) - ({actual})) / ({reference}) * 100
            ELSE 0
        END
    """
    optional_assignments = []
    if frappe.db.has_column(doctype, "discount_percentage"):
        optional_assignments.append(f"discount_percentage = ({used_discount})")
    if frappe.db.has_column(doctype, "net_rate"):
        optional_assignments.append(f"net_rate = ({actual})")
    if frappe.db.has_column(doctype, "net_amount"):
        optional_assignments.append(f"net_amount = ({actual}) * COALESCE(qty, 0)")
    optional_sql = ",\n            " + ",\n            ".join(optional_assignments) if optional_assignments else ""

    frappe.db.sql(
        f"""
        UPDATE `tab{doctype}`
        SET
            amount = ({actual}) * COALESCE(qty, 0),
            source_discount_amount = GREATEST(({reference}) - ({actual}), 0),
            source_discount_percent = ({used_discount}),
            source_commission_amount = ({actual})
                * COALESCE(qty, 0)
                * GREATEST(COALESCE(source_max_discount_percent, 0) - ({used_discount}), 0) / 100
                * COALESCE(source_commission_rate, 0) / 100
            {optional_sql}
        """
    )
