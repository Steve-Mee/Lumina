"""Isolated physics-tape slope wrapper. PHYSICS_SLOPE_ABS==0.004. Production default 0.15."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from lumina_core.birth.tick_enricher import enrich_ticks_for_sim
from lumina_core.rl.trend_features import ENRICH_VERSION, regime_from_strength

# identity 0.12*(8e-6/2.4e-4) — detector scaled with drift; not a hunt of 0.003 / 0.005
PHYSICS_SLOPE_ABS = 0.004  # PHYSICS_SLOPE_ABS==0.004
PROD_SLOPE_ABS = 0.15  # prod default 0.15 — imported as default, not rewritten


class ScaleProtocolError(RuntimeError):
    """AWAKENING_SLOPE_SCALE protocol crime (fail-closed)."""


def classify_prod_regime(strength: float) -> str:
    """Production call: regime_from_strength default threshold 0.15."""
    return regime_from_strength(float(strength))


def classify_scale_regime(strength: float) -> str:
    """Wrapper call: isolated PHYSICS_SLOPE_ABS==0.004."""
    return regime_from_strength(float(strength), threshold=PHYSICS_SLOPE_ABS)


def stamp_two_ticks(
    ticks: list[dict[str, Any]],
    *,
    slope_abs: float | None = None,
) -> list[dict[str, Any]]:
    """Two-tick unit probe. None → production 0.15; wrapper pins 0.004."""
    threshold = PROD_SLOPE_ABS if slope_abs is None else float(slope_abs)
    for tick in ticks:
        strength = float(tick.get("trend_regime_strength", 0.0) or 0.0)
        tick["regime"] = regime_from_strength(strength, threshold=threshold)
    return ticks


def enrich_ticks_for_scale(
    ticks: list[dict[str, Any]],
    *,
    on_progress: Callable[[int, int], None] | None = None,
    workspace_root: Path | str | None = None,
    raw_ticks_hash: str | None = None,
    enrich_version: str = ENRICH_VERSION,
) -> list[dict[str, Any]]:
    """THIS tape only. Calls production enrich_ticks_for_sim with slope_abs=0.004."""
    return enrich_ticks_for_sim(
        ticks,
        on_progress=on_progress,
        workspace_root=workspace_root,
        raw_ticks_hash=raw_ticks_hash,
        enrich_version=enrich_version,
        slope_abs=PHYSICS_SLOPE_ABS,
    )


assert abs(float(regime_from_strength.__kwdefaults__["threshold"]) - PROD_SLOPE_ABS) < 1e-12
assert PHYSICS_SLOPE_ABS == 0.004 and PROD_SLOPE_ABS == 0.15
assert abs(PHYSICS_SLOPE_ABS - 0.12 * (8.0e-6 / 2.4e-4)) < 1e-15

__all__ = [
    "PHYSICS_SLOPE_ABS",
    "PROD_SLOPE_ABS",
    "ScaleProtocolError",
    "classify_prod_regime",
    "classify_scale_regime",
    "enrich_ticks_for_scale",
    "stamp_two_ticks",
]
