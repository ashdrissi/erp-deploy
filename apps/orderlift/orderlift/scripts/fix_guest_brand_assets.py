from __future__ import annotations

import re
import shutil
from pathlib import Path

import frappe

from orderlift.logo_api import LOGO_ENDPOINT_MARKER


FONT_IMPORT_PATTERN = re.compile(r'@import"frappe/public/css/fonts/([^"]+)";')


def run():
    public_logo_url = ensure_public_logo()
    patched_theme_url = patch_active_theme_css()
    bridge_font_url = ensure_theme_font_bridge()

    frappe.db.commit()
    frappe.clear_cache()

    print(f"public_logo_url={public_logo_url}")
    print(f"patched_theme_url={patched_theme_url}")
    print(f"bridge_font_url={bridge_font_url}")


def ensure_public_logo() -> str:
    website_settings = frappe.get_single("Website Settings")
    navbar_settings = frappe.get_single("Navbar Settings")
    current_logo_url = website_settings.app_logo or ""
    endpoint_url = LOGO_ENDPOINT_MARKER + "?v=20260415b"

    if not current_logo_url:
        return ""

    public_url = current_logo_url

    if current_logo_url.startswith("/private/files/"):
        filename = Path(current_logo_url).name
        private_path = Path(frappe.get_site_path("private", "files", filename))
        public_path = Path(frappe.get_site_path("public", "files", filename))
        public_url = f"/files/{filename}"

        public_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(private_path, public_path)

        update_file_record("Website Settings", "Website Settings", current_logo_url, public_url)
        update_file_record("Navbar Settings", "Navbar Settings", current_logo_url, public_url)

    ensure_public_file_record(public_url, Path(public_url).name)
    frappe.db.set_single_value("Website Settings", "app_logo", endpoint_url, update_modified=False)
    frappe.db.set_single_value("Navbar Settings", "app_logo", endpoint_url, update_modified=False)

    return endpoint_url


def update_file_record(doctype: str, name: str, old_url: str, new_url: str) -> None:
    records = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": doctype,
            "attached_to_name": name,
            "file_url": old_url,
        },
        pluck="name",
    )

    for file_name in records:
        file_doc = frappe.get_doc("File", file_name)
        file_doc.file_url = new_url
        file_doc.is_private = 0
        file_doc.save(ignore_permissions=True)


def patch_active_theme_css() -> str:
    theme_name = frappe.db.get_single_value("Website Settings", "website_theme") or ""
    if not theme_name:
        return ""

    theme_url = frappe.db.get_value("Website Theme", theme_name, "theme_url") or ""
    if not theme_url.startswith("/files/website_theme/"):
        return theme_url

    relative_path = theme_url.removeprefix("/files/")
    css_path = Path(frappe.get_site_path("public", relative_path))
    if not css_path.exists():
        return theme_url

    original = css_path.read_text()
    updated = FONT_IMPORT_PATTERN.sub(r'@import"/assets/frappe/css/fonts/\1";', original)
    if updated != original:
        css_path.write_text(updated)

    return theme_url


def ensure_theme_font_bridge() -> str:
    source = Path(frappe.local.sites_path) / "assets" / "frappe" / "css" / "fonts" / "inter" / "inter.css"
    public_url = "/files/website_theme/frappe/public/css/fonts/inter/inter.css"
    target = Path(
        frappe.get_site_path(
            "public",
            "files",
            "website_theme",
            "frappe",
            "public",
            "css",
            "fonts",
            "inter",
            "inter.css",
        )
    )

    if not source.exists():
        return ""

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    ensure_public_file_record(public_url, "inter.css")
    return public_url


def ensure_public_file_record(file_url: str, file_name: str) -> None:
    if frappe.db.exists("File", {"file_url": file_url}):
        return

    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": file_name,
            "file_url": file_url,
            "is_private": 0,
            "folder": "Home/Attachments",
        }
    )
    file_doc.insert(ignore_permissions=True)
