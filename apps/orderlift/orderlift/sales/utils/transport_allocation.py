def compute_transport_allocation(mode, container_price, line_base_amount=0, line_weight_kg=0, line_volume_m3=0, totals=None):
    totals = totals or {}
    mode = (mode or "By Value").strip().title()
    container_price = _to_float(container_price)
    line_base_amount = _to_float(line_base_amount)
    line_weight_kg = _to_float(line_weight_kg)
    line_volume_m3 = _to_float(line_volume_m3)

    out = {
        "mode": mode,
        "container_price": container_price,
        "line_base_amount": line_base_amount,
        "line_weight_kg": line_weight_kg,
        "line_volume_m3": line_volume_m3,
        "denominator": 0.0,
        "numerator": 0.0,
        "applied": 0.0,
        "warning": "",
    }

    if container_price <= 0:
        return out

    if mode == "By Kg":
        denominator = _to_float(totals.get("total_weight_kg"))
        numerator = line_weight_kg
    elif mode == "By M3":
        denominator = _to_float(totals.get("total_volume_m3"))
        numerator = line_volume_m3
    else:
        mode = "By Value"
        denominator = _to_float(totals.get("total_merch_value"))
        numerator = line_base_amount

    out["mode"] = mode
    out["denominator"] = denominator
    out["numerator"] = numerator

    if denominator <= 0:
        out["warning"] = f"transport denominator is zero for mode {mode}; transport set to 0"
        return out

    if numerator <= 0:
        out["warning"] = f"transport numerator is zero for mode {mode}; transport set to 0"
        return out

    out["applied"] = (numerator / denominator) * container_price
    return out


def _to_float(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0
