"""Regime detector façade (M5)."""
from __future__ import annotations

from lumina_core.risk.regime_calendar import RegimeCalendarMixin
from lumina_core.risk.regime_detect import RegimeDetectMixin
from lumina_core.risk.regime_policy import RegimePolicyMixin
from lumina_core.risk.regime_types import AdaptiveRegimePolicy, RegimeSnapshot

__all__ = ["AdaptiveRegimePolicy", "RegimeDetector", "RegimeSnapshot"]


class RegimeDetector(RegimeDetectMixin, RegimePolicyMixin, RegimeCalendarMixin):
    """Canonical regime detector for Lumina v50.

    Produces one normalized regime label plus the adaptive policy that other
    services use directly.
    """


