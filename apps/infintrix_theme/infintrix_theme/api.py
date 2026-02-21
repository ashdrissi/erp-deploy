from __future__ import unicode_literals
import os, re, json
import frappe
from frappe.utils import flt, cint, get_time, make_filter_tuple, get_filter, add_to_date, cstr, get_timespan_date_range, nowdate, add_days, getdate, add_months, get_datetime
from frappe import _
from frappe.desk.reportview import get_filters_cond
from frappe.cache_manager import clear_user_cache
from six import string_types


@frappe.whitelist()
def get_module_name_from_doctype(doc_name, current_module=""):
    # frappe.msgprint("======"+str(doc_name))
    condition = ""
    if doc_name:
        if current_module:
            condition = "and  w.`name` = {current_module} ".format(current_module=current_module)

        list_od_dicts = frappe.db.sql("""
            select *
                    from (
                            select  w.`name` `module`,
                                 (select restrict_to_domain from `tabModule Def` where `name` = w.module ) restrict_to_domain
                                             from  tabWorkspace w
                                             inner join
                                                        `tabWorkspace Link` l
                                                        on w.`name` = l.parent
                                                         where link_to = '{doc_name}'
                                                          %s
                                )	T
        """.format(doc_name=doc_name), (condition), as_dict=True, debug=False)
        if list_od_dicts:
            return [{"module": list_od_dicts[0]["module"]}]
        else:
            list_od_dicts = frappe.db.sql("""
                select *
                        from (
                                select  w.`name` `module`,
                                     (select restrict_to_domain from `tabModule Def` where `name` = w.module ) restrict_to_domain
                                                 from  tabWorkspace w
                                                 inner join
                                                            `tabWorkspace Link` l
                                                            on w.`name` = l.parent
                                                             where link_to = '{doc_name}'
                                    )	T
            """.format(doc_name=doc_name), as_dict=True, debug=False)
        if list_od_dicts:
            return [{"module": list_od_dicts[0]["module"]}]


@frappe.whitelist()
def change_language(language):
    frappe.db.set_value("User", frappe.session.user, "language", language)
    clear()
    return True


@frappe.whitelist()
def get_current_language():
    return frappe.db.get_value("User", frappe.session.user, "language")


@frappe.whitelist()
def get_company_logo():
    logo_path = ""
    current_company = frappe.defaults.get_user_default("company")
    if current_company:
        logo_path = frappe.db.get_value("Company", current_company, "company_logo")

    return logo_path


@frappe.whitelist(allow_guest=True)
def get_theme_settings():
    slideshow_photos = []
    settings_list = {}
    settings = frappe.db.sql("""
                       SELECT * FROM tabSingles WHERE doctype = 'Theme Settings';
    """, as_dict=True, debug=False)

    for setting in settings:
        settings_list[setting['field']] = setting['value']

    if (("background_type" in settings_list) and settings_list['background_type'] == 'Slideshow'):
        slideshow_photos = frappe.db.sql("""
                               SELECT `photo` FROM `tabSlideshow Photos` WHERE `parent` = 'Theme Settings';
            """, as_dict=True, debug=False)

    return {
        'enable_background': settings_list['enable_background'] if ("enable_background" in settings_list) else '',
        'background_photo': settings_list['background_photo'] if ("background_photo" in settings_list) else '',
        'background_type': settings_list['background_type'] if ("background_type" in settings_list) else '',
        'full_page_background': settings_list['full_page_background'] if ("full_page_background" in settings_list) else '',
        'transparent_background': settings_list['transparent_background'] if ("transparent_background" in settings_list) else '',
        'slideshow_photos': slideshow_photos,
        'dark_view': settings_list['dark_view'] if ("dark_view" in settings_list) else '',
        'theme_color': settings_list['theme_color'] if ("theme_color" in settings_list) else '',
        'open_workspace_on_mobile_menu': settings_list['open_workspace_on_mobile_menu'] if ("open_workspace_on_mobile_menu" in settings_list) else '',
        'show_icon_label': settings_list['show_icon_label'] if ("show_icon_label" in settings_list) else '',
        'hide_icon_tooltip': settings_list['hide_icon_tooltip'] if ("hide_icon_tooltip" in settings_list) else '',
        'always_close_sub_menu': settings_list['always_close_sub_menu'] if ("always_close_sub_menu" in settings_list) else '',
        'menu_opening_type': settings_list['menu_opening_type'] if ("menu_opening_type" in settings_list) else '',
        'loading_image': settings_list['loading_image'] if ("loading_image" in settings_list) else '',
        'theme_preset': settings_list['theme_preset'] if ("theme_preset" in settings_list) else 'Modern Pro',
        'surface_bg_color': settings_list['surface_bg_color'] if ("surface_bg_color" in settings_list) else '#F7F9FC',
        'surface_card_color': settings_list['surface_card_color'] if ("surface_card_color" in settings_list) else '#FFFFFF',
        'border_color': settings_list['border_color'] if ("border_color" in settings_list) else '#D7DEEB',
        'text_primary_color': settings_list['text_primary_color'] if ("text_primary_color" in settings_list) else '#0F172A',
        'text_muted_color': settings_list['text_muted_color'] if ("text_muted_color" in settings_list) else '#64748B',
        'link_color': settings_list['link_color'] if ("link_color" in settings_list) else '#1D4ED8',
        'navbar_height': settings_list['navbar_height'] if ("navbar_height" in settings_list) else '54',
        'input_focus_ring_color': settings_list['input_focus_ring_color'] if ("input_focus_ring_color" in settings_list) else 'rgba(37, 99, 235, 0.25)',
        'list_row_radius': settings_list['list_row_radius'] if ("list_row_radius" in settings_list) else '12',
        'list_row_padding': settings_list['list_row_padding'] if ("list_row_padding" in settings_list) else '10',
        'list_row_gap': settings_list['list_row_gap'] if ("list_row_gap" in settings_list) else '10',
        'list_header_height': settings_list['list_header_height'] if ("list_header_height" in settings_list) else '52',
        'list_header_radius': settings_list['list_header_radius'] if ("list_header_radius" in settings_list) else '12',
        'list_header_bg': settings_list['list_header_bg'] if ("list_header_bg" in settings_list) else 'var(--brand-color)',
        'list_header_text_color': settings_list['list_header_text_color'] if ("list_header_text_color" in settings_list) else '#FFFFFF',
        'list_hover_style': settings_list['list_hover_style'] if ("list_hover_style" in settings_list) else 'Lift',
        'list_hover_bg': settings_list['list_hover_bg'] if ("list_hover_bg" in settings_list) else 'rgba(37, 99, 235, 0.08)',
        'table_header_text_color': settings_list['table_header_text_color'] if ("table_header_text_color" in settings_list) else '#FFFFFF',
        'table_hover_bg': settings_list['table_hover_bg'] if ("table_hover_bg" in settings_list) else 'rgba(37, 99, 235, 0.08)',
        'table_border_color': settings_list['table_border_color'] if ("table_border_color" in settings_list) else '#D7DEEB',
        'table_cell_padding': settings_list['table_cell_padding'] if ("table_cell_padding" in settings_list) else '12',
        'table_density_mode': settings_list['table_density_mode'] if ("table_density_mode" in settings_list) else 'Standard',
        'table_header_height': settings_list['table_header_height'] if ("table_header_height" in settings_list) else '44',
        'table_header_radius': settings_list['table_header_radius'] if ("table_header_radius" in settings_list) else '10',
        'table_border_mode': settings_list['table_border_mode'] if ("table_border_mode" in settings_list) else 'Subtle',
        'table_zebra_mode': settings_list['table_zebra_mode'] if ("table_zebra_mode" in settings_list) else 'Soft',
        'table_hover_style': settings_list['table_hover_style'] if ("table_hover_style" in settings_list) else 'Lift',
        'table_row_radius': settings_list['table_row_radius'] if ("table_row_radius" in settings_list) else '10',
        'table_row_gap': settings_list['table_row_gap'] if ("table_row_gap" in settings_list) else '6',
        'table_sort_icon_style': settings_list['table_sort_icon_style'] if ("table_sort_icon_style" in settings_list) else 'Bold',
        'table_toolbar_style': settings_list['table_toolbar_style'] if ("table_toolbar_style" in settings_list) else 'Glass',
        'sticky_table_header': settings_list['sticky_table_header'] if ("sticky_table_header" in settings_list) else '1',
        'report_toolbar_bg': settings_list['report_toolbar_bg'] if ("report_toolbar_bg" in settings_list) else 'rgba(255, 255, 255, 0.75)',
        'shortcut_card_radius': settings_list['shortcut_card_radius'] if ("shortcut_card_radius" in settings_list) else '16',
        'shortcut_card_padding': settings_list['shortcut_card_padding'] if ("shortcut_card_padding" in settings_list) else '16',
        'shortcut_icon_bg': settings_list['shortcut_icon_bg'] if ("shortcut_icon_bg" in settings_list) else 'rgba(37, 99, 235, 0.12)',
        'shortcut_icon_color': settings_list['shortcut_icon_color'] if ("shortcut_icon_color" in settings_list) else '#1D4ED8',
        'shortcut_hover_lift': settings_list['shortcut_hover_lift'] if ("shortcut_hover_lift" in settings_list) else '4',
        'badge_radius': settings_list['badge_radius'] if ("badge_radius" in settings_list) else '999',
        'badge_style': settings_list['badge_style'] if ("badge_style" in settings_list) else 'Soft',
        'ui_density_mode': settings_list['ui_density_mode'] if ("ui_density_mode" in settings_list) else 'Standard',
        'content_max_width': settings_list['content_max_width'] if ("content_max_width" in settings_list) else '1680',
        'navbar_blur_strength': settings_list['navbar_blur_strength'] if ("navbar_blur_strength" in settings_list) else '20',
        'button_text_transform': settings_list['button_text_transform'] if ("button_text_transform" in settings_list) else 'None',
        'card_border_style': settings_list['card_border_style'] if ("card_border_style" in settings_list) else 'Subtle',
        'custom_css_code': settings_list['custom_css_code'] if ("custom_css_code" in settings_list) else '',
        'custom_js_code': settings_list['custom_js_code'] if ("custom_js_code" in settings_list) else ''
    }


@frappe.whitelist()
def update_theme_settings(**data):
    data = frappe._dict(data)
    doc = frappe.get_doc("Theme Settings")
    doc.theme_color = data.theme_color
    doc.apply_on_menu = data.apply_on_menu
    doc.apply_on_dashboard = data.apply_on_dashboard
    doc.apply_on_workspace = data.apply_on_workspace
    doc.apply_on_navbar = data.apply_on_navbar
    doc.save(ignore_permissions=True)
    return doc


@frappe.whitelist()
def get_events(start=getdate(), end=getdate().year, user=None, for_reminder=False, filters=None):
    end = str(getdate().year) + "-12-31"
    if not user:
        user = frappe.session.user

    if isinstance(filters, string_types):
        filters = json.loads(filters)

    filter_condition = get_filters_cond('Event', filters, [])

    tables = ["`tabEvent`"]
    if "`tabEvent Participants`" in filter_condition:
        tables.append("`tabEvent Participants`")

    events = frappe.db.sql("""
        SELECT `tabEvent`.name,
                `tabEvent`.subject,
                `tabEvent`.description,
                `tabEvent`.color,
                `tabEvent`.starts_on,
                `tabEvent`.ends_on,
                `tabEvent`.owner,
                `tabEvent`.all_day,
                `tabEvent`.event_type,
                `tabEvent`.repeat_this_event,
                `tabEvent`.repeat_on,
                `tabEvent`.repeat_till,
                `tabEvent`.monday,
                `tabEvent`.tuesday,
                `tabEvent`.wednesday,
                `tabEvent`.thursday,
                `tabEvent`.friday,
                `tabEvent`.saturday,
                `tabEvent`.sunday
        FROM {tables}
        WHERE (
                (
                    (date(`tabEvent`.starts_on) BETWEEN date(%(start)s) AND date(%(end)s))
                    OR (date(`tabEvent`.ends_on) BETWEEN date(%(start)s) AND date(%(end)s))
                    OR (
                        date(`tabEvent`.starts_on) <= date(%(start)s)
                        AND date(`tabEvent`.ends_on) >= date(%(end)s)
                    )
                )
                OR (
                    date(`tabEvent`.starts_on) <= date(%(start)s)
                    AND `tabEvent`.repeat_this_event=1
                    AND coalesce(`tabEvent`.repeat_till, '3000-01-01') > date(%(start)s)
                )
            )
        {reminder_condition}
        {filter_condition}
        AND (
                `tabEvent`.event_type='Public'
                OR `tabEvent`.owner=%(user)s
                OR EXISTS(
                    SELECT `tabDocShare`.name
                    FROM `tabDocShare`
                    WHERE `tabDocShare`.share_doctype='Event'
                        AND `tabDocShare`.share_name=`tabEvent`.name
                        AND `tabDocShare`.user=%(user)s
                )
            )
        AND `tabEvent`.status='Open'
        ORDER BY `tabEvent`.starts_on""".format(
        tables=", ".join(tables),
        filter_condition=filter_condition,
        reminder_condition="AND coalesce(`tabEvent`.send_reminder, 0)=1" if for_reminder else ""
    ), {
        "start": start,
        "end": end,
        "user": user,
    }, as_dict=1)

    return events


@frappe.whitelist()
def update_menu_modules(modules):
    modules_list = json.loads(modules)
    for module in modules_list:
        if frappe.db.exists("Workspace", module["name"]):
            if (module["_is_deleted"] == 'true'):
                frappe.delete_doc("Workspace", module["name"], force=True)
            else:
                frappe.db.set_value("Workspace", module["name"], {
                    "title": module['title'],
                    "label": module["title"],
                    "icon": module["icon"],
                    "sequence_id": int(module["sequence_id"])
                })
        else:
            if (module["_is_new"] == 'true'):
                workspace = frappe.new_doc("Workspace")
                workspace.title = module["title"]
                workspace.icon = module["icon"]
                workspace.content = module["content"]
                workspace.label = module["label"]
                workspace.sequence_id = int(module["sequence_id"])
                workspace.for_user = ""
                workspace.public = 1
                workspace.save(ignore_permissions=True)

    return True


def clear():
    frappe.local.session_obj.update(force=True)
    frappe.local.db.commit()
    clear_user_cache(frappe.session.user)
    frappe.response['message'] = _("Cache Cleared")
