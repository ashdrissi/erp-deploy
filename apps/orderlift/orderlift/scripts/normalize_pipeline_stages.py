"""Normalize stale pipeline status values across all doctypes and companies.

Run with:
    bench --site erp.ecomepivot.com execute orderlift.scripts.normalize_pipeline_stages.run --kwargs '{"dry_run": 1}'
    bench --site erp.ecomepivot.com execute orderlift.scripts.normalize_pipeline_stages.run

The script fixes records whose stored status value no longer matches an active
status row name (typically after a rename in Status Control).
"""
from __future__ import annotations

import json

import frappe


DOCTYPES = [
    {
        "doctype": "Opportunity",
        "status_field": "sales_stage",
        "status_doctype": "Sales Stage",
        "status_name_field": "name",
        "status_active_field": "custom_is_active",
        "status_company_field": "custom_company",
    },
    {
        "doctype": "Project",
        "status_field": "custom_project_status",
        "status_doctype": "Project Status",
        "status_name_field": "name",
        "status_active_field": "is_active",
        "status_company_field": "company",
    },
    {
        "doctype": "Sales Order",
        "status_field": "custom_orderlift_order_status",
        "status_doctype": "Orderlift Order Status",
        "status_name_field": "name",
        "status_active_field": "is_active",
        "status_company_field": "company",
    },
]


def _strip_short_name(value):
    """Strip company prefix to get the short label."""
    if not value:
        return value
    prefix = value.split(" - ", 1)
    return prefix[-1] if len(prefix) > 1 else value


def _active_statuses_by_company(status_doctype, active_field, company_field, name_field):
    """Build {company: {stored_value: canonical_name}} lookup."""
    conditions = f"`{active_field}` = 1"
    if status_doctype != "Sales Stage":
        conditions += f" AND `{company_field}` IS NOT NULL AND `{company_field}` != ''"

    sql = f"""
        SELECT `{name_field}` as name, `{company_field}` as company
        FROM `tab{status_doctype}`
        WHERE {conditions}
    """
    rows = frappe.db.sql(sql, as_dict=True)

    lookup: dict[str, dict[str, str]] = {}
    for row in rows:
        company = row.company or ""
        name = row.name
        if company not in lookup:
            lookup[company] = {}
        # Map exact name
        lookup[company][name] = name
        # Map short name -> full name (for fuzzy matching)
        short = _strip_short_name(name)
        if short != name:
            lookup[company][short] = name
    return lookup


def _find_matches_for_company(table_a, table_b, field_a, field_b, company_field, is_active_field):
    """SQL LEFT JOIN to find records where stored value has no active match."""
    return f"""
        SELECT a.name as doc_name, a.company, a.`{field_a}` as stored_value
        FROM `tab{table_a}` a
        LEFT JOIN `tab{table_b}` b
            ON b.`{field_b}` = a.`{field_a}`
            AND b.`{company_field}` = a.company
            AND b.`{is_active_field}` = 1
        WHERE a.`{field_a}` IS NOT NULL AND a.`{field_a}` != ''
            AND a.company IS NOT NULL AND a.company != ''
            AND b.`{field_b}` IS NULL
        ORDER BY a.company, a.`{field_a}`
    """


def run(dry_run=True):
    """Find and fix all stale pipeline status values."""
    if isinstance(dry_run, str):
        dry_run = dry_run.lower() in ("1", "true", "yes")

    results = {}

    for cfg in DOCTYPES:
        doctype = cfg["doctype"]
        status_field = cfg["status_field"]
        status_doctype = cfg["status_doctype"]
        active_field = cfg["status_active_field"]
        company_field = cfg["status_company_field"]

        # Build lookup: {company: {any_form -> canonical_name}}
        lookup = _active_statuses_by_company(
            status_doctype, active_field, company_field, status_doctype == "Sales Stage" and "name" or "name"
        )

        # Find mismatched records
        mismatches_sql = _find_matches_for_company(
            doctype,
            status_doctype,
            status_field,
            "name",
            company_field,
            active_field,
        )
        mismatches = frappe.db.sql(mismatches_sql, as_dict=True)

        fixes = []
        for row in mismatches:
            company = row.company
            stored = row.stored_value
            company_lookup = lookup.get(company, {})

            # Try exact match first (already failed in SQL, but double-check short name)
            canonical = company_lookup.get(stored) or company_lookup.get(_strip_short_name(stored))

            if canonical:
                fixes.append({
                    "doc": row.doc_name,
                    "company": company,
                    "from": stored,
                    "to": canonical,
                })

        if fixes:
            if not dry_run:
                for fix in fixes:
                    frappe.db.set_value(
                        doctype,
                        fix["doc"],
                        status_field,
                        fix["to"],
                        update_modified=False,
                    )
                frappe.db.commit()

            results[doctype] = {
                "mismatches_found": len(mismatches),
                "fixes_applied": len(fixes),
                "fixes": fixes,
            }
        else:
            results[doctype] = {
                "mismatches_found": len(mismatches),
                "fixes_applied": 0,
                "fixes": [],
            }

    output = {"dry_run": dry_run, "results": results}
    print(json.dumps(output, indent=2, default=str))
    return output
