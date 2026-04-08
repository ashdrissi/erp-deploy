from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now

from orderlift.client_portal.utils.access import ensure_internal_reviewer


class PortalQuoteRequest(Document):
    def validate(self):
        if self.customer:
            self.customer_group = frappe.db.get_value("Customer", self.customer, "customer_group") or self.customer_group
        self._sync_totals()

    def _sync_totals(self):
        total_qty = 0.0
        total_amount = 0.0
        for row in self.items or []:
            row.qty = flt(row.qty)
            row.unit_price = flt(row.unit_price)
            row.line_total = flt(row.qty) * flt(row.unit_price)
            total_qty += flt(row.qty)
            total_amount += flt(row.line_total)
        self.total_qty = total_qty
        self.total_amount = total_amount

    @frappe.whitelist()
    def approve_request(self, review_comment: str | None = None):
        ensure_internal_reviewer()
        if self.status not in {"Submitted", "Under Review", "Approved"}:
            frappe.throw(_("Only submitted requests can be approved."))
        self.status = "Approved"
        self.review_comment = (review_comment or "").strip()
        self.reviewed_by = frappe.session.user
        self.reviewed_on = now()
        self.save(ignore_permissions=True)
        self._notify_customer(_("Your quotation request was approved and is being prepared."))
        return self.name

    @frappe.whitelist()
    def reject_request(self, review_comment: str | None = None):
        ensure_internal_reviewer()
        if self.status in {"Quotation Created", "Rejected"}:
            frappe.throw(_("This request cannot be rejected anymore."))
        self.status = "Rejected"
        self.review_comment = (review_comment or "").strip()
        self.reviewed_by = frappe.session.user
        self.reviewed_on = now()
        self.save(ignore_permissions=True)
        self._notify_customer(_("Your quotation request was reviewed and could not be approved."))
        return self.name

    @frappe.whitelist()
    def create_quotation(self):
        ensure_internal_reviewer()
        if self.linked_quotation:
            return self.linked_quotation
        if self.status not in {"Approved", "Submitted", "Under Review"}:
            frappe.throw(_("Only approved/submitted requests can be converted to quotation."))

        quotation = frappe.new_doc("Quotation")
        quotation.company = frappe.defaults.get_user_default("Company") or frappe.get_all("Company", pluck="name", limit_page_length=1)[0]
        quotation.quotation_to = "Customer"
        quotation.party_name = self.customer
        unique_lists = sorted({(row.source_price_list or "").strip() for row in self.items if (row.source_price_list or "").strip()})
        if len(unique_lists) == 1:
            quotation.selling_price_list = unique_lists[0]
            quotation.price_list_currency = self.currency or frappe.db.get_value("Price List", unique_lists[0], "currency") or ""

        for row in self.items or []:
            quotation.append(
                "items",
                {
                    "item_code": row.item_code,
                    "qty": row.qty,
                    "uom": row.uom,
                    "rate": row.unit_price,
                    "amount": row.line_total,
                    "description": row.item_name,
                },
            )

        if not quotation.items:
            frappe.throw(_("No valid items found to create quotation."))

        quotation.insert(ignore_permissions=True)
        self.linked_quotation = quotation.name
        self.status = "Quotation Created"
        self.reviewed_by = frappe.session.user
        self.reviewed_on = now()
        self.save(ignore_permissions=True)
        self._notify_customer(_("Your quotation request is now available as quotation {0}.").format(quotation.name))
        return quotation.name

    def _notify_customer(self, message: str):
        email = frappe.db.get_value("Contact", self.contact, "email_id") or frappe.db.get_value("User", self.portal_user, "email")
        if not email:
            return
        frappe.sendmail(
            recipients=[email],
            subject=_("Portal Quote Request {0}").format(self.name),
            message=message,
            delayed=False,
        )
