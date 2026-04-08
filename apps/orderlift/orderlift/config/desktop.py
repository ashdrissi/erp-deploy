from frappe import _


def get_data():
    return [
        {
            "module_name": "Orderlift SAV",
            "label": _("After-Sales Service"),
            "color": "#e74c3c",
            "icon": "octicon octicon-tools",
            "type": "module",
            "description": "SAV tickets, technician assignment, closure tracking, and service dashboards.",
        },
        {
            "module_name": "Orderlift SIG",
            "label": _("SIG Projects"),
            "color": "#2ecc71",
            "icon": "octicon octicon-location",
            "type": "module",
            "description": "Installation project QC, maps, dashboard visibility, and field execution tools.",
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
            "label": _("B2B Portal"),
            "color": "#9b59b6",
            "icon": "octicon octicon-globe",
            "type": "module",
            "description": "Invite-only B2B portal for customer-group pricing and quotation requests.",
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
            "label": _("CRM"),
            "color": "#1abc9c",
            "icon": "octicon octicon-organization",
            "type": "module",
            "description": "CRM dashboard, customer pipeline visibility, and customer-facing commercial operations.",
        },
        {
            "module_name": "Orderlift HR",
            "label": _("HR Extensions"),
            "color": "#34495e",
            "icon": "octicon octicon-person",
            "type": "module",
            "description": "HR dashboard, employee, leave, attendance, payroll, and expense visibility.",
        },
    ]
