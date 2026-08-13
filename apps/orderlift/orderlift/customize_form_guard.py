from __future__ import annotations

import frappe
from frappe.custom.doctype.customize_form.customize_form import (
    CustomizeForm,
    is_standard_or_system_generated_field,
)


class OrderliftCustomizeForm(CustomizeForm):
    """Do not interpret omitted Administrator-owned fields as user deletions."""

    def delete_custom_fields(self):
        meta = frappe.get_meta(self.doc_type)
        submitted_fields = {df.fieldname for df in self.get("fields")}
        fields_to_remove = {df.fieldname for df in meta.get("fields")} - submitted_fields

        for fieldname in fields_to_remove:
            df = meta.get("fields", {"fieldname": fieldname})[0]
            if is_standard_or_system_generated_field(df):
                continue
            custom_field = frappe.get_doc("Custom Field", df.name)
            if custom_field.owner == "Administrator" and frappe.session.user != "Administrator":
                continue
            frappe.delete_doc("Custom Field", df.name)
