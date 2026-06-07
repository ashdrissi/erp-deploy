import re
import unicodedata


def resolve_customs_rule(rules, tariff_number=None, material=None):
    tariff_number = _normalize_tariff_number(tariff_number)
    material = _normalize_material(material)

    active = [rule for rule in (rules or []) if _to_int(rule.get("is_active", 1))]
    if not active:
        return None

    scored = []
    for rule in active:
        r_tariff_number = _normalize_tariff_number(rule.get("tariff_number"))
        r_material = _normalize_material(rule.get("material"))

        if r_tariff_number and r_tariff_number != tariff_number:
            continue
        if r_material and r_material != material:
            continue

        if r_tariff_number and r_material:
            specificity = 4
        elif r_tariff_number:
            specificity = 3
        elif r_material:
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
    base_amount_fallback=False,
):
    qty = float(qty or 0)
    unit_weight_kg = float(unit_weight_kg or 0)
    base_amount = float(base_amount or 0)
    rate_percent = float(rate_percent or 0)
    value_per_kg = float(value_per_kg or 0)
    component_values = []
    if not rate_percent:
        component_values = _parse_percent_components(rate_components)
        if component_values:
            rate_percent = sum(component_values)
    total_weight_kg = qty * unit_weight_kg
    use_base_amount = bool(base_amount_fallback and total_weight_kg <= 0 and base_amount > 0)
    customs_base_value = base_amount if use_base_amount else total_weight_kg * value_per_kg
    applied = customs_base_value * (rate_percent / 100.0)
    displayed_components = component_values or ([rate_percent] if rate_percent else [])
    return {
        "mode": "buying_amount_fallback" if use_base_amount else "customs_material",
        "base_value": customs_base_value,
        "total_percent": rate_percent,
        "component_values": displayed_components,
        "component_display": _format_percent_components(displayed_components),
        "by_kg": 0.0,
        "by_percent": applied,
        "applied": applied,
        "basis": "Buying Amount x Rate Percent (Weight Fallback)"
        if use_base_amount
        else "Value Per Kg x Weight x Rate Percent",
    }


def _to_int(value):
    try:
        return int(value)
    except Exception:
        return 0


def _normalize_tariff_number(value):
    return re.sub(r"[^A-Za-z0-9]", "", str(value or "").upper())


def _normalize_material(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text.strip().lower())
    text = re.sub(r"\s+\)", ")", text)
    aliases = {
        "concrete": "beton",
        "copper": "cuivre",
        "plastic": "plastique",
        "plastique / pvc": "plastique",
        "pvc": "plastique",
        "steel": "acier",
        "carte": "acier (carte)",
    }
    return aliases.get(text, text)


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
