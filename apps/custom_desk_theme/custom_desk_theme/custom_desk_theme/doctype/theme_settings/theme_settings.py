# Copyright (c) 2026, Syntax Line and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ThemeSettings(Document):
    pass


@frappe.whitelist()
def get_theme_settings():
    """Return theme settings for the client-side JS to apply."""
    try:
        doc = frappe.get_single("Theme Settings")
        return {
            "theme_mode": doc.theme_mode or "Auto",
            "primary_color": doc.primary_color or "#00D4B4",
            "sidebar_bg_dark": doc.sidebar_bg_dark or "#0D1528",
            "sidebar_bg_light": doc.sidebar_bg_light or "#FFFFFF",
            "custom_css": doc.custom_css or "",
        }
    except Exception:
        # DocType may not be created yet (first boot)
        return {
            "theme_mode": "Auto",
            "primary_color": "#00D4B4",
            "sidebar_bg_dark": "#0D1528",
            "sidebar_bg_light": "#FFFFFF",
            "custom_css": "",
        }
