from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

import frappe
from frappe import _
from frappe.utils import cint
from frappe.utils.file_manager import save_file


MAX_IMAGE_BYTES = 10 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 30


@frappe.whitelist()
def run(
    dry_run: int | str = 1,
    limit: int | str | None = None,
    start: int | str = 0,
    timeout: int | str = DEFAULT_TIMEOUT_SECONDS,
):
    frappe.only_for("System Manager")
    dry_run = _truthy(dry_run)
    limit = cint(limit or 0)
    start = cint(start or 0)
    timeout = cint(timeout or DEFAULT_TIMEOUT_SECONDS)

    rows = _external_image_items()
    selected_rows = rows[start : start + limit] if limit else rows[start:]
    summary = {
        "dry_run": dry_run,
        "total_external_images": len(rows),
        "start": start,
        "limit": limit or None,
        "selected": len(selected_rows),
        "downloaded": 0,
        "reused_files": 0,
        "items_updated": 0,
        "skipped": 0,
        "failures": [],
        "samples": [],
    }

    content_cache = {}
    for row in selected_rows:
        _process_item_image(row.name, row.image, summary, dry_run=dry_run, timeout=timeout, content_cache=content_cache)

    if not dry_run:
        frappe.db.commit()
    return summary


def _external_image_items():
    return frappe.get_all(
        "Item",
        filters={"image": ["like", "http%"]},
        fields=["name", "image"],
        order_by="name asc",
        limit_page_length=0,
    )


def _process_item_image(item_code: str, image_url: str, summary: dict, dry_run: bool, timeout: int, content_cache: dict):
    if not _is_google_image_url(image_url):
        summary["skipped"] += 1
        return

    try:
        content, content_type, response_filename, downloaded = _download_image(image_url, timeout=timeout, cache=content_cache)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        _append_failure(summary, item_code, image_url, str(exc))
        return
    if downloaded:
        summary["downloaded"] += 1
    filename = _file_name(item_code, image_url, content_type=content_type, response_filename=response_filename)
    if dry_run:
        _append_sample(summary, item_code, image_url, f"/files/{filename}", "would_download")
        return
    file_doc = save_file(filename, content, "Item", item_code, is_private=0)

    if not dry_run:
        current = frappe.db.get_value("Item", item_code, "image")
        if current != file_doc.file_url:
            frappe.db.set_value("Item", item_code, "image", file_doc.file_url, update_modified=False)
            summary["items_updated"] += 1
    _append_sample(summary, item_code, image_url, file_doc.file_url if not dry_run else filename, "updated")


def _download_image(url: str, timeout: int, cache: dict):
    if url in cache:
        content, content_type, response_filename = cache[url]
        return content, content_type, response_filename, False

    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=timeout) as response:
        content_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if not content_type.startswith("image/"):
            raise ValueError(_("URL did not return an image: {0}").format(content_type or "unknown content type"))
        content_length = cint(response.headers.get("Content-Length") or 0)
        if content_length > MAX_IMAGE_BYTES:
            raise ValueError(_("Image is too large: {0} bytes").format(content_length))
        content = response.read(MAX_IMAGE_BYTES + 1)
        if len(content) > MAX_IMAGE_BYTES:
            raise ValueError(_("Image is too large: over {0} bytes").format(MAX_IMAGE_BYTES))
        response_filename = _response_filename(response.headers.get("Content-Disposition") or "")
        cache[url] = (content, content_type, response_filename)
        return content, content_type, response_filename, True


def _response_filename(content_disposition: str) -> str:
    match = re.search(r"filename\*=UTF-8''([^;]+)", content_disposition, flags=re.I)
    if match:
        return unquote(match.group(1).strip().strip('"'))
    match = re.search(r'filename="?([^";]+)"?', content_disposition, flags=re.I)
    if match:
        return unquote(match.group(1).strip())
    return ""


def _file_name(item_code: str, url: str, content_type: str = "", response_filename: str = "") -> str:
    extension = Path(response_filename or urlparse(url).path).suffix.lower()
    if not extension or len(extension) > 6:
        extension = mimetypes.guess_extension(content_type or "") or ".png"
    if extension == ".jpe":
        extension = ".jpg"
    return f"{_safe_name(item_code)}{extension}"


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", (value or "").strip()).strip(".-") or "item-image"


def _is_google_image_url(value: str) -> bool:
    parsed = urlparse(value or "")
    return parsed.scheme in {"http", "https"} and (
        parsed.netloc.endswith("drive.google.com") or parsed.netloc.endswith("googleusercontent.com")
    )


def _append_sample(summary: dict, item_code: str, source_url: str, file_url: str, status: str):
    if len(summary["samples"]) < 20:
        summary["samples"].append(
            {"item_code": item_code, "source_url": source_url, "file_url": file_url, "status": status}
        )


def _append_failure(summary: dict, item_code: str, source_url: str, error: str):
    if len(summary["failures"]) < 200:
        summary["failures"].append({"item_code": item_code, "source_url": source_url, "error": error})


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"", "0", "false", "no"}
