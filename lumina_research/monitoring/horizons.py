"""Combine short-horizon (incl. material breaks) and medium-horizon decay assessments."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Sequence

from lumina_research.monitoring.acceptance import MEDIUM_WINDOW
from lumina_research.monitoring.config import ContinuityConfig
from lumina_research.monitoring.material import assess_material
from lumina_research.monitoring.statistics import assess_decay
from lumina_research.monitoring.types import (
    DecayAssessment,
    DecayHorizon,
    Instrument,
    VolRegime,
    stage_rank,
    tighter_stage,
)
from lumina_research.monitoring.vol_regime import classify_vol_regime


@dataclass(frozen=True, slots=True)
class CombinedDecay:
    assessment: DecayAssessment
    vol_regime: VolRegime
    horizon: DecayHorizon


def combined_assessment(
    series: Sequence[float],
    oos: Sequence[float],
    config: ContinuityConfig,
    *,
    vix: float | None = None,
    instrument: Instrument | str | None = None,
) -> CombinedDecay:
    """Short window + material breaks + medium window. Stage only tightens. CONFIRM is elsewhere."""
    regime = classify_vol_regime(series, vix=vix, instrument=instrument)
    short = assess_decay(series, oos, config)
    material = assess_material(series, oos, config, vol_regime=regime)
    medium = _medium(series, oos, config)
    stage = tighter_stage(short.stage, material.stage)
    stage = tighter_stage(stage, medium.stage)
    horizon: DecayHorizon = "short"
    if stage_rank(medium.stage) >= stage_rank(stage) and stage_rank(medium.stage) > stage_rank(short.stage):
        if stage_rank(medium.stage) > stage_rank(material.stage):
            horizon = "medium"
    chosen = short
    if stage_rank(material.stage) > stage_rank(chosen.stage):
        chosen = material
    if stage_rank(medium.stage) > stage_rank(chosen.stage):
        chosen = medium
        horizon = "medium"
    assessment = replace(chosen, stage=stage, vol_regime=regime, horizon=horizon)
    return CombinedDecay(assessment=assessment, vol_regime=regime, horizon=horizon)


def _medium(series: Sequence[float], oos: Sequence[float], config: ContinuityConfig) -> DecayAssessment:
    if len(series) < MEDIUM_WINDOW:
        return DecayAssessment(
            method=config.method,
            severity=0,
            stage="active",
            statistic=0.0,
            threshold=0.0,
            live_mean=None,
            oos_mean=None,
            oos_stdev=None,
            percentile=None,
            cusum=None,
            sprt_llr=None,
            window=MEDIUM_WINDOW,
            votes_deweight=0,
            votes_suspend=0,
            votes_retire=0,
            ready=False,
            horizon="medium",
        )
    medium_cfg = replace(config, window=MEDIUM_WINDOW, min_observations=MEDIUM_WINDOW)
    assessed = assess_decay(series, oos, medium_cfg)
    return replace(assessed, horizon="medium")
