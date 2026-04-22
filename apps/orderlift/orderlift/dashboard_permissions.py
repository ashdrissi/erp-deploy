from __future__ import annotations

import frappe
from frappe.boot import get_allowed_report_names
from frappe.permissions import get_doctypes_with_read
from frappe.utils.modules import get_modules_from_all_apps_for_user


def install_runtime_patches() -> None:
    """Patch Frappe core permission builders for the current worker process."""
    from frappe.desk.doctype.number_card import number_card as number_card_module

    if number_card_module.get_permission_query_conditions is not get_number_card_permission_query_conditions:
        number_card_module.get_permission_query_conditions = get_number_card_permission_query_conditions

def get_number_card_permission_query_conditions(user: str | None = None):
    """Mirror Frappe Number Card visibility, but handle empty module access safely.

    Restricted admins intentionally block most modules. Frappe core currently builds
    ``module IN ()`` when the allowed module list is empty, which breaks list dashboard
    queries. For those users, keep the type/report/doctype checks and only allow cards
    without a module assignment.
    """
    user = user or frappe.session.user

    if user == "Administrator":
        return

    roles = frappe.get_roles(user)
    if "System Manager" in roles:
        return

    allowed_reports = get_allowed_report_names()
    allowed_doctypes = get_doctypes_with_read()
    allowed_modules = [module.get("module_name") for module in get_modules_from_all_apps_for_user(user)]

    nc = frappe.qb.DocType("Number Card")
    conditions = (
        ((nc.type == "Report") & nc.report_name.isin(allowed_reports))
        | ((nc.type == "Custom") & nc.document_type.isin(allowed_doctypes))
        | ((nc.type == "Document Type") & nc.document_type.isin(allowed_doctypes))
    )

    module_conditions = nc.module.isnull() | (nc.module == "")
    if allowed_modules:
        module_conditions = nc.module.isin(allowed_modules) | module_conditions

    return (conditions & module_conditions).get_sql(quote_char="`")


install_runtime_patches()
