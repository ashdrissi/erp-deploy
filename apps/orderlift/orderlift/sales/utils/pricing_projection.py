from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass
class ExpenseStep:
    label: str
    expense_type: str
    applies_to: str
    value: float
    scope: str
    sequence: int


def apply_expenses(base_unit: float, qty: float, expenses: Iterable[dict]) -> dict:
    running_total = float(base_unit)
    line_fixed_total = 0.0
    sheet_fixed_total = 0.0
    steps = []

    ordered = sorted(
        [e for e in expenses if float(e.get("is_active", 1))],
        key=lambda x: (int(x.get("sequence") or 0), int(x.get("idx") or 0)),
    )

    for expense in ordered:
        expense_type = (expense.get("type") or "Percentage").strip().title()
        applies_to = (expense.get("applies_to") or "Running Total").strip().title()
        scope = (expense.get("scope") or "Per Unit").strip().title()
        value = float(expense.get("value") or 0.0)
        sequence = int(expense.get("sequence") or 0)
        label = expense.get("label") or "Expense"
        expense_key = expense.get("expense_key")
        is_overridden = 1 if float(expense.get("is_overridden") or 0) else 0

        basis = float(base_unit) if applies_to == "Base Price" else float(running_total)
        delta_unit = 0.0
        delta_line = 0.0
        delta_sheet = 0.0

        if expense_type == "Percentage":
            delta_unit = basis * (value / 100.0)
            running_total += delta_unit
        else:
            if scope == "Per Sheet":
                delta_sheet = value
                sheet_fixed_total += delta_sheet
            elif scope == "Per Line":
                delta_line = value
                line_fixed_total += delta_line
                running_total += delta_line / qty if qty else 0
            else:
                delta_unit = value
                running_total += delta_unit

        steps.append(
            {
                "label": label,
                "type": expense_type,
                "value": value,
                "applies_to": applies_to,
                "scope": scope,
                "sequence": sequence,
                "expense_key": expense_key,
                "is_overridden": is_overridden,
                "basis": basis,
                "delta_unit": delta_unit,
                "delta_line": delta_line,
                "delta_sheet": delta_sheet,
                "running_total": running_total,
            }
        )

    projected_unit = running_total
    projected_line = projected_unit * qty + line_fixed_total
    return {
        "projected_unit": projected_unit,
        "projected_line": projected_line,
        "expense_total_unit": projected_unit - float(base_unit),
        "line_fixed_total": line_fixed_total,
        "sheet_fixed_total": sheet_fixed_total,
        "steps": steps,
    }
