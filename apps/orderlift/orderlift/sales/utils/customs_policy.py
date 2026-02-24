def resolve_customs_rule(rules, material=None):
    material = (material or "").strip().lower()

    active = [rule for rule in (rules or []) if _to_int(rule.get("is_active", 1))]
    if not active:
        return None

    scored = []
    for rule in active:
        r_material = (rule.get("material") or "").strip().lower()
        if r_material and r_material != material:
            continue

        specificity = 1 if r_material else 0
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


def compute_customs_amount(base_amount, qty, unit_weight_kg, rate_per_kg, rate_percent):
    qty = float(qty or 0)
    unit_weight_kg = float(unit_weight_kg or 0)
    base_amount = float(base_amount or 0)
    rate_per_kg = float(rate_per_kg or 0)
    rate_percent = float(rate_percent or 0)

    by_kg = qty * unit_weight_kg * rate_per_kg
    by_percent = base_amount * (rate_percent / 100.0)
    applied = max(by_kg, by_percent)
    basis = "Per Kg" if by_kg >= by_percent else "Percent"
    return {
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
