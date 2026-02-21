import frappe


def extend_bootinfo(bootinfo):
    """Replace 'ERPNext' app title with 'Orderlift' in the sidebar subtitle."""
    for app in bootinfo.get("app_data", []):
        if app.get("app_title") == "ERPNext":
            app["app_title"] = "Orderlift"
