from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from orderlift.orderlift_crm.party_management import add_party_company_access
from orderlift.role_capabilities import CAPABILITY_PARTY_COMPANY_ACCESS_APPROVAL, user_has_capability


class PartyCompanyAccessRequest(Document):
    def before_insert(self):
        self.requested_by = self.requested_by or frappe.session.user
        self.requested_on = self.requested_on or now_datetime()

    def validate(self):
        if self.party_type not in {"Lead", "Prospect", "Customer"}:
            frappe.throw(_("Party Type must be Lead, Prospect, or Customer."))
        if not self.party_name or not frappe.db.exists(self.party_type, self.party_name):
            frappe.throw(_("The selected party does not exist."))
        if self.status not in {"Pending", "Approved", "Rejected"}:
            frappe.throw(_("Invalid access request status."))


@frappe.whitelist()
def approve_request(name: str, review_comment: str | None = None) -> dict:
    _require_approval_capability()
    request = frappe.get_doc("Party Company Access Request", name)
    request.check_permission("write")
    if request.status == "Approved":
        return {"name": request.name, "status": request.status}
    if request.status != "Pending":
        frappe.throw(_("Only pending requests can be approved."))
    if request.requested_by == frappe.session.user:
        frappe.throw(_("A company access request must be approved by another user."))

    add_party_company_access(
        request.party_type,
        request.party_name,
        request.requested_company,
        approved_by=frappe.session.user,
    )
    request.status = "Approved"
    request.reviewed_by = frappe.session.user
    request.reviewed_on = now_datetime()
    request.review_comment = review_comment or ""
    request.save(ignore_permissions=True)
    return {"name": request.name, "status": request.status}


@frappe.whitelist()
def reject_request(name: str, review_comment: str | None = None) -> dict:
    _require_approval_capability()
    request = frappe.get_doc("Party Company Access Request", name)
    request.check_permission("write")
    if request.status != "Pending":
        frappe.throw(_("Only pending requests can be rejected."))
    if request.requested_by == frappe.session.user:
        frappe.throw(_("A company access request must be reviewed by another user."))
    request.status = "Rejected"
    request.reviewed_by = frappe.session.user
    request.reviewed_on = now_datetime()
    request.review_comment = review_comment or ""
    request.save(ignore_permissions=True)
    return {"name": request.name, "status": request.status}


def _require_approval_capability() -> None:
    if not user_has_capability(CAPABILITY_PARTY_COMPANY_ACCESS_APPROVAL):
        frappe.throw(_("You do not have permission to approve party company access."), frappe.PermissionError)
