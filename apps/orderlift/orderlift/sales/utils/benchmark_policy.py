"""Benchmark policy resolver for pricing engine.

Fetches benchmark prices from multiple price lists, computes a
reference value (median/average/weighted average), calculates the
landed_cost-to-benchmark ratio, and selects target margin from
ratio-band rules.
"""

from statistics import median

from frappe.utils import cint, flt


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_benchmark_margin(
    item_code,
    landed_cost,
    benchmark_sources,
    benchmark_rules,
    method="Median",
    min_sources=2,
    fallback_margin=10.0,
    price_map=None,
    context=None,
    benchmark_basis="Selling Market",
):
    """Resolve target margin for an item based on benchmark comparison.

    Args:
        item_code: Item code to look up.
        landed_cost: Fully-loaded cost (buy + expenses + customs + transport).
        benchmark_sources: list of dicts with ``price_list``, ``weight``, ``is_active``.
        benchmark_rules: list of dicts with ratio band and scope fields.
        method: "Median", "Average", or "Weighted Average".
        min_sources: Minimum valid prices required.
        fallback_margin: Margin % to use when benchmark data insufficient.
        price_map: dict of ``{price_list_name: {item_code: price}}``.
        context: dict of scope fields for rule matching (item, item_group, etc.).

    Returns:
        dict with keys:
            target_margin_percent, benchmark_reference, source_count,
            method, ratio, matched_rule, warnings, is_fallback
    """
    warnings = []
    context = context or {}
    benchmark_basis = (benchmark_basis or "Selling Market").strip() or "Selling Market"

    source_types = {
        _norm(src.get("price_list")): _norm(src.get("price_list_type") or src.get("source_kind") or "")
        for src in (benchmark_sources or [])
        if src.get("price_list")
    }
    basis_warning = _basis_warning(benchmark_basis, source_types)
    if basis_warning:
        warnings.append(basis_warning)

    # Gather benchmark prices from all active sources
    prices, source_labels = _fetch_benchmark_prices(
        item_code, benchmark_sources, price_map=price_map
    )

    # Validate data quality
    is_fallback = False
    if len(prices) < min_sources:
        warnings.append(
            f"Only {len(prices)} benchmark source(s) for {item_code}; "
            f"need {min_sources}. Benchmark comparison disabled."
        )
        is_fallback = True

    # Compute benchmark reference
    benchmark_ref = 0.0
    if not is_fallback:
        weights = _get_weights(benchmark_sources, source_labels)
        benchmark_ref = _compute_reference(prices, method, weights)
        if flt(benchmark_ref) <= 0:
            warnings.append(f"Benchmark reference for {item_code} is zero. Benchmark comparison disabled.")
            is_fallback = True

    # Compute ratio
    ratio = flt(landed_cost) / flt(benchmark_ref) if not is_fallback and benchmark_ref > 0 else 0.0

    # Match benchmark rule only when benchmark comparison is valid
    matched = None
    if not is_fallback:
        matched = _match_benchmark_rule(ratio, benchmark_rules, context)

    target_margin = flt(fallback_margin)
    if matched:
        target_margin = flt(matched.get("target_margin_percent"))
    elif not is_fallback:
        is_fallback = True
        warnings.append(
            f"No benchmark rule matched for {item_code}; "
            f"using fallback margin {fallback_margin}%."
        )

    return {
        "target_margin_percent": target_margin,
        "benchmark_reference": flt(benchmark_ref),
        "source_count": len(prices),
        "method": method,
        "benchmark_basis": benchmark_basis,
        "ratio": ratio,
        "matched_rule": matched,
        "warnings": warnings,
        "is_fallback": is_fallback,
        "source_labels": source_labels,
    }


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _fetch_benchmark_prices(item_code, sources, price_map=None):
    """Gather valid prices for item from active benchmark sources.

    Returns (prices_list, source_labels_list) – parallel lists.
    """
    prices = []
    labels = []
    price_map = price_map or {}

    for src in sources or []:
        if not cint(src.get("is_active", 1)):
            continue
        pl = src.get("price_list")
        if not pl:
            continue
        pl_prices = price_map.get(pl) or {}
        price = pl_prices.get(item_code)
        if price is not None and flt(price) > 0:
            prices.append(flt(price))
            labels.append(src.get("label") or pl)

    return prices, labels


def _get_weights(sources, used_labels):
    """Build weights list parallel to the used_labels list."""
    label_to_weight = {}
    for src in sources or []:
        if not cint(src.get("is_active", 1)):
            continue
        label = src.get("label") or src.get("price_list") or ""
        label_to_weight[label] = flt(src.get("weight")) or 1.0
    return [label_to_weight.get(lbl, 1.0) for lbl in used_labels]


def _compute_reference(prices, method="Median", weights=None):
    """Compute benchmark reference value from gathered prices.

    Methods:
        Median: middle value (or mean of two middle values)
        Average: arithmetic mean
        Weighted Average: weighted by source weights
    """
    if not prices:
        return 0.0

    method = (method or "Median").strip().title()

    if method == "Median":
        return median(prices)

    if method == "Average":
        return sum(prices) / len(prices)

    if method == "Weighted Average":
        weights = weights or [1.0] * len(prices)
        if len(weights) != len(prices):
            weights = [1.0] * len(prices)
        total_weight = sum(weights)
        if total_weight <= 0:
            return sum(prices) / len(prices)
        return sum(p * w for p, w in zip(prices, weights)) / total_weight

    # Unknown method, fallback to median
    return median(prices)


def _match_benchmark_rule(ratio, rules, context=None):
    """Find the best matching benchmark rule for the given ratio.

    Rules are filtered by:
    1. ratio_min <= ratio < ratio_max (0 means unlimited)
    2. scope matching (item, item_group, material, territory, etc.)
    3. specificity + priority for tie-breaking
    """
    context = context or {}
    candidates = []

    for rule in rules or []:
        if not cint(rule.get("is_active", 1)):
            continue

        # Check ratio band
        rmin = flt(rule.get("ratio_min"))
        rmax = flt(rule.get("ratio_max"))
        if ratio < rmin:
            continue
        if rmax > 0 and ratio >= rmax:
            continue

        # Check scope filters
        if not _scope_matches(rule, context):
            continue

        specificity = _scope_specificity(rule)
        candidates.append(
            (
                -specificity,
                cint(rule.get("priority") or 10),
                cint(rule.get("sequence") or 90),
                cint(rule.get("idx") or 0),
                rule,
            )
        )

    if not candidates:
        return None

    candidates.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
    return candidates[0][4]


def _scope_matches(rule, context):
    """Check if rule scope filters match the context."""
    for key in (
        "item_group", "material", "source_bundle", "geography_territory", "customer_type"
    ):
        rule_val = _norm(rule.get(key))
        if not rule_val:
            continue
        if rule_val != _norm(context.get(key)):
            return False
    return True


def _scope_specificity(rule):
    """Compute specificity score for scope filters (higher = more specific)."""
    weights = {
        "source_bundle": 128,
        "item_group": 64,
        "material": 32,
        "customer_type": 8,
        "geography_territory": 2,
    }
    score = 0
    for key, weight in weights.items():
        if _norm(rule.get(key)):
            score += weight
    return score


def _norm(val):
    if val is None:
        return ""
    return str(val).strip().lower()


def _basis_warning(benchmark_basis, source_types):
    if not source_types:
        return ""

    kinds = set(source_types.values())
    selling_like = {"selling", "competitor", "internal"}
    buying_like = {"buying", "supplier"}

    has_buying = any(k in buying_like for k in kinds)
    has_selling = any(k in selling_like for k in kinds)
    has_unknown = any(k in {"", "other", "mixed", "unknown"} for k in kinds)

    if benchmark_basis == "Selling Market":
        if has_buying or has_unknown:
            return "Benchmark Basis is 'Selling Market' but one or more sources are buying/unknown lists."
    elif benchmark_basis == "Buying Supplier":
        if has_selling or has_unknown:
            return "Benchmark Basis is 'Buying Supplier' but one or more sources are selling/unknown lists."
    elif benchmark_basis == "Any List":
        if has_buying and has_selling:
            return "Benchmark sources include both buying and selling lists; interpretation is mixed."

    return ""
