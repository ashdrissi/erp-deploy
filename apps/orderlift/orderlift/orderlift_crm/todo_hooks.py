from __future__ import annotations

from orderlift.orderlift_crm.todo_priority import normalize_todo_priority


def normalize_todo_priority_on_validate(doc, method=None) -> None:
    doc.priority = normalize_todo_priority(getattr(doc, "priority", None))
