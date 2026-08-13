import frappe


TABLE = "`tabPricing Sheet Item`"
TOLERANCE = 0.000000001


def execute():
    if not frappe.db.table_exists("Pricing Sheet Item"):
        return

    required_columns = {
        "sell_unit_price",
        "sell_total",
        "discount_amount_per_unit",
        "qty",
        "manual_sell_unit_price",
        "final_sell_unit_price",
        "final_sell_total",
        "static_list_price",
        "projected_unit_price",
        "discount_percent",
        "discount_amount",
        "discounted_sell_unit_price",
        "discounted_sell_total",
    }
    missing_columns = sorted(
        column
        for column in required_columns
        if not frappe.db.has_column("Pricing Sheet Item", column)
    )
    if missing_columns:
        raise RuntimeError(
            "Cannot backfill canonical Pricing Sheet prices; missing columns: "
            + ", ".join(missing_columns)
        )

    legacy_unit = """
        COALESCE(
            NULLIF(discounted_sell_unit_price, 0),
            NULLIF(final_sell_unit_price, 0) * (1 - COALESCE(discount_percent, 0) / 100),
            NULLIF(final_sell_unit_price, 0),
            NULLIF(manual_sell_unit_price, 0),
            0
        )
    """
    legacy_total = f"""
        COALESCE(
            NULLIF(discounted_sell_total, 0),
            ({legacy_unit}) * COALESCE(qty, 0),
            NULLIF(final_sell_total, 0),
            0
        )
    """
    legacy_reference_unit = f"""
        COALESCE(
            NULLIF(static_list_price, 0),
            NULLIF(projected_unit_price, 0),
            NULLIF(final_sell_unit_price, 0),
            ({legacy_unit}),
            0
        )
    """
    canonical_discount_per_unit = f"""
        GREATEST(({legacy_reference_unit}) - ({legacy_unit}), 0)
    """
    canonical_discount_percent = f"""
        CASE
            WHEN ({legacy_reference_unit}) > 0 AND ({legacy_unit}) < ({legacy_reference_unit})
                THEN (({legacy_reference_unit}) - ({legacy_unit})) / ({legacy_reference_unit}) * 100
            ELSE 0
        END
    """

    frappe.db.sql(
        f"""
        UPDATE {TABLE}
        SET
            sell_unit_price = CASE
                WHEN ABS(COALESCE(sell_unit_price, 0)) <= %(tolerance)s
                    THEN ({legacy_unit})
                ELSE sell_unit_price
            END,
            sell_total = CASE
                WHEN ABS(COALESCE(sell_total, 0)) <= %(tolerance)s
                    THEN ({legacy_total})
                ELSE sell_total
            END,
            discount_amount_per_unit = CASE
                WHEN ABS(COALESCE(discount_amount_per_unit, 0)) <= %(tolerance)s
                    THEN ({canonical_discount_per_unit})
                ELSE discount_amount_per_unit
            END,
            discount_percent = ({canonical_discount_percent})
        """,
        {"tolerance": TOLERANCE},
    )

    mismatches = frappe.db.sql(
        f"""
        SELECT name
        FROM {TABLE}
        WHERE
            (
                ABS(({legacy_unit})) > %(tolerance)s
                AND ABS(COALESCE(sell_unit_price, 0) - ({legacy_unit})) > %(tolerance)s
            )
            OR (
                ABS(({legacy_total})) > %(tolerance)s
                AND ABS(COALESCE(sell_total, 0) - ({legacy_total})) > %(tolerance)s
            )
            OR (
                ABS(({canonical_discount_per_unit})) > %(tolerance)s
                AND ABS(
                    COALESCE(discount_amount_per_unit, 0) - ({canonical_discount_per_unit})
                ) > %(tolerance)s
            )
            OR ABS(COALESCE(discount_percent, 0) - ({canonical_discount_percent})) > %(tolerance)s
        LIMIT 20
        """,
        {"tolerance": TOLERANCE},
        as_dict=True,
    )
    if mismatches:
        names = ", ".join(row.name for row in mismatches)
        raise RuntimeError(
            "Canonical Pricing Sheet price backfill verification failed for rows: " + names
        )

    for fieldname in (
        "manual_sell_unit_price",
        "final_sell_unit_price",
        "final_sell_total",
        "discount_amount",
        "discounted_sell_unit_price",
        "discounted_sell_total",
    ):
        for name in frappe.get_all(
            "Property Setter",
            filters={"doc_type": "Pricing Sheet Item", "field_name": fieldname},
            pluck="name",
            limit_page_length=0,
        ):
            frappe.delete_doc("Property Setter", name, ignore_permissions=True, force=True)
