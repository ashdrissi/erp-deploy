from __future__ import annotations


TODO_PRIORITY_OPTIONS = [
    "Important Urgent",
    "Important Non Urgent",
    "Non Important Urgent",
    "Non Important Non Urgent",
]
TODO_PRIORITY_OPTIONS_TEXT = "\n".join(TODO_PRIORITY_OPTIONS)
DEFAULT_TODO_PRIORITY = "Important Non Urgent"

LEGACY_TODO_PRIORITY_MAP = {
    "High": "Important Urgent",
    "Medium": "Important Non Urgent",
    "Low": "Non Important Non Urgent",
}


def normalize_todo_priority(value: str | None) -> str:
    value = (value or "").strip()
    if value in LEGACY_TODO_PRIORITY_MAP:
        return LEGACY_TODO_PRIORITY_MAP[value]
    if value in TODO_PRIORITY_OPTIONS:
        return value
    return DEFAULT_TODO_PRIORITY
