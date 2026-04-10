import frappe

def run():
    wf = frappe.get_doc("Workflow", "approve order")

    # Fix 1: Disable email alert (causes errors if SMTP not configured)
    wf.send_email_alert = 0

    # Fix 2: Clear the update_field on the Pending state
    # It tries to write order_confirmation_date = None when setting initial state
    # which triggers a write permission check that some users may fail
    for state in wf.states:
        if state.state == "Pending":
            state.update_field = None
            state.update_value = None
            print(f"Cleared update_field on state: {state.state}")

    wf.flags.ignore_permissions = True
    wf.save()
    frappe.db.commit()
    print("Workflow saved successfully.")
    print(f"send_email_alert: {wf.send_email_alert}")

    # Also clear any email-related workflow action records that may be stuck
    stuck = frappe.get_all(
        "Workflow Action",
        filters={"status": "Open", "reference_doctype": "Purchase Order"},
        fields=["name"],
        limit=5
    )
    print(f"Open Workflow Actions for PO: {len(stuck)}")
