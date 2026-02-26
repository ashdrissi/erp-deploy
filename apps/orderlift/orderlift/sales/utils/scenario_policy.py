def resolve_scenario_rule(rules, context=None):
    context = context or {}
    active = [rule for rule in (rules or []) if _to_int(rule.get("is_active", 1))]
    if not active:
        return None

    scored = []
    for rule in active:
        if not _matches(rule, context):
            continue
        scored.append(
            (
                -_specificity(rule),
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


def _matches(rule, context):
    for key in (
        "sales_person",
        "geography_type",
        "geography_value",
        "customer_segment",
        "customer_type",
        "tier",
        "item",
        "item_group",
        "material",
    ):
        rule_val = _norm(rule.get(key))
        if not rule_val:
            continue
        if rule_val != _norm(context.get(key)):
            return False
    return True


def _specificity(rule):
    weights = {
        "item": 32,
        "item_group": 16,
        "material": 8,
        "sales_person": 16,
        "geography_value": 8,
        "geography_type": 2,
        "customer_type": 4,
        "tier": 2,
        "customer_segment": 1,
    }
    score = 0
    for key, weight in weights.items():
        if _norm(rule.get(key)):
            score += weight
    return score


def _norm(value):
    return (value or "").strip().lower()


def _to_int(value):
    try:
        return int(value)
    except Exception:
        return 0
