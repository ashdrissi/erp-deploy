import re


def resolve_customs_rule(rules, tariff_number=None, material=None):
    tariff_number = _normalize_tariff_number(tariff_number)
    material = (material or "").strip().lower()

    active = [rule for rule in (rules or []) if _to_int(rule.get("is_active", 1))]
    if not active:
        return None

    scored = []
    for rule in active:
        r_tariff_number = _normalize_tariff_number(rule.get("tariff_number"))
        r_material = (rule.get("material") or "").strip().lower()

        specificity = None
        if r_tariff_number:
            if r_tariff_number != tariff_number:
                continue
            specificity = 3
        elif r_material:
            if r_material != material:
                continue
            specificity = 2
        else:
            specificity = 1

        scored.append(
            (
                -specificity,
                _to_int(rule.get("priority") or 10),
                _to_int(rule.get("sequence") or 90),
                _to_int(rule.get("idx") or 0),
                rule,
            )
        )

    if not scored:
        return None

    scored.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
    return scored[0][4]


def compute_customs_amount(
    base_amount,
    qty,
    unit_weight_kg,
    rate_per_kg=0,
    rate_percent=0,
    value_per_kg=0,
    rate_components="",
):
    qty = float(qty or 0)
    unit_weight_kg = float(unit_weight_kg or 0)
    base_amount = float(base_amount or 0)
    rate_per_kg = float(rate_per_kg or 0)
    rate_percent = float(rate_percent or 0)
    value_per_kg = float(value_per_kg or 0)
    component_values = _parse_percent_components(rate_components)

    if value_per_kg or component_values:
        total_percent = sum(component_values) if component_values else rate_percent
        customs_base_value = qty * unit_weight_kg * value_per_kg
        applied = customs_base_value * (total_percent / 100.0)
        return {
            "mode": "tariff",
            "base_value": customs_base_value,
            "total_percent": total_percent,
            "component_values": component_values,
            "component_display": _format_percent_components(component_values),
            "applied": applied,
            "basis": "Tariff Value x Percent",
            "by_kg": 0.0,
            "by_percent": 0.0,
        }

    by_kg = qty * unit_weight_kg * rate_per_kg
    by_percent = base_amount * (rate_percent / 100.0)
    applied = max(by_kg, by_percent)
    basis = "Per Kg" if by_kg >= by_percent else "Percent"
    return {
        "mode": "legacy",
        "base_value": 0.0,
        "total_percent": rate_percent,
        "component_values": [rate_percent] if rate_percent else [],
        "component_display": _format_percent_components([rate_percent] if rate_percent else []),
        "by_kg": by_kg,
        "by_percent": by_percent,
        "applied": applied,
        "basis": basis,
    }


def _to_int(value):
    try:
        return int(value)
    except Exception:
        return 0


def _normalize_tariff_number(value):
    return re.sub(r"[^A-Za-z0-9]", "", str(value or "").upper())


def _parse_percent_components(value):
    text = str(value or "").strip()
    if not text:
        return []
    return [float(match) for match in re.findall(r"\d+(?:\.\d+)?", text)]


def _format_percent_components(values):
    return " + ".join(_format_component(value) for value in values if float(value or 0) != 0)


def _format_component(value):
    number = float(value or 0)
    if number.is_integer():
        return str(int(number))
    return f"{number:.4f}".rstrip("0").rstrip(".")
