import frappe


def execute():
    if not frappe.db.exists("DocType", "Pricing Sheet"):
        return

    sheets = frappe.get_all("Pricing Sheet", pluck="name", limit_page_length=0)
    for name in sheets:
        doc = frappe.get_doc("Pricing Sheet", name)
        changed = False

        for row in doc.get("lines") or []:
            if not row.get("resolved_pricing_scenario"):
                row.resolved_pricing_scenario = row.get("pricing_scenario") or doc.get("pricing_scenario")
                changed = True

            if not row.get("scenario_source"):
                row.scenario_source = "Line" if row.get("pricing_scenario") else "Sheet Default"
                changed = True

            if row.get("has_scenario_override") is None:
                row.has_scenario_override = 0
                changed = True

            if row.get("has_line_override") is None:
                row.has_line_override = 0
                changed = True

            if not row.get("line_type"):
                row.line_type = "Standard"
                changed = True

        if changed:
            doc.save(ignore_permissions=True)
