"""
Grant Orderlift Admin full CRUD on all business doctypes.
Full access to everything except system/build doctypes.
"""
import frappe


ROLE = "Orderlift Admin"

# Full CRUD + submit/cancel/amend where applicable
FULL_ACCESS_DOCTYPES = [
    # Users & HR
    "User",
    "Employee",
    "Employee Checkin",
    "Employee Promotion",
    "Employee Separation",
    "Employee Transfer",
    "Attendance",
    "Leave Application",
    "Leave Allocation",
    "Expense Claim",
    "Shift Assignment",
    "Shift Type",
    "Department",
    "Designation",
    "Employment Type",
    "Branch",
    "Holiday List",

    # CRM
    "Lead",
    "Opportunity",
    "Customer",
    "Customer Group",
    "Contact",
    "Address",
    "Campaign",
    "Appointment",
    "Contract",
    "Contract Template",

    # Sales
    "Quotation",
    "Sales Order",
    "Sales Invoice",
    "Delivery Note",
    "Blanket Order",
    "Pricing Rule",
    "Coupon Code",

    # Purchasing
    "Supplier",
    "Supplier Group",
    "Purchase Order",
    "Purchase Invoice",
    "Purchase Receipt",
    "Request for Quotation",
    "Supplier Quotation",
    "Buying Settings",

    # Stock / Inventory
    "Item",
    "Item Group",
    "Warehouse",
    "Stock Entry",
    "Stock Reconciliation",
    "Material Request",
    "Packing Slip",
    "Serial No",
    "Batch",
    "Item Price",
    "Price List",
    "Stock Settings",
    "Brand",
    "Manufacturer",
    "UOM",

    # Accounting
    "Journal Entry",
    "Payment Entry",
    "Payment Order",
    "Bank Account",
    "Bank Transaction",
    "Cost Center",
    "Account",
    "Fiscal Year",
    "Finance Book",
    "Tax Rule",
    "Tax Category",
    "Tax Withholding Category",
    "Mode of Payment",
    "Company",
    "Currency Exchange",
    "Accounts Settings",
    "POS Profile",
    "POS Opening Entry",
    "POS Closing Entry",
    "POS Invoice",
    "Dunning",
    "Dunning Type",
    "Exchange Rate Revaluation",
    "Period Closing Voucher",
    "Budget",
    "Cheque Print Template",
    "Bank Guarantee",
    "Letter Head",
    "Terms and Conditions",

    # Projects
    "Project",
    "Task",
    "Timesheet",
    "Activity Type",
    "Project Type",

    # Assets
    "Asset",
    "Asset Category",
    "Asset Movement",
    "Asset Value Adjustment",

    # Manufacturing
    "BOM",
    "Work Order",
    "Production Plan",
    "Operation",
    "Workstation",
    "Routing",

    # Logistics (Orderlift custom)
    "Container Load Plan",
    "Container Profile",
    "Forecast Load Plan",
    "Shipment Analysis",
    "Delivery Trip",

    # Other business
    "Communication",
    "Email Template",
    "Note",
    "Event",
    "ToDo",
    "File",
    "Comment",
    "Dashboard",
    "Dashboard Chart",
    "Number Card",
    "Kanban Board",
    "Calendar View",
    "List Filter",
    "Document Follow",
    "Tag",
    "Report",
    "Page",
]


def _ensure_perm(doctype):
    """Create or update Custom DocPerm for Orderlift Admin on this doctype."""
    # Check if doctype actually exists
    if not frappe.db.exists("DocType", doctype):
        return False

    existing = frappe.db.exists("Custom DocPerm", {
        "parent": doctype,
        "role": ROLE,
        "permlevel": 0,
    })

    meta = frappe.get_meta(doctype)
    is_submittable = meta.is_submittable

    values = {
        "read": 1,
        "write": 1,
        "create": 1,
        "delete": 1,
        "report": 1,
        "export": 1,
        "import": 1,
        "share": 1,
        "print": 1,
        "email": 1,
        "submit": 1 if is_submittable else 0,
        "cancel": 1 if is_submittable else 0,
        "amend": 1 if is_submittable else 0,
    }

    if existing:
        doc = frappe.get_doc("Custom DocPerm", existing)
        for k, v in values.items():
            setattr(doc, k, v)
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.get_doc({
            "doctype": "Custom DocPerm",
            "parent": doctype,
            "parenttype": "DocType",
            "parentfield": "permissions",
            "role": ROLE,
            "permlevel": 0,
            **values,
        })
        doc.insert(ignore_permissions=True)

    return True


def run():
    granted = 0
    skipped = 0
    for dt in FULL_ACCESS_DOCTYPES:
        if _ensure_perm(dt):
            granted += 1
        else:
            skipped += 1
            print(f"  Skipped (not found): {dt}")

    frappe.db.commit()
    frappe.clear_cache()
    print(f"\nDone: {granted} doctypes granted full access, {skipped} skipped")
