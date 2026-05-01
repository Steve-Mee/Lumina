"""Compatibility shim — imports forwarded to lumina_core.risk.dynamic_kelly.

The canonical implementation lives in the ``risk`` bounded context.
"""
from lumina_core.risk.dynamic_kelly import (  # noqa: F401
    DynamicKellyEstimator,
    get_global_kelly_estimator,
    _MIN_WINDOW_TRADES,
    _DEFAULT_HISTORY_PATH,
)

__all__ = [
    "DynamicKellyEstimator",
    "get_global_kelly_estimator",
    "_MIN_WINDOW_TRADES",
    "_DEFAULT_HISTORY_PATH",
]
