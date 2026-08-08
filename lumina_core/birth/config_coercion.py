"""Birth v2 config coercion + section builders.

Wave E split: helpers / budget / curriculum / sections façades.
"""
from __future__ import annotations

from lumina_core.birth.config_coercion_budget import (
    resolve_effective_trade_budget,
    resolve_trade_budget_cap,
)
from lumina_core.birth.config_coercion_curriculum import build_curriculum_config
from lumina_core.birth.config_coercion_helpers import (
    _coerce_float,
    _coerce_int,
    _coerce_wall_behavior,
    _parse_expansion_steps,
)
from lumina_core.birth.config_coercion_sections import (
    build_certificate_thresholds,
    build_news_config,
    build_reward_config,
)

__all__ = [
    "build_certificate_thresholds",
    "build_curriculum_config",
    "build_news_config",
    "build_reward_config",
    "resolve_effective_trade_budget",
    "resolve_trade_budget_cap",
    "_coerce_float",
    "_coerce_int",
    "_coerce_wall_behavior",
    "_parse_expansion_steps",
]
