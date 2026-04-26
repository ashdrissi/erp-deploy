from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def get_pipeline_data(search: str | None = None, owner: str | None = None, source: str | None = None) -> dict:
    stages = _installation_stages()
    stage_names = [stage["name"] for stage in stages]
    cards = _opportunity_cards(search=search, owner=owner, source=source, stage_names=stage_names)
    columns = []
    for stage in stages:
        stage_cards = [card for card in cards if card.get("stage") == stage["name"]]
        columns.append({**stage, "cards": stage_cards})

    return {
        "columns": columns,
        "kpis": {
            "open_opportunities": len(cards),
            "pipeline_amount": sum(flt(card.get("amount")) for card in cards),
            "projects_started": len([card for card in cards if card.get("stage") == "Won / Project"]),
            "stage_count": len(stages),
        },
        "filters": {
            "owners": sorted({card.get("owner") for card in cards if card.get("owner")}),
            "sources": sorted({card.get("source") for card in cards if card.get("source")}),
        },
    }


@frappe.whitelist()
def update_opportunity_stage(opportunity: str, stage: str) -> dict:
    if not frappe.db.exists("Opportunity", opportunity):
        frappe.throw(_("Opportunity {0} was not found.").format(opportunity))
    if not frappe.db.exists("Installation Stage", stage):
        frappe.throw(_("Installation stage {0} was not found.").format(stage))

    doc = frappe.get_doc("Opportunity", opportunity)
    if not doc.meta.get_field("custom_installation_stage"):
        frappe.throw(_("Opportunity is missing custom_installation_stage. Run migrate first."))

    doc.custom_installation_stage = stage
    probability = frappe.db.get_value("Installation Stage", stage, "default_probability")
    if probability is not None:
        doc.probability = probability
    doc.save(ignore_permissions=False)
    frappe.db.commit()
    return _card_from_opportunity(doc)


def _installation_stages() -> list[dict]:
    if not frappe.db.exists("DocType", "Installation Stage"):
        return []
    rows = frappe.get_all(
        "Installation Stage",
        filters={"is_active": 1},
        fields=["name", "stage_name", "sequence", "color", "is_closed"],
        order_by="sequence asc, stage_name asc",
        limit_page_length=0,
    )
    return [
        {
            "name": row.name,
            "label": row.stage_name or row.name,
            "sequence": row.sequence,
            "color": row.color,
            "is_closed": row.is_closed,
        }
        for row in rows
    ]


def _opportunity_cards(search=None, owner=None, source=None, stage_names=None) -> list[dict]:
    filters = {"status": ["not in", ["Lost", "Closed"]]}
    if owner and owner != "All":
        filters["opportunity_owner"] = owner
    if source and source != "All" and _has_field("Opportunity", "custom_source_channel"):
        filters["custom_source_channel"] = source

    fields = [
        "name",
        "title",
        "party_name",
        "customer_name",
        "opportunity_amount",
        "opportunity_owner",
        "probability",
        "status",
        "sales_stage",
    ]
    for custom_field in ["custom_installation_stage", "custom_next_action", "custom_source_channel"]:
        if _has_field("Opportunity", custom_field):
            fields.append(custom_field)

    rows = frappe.get_all("Opportunity", filters=filters, fields=fields, order_by="modified desc", limit_page_length=200)
    cards = [_card_from_row(row, stage_names=stage_names) for row in rows]
    if search:
        needle = search.strip().lower()
        cards = [
            card
            for card in cards
            if needle in f"{card.get('name')} {card.get('title')} {card.get('party')} {card.get('next_action')}".lower()
        ]
    return cards


def _card_from_opportunity(doc) -> dict:
    docs = _related_docs(doc.name)
    return {
        "name": doc.name,
        "title": doc.title or doc.name,
        "party": doc.customer_name or doc.party_name,
        "amount": doc.opportunity_amount,
        "owner": doc.opportunity_owner,
        "source": doc.get("custom_source_channel") or "",
        "probability": doc.probability,
        "stage": doc.get("custom_installation_stage") or doc.sales_stage,
        "next_action": doc.get("custom_next_action") or "",
        "status": doc.status,
        "docs": docs,
    }


def _card_from_row(row, stage_names=None) -> dict:
    docs = _related_docs(row.name)
    stage = _resolve_stage(row, docs, stage_names)
    return {
        "name": row.name,
        "title": row.get("title") or row.name,
        "party": row.get("customer_name") or row.get("party_name") or "",
        "amount": row.get("opportunity_amount") or 0,
        "owner": row.get("opportunity_owner") or "",
        "source": row.get("custom_source_channel") or "",
        "probability": row.get("probability") or 0,
        "stage": stage,
        "next_action": row.get("custom_next_action") or "",
        "status": row.get("status"),
        "docs": docs,
    }


def _related_docs(opportunity: str) -> list[dict]:
    docs = [{"doctype": "Opportunity", "name": opportunity, "label": "Opportunity"}]
    quotation = frappe.db.get_value("Quotation", {"opportunity": opportunity, "docstatus": ["<", 2]}, "name")
    if quotation:
        docs.append({"doctype": "Quotation", "name": quotation, "label": "Quotation"})
        sales_order = frappe.db.sql(
            """
            SELECT DISTINCT soi.parent
            FROM `tabSales Order Item` soi
            INNER JOIN `tabSales Order` so ON so.name = soi.parent
            WHERE soi.prevdoc_docname = %s AND so.docstatus < 2
            LIMIT 1
            """,
            (quotation,),
        )
        if sales_order:
            sales_order_name = sales_order[0][0]
            docs.append({"doctype": "Sales Order", "name": sales_order_name, "label": "Sales Order"})
            project = frappe.db.get_value("Sales Order", sales_order_name, "custom_installation_project")
            if project:
                docs.append({"doctype": "Project", "name": project, "label": "Project"})
            material_request = frappe.db.sql(
                """
                SELECT DISTINCT mri.parent
                FROM `tabMaterial Request Item` mri
                INNER JOIN `tabMaterial Request` mr ON mr.name = mri.parent
                WHERE mri.sales_order = %s AND mr.docstatus < 2
                LIMIT 1
                """,
                (sales_order_name,),
            )
            if material_request:
                docs.append({"doctype": "Material Request", "name": material_request[0][0], "label": "Material Request"})
    return docs


def _resolve_stage(row, docs: list[dict], stage_names: list[str] | None) -> str | None:
    stage = row.get("custom_installation_stage") or row.get("sales_stage")
    if stage_names and stage in stage_names:
        return stage

    status = row.get("status") or ""
    labels = {doc.get("label") for doc in docs}

    if status == "Converted" and stage_names and "Won / Project" in stage_names:
        return "Won / Project"
    if "Sales Order" in labels and stage_names and "Won / Project" in stage_names:
        return "Won / Project"
    if "Quotation" in labels and stage_names and "Quotation Sent" in stage_names:
        return "Quotation Sent"
    if status == "Lost" and stage_names and "Lost" in stage_names:
        return "Lost"
    if stage_names:
        return stage_names[0]
    return stage


def _has_field(doctype: str, fieldname: str) -> bool:
    return bool(frappe.get_meta(doctype).get_field(fieldname))
