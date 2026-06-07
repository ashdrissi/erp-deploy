"""Performance metric registry.

Importing this package triggers registration of every builtin metric
into the REGISTRY dict, keyed by `metric_code`.
"""

from __future__ import annotations

from orderlift.orderlift_hr.metrics.base import (
    REGISTRY,
    MetricResult,
    normalise_score,
    register,
)

# Side-effect imports populate REGISTRY.
from orderlift.orderlift_hr.metrics import (  # noqa: F401
    sales,
    crm,
    operations,
    attendance,
    training_bridge,
    doc_query,
)

__all__ = ["REGISTRY", "MetricResult", "normalise_score", "register"]
