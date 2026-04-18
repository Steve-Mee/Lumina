from __future__ import annotations

"""Backward-compatible facade for HardRiskController.

This module intentionally stays thin and delegates to the archived implementation
in `risk_controller_legacy.py` while preserving the public import surface.
"""

from .risk_controller_legacy import (
    HardRiskController,
    MarginTracker,
    RiskLimits,
    RiskState,
    _utcnow,
    risk_limits_from_config,
)

__all__ = [
    "_utcnow",
    "MarginTracker",
    "RiskLimits",
    "RiskState",
    "HardRiskController",
    "risk_limits_from_config",
]