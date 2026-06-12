"""Deprecated Meta-RL environment — removed in Birth v2 closeout (PR-H).

Use ``lumina_core.rl.RLTradingEnvironment`` (32-dim SSOT, ADR-0015).
"""

from __future__ import annotations

_DEPRECATION = (
    "MetaRLTradingEnvironmentLegacy was removed. "
    "Use lumina_core.rl.RLTradingEnvironment (32-dim SSOT, ADR-0015)."
)


def __getattr__(name: str) -> object:
    if name in {"MetaRLTradingEnvironmentLegacy", "RLTradingEnvironment"}:
        raise ImportError(_DEPRECATION)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
