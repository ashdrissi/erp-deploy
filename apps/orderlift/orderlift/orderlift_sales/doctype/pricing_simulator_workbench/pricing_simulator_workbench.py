import frappe
from frappe.model.document import Document

from orderlift.orderlift_sales.page.pricing_simulator.pricing_simulator import (
    get_simulation_defaults,
    run_pricing_simulation,
)


class PricingSimulatorWorkbench(Document):
    @frappe.whitelist()
    def load_defaults(self):
        return get_simulation_defaults(sales_person="", mode="Auto")

    @frappe.whitelist()
    def run_simulation(self):
        return _run_simulation_for_payload(_payload_from_doc(self), self.view_mode)


@frappe.whitelist()
def load_defaults_doc(name):
    doc = frappe.get_doc("Pricing Simulator Workbench", name)
    doc.check_permission("write")
    return doc.load_defaults()


@frappe.whitelist()
def run_simulation_doc(name):
    doc = frappe.get_doc("Pricing Simulator Workbench", name)
    doc.check_permission("write")
    return doc.run_simulation()


@frappe.whitelist()
def run_simulation_preview(payload=None, view_mode="Compare"):
    data = frappe.parse_json(payload) if isinstance(payload, str) else (payload or {})
    return _run_simulation_for_payload(data, view_mode)


def _payload_from_doc(doc):
    return {
        "customer": (doc.customer or "").strip(),
        "sales_person": "",
        "geography_territory": (doc.geography_territory or "").strip(),
        "selling_price_lists": [
            row.selling_price_list
            for row in (doc.static_sources or [])
            if (row.selling_price_list or "").strip() and frappe.utils.cint(row.is_active)
        ],
        "sourcing_rules": [
            {
                "buying_price_list": row.buying_price_list,
                "pricing_scenario": row.pricing_scenario,
                "customs_policy": row.customs_policy,
                "benchmark_policy": row.benchmark_policy,
                "is_active": row.is_active,
            }
            for row in (doc.dynamic_sources or [])
            if (row.buying_price_list or "").strip() and frappe.utils.cint(row.is_active)
        ],
        "use_all_enabled_items": 1,
        "default_qty": 1,
        "max_items": frappe.utils.cint(doc.max_items or 0),
        "only_priced_items": frappe.utils.cint(doc.only_priced_items or 0),
        "items": [],
    }


def _run_simulation_for_payload(payload, view_mode):
    view_mode = (view_mode or "Compare").strip()
    if view_mode == "Dynamic":
        return run_pricing_simulation({**payload, "mode": "Dynamic"})
    if view_mode == "Static":
        return run_pricing_simulation({**payload, "mode": "Static"})

    dynamic = run_pricing_simulation({**payload, "mode": "Dynamic"})
    static = run_pricing_simulation({**payload, "mode": "Static"})
    return {"dynamic": dynamic, "static": static, "view_mode": "Compare"}
