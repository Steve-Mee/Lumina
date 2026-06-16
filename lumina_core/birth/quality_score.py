"""Compute reusable birth research quality score for operator decisions."""

from __future__ import annotations

from typing import Any


def compute_quality_score(
    *,
    real_data_pct: float,
    patterns_mined: int,
    stages_passed: list[str],
    buffer_size: int,
    constitution_violations: int,
    holdout_regime_count: int = 0,
) -> float:
    score = 0.0
    score += min(0.25, float(real_data_pct) / 400.0)
    score += min(0.25, len(stages_passed) * 0.08)
    score += min(0.20, patterns_mined / 5000.0)
    score += min(0.15, buffer_size / 5000.0)
    score += min(0.15, holdout_regime_count / 3.0)
    if constitution_violations > 0:
        score *= max(0.2, 1.0 - constitution_violations * 0.1)
    return round(max(0.0, min(1.0, score)), 4)


def quality_score_from_manifest(manifest: dict[str, Any] | None, stage_metrics: dict[str, Any] | None) -> float:
    manifest = manifest or {}
    metrics = stage_metrics or {}
    regimes = manifest.get("holdout_regimes") or []
    return compute_quality_score(
        real_data_pct=float(manifest.get("real_data_pct", 0.0) or 0.0),
        patterns_mined=int(metrics.get("patterns_mined", 0) or 0),
        stages_passed=list(metrics.get("stages_passed") or []),
        buffer_size=int(metrics.get("buffer_size", 0) or 0),
        constitution_violations=int(metrics.get("constitution_violations", 0) or 0),
        holdout_regime_count=len(regimes) if isinstance(regimes, list) else 0,
    )
