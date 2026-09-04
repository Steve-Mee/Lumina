"""Gate 1 P0: certified synthetic cache cannot stamp real_data_pct=100."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from lumina_core.birth.birth_certificate import BirthCertificateThresholds
from lumina_core.birth.certificate_evaluator import (
    build_certificate_failure_reasons,
    evaluate_holdout_certificate,
)
from lumina_core.birth.data_pipeline_resume import BirthDataPipelineResumeMixin
from lumina_core.birth.data_source_honesty import (
    REAL_SOURCE_ALLOWLIST,
    SYNTHETIC_SOURCE_BLOCKLIST,
    DataSourceHonestyError,
    assert_pct_matches_ticks,
    host_real_data_pct,
    real_data_percentage,
    source_is_real,
)
from lumina_core.birth.purged_split import PurgedSplit
from lumina_core.birth.tick_cache_persist import load_cache_manifest, save_birth_data_cache
from lumina_core.birth.tick_enricher import real_data_percentage as enricher_pct


class _FakeRollout:
    trades = 60
    wins = 35
    pnl_series = [5.0, 4.0, 3.0, 2.0, 6.0, 7.0, 8.0, 1.0]
    constitution_violations = 0
    regimes_seen = {"TREND_UP", "TREND_DOWN", "NEUTRAL"}
    trajectories: list[dict[str, Any]] = []


def _rollout_ok(**kwargs: Any) -> _FakeRollout:
    _ = kwargs
    return _FakeRollout()


@pytest.mark.unit
def test_synthetic_cloud_fixture_pct_is_zero() -> None:
    ticks = [{"source": "synthetic_cloud_fixture"}]
    assert real_data_percentage(ticks) == 0.0
    assert enricher_pct(ticks) == 0.0
    assert source_is_real("synthetic_cloud_fixture") is False


@pytest.mark.unit
def test_mixed_tape_is_not_100() -> None:
    ticks = [{"source": "real"}, {"source": "synthetic_cloud_fixture"}]
    pct = real_data_percentage(ticks)
    assert pct == 50.0
    assert pct != 100.0


@pytest.mark.unit
def test_allowlisted_real_is_100_only_when_all_real() -> None:
    assert real_data_percentage([{"source": "real"}]) == 100.0
    assert real_data_percentage([{"source": "REAL_NT"}]) == 100.0
    assert real_data_percentage([{"source": "real_fabric"}]) == 100.0
    assert real_data_percentage([{"source": "nt8"}]) == 100.0
    assert real_data_percentage([{"source": "ninja"}]) == 100.0
    assert real_data_percentage([{"source": "real"}, {"source": "real"}]) == 100.0
    mixed = [{"source": "real"}] * 99 + [{"source": "synthetic"}]
    assert real_data_percentage(mixed) < 100.0
    assert real_data_percentage(mixed) < 95.0 or real_data_percentage(mixed) <= 99.999


@pytest.mark.unit
def test_startswith_real_is_not_enough() -> None:
    assert source_is_real("realistic_sim") is False
    assert real_data_percentage([{"source": "realistic_sim"}]) == 0.0
    assert source_is_real("real_historical") is False
    assert real_data_percentage([{"source": "real_historical"}]) == 0.0


@pytest.mark.unit
def test_empty_source_is_not_real() -> None:
    assert source_is_real("") is False
    assert source_is_real("   ") is False
    assert real_data_percentage([{"source": ""}]) == 0.0
    assert real_data_percentage([{}]) == 0.0
    assert real_data_percentage([]) == 0.0


@pytest.mark.unit
def test_certificate_reasons_include_synthetic_source(monkeypatch: pytest.MonkeyPatch) -> None:
    reasons = build_certificate_failure_reasons(
        real_data_pct=100.0,
        winrate=0.55,
        sharpe=1.0,
        drawdown=5.0,
        regimes=["TREND_UP", "TREND_DOWN", "NEUTRAL"],
        holdout_trades=80,
        constitution_violations=0,
        thresholds=BirthCertificateThresholds(min_regimes=3, min_holdout_trades=50),
        holdout_ticks=[{"source": "synthetic_cloud_fixture", "last": 5000.0}],
    )
    assert any(r.startswith("synthetic_source:") for r in reasons)
    assert any("synthetic_cloud_fixture" in r for r in reasons)
    monkeypatch.setattr(
        "lumina_core.birth.certificate_evaluator.run_policy_rollout",
        _rollout_ok,
    )
    result = evaluate_holdout_certificate(
        runtime=MagicMock(),
        holdout_data=[{"last": 5000.0, "source": "synthetic_cloud_fixture"}],
        policy=None,
        real_data_pct=100.0,
        holdout_days=10,
        constitution_violations=0,
        workspace_root=".",
        thresholds=BirthCertificateThresholds(min_holdout_trades=50, min_regimes=3),
    )
    assert result["certificate_passed"] is False
    assert float(result["real_data_pct"]) == 0.0
    assert any(str(r).startswith("synthetic_source:") for r in result["failure_reasons"])
    assert any("real_data_pct:" in str(r) for r in result["failure_reasons"])


@pytest.mark.unit
def test_resume_manifest_cannot_override_ticks_to_100(tmp_path: Path) -> None:
    ticks = [{"source": "synthetic_cloud_fixture", "last": 1.0}]
    assert host_real_data_pct(ticks, manifest_pct=100.0) == 0.0
    with pytest.raises(DataSourceHonestyError):
        assert_pct_matches_ticks(100.0, ticks)
    host = MagicMock()
    host._data_manifest = {"real_data_pct": 100.0}
    mixin = BirthDataPipelineResumeMixin()
    mixin._host = host
    pct = host_real_data_pct(
        ticks,
        manifest_pct=float(host._data_manifest["real_data_pct"]),
    )
    host._real_data_pct = pct
    host._data_manifest["real_data_pct"] = pct
    assert host._real_data_pct == 0.0
    assert host._data_manifest["real_data_pct"] == 0.0


@pytest.mark.unit
def test_prefer_real_data_only_does_not_imply_pct_100() -> None:
    ticks = [{"source": "synthetic_cloud_fixture"}]
    assert (
        host_real_data_pct(
            ticks,
            prefer_real_data_only=True,
            certified_cache=True,
        )
        == 0.0
    )


@pytest.mark.unit
def test_save_birth_data_cache_persists_synthetic_pct_zero(tmp_path: Path) -> None:
    ticks = [
        {
            "timestamp": "2026-01-01T00:00:00Z",
            "last": 5000.0,
            "regime": "NEUTRAL",
            "source": "synthetic_cloud_fixture",
        },
        {
            "timestamp": "2026-01-02T00:00:00Z",
            "last": 5001.0,
            "regime": "TREND_UP",
            "source": "synthetic_cloud_fixture",
        },
    ]
    split = PurgedSplit(train=[ticks[0]], holdout=[ticks[1]], holdout_days=1, train_days=1)
    save_birth_data_cache(
        tmp_path,
        ticks=ticks,
        split=split,
        holdout_pct=0.2,
        raw_ticks_hash="raw",
        train_hash="train",
    )
    manifest = load_cache_manifest(tmp_path)
    assert manifest is not None
    assert float(manifest["real_data_pct"]) == 0.0
    assert manifest["source"] == "synthetic_cloud_fixture"


@pytest.mark.unit
def test_allowlist_and_blocklist_are_explicit() -> None:
    assert REAL_SOURCE_ALLOWLIST == frozenset(
        {"real", "real_nt", "real_fabric", "nt8", "ninja"}
    )
    assert "synthetic_cloud_fixture" in SYNTHETIC_SOURCE_BLOCKLIST
    src = Path("lumina_core/birth/data_source_honesty.py").read_text(encoding="utf-8")
    assert "REAL_SOURCE_ALLOWLIST" in src
    assert "SYNTHETIC_SOURCE_BLOCKLIST" in src
    assert "def source_is_real" in src
    enricher = Path("lumina_core/birth/tick_enricher.py").read_text(encoding="utf-8")
    assert 'startswith("real")' not in enricher
    assert "startswith('real')" not in enricher


@pytest.mark.unit
def test_history_loader_preserves_synthetic_source() -> None:
    from lumina_core.birth.history_loader import normalize_tick_rows

    rows = normalize_tick_rows(
        [{"timestamp": "2026-01-01T00:00:00Z", "last": 5000.0, "source": "synthetic_cloud_fixture"}],
        source_label="real",
    )
    assert rows[0]["source"] == "synthetic_cloud_fixture"
    assert real_data_percentage(rows) == 0.0
    unlabeled = normalize_tick_rows(
        [{"timestamp": "2026-01-01T00:00:00Z", "last": 5000.0}],
        source_label="real",
    )
    assert unlabeled[0]["source"] == "real"
    assert real_data_percentage(unlabeled) == 100.0


@pytest.mark.unit
def test_min_real_data_pct_threshold_stays_95() -> None:
    assert BirthCertificateThresholds().min_real_data_pct == 95.0
    reasons = build_certificate_failure_reasons(
        real_data_pct=0.0,
        winrate=0.99,
        sharpe=5.0,
        drawdown=1.0,
        regimes=["TREND_UP", "TREND_DOWN", "NEUTRAL"],
        holdout_trades=80,
        constitution_violations=0,
        thresholds=BirthCertificateThresholds(),
        holdout_ticks=[{"source": "synthetic_cloud_fixture"}],
    )
    assert any(r.startswith("real_data_pct:0.00/95.00") for r in reasons)
