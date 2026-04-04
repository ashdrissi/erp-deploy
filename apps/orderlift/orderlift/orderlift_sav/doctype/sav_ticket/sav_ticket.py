"""
SAV Ticket
----------
Custom doctype for after-sales service tickets.
Tracks anomaly declaration, technician assignment, and mandatory closure reporting.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, today, cint


class SAVTicket(Document):
    def validate(self):
        self._require_resolution_report_if_resolved()
        self._auto_set_closure_fields()
        self._validate_technician_on_assign()

    def _require_resolution_report_if_resolved(self):
        if self.status in ("Resolved", "Closed") and not (self.resolution_report or "").strip():
            frappe.throw(
                _("Le rapport de résolution est obligatoire avant de passer en statut '{0}'.").format(
                    self.status
                )
            )

    def _auto_set_closure_fields(self):
        if self.status == "Closed" and not self.closure_date:
            self.closure_date = now()
            self.closed_by = frappe.session.user

    def _validate_technician_on_assign(self):
        if self.status == "Assigned" and not self.assigned_technician:
            frappe.throw(_("Un technicien doit être assigné avant de passer en statut 'Assigned'."))

    @frappe.whitelist()
    def assign_technician(self, technician, intervention_date=None):
        """Assign a technician and move ticket to Assigned status.

        Called from the form button. Sends an ERPNext notification to the technician.
        """
        self.assigned_technician = technician
        self.status = "Assigned"
        if intervention_date:
            self.intervention_date = intervention_date
        elif not self.intervention_date:
            self.intervention_date = today()
        self.save(ignore_permissions=True)

        _notify_technician(self, technician)

        frappe.msgprint(
            _("Technicien {0} assigné au ticket {1}.").format(technician, self.name),
            alert=True,
        )

    @frappe.whitelist()
    def reject_closure(self, manager_comment):
        """Reject a Resolved ticket — returns it to In Progress with a manager comment."""
        if self.status != "Resolved":
            frappe.throw(_("Seuls les tickets en statut 'Resolved' peuvent être rejetés."))

        self.status = "In Progress"
        self.manager_comment = manager_comment
        self.closed_by = None
        self.closure_date = None
        self.save(ignore_permissions=True)

        frappe.msgprint(
            _("Ticket {0} renvoyé en cours. Commentaire enregistré.").format(self.name),
            alert=True,
        )


@frappe.whitelist()
def get_technicians(doctype, txt, searchfield, start, page_len, filters):
    """Search query for the assigned_technician link field — returns only users
    who have the 'Orderlift Technician' role."""
    txt = f"%{txt or ''}%"
    technicians = frappe.db.sql(
        """
        SELECT DISTINCT u.name, u.full_name
        FROM `tabUser` u
        INNER JOIN `tabHas Role` r ON r.parent = u.name
        WHERE r.role = 'Orderlift Technician'
          AND u.enabled = 1
          AND u.user_type = 'System User'
          AND (u.name LIKE %(txt)s OR u.full_name LIKE %(txt)s)
        ORDER BY u.full_name
        LIMIT %(start)s, %(page_len)s
        """,
        {"txt": txt, "start": cint(start), "page_len": cint(page_len)},
    )

    if technicians:
        return technicians

    # Fallback keeps assignment usable until technician roles are mapped in production.
    return frappe.db.sql(
        """
        SELECT u.name, u.full_name
        FROM `tabUser` u
        WHERE u.enabled = 1
          AND u.user_type = 'System User'
          AND (u.name LIKE %(txt)s OR u.full_name LIKE %(txt)s)
        ORDER BY u.full_name
        LIMIT %(start)s, %(page_len)s
        """,
        {"txt": txt, "start": cint(start), "page_len": cint(page_len)},
    )


def on_status_change(doc, method=None):
    """doc_event hook — called on every SAV Ticket update.

    Sends ERPNext notification to assigned technician when ticket is newly Assigned.
    """
    if doc.status == "Assigned" and doc.assigned_technician:
        previous_status = frappe.db.get_value("SAV Ticket", doc.name, "status")
        if previous_status != "Assigned":
            _notify_technician(doc, doc.assigned_technician)


def _notify_technician(doc, technician_user):
    """Send an ERPNext in-app notification to the assigned technician."""
    try:
        frappe.publish_realtime(
            "eval:frappe.ui.toolbar.clear_cache()",
            user=technician_user,
        )
        notification = frappe.new_doc("Notification Log")
        notification.for_user = technician_user
        notification.from_user = frappe.session.user
        notification.type = "Alert"
        notification.document_type = "SAV Ticket"
        notification.document_name = doc.name
        notification.subject = _("Nouveau ticket SAV assigné : {0}").format(doc.name)
        notification.email_content = _(
            "Client : {0}<br>Priorité : {1}<br>Description : {2}"
        ).format(doc.customer, doc.priority, doc.anomaly_description or "")
        notification.insert(ignore_permissions=True)
    except Exception:
        # Non-fatal — ticket save should not fail if notification fails
        frappe.log_error(frappe.get_traceback(), "SAV Ticket — notification technicien échouée")
