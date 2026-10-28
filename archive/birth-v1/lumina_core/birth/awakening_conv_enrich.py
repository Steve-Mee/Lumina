"""G1 isolated slope-abs wrapper. PHYSICS_SLOPE_ABS = 0.12. Production default still 0.15."""

from __future__ import annotations

from typing import Any, Callable

from pathlib import Path

from lumina_core.birth.tick_enricher import enrich_ticks_for_sim
from lumina_core.rl.trend_features import ENRICH_VERSION, regime_from_strength

PHYSICS_SLOPE_ABS = 0.12
PROD_SLOPE_ABS = 0.15  # production default still 0.15 — imported as default, not rewritten
# no second knob — slope threshold only


class ConvProtocolError(RuntimeError):
    """AWAKENING_ENRICHER_CONVERSION protocol crime (fail-closed)."""


def classify_prod_regime(strength: float) -> str:
    """Production call: regime_from_strength default threshold 0.15."""
    return regime_from_strength(float(strength))


def classify_conv_regime(strength: float) -> str:
    """Wrapper call: isolated PHYSICS_SLOPE_ABS = 0.12."""
    return regime_from_strength(float(strength), threshold=PHYSICS_SLOPE_ABS)


def stamp_two_ticks(
    ticks: list[dict[str, Any]],
    *,
    slope_abs: float | None = None,
) -> list[dict[str, Any]]:
    """Two-tick unit probe. None → production 0.15; wrapper pins 0.12."""
    threshold = PROD_SLOPE_ABS if slope_abs is None else float(slope_abs)
    for tick in ticks:
        strength = float(tick.get("trend_regime_strength", 0.0) or 0.0)
        tick["regime"] = regime_from_strength(strength, threshold=threshold)
    return ticks


def enrich_ticks_for_conv(
    ticks: list[dict[str, Any]],
    *,
    on_progress: Callable[[int, int], None] | None = None,
    workspace_root: Path | str | None = None,
    raw_ticks_hash: str | None = None,
    enrich_version: str = ENRICH_VERSION,
) -> list[dict[str, Any]]:
    """THIS tape only. Calls production enrich_ticks_for_sim with slope_abs=0.12."""
    return enrich_ticks_for_sim(
        ticks,
        on_progress=on_progress,
        workspace_root=workspace_root,
        raw_ticks_hash=raw_ticks_hash,
        enrich_version=enrich_version,
        slope_abs=PHYSICS_SLOPE_ABS,
    )


assert abs(float(regime_from_strength.__kwdefaults__["threshold"]) - PROD_SLOPE_ABS) < 1e-12
assert PHYSICS_SLOPE_ABS == 0.12 and PROD_SLOPE_ABS == 0.15

__all__ = [
    "PHYSICS_SLOPE_ABS",
    "PROD_SLOPE_ABS",
    "ConvProtocolError",
    "classify_conv_regime",
    "classify_prod_regime",
    "enrich_ticks_for_conv",
    "stamp_two_ticks",
]
