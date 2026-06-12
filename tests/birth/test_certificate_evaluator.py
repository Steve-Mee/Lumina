from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

import pytest

from lumina_core.birth.birth_certificate import BirthCertificateThresholds
from lumina_core.birth.certificate_evaluator import evaluate_holdout_certificate


@dataclass
class _FakeRollout:
    trades: int = 100
    wins: int = 55
    pnl_series: list[float] = field(default_factory=lambda: [10.0, -5.0, 8.0, 12.0, -3.0, 6.0])
    constitution_violations: int = 0
    regimes_seen: set[str] = field(default_factory=lambda: {"NEUTRAL"})


@pytest.fixture
def patch_rollout(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_rollout(**kwargs: Any) -> _FakeRollout:
        return _FakeRollout()

    monkeypatch.setattr(
        "lumina_core.birth.certificate_evaluator.run_policy_rollout",
        lambda **kwargs: _FakeRollout(),
    )


@pytest.mark.unit
def test_certificate_evaluator_uses_honest_regimes_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lumina_core.birth.certificate_evaluator.run_policy_rollout",
        lambda **kwargs: _FakeRollout(regimes_seen={"TREND_UP"}),
    )
    result = evaluate_holdout_certificate(
        runtime=MagicMock(),
        holdout_data=[{"last": 5000.0}],
        policy=None,
        real_data_pct=98.0,
        holdout_days=10,
        constitution_violations=0,
        workspace_root=".",
        thresholds=BirthCertificateThresholds(min_regimes=3),
    )
    assert result["regimes_covered"] == ["TREND_UP"]
    assert result["certificate_passed"] is False


@pytest.mark.unit
def test_certificate_evaluator_passes_when_regimes_met(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lumina_core.birth.certificate_evaluator.run_policy_rollout",
        lambda **kwargs: _FakeRollout(
            regimes_seen={"TREND_UP", "TREND_DOWN", "NEUTRAL"},
            trades=60,
            wins=35,
            pnl_series=[5.0, 4.0, 3.0, 2.0, 6.0, 7.0, 8.0, 1.0],
        ),
    )
    result = evaluate_holdout_certificate(
        runtime=MagicMock(),
        holdout_data=[{"last": 5000.0}],
        policy=None,
        real_data_pct=98.0,
        holdout_days=10,
        constitution_violations=0,
        workspace_root=".",
        thresholds=BirthCertificateThresholds(min_holdout_trades=50),
    )
    assert set(result["regimes_covered"]) == {"TREND_UP", "TREND_DOWN", "NEUTRAL"}
    assert result["certificate_passed"] is True


@pytest.mark.unit
def test_certificate_evaluator_fails_min_holdout_trades(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lumina_core.birth.certificate_evaluator.run_policy_rollout",
        lambda **kwargs: _FakeRollout(
            trades=10,
            regimes_seen={"TREND_UP", "TREND_DOWN", "NEUTRAL"},
        ),
    )
    result = evaluate_holdout_certificate(
        runtime=MagicMock(),
        holdout_data=[{"last": 5000.0}],
        policy=None,
        real_data_pct=98.0,
        holdout_days=10,
        constitution_violations=0,
        workspace_root=".",
        thresholds=BirthCertificateThresholds(min_holdout_trades=50),
    )
    assert result["certificate_passed"] is False
