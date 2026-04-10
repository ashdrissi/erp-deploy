# frappe.desk.desktop.get_workspace_sidebar_items
from frappe.desk.desktop import get_workspace_sidebar_items, get_desktop_page
import frappe
import json


CACHE_KEY_PREFIX = "custom_workspace_pages_cache"
CACHE_TTL = 60 * 60  # 1 hour — tune based on your load profile
BUSINESS_ADMIN_ROLE = "Orderlift Client User"
BUSINESS_ADMIN_WORKSPACES = {"Main Dashboard"}


def _get_cache_key():
    return f"{CACHE_KEY_PREFIX}:{frappe.session.user}"


def _filter_pages(pages):
    if BUSINESS_ADMIN_ROLE not in frappe.get_roles():
        return pages

    return [page for page in pages if page.get("name") in BUSINESS_ADMIN_WORKSPACES]


@frappe.whitelist()
def sidebar():
    cache = frappe.cache()
    cache_key = _get_cache_key()

    # 1. Try serving from cache first
    cached = cache.get_value(cache_key)
    if cached:
        return cached  # fast path, no DB load

    # 2. Cache miss → compute fresh
    response = get_workspace_sidebar_items()
    final_pages = []
    pages = _filter_pages(response.get("pages", []))

    for page in pages:
        page_name = page.get("name")
        if not page_name:
            continue

        output = get_desktop_page(
            page=json.dumps({
                "name": page_name,
                "title": page_name
            })
        )

        page["subpages"] = output
        final_pages.append(page)

    # 3. Store result in Redis so next request is instant
    cache.set_value(cache_key, final_pages, expires_in_sec=CACHE_TTL)

    return final_pages
