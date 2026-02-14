# Copyright (c) 2026, Syntax Line and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ThemeSettings(Document):
    pass


def _get_settings_dict():
    """Internal helper to build the theme settings dict."""
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
        return {
            "theme_mode": "Auto",
            "primary_color": "#00D4B4",
            "sidebar_bg_dark": "#0D1528",
            "sidebar_bg_light": "#FFFFFF",
            "custom_css": "",
        }


def get_theme_settings(bootinfo=None):
    """Called by boot_session hook (with bootinfo) or as whitelisted API."""
    settings = _get_settings_dict()
    if bootinfo is not None:
        bootinfo["custom_desk_theme"] = settings
    return settings


@frappe.whitelist()
def get_theme_settings_api():
    """Whitelisted API endpoint for JS fallback calls."""
    return _get_settings_dict()
