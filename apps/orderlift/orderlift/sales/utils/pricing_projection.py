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


def apply_expenses(base_unit: float, qty: float, expenses: Iterable[dict], include_sheet_fixed: bool = False) -> dict:
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

    projected_line = running_total * qty
    if include_sheet_fixed:
        projected_line += sheet_fixed_total
    projected_unit = projected_line / qty if qty else running_total
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
    actual_unit_price: float | None = None,
    uplift_commission_rate: float = 20.0,
    enforce_discount_cap: bool = True,
    discount_base_unit_price: float | None = None,
) -> dict:
    gross_unit_price = float(gross_unit_price or 0)
    qty = float(qty or 0)
    discount_percent = float(discount_percent or 0)
    max_discount_percent = float(max_discount_percent or 0)
    commission_rate = float(commission_rate or 0)
    uplift_commission_rate = float(uplift_commission_rate or 0)
    discount_base_unit_price = float(discount_base_unit_price if discount_base_unit_price is not None else gross_unit_price)

    if discount_percent < 0:
        raise ValueError("Discount % cannot be negative")
    if enforce_discount_cap and discount_percent > max_discount_percent + 1e-9:
        raise ValueError(f"Discount % cannot exceed {max_discount_percent:.1f}%")

    gross_total = gross_unit_price * qty
    discounted_unit_price = (
        float(actual_unit_price or 0)
        if actual_unit_price is not None
        else discount_base_unit_price * (1 - (discount_percent / 100.0))
    )
    discounted_total = discounted_unit_price * qty
    discount_amount = max(discount_base_unit_price * qty * (discount_percent / 100.0), 0.0)
    commission = calculate_agent_commission(
        price_list_unit_price=gross_unit_price,
        actual_unit_price=discounted_unit_price,
        qty=qty,
        max_discount_percent=max_discount_percent,
        commission_rate=commission_rate,
        discount_percent=discount_percent,
        uplift_commission_rate=uplift_commission_rate,
        enforce_discount_cap=enforce_discount_cap,
    )

    return {
        "gross_total": gross_total,
        "max_discount_percent": max_discount_percent,
        "discount_percent": discount_percent,
        "unused_discount_percent": commission["unused_discount_percent"],
        "discount_amount": discount_amount,
        "discounted_unit_price": discounted_unit_price,
        "discounted_total": discounted_total,
        "commission_rate": commission_rate,
        "commission_amount": commission["commission_amount"],
        "base_commission_amount": commission["base_commission_amount"],
        "uplift_commission_amount": commission["uplift_commission_amount"],
    }


def calculate_agent_commission(
    *,
    price_list_unit_price: float,
    actual_unit_price: float,
    qty: float,
    max_discount_percent: float,
    commission_rate: float,
    discount_percent: float | None = None,
    uplift_commission_rate: float = 20.0,
    enforce_discount_cap: bool = True,
) -> dict:
    price_list_unit_price = float(price_list_unit_price or 0)
    actual_unit_price = float(actual_unit_price or 0)
    qty = float(qty or 0)
    max_discount_percent = float(max_discount_percent or 0)
    commission_rate = float(commission_rate or 0)
    uplift_commission_rate = float(uplift_commission_rate or 0)

    if discount_percent is None:
        discount_percent = 0.0
        if price_list_unit_price > 0 and actual_unit_price < price_list_unit_price:
            discount_percent = ((price_list_unit_price - actual_unit_price) / price_list_unit_price) * 100.0
    else:
        discount_percent = float(discount_percent or 0)
    if enforce_discount_cap and discount_percent > max_discount_percent + 1e-9:
        raise ValueError(f"Discount % cannot exceed {max_discount_percent:.1f}%")

    price_list_total = price_list_unit_price * qty
    unused_discount_percent = max(max_discount_percent - discount_percent, 0.0)
    base_commission = price_list_total * (unused_discount_percent / 100.0) * (commission_rate / 100.0)
    uplift_commission = max(actual_unit_price - price_list_unit_price, 0.0) * qty * (uplift_commission_rate / 100.0)

    return {
        "discount_percent": discount_percent,
        "unused_discount_percent": unused_discount_percent,
        "base_commission_amount": base_commission,
        "uplift_commission_amount": uplift_commission,
        "commission_amount": base_commission + uplift_commission,
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

    if not is_fallback:
        return rule_max_discount_percent or 0.0

    return fallback_max_discount_percent or 0.0
