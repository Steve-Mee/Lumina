"""ShadowDeploymentTracker — persistent shadow run management for Lumina v53.

Wave F: shadow_helpers + shadow_tracker_core + shadow_tracker_verdict.
"""
from __future__ import annotations

from lumina_core.evolution.shadow_helpers import (
    ShadowRun,
    ShadowStatus,
    ShadowVerdict,
    _cohens_d,
    _days_elapsed,
    _regularized_inc_beta,
    _sample_sharpe,
    _utcnow,
    _welch_t_pvalue,
)
from lumina_core.evolution.shadow_tracker_core import ShadowDeploymentTrackerCore
from lumina_core.evolution.shadow_tracker_verdict import ShadowTrackerVerdictMixin

__all__ = [
    "ShadowDeploymentTracker",
    "ShadowRun",
    "ShadowStatus",
    "ShadowVerdict",
    "_cohens_d",
    "_welch_t_pvalue",
    "_sample_sharpe",
    "_regularized_inc_beta",
    "_utcnow",
    "_days_elapsed",
]


class ShadowDeploymentTracker(ShadowTrackerVerdictMixin, ShadowDeploymentTrackerCore):
    """Full tracker: core lifecycle + verdict/A-B."""
