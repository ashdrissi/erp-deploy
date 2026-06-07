from __future__ import annotations


def calculate_preview_rows(item_rows, manual_prices=None, formula_rules=None, fixed_percent=None):
    manual_prices = manual_prices or {}
    formula_rules = normalize_formula_rules(formula_rules or [])
    fixed_percent = fixed_percent or {}
    fixed_targets = _fixed_percent_targets(fixed_percent)
    fixed_pct = _to_float(fixed_percent.get("pct"))

    rows = []
    for item in item_rows or []:
        code = (item.get("item_code") or item.get("code") or "").strip()
        if not code:
            continue
        list_price = _to_float(item.get("list_price"))
        if code in manual_prices:
            chosen = _to_float(manual_prices.get(code))
        elif _fixed_percent_applies(code, fixed_percent, fixed_targets):
            chosen = round_money(list_price * (1 + fixed_pct / 100))
        else:
            chosen = list_price
        rows.append(
            {
                "item_code": code,
                "code": code,
                "item_name": item.get("item_name") or item.get("name") or code,
                "brand": item.get("brand") or "",
                "category": item.get("category") or "",
                "item_group": item.get("item_group") or "",
                "uom": item.get("uom") or item.get("stock_uom") or "",
                "list_price": list_price,
                "chosen_price": chosen,
                "final_price": round_money(chosen),
                "delta": round_money(chosen - list_price),
                "formula_rule": "",
                "formula_source": "",
            }
        )

    by_code = {row["item_code"]: row for row in rows}
    for rule in formula_rules:
        if not rule.get("checked"):
            continue
        source = by_code.get(rule.get("source") or "")
        if not source:
            continue
        for target in rule.get("targets") or []:
            target_code = target.get("code") or ""
            target_row = by_code.get(target_code)
            if not target_row or target_code == source["item_code"]:
                continue
            pct = _to_float(target.get("pct"))
            final_price = round_money(source["final_price"] * (1 + pct / 100))
            target_row["final_price"] = final_price
            target_row["delta"] = round_money(final_price - target_row["list_price"])
            target_row["formula_rule"] = rule.get("name") or "Formula rule"
            target_row["formula_source"] = source["item_code"]
            target_row["formula_percent"] = pct

    return rows


def normalize_formula_rules(rules):
    out = []
    for rule in rules or []:
        get = rule.get if isinstance(rule, dict) else lambda key, default=None: getattr(rule, key, default)
        source = (get("source") or get("source_item") or "").strip()
        if not source:
            continue
        targets = normalize_formula_targets(get("targets") or get("target_items") or [], default_pct=get("pct"))
        if not targets and get("target"):
            targets = [{"code": (get("target") or "").strip(), "pct": _to_float(get("pct"))}]
        targets = [row for row in targets if row.get("code") and row.get("code") != source]
        if not targets:
            continue
        out.append(
            {
                "name": (get("name") or get("rule_name") or get("label") or "Formula rule").strip(),
                "source": source,
                "targets": targets,
                "checked": _truthy(get("checked", get("is_active", 1))),
            }
        )
    return out


def normalize_formula_targets(targets, default_pct=0):
    out = []
    for target in targets or []:
        if isinstance(target, str):
            out.append({"code": target.strip(), "pct": _to_float(default_pct)})
            continue
        get = target.get if isinstance(target, dict) else lambda key, default=None: getattr(target, key, default)
        code = (get("code") or get("item_code") or get("target_item") or "").strip()
        pct = _to_float(get("pct", get("adjustment_percent", default_pct)))
        out.append({"code": code, "pct": pct})
    return out


def round_money(value):
    return round(_to_float(value), 2)


def _fixed_percent_targets(fixed_percent):
    return set(fixed_percent.get("item_codes") or fixed_percent.get("targets") or [])


def _fixed_percent_applies(code, fixed_percent, targets):
    if not fixed_percent:
        return False
    if (fixed_percent.get("scope") or "").strip().lower() == "all":
        return True
    return code in targets


def _to_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _truthy(value):
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no"}
    return bool(value)
