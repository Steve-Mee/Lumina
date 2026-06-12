"""Evolution metrics loaders — Streamlit render removed; use Command Deck / API."""

from __future__ import annotations

from lumina_core.evolution.evolution_metrics_loaders import (
    GENERATED_BIBLE_PATH,
    METRICS_PATH,
    ROLLOUT_HISTORY_PATH,
    SHADOW_STATE_PATH,
    load_evolution_metrics,
    load_generated_strategies,
    load_rollout_history,
    load_shadow_runs,
)

_load_metrics = load_evolution_metrics
_load_shadow_runs = load_shadow_runs
_load_generated_strategies = load_generated_strategies
_load_rollout_history = load_rollout_history

__all__ = [
    "GENERATED_BIBLE_PATH",
    "METRICS_PATH",
    "ROLLOUT_HISTORY_PATH",
    "SHADOW_STATE_PATH",
    "load_evolution_metrics",
    "load_generated_strategies",
    "load_rollout_history",
    "load_shadow_runs",
    "_load_metrics",
    "_load_rollout_history",
]
