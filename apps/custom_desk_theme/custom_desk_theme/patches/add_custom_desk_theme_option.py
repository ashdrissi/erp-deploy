import frappe


def execute():
    """Add 'Custom' option to User.desk_theme field options."""

    user_doctype = frappe.get_doc("DocType", "User")

    new_options = ["Custom"]

    for field in user_doctype.fields:
        if field.fieldname != "desk_theme":
            continue

        current_options = field.options.split("\n") if field.options else []
        needs_update = False

        for option in new_options:
            if option not in current_options:
                current_options.append(option)
                needs_update = True

        if needs_update:
            field.options = "\n".join(current_options)
            user_doctype.save()
            frappe.db.commit()
        break
