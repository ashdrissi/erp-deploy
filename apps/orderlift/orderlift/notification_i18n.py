from __future__ import annotations

import re


I18N_BLOCK_RE = re.compile(r"\[\[(fr|en)\]\](.*?)\[\[/\1\]\]", re.DOTALL)


def build_multilingual_text(french: str, english: str) -> str:
    return f"[[fr]]{french}[[/fr]][[en]]{english}[[/en]]"


def apply_user_language_to_notification_log(doc, method=None) -> None:
    language = _get_user_language(doc.get("for_user"))
    for fieldname in ("subject", "email_content"):
        value = doc.get(fieldname)
        if value:
            doc.set(fieldname, select_multilingual_text(value, language))


def select_multilingual_text(value: str, language: str | None) -> str:
    blocks = {lang: text.strip() for lang, text in I18N_BLOCK_RE.findall(value or "")}
    if not blocks:
        return value

    selected_language = normalize_language(language)
    return blocks.get(selected_language) or blocks.get("en") or blocks.get("fr") or value


def normalize_language(language: str | None) -> str:
    value = (language or "").strip().lower()
    if value.startswith("fr") or "french" in value or "fran" in value:
        return "fr"
    return "en"


def _get_user_language(user: str | None) -> str:
    if not user:
        return "en"

    import frappe

    return frappe.db.get_value("User", user, "language") or frappe.db.get_default("language") or "en"
