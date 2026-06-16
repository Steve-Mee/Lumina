"""Test helpers for birth holdout preflight bypass in engine integration tests."""

from __future__ import annotations

from typing import Any

import pytest

from lumina_core.birth.preflight import PreflightReport


def patch_holdout_preflight_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    def _ok_preflight(split: Any, **_kwargs: Any) -> PreflightReport:
        regimes = tuple(sorted({str(t.get("regime", "NEUTRAL")) for t in split.holdout}) or ["NEUTRAL"])
        if len(regimes) < 3:
            regimes = ("TREND_UP", "TREND_DOWN", "NEUTRAL")
        return PreflightReport(
            ok=True,
            holdout_regimes=regimes,
            holdout_tick_count=max(500, len(split.holdout)),
            holdout_days=int(split.holdout_days),
            train_regimes=regimes,
            estimated_holdout_trades=max(100, len(split.holdout) // 80),
            message="Holdout preflight OK",
        )

    monkeypatch.setattr("lumina_core.birth.engine.assess_split_preflight", _ok_preflight)
