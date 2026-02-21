# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import os

no_cache = 1

import json
import re
from urllib.parse import urlencode

import frappe
import frappe.sessions
from frappe import _
from frappe.utils.jinja_globals import is_rtl
from pprint import pprint

SCRIPT_TAG_PATTERN = re.compile(r"\<script[^<]*\</script\>")
CLOSING_SCRIPT_TAG_PATTERN = re.compile(r"</script\>")


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.response["status_code"] = 403
		frappe.msgprint(_("Log in to access this page."))
		frappe.redirect(f"/login?{urlencode({'redirect-to': frappe.request.path})}")
	elif frappe.db.get_value("User", frappe.session.user, "user_type", order_by=None) == "Website User":
		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)

	hooks = frappe.get_hooks()
	try:
		boot = frappe.sessions.get()
	except Exception as e:
		raise frappe.SessionBootFailed from e

	# this needs commit
	csrf_token = frappe.sessions.get_csrf_token()

	frappe.db.commit()


	desk_theme = frappe.db.get_value("User", frappe.session.user, "desk_theme")


	theme_settings_list = {}
	theme_settings = frappe.db.sql(""" SELECT * FROM tabSingles WHERE doctype = 'Theme Settings'; """, as_dict=True)
	for theme_setting in theme_settings:
		theme_settings_list[theme_setting['field']] = theme_setting['value']

	theme_defaults = {
		"font_family": "Inter",
		"font_size": "14",
		"color": "#2563EB",
		"btn_radius": "10",
		"btn_shadow": "1",
		"btn_hover_lift": "1",
		"card_radius": "16",
		"card_shadow": "1",
		"glass_blur": "10",
		"table_density_mode": "Standard",
		"table_row_height": "Standard",
		"table_header_height": "44",
		"table_header_radius": "10",
		"table_header_bg": "1",
		"table_border_mode": "Subtle",
		"table_zebra_mode": "Soft",
		"table_hover_style": "Lift",
		"table_row_radius": "10",
		"table_row_gap": "6",
		"table_sort_icon_style": "Bold",
		"table_toolbar_style": "Glass",
		"table_striped": "1",
		"table_header_text_color": "#FFFFFF",
		"table_hover_bg": "rgba(37, 99, 235, 0.08)",
		"table_border_color": "#D7DEEB",
		"table_cell_padding": "12",
		"sticky_table_header": "1",
		"list_row_radius": "12",
		"list_row_padding": "10",
		"list_row_gap": "10",
		"list_header_height": "52",
		"list_header_radius": "12",
		"list_header_bg": "var(--brand-color)",
		"list_header_text_color": "#FFFFFF",
		"list_hover_style": "Lift",
		"list_hover_bg": "rgba(37, 99, 235, 0.08)",
		"shortcut_card_radius": "16",
		"shortcut_card_padding": "16",
		"shortcut_icon_bg": "rgba(37, 99, 235, 0.12)",
		"shortcut_icon_color": "#1D4ED8",
		"shortcut_hover_lift": "4",
		"report_toolbar_bg": "rgba(255, 255, 255, 0.75)",
		"surface_bg_color": "#F7F9FC",
		"surface_card_color": "#FFFFFF",
		"border_color": "#D7DEEB",
		"text_primary_color": "#0F172A",
		"text_muted_color": "#64748B",
		"link_color": "#1D4ED8",
		"navbar_height": "54",
		"sidebar_width": "248",
		"input_focus_ring_color": "rgba(37, 99, 235, 0.25)",
		"badge_radius": "999",
		"badge_style": "Soft",
		"ui_density_mode": "Standard",
		"content_max_width": "1680",
		"navbar_blur_strength": "20",
		"button_text_transform": "None",
		"card_border_style": "Subtle",
	}

	for key, value in theme_defaults.items():
		theme_settings_list.setdefault(key, value)

	custom_css_code = (theme_settings_list.get("custom_css_code") or "")
	custom_css_code = re.sub(r"<\/?style[^>]*>", "", custom_css_code, flags=re.IGNORECASE)
	custom_css_code = re.sub(r"<\/?script[^>]*>", "", custom_css_code, flags=re.IGNORECASE)

	custom_js_code = (theme_settings_list.get("custom_js_code") or "")
	custom_js_code = re.sub(r"<script[^>]*>", "", custom_js_code, flags=re.IGNORECASE)
	custom_js_code = re.sub(r"</script>", "", custom_js_code, flags=re.IGNORECASE)

	light_logo = theme_settings_list.get('light_logo')
	dark_logo = theme_settings_list.get('dark_logo')
	default_light_logo = boot.app_logo_url or "/assets/frappe/images/frappe-logo.png"
	
	if desk_theme == 'Dark' and dark_logo:
		boot.app_logo_url = dark_logo
	elif light_logo:
		boot.app_logo_url = light_logo
	else:
		boot.app_logo_url = default_light_logo

	boot.light_logo = light_logo or default_light_logo
	boot.dark_logo = dark_logo or default_light_logo


	boot_json = frappe.as_json(boot, indent=None, separators=(",", ":"))
	# remove script tags from boot
	boot_json = SCRIPT_TAG_PATTERN.sub("", boot_json)

	# TODO: Find better fix
	boot_json = CLOSING_SCRIPT_TAG_PATTERN.sub("", boot_json)

	include_js = hooks.get("app_include_js", []) + frappe.conf.get("app_include_js", [])
	include_css = hooks.get("app_include_css", []) + frappe.conf.get("app_include_css", [])
	include_icons = hooks.get("app_include_icons", [])
	frappe.local.preload_assets["icons"].extend(include_icons)

	if frappe.get_system_settings("enable_telemetry") and os.getenv("FRAPPE_SENTRY_DSN"):
		include_js.append("sentry.bundle.js")


	theme = 'light'
	if (desk_theme == 'Dark'):
		theme = 'dark'

	context.update(
		{
			"no_cache": 1,
			"build_version": frappe.utils.get_build_version(),
			"include_js": include_js,
			"include_css": include_css,
			"include_icons": include_icons,
			"layout_direction": "rtl" if is_rtl() else "ltr",
			"lang": frappe.local.lang,
			"sounds": hooks["sounds"],
			"boot": boot if context.get("for_mobile") else json.loads(boot_json),
			"desk_theme": boot.get("desk_theme") or "Light",
			"csrf_token": csrf_token,
			"google_analytics_id": frappe.conf.get("google_analytics_id"),
			"google_analytics_anonymize_ip": frappe.conf.get("google_analytics_anonymize_ip"),
			"app_name": (
				frappe.get_website_settings("app_name") or frappe.get_system_settings("app_name") or "Frappe"
			),
			"dark_theme": theme,
			"theme_settings": theme_settings_list,
			"disable_splash" : bool(int(theme_settings_list.get('disable_splash', 0))),
			"theme_color": theme_settings_list.get("color") or "#2563EB",
			"custom_css_code": custom_css_code,
			"custom_js_code": custom_js_code,
		}
	)

	# pprint(context)

	return context
