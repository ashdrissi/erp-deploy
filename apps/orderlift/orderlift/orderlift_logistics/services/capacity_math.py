def _flt(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def round3(value):
    return round(_flt(value), 3)


def compute_utilization(total_weight_kg, total_volume_m3, max_weight_kg, max_volume_m3):
    weight_pct = (_flt(total_weight_kg) / _flt(max_weight_kg) * 100) if _flt(max_weight_kg) > 0 else 0
    volume_pct = (_flt(total_volume_m3) / _flt(max_volume_m3) * 100) if _flt(max_volume_m3) > 0 else 0
    return {
        "weight_utilization_pct": round3(weight_pct),
        "volume_utilization_pct": round3(volume_pct),
    }


def detect_limiting_factor(weight_utilization_pct, volume_utilization_pct, epsilon=1.0):
    weight_pct = _flt(weight_utilization_pct)
    volume_pct = _flt(volume_utilization_pct)
    if abs(weight_pct - volume_pct) <= _flt(epsilon):
        return "both"
    return "weight" if weight_pct > volume_pct else "volume"


def candidate_pressure(total_weight_kg, total_volume_m3, remaining_weight_kg, remaining_volume_m3):
    weight_pressure = _flt(total_weight_kg) / _flt(remaining_weight_kg) if _flt(remaining_weight_kg) > 0 else 0
    volume_pressure = _flt(total_volume_m3) / _flt(remaining_volume_m3) if _flt(remaining_volume_m3) > 0 else 0
    return max(weight_pressure, volume_pressure)
