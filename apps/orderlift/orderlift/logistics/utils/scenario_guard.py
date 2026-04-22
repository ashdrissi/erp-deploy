"""
Scenario Guard
--------------
Minimum validation rules that prevent invalid document combinations
per the logistics scenario matrix:

  flow_scope          | shipping_responsibility | source_type      | FLP allowed | Trip allowed
  --------------------|-------------------------|------------------|-------------|-------------
  Inbound             | Orderlift               | Purchase Order   | YES         | NO
  Domestic            | Orderlift               | Delivery Note    | YES         | YES
  Outbound            | Customer                | —                | YES         | NO
  Outbound            | Orderlift               | Delivery Note    | YES         | YES (local)

Called via hooks.py doc_events:
  - Delivery Trip → validate (once Delivery Trip custom fields exist in Phase 4)
"""

import frappe


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

    forecast_name = doc.get("custom_forecast_plan")
    if not forecast_name:
        return

    forecast_fields = frappe.db.get_value(
        "Forecast Load Plan",
        forecast_name,
        ["flow_scope", "shipping_responsibility"],
        as_dict=True,
    )
    if not forecast_fields:
        return

    if forecast_fields.flow_scope == "Inbound":
        frappe.throw(
            "Delivery Trip cannot be created for inbound/import plans. "
            "Use Purchase Receipt to receive imported goods after container arrival.",
            title="Invalid Scenario",
        )

    if (
        forecast_fields.flow_scope == "Outbound"
        and forecast_fields.shipping_responsibility == "Customer"
    ):
        frappe.throw(
            "Delivery Trip is not applicable when the customer manages shipping.",
            title="Invalid Scenario",
        )
