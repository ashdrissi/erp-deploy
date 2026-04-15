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
        applies_to = (expense.get("applies_to") or "Base Price").strip() or "Base Price"
        scope = (expense.get("scope") or "Per Unit").strip().title()
        value = float(expense.get("value") or 0.0)
        sequence = int(expense.get("sequence") or 0)
        label = expense.get("label") or "Expense"
        expense_key = expense.get("expense_key")
        is_overridden = 1 if float(expense.get("is_overridden") or 0) else 0
        override_source = expense.get("override_source")

        basis = float(base_unit)
        delta_unit = 0.0
        delta_line = 0.0
        delta_sheet = 0.0

        if expense_type == "Percentage":
            if applies_to != "Base Price":
                raise ValueError(f"Percentage step '{label}' must apply to Base Price, got '{applies_to}'")
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
                "override_source": override_source,
                "basis": basis,
                "delta_unit": delta_unit,
                "delta_line": delta_line,
                "delta_sheet": delta_sheet,
                "running_total": running_total,
            }
        )

    projected_unit = running_total
    projected_line = projected_unit * qty
    return {
        "projected_unit": projected_unit,
        "projected_line": projected_line,
        "expense_total_unit": projected_unit - float(base_unit),
        "line_fixed_total": line_fixed_total,
        "sheet_fixed_total": sheet_fixed_total,
        "steps": steps,
    }


def apply_discount_and_commission(
    gross_unit_price: float,
    qty: float,
    discount_percent: float,
    max_discount_percent: float,
    commission_rate: float,
) -> dict:
    gross_unit_price = float(gross_unit_price or 0)
    qty = float(qty or 0)
    discount_percent = float(discount_percent or 0)
    max_discount_percent = float(max_discount_percent or 0)
    commission_rate = float(commission_rate or 0)

    if discount_percent < 0:
        raise ValueError("Discount % cannot be negative")
    if discount_percent > max_discount_percent + 1e-9:
        raise ValueError(f"Discount % cannot exceed {max_discount_percent:.1f}%")

    gross_total = gross_unit_price * qty
    discount_amount = gross_total * (discount_percent / 100.0) if discount_percent else 0.0
    discounted_unit_price = gross_unit_price * (1 - (discount_percent / 100.0)) if discount_percent else gross_unit_price
    discounted_total = gross_total - discount_amount
    commission_amount = discount_amount * (commission_rate / 100.0) if discount_amount and commission_rate else 0.0

    return {
        "gross_total": gross_total,
        "max_discount_percent": max_discount_percent,
        "discount_percent": discount_percent,
        "discount_amount": discount_amount,
        "discounted_unit_price": discounted_unit_price,
        "discounted_total": discounted_total,
        "commission_rate": commission_rate,
        "commission_amount": commission_amount,
    }


def resolve_max_discount_cap(
    *,
    rule_max_discount_percent: float,
    fallback_max_discount_percent: float,
    agent_max_discount_percent: float,
    is_fallback: bool,
) -> float:
    rule_max_discount_percent = float(rule_max_discount_percent or 0)
    fallback_max_discount_percent = float(fallback_max_discount_percent or 0)
    agent_max_discount_percent = float(agent_max_discount_percent or 0)

    if not is_fallback:
        return rule_max_discount_percent or agent_max_discount_percent or 0.0

    positive_caps = [
        value for value in (fallback_max_discount_percent, agent_max_discount_percent)
        if value > 0
    ]
    if positive_caps:
        return min(positive_caps)

    return 0.0
