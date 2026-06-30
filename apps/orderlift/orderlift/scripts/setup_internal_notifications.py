from __future__ import annotations

from copy import deepcopy

import frappe
from frappe.utils import cint

from orderlift.notification_i18n import build_multilingual_text


SYSTEM_CHANNEL = "System Notification"
ORDERLIFT_MODULE = "Orderlift"


NOTIFICATIONS = [
    {
        "name": "Orderlift - Opportunity Created",
        "doctype": "Opportunity",
        "event": "New",
        "subject": "Nouvelle opportunité : {{ doc.name }}",
        "subject_en": "New opportunity: {{ doc.name }}",
        "message": "L'opportunité **{{ doc.name }}** a été créée pour {{ doc.customer_name or doc.party_name or 'un prospect' }}.",
        "message_en": "Opportunity **{{ doc.name }}** was created for {{ doc.customer_name or doc.party_name or 'a prospect' }}.",
        "roles": ["Sales Manager", "Sales User", "Orderlift Admin"],
    },
    {
        "name": "Orderlift - Opportunity Sales Stage Changed",
        "doctype": "Opportunity",
        "event": "Value Change",
        "value_changed": "sales_stage",
        "subject": "Étape commerciale modifiée : {{ doc.name }}",
        "subject_en": "Sales stage changed: {{ doc.name }}",
        "message": "L'opportunité **{{ doc.name }}** est passée à l'étape commerciale **{{ doc.sales_stage or '-' }}**.",
        "message_en": "Opportunity **{{ doc.name }}** moved to sales stage **{{ doc.sales_stage or '-' }}**.",
        "roles": ["Sales Manager", "Sales User", "Orderlift Admin"],
    },
    {
        "name": "Orderlift - Quotation Submitted",
        "doctype": "Quotation",
        "event": "Submit",
        "subject": "Devis validé : {{ doc.name }}",
        "subject_en": "Quotation submitted: {{ doc.name }}",
        "message": "Le devis **{{ doc.name }}** a été validé pour {{ doc.customer_name or doc.party_name or 'un client' }}.",
        "message_en": "Quotation **{{ doc.name }}** was submitted for {{ doc.customer_name or doc.party_name or 'a customer' }}.",
        "roles": ["Sales Manager", "Sales User", "Orderlift Admin"],
    },
    {
        "name": "Orderlift - Quotation Expiring Soon",
        "doctype": "Quotation",
        "event": "Days Before",
        "date_changed": "valid_till",
        "days_in_advance": 3,
        "condition": "doc.docstatus == 1 and doc.status not in ('Ordered', 'Lost', 'Cancelled', 'Expired')",
        "subject": "Devis bientôt expiré : {{ doc.name }}",
        "subject_en": "Quotation expiring soon: {{ doc.name }}",
        "message": "Le devis **{{ doc.name }}** expire le {{ doc.valid_till }}.",
        "message_en": "Quotation **{{ doc.name }}** expires on {{ doc.valid_till }}.",
        "roles": ["Sales Manager", "Sales User", "Orderlift Admin"],
    },
    {
        "name": "Orderlift - Quotation Lost",
        "doctype": "Quotation",
        "event": "Value Change",
        "value_changed": "status",
        "condition": "doc.status == 'Lost'",
        "subject": "Devis perdu : {{ doc.name }}",
        "subject_en": "Quotation lost: {{ doc.name }}",
        "message": "Le devis **{{ doc.name }}** a été marqué comme perdu.",
        "message_en": "Quotation **{{ doc.name }}** was marked as lost.",
        "roles": ["Sales Manager", "Sales User", "Orderlift Admin"],
    },
    {
        "name": "Orderlift - Sales Order Submitted",
        "doctype": "Sales Order",
        "event": "Submit",
        "subject": "Commande client validée : {{ doc.name }}",
        "subject_en": "Sales order submitted: {{ doc.name }}",
        "message": "La commande client **{{ doc.name }}** a été validée pour {{ doc.customer_name or doc.customer or 'un client' }}.",
        "message_en": "Sales order **{{ doc.name }}** was submitted for {{ doc.customer_name or doc.customer or 'a customer' }}.",
        "roles": ["Sales Manager", "Sales User", "Logistics User", "Finance User", "Orderlift Admin"],
    },
    {
        "name": "Orderlift - Sales Order Delivery Due Soon",
        "doctype": "Sales Order",
        "event": "Days Before",
        "date_changed": "delivery_date",
        "days_in_advance": 2,
        "condition": "doc.docstatus == 1 and doc.status not in ('Completed', 'Closed', 'Cancelled')",
        "subject": "Livraison commande bientôt due : {{ doc.name }}",
        "subject_en": "Sales order delivery due soon: {{ doc.name }}",
        "message": "La commande client **{{ doc.name }}** doit être livrée le {{ doc.delivery_date }}.",
        "message_en": "Sales order **{{ doc.name }}** is due for delivery on {{ doc.delivery_date }}.",
        "roles": ["Sales Manager", "Sales User", "Logistics User", "Logistics Manager", "Orderlift Admin"],
    },
    {
        "name": "Orderlift - Sales Invoice Overdue",
        "doctype": "Sales Invoice",
        "event": "Days After",
        "date_changed": "due_date",
        "days_in_advance": 1,
        "condition": "doc.docstatus == 1 and doc.outstanding_amount > 0",
        "subject": "Facture en retard : {{ doc.name }}",
        "subject_en": "Invoice overdue: {{ doc.name }}",
        "message": "La facture client **{{ doc.name }}** est en retard avec un solde restant de {{ doc.outstanding_amount }}.",
        "message_en": "Sales invoice **{{ doc.name }}** is overdue with {{ doc.outstanding_amount }} still outstanding.",
        "roles": ["Finance User", "Finance Admin", "Orderlift Accountant", "Orderlift Admin"],
    },
    {
        "name": "Orderlift - Payment Entry Submitted",
        "doctype": "Payment Entry",
        "event": "Submit",
        "subject": "Paiement validé : {{ doc.name }}",
        "subject_en": "Payment submitted: {{ doc.name }}",
        "message": "Le paiement **{{ doc.name }}** a été validé pour {{ doc.party_name or 'un tiers' }}.",
        "message_en": "Payment **{{ doc.name }}** was submitted for {{ doc.party_name or 'a party' }}.",
        "roles": ["Finance User", "Finance Admin", "Orderlift Accountant", "Orderlift Admin"],
    },
    {
        "name": "Orderlift - Material Request Created",
        "doctype": "Material Request",
        "event": "New",
        "subject": "Demande de matériel créée : {{ doc.name }}",
        "subject_en": "Material request created: {{ doc.name }}",
        "message": "La demande de matériel **{{ doc.name }}** a été créée pour {{ doc.material_request_type or 'une action stock' }}.",
        "message_en": "Material request **{{ doc.name }}** was created for {{ doc.material_request_type or 'a stock action' }}.",
        "roles": ["Stock Manager", "Logistics Manager", "Purchase Manager", "Orderlift Admin"],
    },
    {
        "name": "Orderlift - Low Stock Reorder Alert",
        "doctype": "Bin",
        "event": "Value Change",
        "value_changed": "actual_qty",
        "condition": "doc.item_code and doc.warehouse and frappe.db.exists('Item Reorder', {'parent': doc.item_code, 'warehouse': doc.warehouse, 'warehouse_reorder_level': ['>=', doc.actual_qty or 0]})",
        "subject": "Stock bas : {{ doc.item_code }}",
        "subject_en": "Low stock: {{ doc.item_code }}",
        "message": "L'article **{{ doc.item_code }}** est en stock bas dans l'entrepôt **{{ doc.warehouse }}**. Quantité actuelle : {{ doc.actual_qty }}.",
        "message_en": "Item **{{ doc.item_code }}** is low in warehouse **{{ doc.warehouse }}**. Current quantity: {{ doc.actual_qty }}.",
        "roles": ["Stock Manager", "Logistics Manager", "Purchase Manager", "Orderlift Admin"],
    },
    {
        "name": "Orderlift - Purchase Receipt Submitted",
        "doctype": "Purchase Receipt",
        "event": "Submit",
        "subject": "Réception achat validée : {{ doc.name }}",
        "subject_en": "Purchase receipt submitted: {{ doc.name }}",
        "message": "La réception achat **{{ doc.name }}** a été validée pour le fournisseur {{ doc.supplier_name or doc.supplier or '-' }}.",
        "message_en": "Purchase receipt **{{ doc.name }}** was submitted for supplier {{ doc.supplier_name or doc.supplier or '-' }}.",
        "roles": ["Stock Manager", "Logistics Manager", "Purchase Manager", "Orderlift Admin"],
    },
    {
        "name": "Orderlift - Stock Entry Submitted",
        "doctype": "Stock Entry",
        "event": "Submit",
        "subject": "Mouvement de stock validé : {{ doc.name }}",
        "subject_en": "Stock entry submitted: {{ doc.name }}",
        "message": "Le mouvement de stock **{{ doc.name }}** a été validé pour {{ doc.stock_entry_type or 'un mouvement de stock' }}.",
        "message_en": "Stock entry **{{ doc.name }}** was submitted for {{ doc.stock_entry_type or 'a stock movement' }}.",
        "roles": ["Stock Manager", "Logistics Manager", "Orderlift Admin"],
    },
    {
        "name": "Orderlift - Delivery Note Submitted",
        "doctype": "Delivery Note",
        "event": "Submit",
        "subject": "Bon de livraison validé : {{ doc.name }}",
        "subject_en": "Delivery note submitted: {{ doc.name }}",
        "message": "Le bon de livraison **{{ doc.name }}** a été validé pour {{ doc.customer_name or doc.customer or 'un client' }}.",
        "message_en": "Delivery note **{{ doc.name }}** was submitted for {{ doc.customer_name or doc.customer or 'a customer' }}.",
        "roles": ["Stock Manager", "Logistics Manager", "Sales Manager", "Orderlift Admin"],
    },
    {
        "name": "Orderlift - SAV Ticket Assigned",
        "doctype": "SAV Ticket",
        "event": "Value Change",
        "value_changed": "assigned_technician",
        "condition": "doc.assigned_technician",
        "subject": "Ticket SAV assigné : {{ doc.name }}",
        "subject_en": "SAV ticket assigned: {{ doc.name }}",
        "message": "Le ticket SAV **{{ doc.name }}** a été assigné à {{ doc.assigned_technician }}.",
        "message_en": "SAV ticket **{{ doc.name }}** was assigned to {{ doc.assigned_technician }}.",
        "roles": ["Service User", "Orderlift Admin"],
        "document_fields": ["assigned_technician"],
    },
    {
        "name": "Orderlift - SAV Ticket Resolved",
        "doctype": "SAV Ticket",
        "event": "Value Change",
        "value_changed": "status",
        "condition": "doc.status == 'Resolved'",
        "subject": "Ticket SAV résolu : {{ doc.name }}",
        "subject_en": "SAV ticket resolved: {{ doc.name }}",
        "message": "Le ticket SAV **{{ doc.name }}** a été marqué comme résolu.",
        "message_en": "SAV ticket **{{ doc.name }}** was marked as resolved.",
        "roles": ["Service User", "Orderlift Admin"],
        "document_fields": ["assigned_technician"],
    },
    {
        "name": "Orderlift - Project Status Changed",
        "doctype": "Project",
        "event": "Value Change",
        "value_changed": "custom_project_status",
        "subject": "Statut projet modifié : {{ doc.name }}",
        "subject_en": "Project status changed: {{ doc.name }}",
        "message": "Le projet **{{ doc.name }}** est passé au statut **{{ doc.custom_project_status or doc.status or '-' }}**.",
        "message_en": "Project **{{ doc.name }}** moved to status **{{ doc.custom_project_status or doc.status or '-' }}**.",
        "roles": ["Installation User", "Project Manager", "Sales Manager", "Orderlift Admin"],
    },
    {
        "name": "Orderlift - Forecast Load Plan In Transit",
        "doctype": "Forecast Load Plan",
        "event": "Value Change",
        "value_changed": "status",
        "condition": "doc.status == 'In Transit'",
        "subject": "Expédition en transit : {{ doc.name }}",
        "subject_en": "Shipment in transit: {{ doc.name }}",
        "message": "Le plan d'expédition **{{ doc.name }}** est maintenant en transit.",
        "message_en": "Shipment plan **{{ doc.name }}** is now in transit.",
        "roles": ["Logistics User", "Logistics Manager", "Orderlift Admin"],
    },
    {
        "name": "Orderlift - Forecast Load Plan Delivered",
        "doctype": "Forecast Load Plan",
        "event": "Value Change",
        "value_changed": "status",
        "condition": "doc.status == 'Delivered'",
        "subject": "Expédition livrée : {{ doc.name }}",
        "subject_en": "Shipment delivered: {{ doc.name }}",
        "message": "Le plan d'expédition **{{ doc.name }}** a été livré.",
        "message_en": "Shipment plan **{{ doc.name }}** has been delivered.",
        "roles": ["Logistics User", "Logistics Manager", "Sales Manager", "Orderlift Admin"],
    },
    {
        "name": "Orderlift - Sales Commission To Pay",
        "doctype": "Sales Commission",
        "event": "Value Change",
        "value_changed": "status",
        "condition": "doc.status == 'To Pay'",
        "subject": "Commission prête à payer : {{ doc.name }}",
        "subject_en": "Commission ready to pay: {{ doc.name }}",
        "message": "La commission commerciale **{{ doc.name }}** pour {{ doc.salesperson_name or doc.salesperson or 'un agent' }} est prête à payer.",
        "message_en": "Sales commission **{{ doc.name }}** for {{ doc.salesperson_name or doc.salesperson or 'an agent' }} is ready to pay.",
        "roles": ["Commission Manager", "Finance Admin", "Orderlift Accountant", "Orderlift Admin"],
    },
]


@frappe.whitelist()
def run() -> dict:
    frappe.only_for("System Manager")
    results = []
    for spec in NOTIFICATIONS:
        result = _upsert_notification(deepcopy(spec))
        if result:
            results.append(result)
    frappe.db.commit()
    return {"notifications": results}


def after_migrate() -> None:
    run()


def _upsert_notification(spec: dict) -> dict | None:
    doctype = spec["doctype"]
    if not frappe.db.exists("DocType", doctype):
        return {"name": spec["name"], "doctype": doctype, "action": "skipped", "reason": "missing doctype"}

    meta = frappe.get_meta(doctype)
    if not _spec_fields_exist(meta, spec):
        return {"name": spec["name"], "doctype": doctype, "action": "skipped", "reason": "missing field"}

    recipients = _notification_recipients(spec, meta)
    if not recipients:
        return {"name": spec["name"], "doctype": doctype, "action": "skipped", "reason": "missing recipients"}

    doc = frappe.get_doc("Notification", spec["name"]) if frappe.db.exists("Notification", spec["name"]) else frappe.new_doc("Notification")
    is_new = doc.is_new()
    doc.name = spec["name"]
    doc.enabled = 1
    doc.channel = SYSTEM_CHANNEL
    doc.send_system_notification = 1
    doc.subject = build_multilingual_text(spec["subject"], spec["subject_en"])
    doc.event = spec["event"]
    doc.document_type = doctype
    doc.condition_type = "Python"
    doc.condition = spec.get("condition") or ""
    doc.message_type = "Markdown"
    doc.message = build_multilingual_text(spec["message"], spec["message_en"])
    doc.attach_print = 0
    if frappe.db.exists("Module Def", ORDERLIFT_MODULE):
        doc.module = ORDERLIFT_MODULE
    if doc.meta.get_field("is_standard"):
        doc.is_standard = 0

    for fieldname in ("date_changed", "value_changed"):
        if doc.meta.get_field(fieldname):
            setattr(doc, fieldname, spec.get(fieldname) or "")
    if doc.meta.get_field("days_in_advance"):
        doc.days_in_advance = cint(spec.get("days_in_advance") or 0)

    doc.set("recipients", [])
    for recipient in recipients:
        doc.append("recipients", recipient)

    if is_new:
        doc.insert(ignore_permissions=True)
        action = "created"
    else:
        doc.save(ignore_permissions=True)
        action = "updated"
    return {"name": doc.name, "doctype": doctype, "action": action, "recipients": len(recipients)}


def _spec_fields_exist(meta, spec: dict) -> bool:
    fieldnames = [spec.get("date_changed"), spec.get("value_changed"), *(spec.get("document_fields") or [])]
    return all(not fieldname or meta.get_field(fieldname) for fieldname in fieldnames)


def _notification_recipients(spec: dict, meta) -> list[dict]:
    recipients = []
    seen = set()
    for role in spec.get("roles") or []:
        if role and frappe.db.exists("Role", role) and ("role", role) not in seen:
            recipients.append({"receiver_by_role": role})
            seen.add(("role", role))
    for fieldname in spec.get("document_fields") or []:
        if fieldname and meta.get_field(fieldname) and ("field", fieldname) not in seen:
            recipients.append({"receiver_by_document_field": fieldname})
            seen.add(("field", fieldname))
    return recipients
