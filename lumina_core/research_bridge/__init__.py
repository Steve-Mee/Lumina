"""KEEP ResearchBridge: Event Bus adapter from research candidates to SHADOW intents.

Exports are lazy so ``ungated_place_block`` can import ``sim_gate`` during
``lumina_core`` bootstrap without pulling EventBus through this package.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lumina_core.research_bridge.binding_policy import (
        BindingPolicyRefused,
        independent,
        reduce_fraction_for_stage,
        sla_decision,
    )
    from lumina_core.research_bridge.fill_index import FillIndex, FillIndexRefused
    from lumina_core.research_bridge.fill_translator import FillTranslator, TranslateRefused
    from lumina_core.research_bridge.horizon import HorizonRefused, require_expected_horizon_bars
    from lumina_core.research_bridge.install import attach_shadow_runtime, attach_sim_runtime
    from lumina_core.research_bridge.market_health import MarketHealth, healthy_closed_bar, unhealthy_market
    from lumina_core.research_bridge.shadow_runtime import ShadowRuntime
    from lumina_core.research_bridge.sim_gate import (
        RESEARCH_SIM_GATED,
        SIM_INSTRUMENT_NOT_YET_RELEASED,
        SimGateContext,
        SimGateRefused,
        SurvivorRecord,
        evaluate as evaluate_sim_gate,
    )
    from lumina_core.research_bridge.sim_runtime import SimRuntime

__all__ = [
    "BindingPolicyRefused",
    "FillIndex",
    "FillIndexRefused",
    "FillTranslator",
    "HorizonRefused",
    "MarketHealth",
    "RESEARCH_SIM_GATED",
    "SIM_INSTRUMENT_NOT_YET_RELEASED",
    "ShadowRuntime",
    "SimGateContext",
    "SimGateRefused",
    "SimRuntime",
    "SurvivorRecord",
    "TranslateRefused",
    "attach_shadow_runtime",
    "attach_sim_runtime",
    "evaluate_sim_gate",
    "healthy_closed_bar",
    "independent",
    "reduce_fraction_for_stage",
    "require_expected_horizon_bars",
    "sla_decision",
    "unhealthy_market",
]

_LAZY: dict[str, tuple[str, str]] = {
    "BindingPolicyRefused": ("lumina_core.research_bridge.binding_policy", "BindingPolicyRefused"),
    "FillIndex": ("lumina_core.research_bridge.fill_index", "FillIndex"),
    "FillIndexRefused": ("lumina_core.research_bridge.fill_index", "FillIndexRefused"),
    "FillTranslator": ("lumina_core.research_bridge.fill_translator", "FillTranslator"),
    "HorizonRefused": ("lumina_core.research_bridge.horizon", "HorizonRefused"),
    "MarketHealth": ("lumina_core.research_bridge.market_health", "MarketHealth"),
    "RESEARCH_SIM_GATED": ("lumina_core.research_bridge.sim_gate", "RESEARCH_SIM_GATED"),
    "SIM_INSTRUMENT_NOT_YET_RELEASED": (
        "lumina_core.research_bridge.sim_gate",
        "SIM_INSTRUMENT_NOT_YET_RELEASED",
    ),
    "ShadowRuntime": ("lumina_core.research_bridge.shadow_runtime", "ShadowRuntime"),
    "SimGateContext": ("lumina_core.research_bridge.sim_gate", "SimGateContext"),
    "SimGateRefused": ("lumina_core.research_bridge.sim_gate", "SimGateRefused"),
    "SimRuntime": ("lumina_core.research_bridge.sim_runtime", "SimRuntime"),
    "SurvivorRecord": ("lumina_core.research_bridge.sim_gate", "SurvivorRecord"),
    "TranslateRefused": ("lumina_core.research_bridge.fill_translator", "TranslateRefused"),
    "attach_shadow_runtime": ("lumina_core.research_bridge.install", "attach_shadow_runtime"),
    "attach_sim_runtime": ("lumina_core.research_bridge.install", "attach_sim_runtime"),
    "evaluate_sim_gate": ("lumina_core.research_bridge.sim_gate", "evaluate"),
    "healthy_closed_bar": ("lumina_core.research_bridge.market_health", "healthy_closed_bar"),
    "independent": ("lumina_core.research_bridge.binding_policy", "independent"),
    "reduce_fraction_for_stage": ("lumina_core.research_bridge.binding_policy", "reduce_fraction_for_stage"),
    "require_expected_horizon_bars": ("lumina_core.research_bridge.horizon", "require_expected_horizon_bars"),
    "sla_decision": ("lumina_core.research_bridge.binding_policy", "sla_decision"),
    "unhealthy_market": ("lumina_core.research_bridge.market_health", "unhealthy_market"),
}


def __getattr__(name: str) -> Any:
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = target
    value = getattr(import_module(module_name), attr)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
