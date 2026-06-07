from __future__ import annotations

from html import escape
from pathlib import PurePosixPath

import frappe
from frappe import _
from frappe.utils import cint, flt, now


SUPPORTED_AUDIO_EXTENSIONS = {".aac", ".flac", ".m4a", ".mp3", ".mp4", ".oga", ".ogg", ".opus", ".wav", ".webm"}


@frappe.whitelist()
def add_opportunity_voice_comment(opportunity: str, file: str, note: str | None = None, duration: str | None = None) -> dict:
    opportunity = (opportunity or "").strip()
    file = (file or "").strip()
    note = (note or "").strip()

    if not opportunity or not frappe.db.exists("Opportunity", opportunity):
        frappe.throw(_("Opportunity {0} was not found.").format(opportunity or ""))
    if not file:
        frappe.throw(_("Audio file is required."))

    opportunity_doc = frappe.get_doc("Opportunity", opportunity)
    if not frappe.has_permission("Opportunity", "write", doc=opportunity_doc):
        frappe.throw(_("You do not have permission to add comments to this Opportunity."), frappe.PermissionError)

    file_doc = _resolve_audio_file(file, opportunity)
    content = _voice_comment_content(file_doc, note, duration)
    comment = frappe.get_doc(
        {
            "doctype": "Comment",
            "comment_type": "Comment",
            "reference_doctype": "Opportunity",
            "reference_name": opportunity,
            "content": content,
        }
    ).insert(ignore_permissions=True)
    _append_opportunity_note(opportunity_doc, content)
    frappe.db.commit()
    return {"comment": comment.name, "file": file_doc.name, "file_url": file_doc.file_url}


def _resolve_audio_file(file: str, opportunity: str):
    filters = {"attached_to_doctype": "Opportunity", "attached_to_name": opportunity}
    if frappe.db.exists("File", file):
        file_doc = frappe.get_doc("File", file)
    else:
        file_name = frappe.db.get_value("File", {**filters, "file_url": file}, "name")
        if not file_name:
            file_name = frappe.db.get_value("File", {**filters, "file_name": file}, "name")
        if not file_name:
            frappe.throw(_("Audio file {0} is not attached to Opportunity {1}.").format(file, opportunity))
        file_doc = frappe.get_doc("File", file_name)

    if file_doc.attached_to_doctype != "Opportunity" or file_doc.attached_to_name != opportunity:
        frappe.throw(_("Audio file {0} is not attached to Opportunity {1}.").format(file_doc.name, opportunity))
    if not _is_audio_file(file_doc):
        frappe.throw(_("Only audio files can be used for voice comments."))
    return file_doc


def _is_audio_file(file_doc) -> bool:
    candidates = [file_doc.get("file_url"), file_doc.get("file_name"), file_doc.name]
    for value in candidates:
        suffix = PurePosixPath(str(value or "").split("?", 1)[0]).suffix.lower()
        if suffix in SUPPORTED_AUDIO_EXTENSIONS:
            return True
    file_type = (file_doc.get("file_type") or "").strip().lower()
    return file_type.startswith("audio")


def _voice_comment_content(file_doc, note: str, duration: str | None) -> str:
    file_url = escape(file_doc.file_url or "", quote=True)
    file_name = escape(file_doc.file_name or file_doc.name, quote=True)
    duration_text = _format_duration(duration)
    meta = f'<p class="text-muted small">{escape(duration_text)}</p>' if duration_text else ""
    note_html = f"<p>{escape(note)}</p>" if note else ""
    return (
        "<div class=\"orderlift-voice-comment\">"
        f"<p><strong>{escape(_('Voice comment'))}</strong></p>"
        f"<audio controls preload=\"metadata\" src=\"{file_url}\" style=\"width:100%;max-width:420px;\"></audio>"
        f"{meta}"
        f"{note_html}"
        f"<p><a href=\"{file_url}\" target=\"_blank\" rel=\"noopener\">{file_name}</a></p>"
        "</div>"
    )


def _append_opportunity_note(opportunity_doc, content: str) -> None:
    if not opportunity_doc.meta.get_field("notes"):
        return
    opportunity_doc.append("notes", {"note": content, "added_by": frappe.session.user, "added_on": now()})
    opportunity_doc.save(ignore_permissions=False)


def _format_duration(duration: str | None) -> str:
    seconds = cint(flt(duration or 0))
    if seconds <= 0:
        return ""
    minutes, remainder = divmod(seconds, 60)
    return _("Duration: {0}:{1}").format(minutes, str(remainder).zfill(2))
