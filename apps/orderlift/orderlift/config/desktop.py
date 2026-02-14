from frappe import _


def get_data():
    return [
        {
            "module_name": "SAV",
            "label": _("After-Sales Service"),
            "color": "#e74c3c",
            "icon": "octicon octicon-tools",
            "type": "module",
            "description": "SAV tickets, technician assignment, closure tracking",
        },
        {
            "module_name": "SIG",
            "label": _("Project Map"),
            "color": "#2ecc71",
            "icon": "octicon octicon-location",
            "type": "module",
            "description": "Geo-location and status tracking for installation projects",
        },
        {
            "module_name": "Logistics",
            "label": _("Logistics"),
            "color": "#3498db",
            "icon": "octicon octicon-package",
            "type": "module",
            "description": "Shipment planning and container/truck optimization",
        },
        {
            "module_name": "Portal",
            "label": _("B2B Portal"),
            "color": "#9b59b6",
            "icon": "octicon octicon-globe",
            "type": "module",
            "description": "B2B client portal orders and pricing",
        },
        {
            "module_name": "Sales",
            "label": _("Commissions & Pricing"),
            "color": "#f39c12",
            "icon": "octicon octicon-graph",
            "type": "module",
            "description": "Sales commissions, market prices, advanced pricing",
        },
        {
            "module_name": "CRM",
            "label": _("CRM"),
            "color": "#1abc9c",
            "icon": "octicon octicon-organization",
            "type": "module",
            "description": "Customer interactions, project stages, contact scheduling",
        },
        {
            "module_name": "HR",
            "label": _("HR Extensions"),
            "color": "#34495e",
            "icon": "octicon octicon-person",
            "type": "module",
            "description": "Employee evaluations and training paths",
        },
    ]
