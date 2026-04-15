"""
SAV Ticket
----------
Custom doctype for after-sales service tickets.
Tracks anomaly declaration, technician assignment, and mandatory closure reporting.
Linked to native ERPNext records: Customer, Serial No, Sales Order, Delivery Note,
Sales Invoice, Project, Quality Inspection, Purchase Receipt, Task, Timesheet, etc.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, today, cint, date_diff, getdate
from orderlift.orderlift_sav.doctype.sav_ticket.auto_fill import (
    _compute_warranty_status,
    _count_recurrences,
    _resolve_site_address,
)


class SAVTicket(Document):
    def validate(self):
        self._require_resolution_report_if_resolved()
        self._auto_set_closure_fields()
        self._validate_technician_on_assign()
        self._auto_compute_derived_fields()
        self._set_defect_type_required_fields()

    def before_save(self):
        self._auto_fetch_contact_from_customer()
        self._auto_fetch_site_address()

    def after_insert(self):
        self._compute_and_set_recurrence()

    def _require_resolution_report_if_resolved(self):
        if self.status in ("Resolved", "Closed") and not (self.resolution_report or "").strip():
            frappe.throw(
                _("Resolution report is mandatory before moving to '{0}'.").format(
                    self.status
                )
            )

    def _auto_set_closure_fields(self):
        if self.status == "Closed" and not self.closure_date:
            self.closure_date = now()
            self.closed_by = frappe.session.user

    def _validate_technician_on_assign(self):
        if self.status == "Assigned" and not self.assigned_technician:
            frappe.throw(_("A technician must be assigned before moving to 'Assigned'."))

    def _auto_compute_derived_fields(self):
        """Auto-compute warranty_status, days_since_delivery, severity, recurrence."""
        # Warranty status
        if self.serial_no and not self.warranty_status:
            warranty_expiry = frappe.db.get_value("Serial No", self.serial_no, "warranty_expiry_date")
            self.warranty_status = _compute_warranty_status(warranty_expiry, self.source_delivery_date)

        # Days since delivery
        if self.source_delivery_date and not self.days_since_delivery:
            self.days_since_delivery = date_diff(today(), self.source_delivery_date)

        # Customer tier — safe, returns empty if field missing
        if self.customer and not self.customer_tier:
            try:
                for field in ("tier", "loyalty_program_tier", "custom_customer_tier"):
                    val = frappe.db.get_value("Customer", self.customer, field)
                    if val:
                        self.customer_tier = val
                        break
                else:
                    self.customer_tier = ""
            except Exception:
                self.customer_tier = ""

        # Severity = function of priority + warranty + recurrence
        self.severity = _compute_severity(
            self.priority,
            self.warranty_status,
            self.recurrence_count or 0,
            self.defect_type,
        )

    def _set_defect_type_required_fields(self):
        """Enforce field requirements based on defect_type."""
        if self.defect_type == "Installation Defect" and not self.installation_project:
            frappe.throw(
                _("Installation project is required for installation defects.")
            )

        if self.defect_type == "Product Defect":
            if not self.item_concerned:
                frappe.throw(_("An item is required for product defects."))

        if self.defect_type == "Supplier Defect":
            if not self.purchase_receipt:
                frappe.throw(_("A purchase receipt is required for supplier defects."))

    def _auto_fetch_contact_from_customer(self):
        """If customer changed and contact is empty, fetch primary contact."""
        if self.customer and not self.contact:
            self.contact = frappe.db.get_value("Customer", self.customer, "customer_primary_contact")

    def _auto_fetch_site_address(self):
        """If site_address is empty, try to resolve from customer or project."""
        if not (self.site_address or "").strip():
            self.site_address = _resolve_site_address(self.customer, self.installation_project)

    def _compute_and_set_recurrence(self):
        """Count existing open tickets for the same serial/item/project."""
        count = _count_recurrences(
            serial_no=self.serial_no,
            item=self.item_concerned,
            project=self.installation_project,
            customer=self.customer,
        )
        # Subtract 1 because the current ticket is already counted after insert
        self.db_set("recurrence_count", max(0, count - 1))

    @frappe.whitelist()
    def resolve_serial_no(self, serial_no):
        """Cascade resolve from Serial No — called from client-side."""
        from orderlift.orderlift_sav.doctype.sav_ticket.auto_fill import resolve_from_serial_no

        return resolve_from_serial_no(serial_no)

    @frappe.whitelist()
    def resolve_sales_order(self, sales_order):
        """Cascade resolve from Sales Order."""
        from orderlift.orderlift_sav.doctype.sav_ticket.auto_fill import resolve_from_sales_order

        return resolve_from_sales_order(sales_order)

    @frappe.whitelist()
    def resolve_delivery_note(self, delivery_note):
        """Cascade resolve from Delivery Note."""
        from orderlift.orderlift_sav.doctype.sav_ticket.auto_fill import resolve_from_delivery_note

        return resolve_from_delivery_note(delivery_note)

    @frappe.whitelist()
    def create_task_for_technician(self):
        """Create a Task linked to this SAV Ticket."""
        if not self.assigned_technician:
            frappe.throw(_("A technician must be assigned before creating a task."))

        task = frappe.new_doc("Task")
        task.subject = _("SAV {0} — {1}").format(self.name, self.customer)
        task.description = self.anomaly_description
        task.project = self.installation_project
        task.assigned_to = self.assigned_technician
        task.status = "Open"
        task.insert(ignore_permissions=True)

        # Add to execution links child table
        self.append("execution_links", {
            "reference_doctype": "Task",
            "reference_name": task.name,
            "type": "Work Item",
            "assigned_to": self.assigned_technician,
            "status": "Open",
        })
        self.save(ignore_permissions=True)

        frappe.msgprint(
            _("Task {0} created and linked to ticket.").format(task.name),
            alert=True,
        )
        return task.name

    @frappe.whitelist()
    def create_stock_entry(self, action_type, target_warehouse=None):
        """Create a Stock Entry for replacement or return."""
        if not self.item_concerned:
            frappe.throw(_("An item is required to create a stock movement."))

        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.stock_entry_type = "Material Transfer"
        stock_entry.purpose = "Material Transfer"
        stock_entry.append("items", {
            "item_code": self.item_concerned,
            "qty": 1,
            "s_warehouse": self._get_default_source_warehouse(),
            "t_warehouse": target_warehouse or self._get_default_target_warehouse(action_type),
        })

        stock_entry.insert(ignore_permissions=True)

        # Add to stock actions child table
        self.append("stock_actions", {
            "action_type": action_type,
            "reference_doctype": "Stock Entry",
            "reference_name": stock_entry.name,
            "status": "Pending",
            "notes": _("Created from SAV ticket {0}").format(self.name),
        })
        self.save(ignore_permissions=True)

        frappe.msgprint(
            _("Stock entry {0} created.").format(stock_entry.name),
            alert=True,
        )
        return stock_entry.name

    def _get_default_source_warehouse(self):
        return frappe.db.get_value("Stock Settings", None, "default_warehouse") or "Stores - OL"

    def _get_default_target_warehouse(self, action_type):
        warehouse_map = {
            "Replacement": "REAL",
            "Return": "RETURN",
            "Vendor Return": "RETURN",
            "Internal Move": "TRANSIT",
        }
        suffix = warehouse_map.get(action_type, "REAL")
        company = self._get_company()
        warehouses = frappe.db.sql_list("""
            SELECT name FROM `tabWarehouse`
            WHERE name LIKE %(suffix)s AND company = %(company)s AND is_group = 0
        """, {"suffix": f"%{suffix}%", "company": company})
        return warehouses[0] if warehouses else None

    def _get_company(self):
        if self.installation_project:
            return frappe.db.get_value("Project", self.installation_project, "company")
        if self.sales_order:
            return frappe.db.get_value("Sales Order", self.sales_order, "company")
        if self.customer:
            return frappe.db.get_value("Customer", self.customer, "default_company")
        return "Orderlift"

    @frappe.whitelist()
    def assign_technician(self, technician, intervention_date=None):
        """Assign a technician and move ticket to Assigned status."""
        self.assigned_technician = technician
        self.status = "Assigned"
        if intervention_date:
            self.intervention_date = intervention_date
        elif not self.intervention_date:
            self.intervention_date = today()
        self.save(ignore_permissions=True)

        _notify_technician(self, technician)

        frappe.msgprint(
            _("Technician {0} assigned to ticket {1}.").format(technician, self.name),
            alert=True,
        )

    @frappe.whitelist()
    def reject_closure(self, manager_comment):
        """Reject a Resolved ticket — returns it to In Progress with a manager comment."""
        if self.status != "Resolved":
            frappe.throw(_("Only tickets in 'Resolved' status can be rejected."))

        self.status = "In Progress"
        self.manager_comment = manager_comment
        self.closed_by = None
        self.closure_date = None
        self.save(ignore_permissions=True)

        frappe.msgprint(
            _("Ticket {0} returned to In Progress. Comment saved.").format(self.name),
            alert=True,
        )


def _compute_severity(priority, warranty_status, recurrence_count, defect_type):
    """Compute severity based on priority, warranty, recurrence, and defect type."""
    score = 0

    # Priority weight
    priority_scores = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
    score += priority_scores.get(priority, 1)

    # Recurrence weight
    if recurrence_count >= 3:
        score += 2
    elif recurrence_count >= 1:
        score += 1

    # Warranty weight (in-warranty = higher business impact)
    if warranty_status and "En garantie" in warranty_status:
        score += 1

    # Defect type weight
    if defect_type == "Supplier Defect":
        score += 1

    if score >= 6:
        return "Critical"
    elif score >= 4:
        return "High"
    elif score >= 2:
        return "Medium"
    return "Low"


@frappe.whitelist()
def get_technicians(doctype, txt, searchfield, start, page_len, filters):
    """Search query for the assigned_technician link field."""
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

    # Fallback keeps assignment usable until technician roles are mapped.
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
    """doc_event hook — called on every SAV Ticket update."""
    if doc.status == "Assigned" and doc.assigned_technician:
        previous_status = frappe.db.get_value("SAV Ticket", doc.name, "status")
        if previous_status != "Assigned":
            _notify_technician(doc, doc.assigned_technician)

    # SLA breach check on status changes
    _check_sla_breach(doc)


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
        notification.subject = _("New SAV ticket assigned: {0}").format(doc.name)
        notification.email_content = _(
            "Customer: {0}<br>Priority: {1}<br>Description: {2}"
        ).format(doc.customer, doc.priority, doc.anomaly_description or "")
        notification.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "SAV Ticket — notification failed")


def _check_sla_breach(doc):
    """Auto-flag SLA breach if ticket has been open too long."""
    sla_thresholds = {"Critical": 1, "High": 3, "Medium": 7, "Low": 14}
    threshold = sla_thresholds.get(doc.priority, 7)

    days_open = date_diff(today(), doc.creation) if doc.creation else 0

    if days_open > threshold and not doc.sla_breach:
        doc.db_set("sla_breach", 1)
