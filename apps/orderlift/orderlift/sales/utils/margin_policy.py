def resolve_margin_rule(rules, customer_type=None, tier=None):
    customer_type = (customer_type or "").strip().lower()
    tier = (tier or "").strip().lower()

    active = [rule for rule in (rules or []) if _to_int(rule.get("is_active", 1))]
    if not active:
        return None

    scored = []
    for rule in active:
        r_customer = (rule.get("customer_type") or "").strip().lower()
        r_tier = (rule.get("tier") or "").strip().lower()

        if r_customer and r_customer != customer_type:
            continue
        if r_tier and r_tier != tier:
            continue

        specificity = 0
        if r_customer:
            specificity += 2
        if r_tier:
            specificity += 1

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


def _to_int(value):
    try:
        return int(value)
    except Exception:
        return 0
