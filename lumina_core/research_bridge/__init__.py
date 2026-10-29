"""KEEP ResearchBridge: Event Bus adapter from research candidates to SHADOW intents."""

from __future__ import annotations

from lumina_core.research_bridge.horizon import HorizonRefused, require_expected_horizon_bars
from lumina_core.research_bridge.install import attach_shadow_runtime
from lumina_core.research_bridge.market_health import MarketHealth, healthy_closed_bar, unhealthy_market
from lumina_core.research_bridge.shadow_runtime import ShadowRuntime

__all__ = [
    "HorizonRefused",
    "MarketHealth",
    "ShadowRuntime",
    "attach_shadow_runtime",
    "healthy_closed_bar",
    "require_expected_horizon_bars",
    "unhealthy_market",
]
