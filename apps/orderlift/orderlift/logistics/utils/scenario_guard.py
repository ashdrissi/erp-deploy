"""
Scenario Guard
--------------
Minimum validation rules that prevent invalid document combinations
per the logistics scenario matrix:

  flow_scope          | shipping_responsibility | source_type      | CLP allowed | Trip allowed
  --------------------|-------------------------|------------------|-------------|-------------
  Inbound             | Orderlift               | Purchase Order   | YES         | NO
  Domestic            | Orderlift               | Delivery Note    | YES (opt)   | YES
  Outbound            | Customer                | —                | NO          | NO
  Outbound            | Orderlift               | Delivery Note    | YES         | YES (local)

Called via hooks.py doc_events:
  - Container Load Plan → validate
  - Delivery Trip → validate (once Delivery Trip custom fields exist in Phase 4)
"""

import frappe


# ── Container Load Plan guards ──────────────────────────────────────────

def validate_container_load_plan(doc, method=None):
    """Block invalid CLP scenario combinations."""
    if not doc:
        return

    flow_scope = (doc.get("flow_scope") or "").strip()
    responsibility = (doc.get("shipping_responsibility") or "").strip()
    source_type = (doc.get("source_type") or "").strip()

    # Rule 1: Outbound + Customer → no CLP needed
    if flow_scope == "Outbound" and responsibility == "Customer":
        frappe.throw(
            "Container Load Plan is not required when the customer manages shipping. "
            "Set Shipping Responsibility to 'Orderlift' if Orderlift handles the shipment.",
            title="Invalid Scenario",
        )

    # Rule 2: source_type must match flow_scope
    if source_type and flow_scope:
        _validate_source_type_consistency(flow_scope, source_type)


def _validate_source_type_consistency(flow_scope, source_type):
    """Enforce that source_type aligns with flow_scope.

    Valid combinations:
      - Inbound  → Purchase Order only
      - Domestic → Delivery Note only
      - Outbound → Delivery Note only
    """
    if flow_scope == "Inbound" and source_type != "Purchase Order":
        frappe.throw(
            "Inbound plans must use 'Purchase Order' as source document type. "
            "Import procurement is planned from Purchase Orders, not Delivery Notes.",
            title="Invalid Source Type",
        )

    if flow_scope in ("Domestic", "Outbound") and source_type != "Delivery Note":
        frappe.throw(
            f"{flow_scope} plans must use 'Delivery Note' as source document type. "
            "Only Inbound/Import plans use Purchase Orders as source.",
            title="Invalid Source Type",
        )


# ── Delivery Trip guards ────────────────────────────────────────────────

def validate_delivery_trip(doc, method=None):
    """Block Delivery Trip creation for inbound or customer-managed scenarios."""
    if not doc:
        return

    # Guard via linked CLP (if present — Phase 4 adds the custom field)
    clp_name = doc.get("custom_container_load_plan")
    if not clp_name:
        return

    clp_fields = frappe.db.get_value(
        "Container Load Plan",
        clp_name,
        ["flow_scope", "shipping_responsibility"],
        as_dict=True,
    )
    if not clp_fields:
        return

    if clp_fields.flow_scope == "Inbound":
        frappe.throw(
            "Delivery Trip cannot be created for inbound/import plans. "
            "Use Purchase Receipt to receive imported goods after container arrival.",
            title="Invalid Scenario",
        )

    if clp_fields.flow_scope == "Outbound" and clp_fields.shipping_responsibility == "Customer":
        frappe.throw(
            "Delivery Trip is not applicable when the customer manages shipping.",
            title="Invalid Scenario",
        )
