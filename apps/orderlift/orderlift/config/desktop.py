from frappe import _


def get_data():
    return [
        {
            "module_name": "Orderlift SAV",
            "label": _("After-Sales Service (Roadmap)"),
            "color": "#e74c3c",
            "icon": "octicon octicon-tools",
            "type": "module",
            "description": "Roadmap module - SAV tickets, technician assignment, and closure tracking are planned next.",
        },
        {
            "module_name": "Orderlift SIG",
            "label": _("Project Map (Roadmap)"),
            "color": "#2ecc71",
            "icon": "octicon octicon-location",
            "type": "module",
            "description": "Roadmap module - geo-location and installation project tracking are planned next.",
        },
        {
            "module_name": "Orderlift Logistics",
            "label": _("Logistics"),
            "color": "#3498db",
            "icon": "octicon octicon-package",
            "type": "module",
            "description": "Container load planning, groupage optimization, and dispatch control",
        },
        {
            "module_name": "Orderlift Client Portal",
            "label": _("B2B Portal (Roadmap)"),
            "color": "#9b59b6",
            "icon": "octicon octicon-globe",
            "type": "module",
            "description": "Roadmap module - client self-service orders and portal pricing are planned next.",
        },
        {
            "module_name": "Orderlift Sales",
            "label": _("Commissions & Pricing"),
            "color": "#f39c12",
            "icon": "octicon octicon-graph",
            "type": "module",
            "description": "Sales commissions and advanced pricing",
        },
        {
            "module_name": "Orderlift CRM",
            "label": _("CRM (Roadmap)"),
            "color": "#1abc9c",
            "icon": "octicon octicon-organization",
            "type": "module",
            "description": "Roadmap module - customer interactions, stage tracking, and contact scheduling are planned next.",
        },
        {
            "module_name": "Orderlift HR",
            "label": _("HR Extensions (Roadmap)"),
            "color": "#34495e",
            "icon": "octicon octicon-person",
            "type": "module",
            "description": "Roadmap module - employee evaluations and training paths are planned next.",
        },
    ]
