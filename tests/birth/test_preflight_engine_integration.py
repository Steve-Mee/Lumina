"""Engine integration tests with real holdout preflight (no conftest bypass)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.birth.birth_certificate import BirthCertificateThresholds
from lumina_core.birth.config import BirthCurriculumConfig, BirthV2Config
from lumina_core.birth.data_expansion import DataExpansionResult
from lumina_core.birth.engine import BirthPhaseEngineV2
from lumina_core.birth.pattern_miner import PatternMineResult
from lumina_core.birth.preflight import assess_split_preflight
from lumina_core.birth.purged_split import purged_train_holdout_split
from lumina_core.birth.sim_runner import SimRolloutResult
from lumina_core.lumina_birth_engine import LuminaBirthEngine

pytestmark = [pytest.mark.no_preflight_bypass, pytest.mark.timeout(120)]


class _FakePpoTrainer:
    def __init__(self) -> None:
        self._active_policy: dict[str, str] = {"policy": "fresh"}

    def create_fresh_birth_policy(self, *, allow_load_existing: bool = True):
        _ = allow_load_existing
        return self._active_policy

    def update_from_buffer(self, **kwargs):
        _ = kwargs
        return {"policy": "updated"}

    def final_birth_polish(self, _buffer) -> None:
        return None

    def save_final_birth_policy(self, path: str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"policy")


def _calendar_ticks(*, days: int = 300, ticks_per_day: int = 10, holdout_neutral_only: bool = False) -> list[dict]:
    """Day-bucketed ticks so purged holdout uses calendar days, not tick index."""
    ticks: list[dict] = []
    price = 5000.0
    holdout_start_day = int(days * 0.8)
    start = datetime(2026, 1, 1)
    for day in range(days):
        in_holdout_window = day >= holdout_start_day
        day_dt = start + timedelta(days=day)
        day_prefix = day_dt.date().isoformat()
        for tick_idx in range(ticks_per_day):
            price += 0.25
            if holdout_neutral_only and in_holdout_window:
                regime = "NEUTRAL"
            else:
                regime = ("TREND_UP", "TREND_DOWN", "NEUTRAL")[tick_idx % 3]
            ticks.append(
                {
                    "timestamp": f"{day_prefix}T{tick_idx:02d}:00:00Z",
                    "last": price,
                    "bid": price - 0.125,
                    "ask": price + 0.125,
                    "volume": 100,
                    "source": "real_historical",
                    "regime": regime,
                }
            )
    return ticks


def _three_regime_calendar_ticks(*, days: int = 300, ticks_per_day: int = 10) -> list[dict]:
    return _calendar_ticks(days=days, ticks_per_day=ticks_per_day, holdout_neutral_only=False)


@pytest.mark.unit
def test_single_regime_holdout_slice_fails_preflight() -> None:
    ticks = _calendar_ticks(days=300, ticks_per_day=10, holdout_neutral_only=True)
    split = purged_train_holdout_split(ticks, holdout_pct=0.2)
    report = assess_split_preflight(
        split,
        thresholds=BirthCertificateThresholds(min_holdout_trades=5, min_regimes=3),
    )
    assert report.ok is False
    assert any("holdout_regimes" in reason for reason in report.failure_reasons)


@pytest.mark.unit
def test_ensure_holdout_preflight_expands_until_regimes_ok(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expansion_calls: list[int] = []

    def _expand(**_kwargs) -> DataExpansionResult:
        expansion_calls.append(1)
        ticks = _three_regime_calendar_ticks(days=300, ticks_per_day=10)
        split = purged_train_holdout_split(ticks, holdout_pct=0.2)
        return DataExpansionResult(
            train_ticks=list(split.train),
            holdout_ticks=list(split.holdout),
            all_ticks=ticks,
            split=split,
            days_back=180,
            step_index=len(expansion_calls),
            real_data_pct=99.0,
            exhausted=False,
        )

    engine = BirthPhaseEngineV2(
        runtime=SimpleNamespace(),
        ppo_trainer=SimpleNamespace(),
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    engine.birth_config = BirthV2Config(
        curriculum=BirthCurriculumConfig(data_expansion_steps=(90, 180)),
        certificate_thresholds=BirthCertificateThresholds(min_holdout_trades=5, min_regimes=3),
    )
    engine.birth_start_time = 1.0
    ticks = _calendar_ticks(days=300, ticks_per_day=10, holdout_neutral_only=True)
    split = purged_train_holdout_split(ticks, holdout_pct=0.2)
    monkeypatch.setattr("lumina_core.birth.certificate_pipeline.expand_birth_data", _expand)

    result = engine._ensure_holdout_preflight(
        ticks=ticks,
        split=split,
        max_days=90,
        prefer_real=False,
        start_price=5000.0,
        training_mode="certified",
    )

    assert expansion_calls, "expected preflight expansion when holdout has one regime"
    assert isinstance(result, tuple)
    _, _, manifest = result
    assert manifest.get("preflight_ok") is True


@pytest.mark.unit
@pytest.mark.slow
def test_engine_expands_history_when_holdout_preflight_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expansion_calls: list[int] = []

    def _expand(**_kwargs) -> DataExpansionResult:
        expansion_calls.append(1)
        ticks = _three_regime_calendar_ticks(days=300, ticks_per_day=10)
        split = purged_train_holdout_split(ticks, holdout_pct=0.2)
        return DataExpansionResult(
            train_ticks=list(split.train),
            holdout_ticks=list(split.holdout),
            all_ticks=ticks,
            split=split,
            days_back=90,
            step_index=len(expansion_calls),
            real_data_pct=99.0,
            exhausted=False,
        )

    trainer = _FakePpoTrainer()
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=trainer,
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    engine.birth_config = BirthV2Config(
        curriculum=BirthCurriculumConfig(
            stage1_trend_trades=5,
            stage2_range_trades=5,
            stage3_mixed_trades=5,
            rollout_chunk_trades=5,
            max_rollouts_per_stage=2,
            data_expansion_steps=(90, 180),
        ),
        trade_budget_cap=200,
        certificate_thresholds=BirthCertificateThresholds(min_holdout_trades=5, min_regimes=3),
    )

    monkeypatch.setattr(
        "lumina_core.birth.data_pipeline.enrich_ticks_for_sim",
        lambda ticks, **_kwargs: ticks,
    )

    monkeypatch.setattr(
        "lumina_core.birth.data_pipeline.load_historical_ticks",
        lambda **_kwargs: _calendar_ticks(days=300, ticks_per_day=10, holdout_neutral_only=True),
    )
    monkeypatch.setattr(
        "lumina_core.birth.news_enricher.enrich_ticks_with_news",
        lambda ticks, **_kwargs: ticks,
    )
    monkeypatch.setattr("lumina_core.birth.certificate_pipeline.expand_birth_data", _expand)
    monkeypatch.setattr(
        "lumina_core.birth.stage_training_loop.mine_winning_patterns",
        lambda **_kwargs: PatternMineResult(
            patterns=[{"reward": 1.0, "observation": {"vector": [5000.0]}} for _ in range(120)],
            wins=120,
            scanned=150,
            regimes_seen={"TREND_UP", "TREND_DOWN", "NEUTRAL"},
        ),
    )
    monkeypatch.setattr(
        "lumina_core.birth.stage_training_loop.run_policy_rollout",
        lambda **_kwargs: SimRolloutResult(
            trades=2,
            wins=1,
            hold_signals=0,
            total_signals=2,
            total_pnl=1.0,
            trajectories=[{"reward": 1.0, "observation": {"vector": [5000.0]}}],
            pnl_series=[1.0],
            constitution_violations=0,
            regimes_seen={"TREND_UP"},
            partial_complete=True,
            rollout_steps=100,
        ),
    )
    monkeypatch.setattr(
        "lumina_core.birth.certificate_pipeline.evaluate_holdout_certificate",
        lambda **_kwargs: {"certificate_passed": False, "failure_reasons": ["oos_sharpe:0/0.35"]},
    )

    engine.run_birth_phase(target_trades=100, force=True, prefer_real_data_only=False)

    assert expansion_calls, "expected holdout preflight to trigger data expansion"
    progress_path = tmp_path / "state" / "lumina_birth_progress.json"
    payload = json.loads(progress_path.read_text(encoding="utf-8"))
    assert payload.get("phase") not in {"holdout_preflight_failed", "loading_history_failed"}


@pytest.mark.unit
def test_engine_fail_closed_when_preflight_expansion_exhausted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trainer = _FakePpoTrainer()
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=trainer,
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    engine.birth_config = BirthV2Config(
        curriculum=BirthCurriculumConfig(data_expansion_steps=(90,)),
        trade_budget_cap=200,
    )
    bad_ticks = _calendar_ticks(days=30, ticks_per_day=5, holdout_neutral_only=True)

    monkeypatch.setattr(
        "lumina_core.birth.data_pipeline.load_historical_ticks",
        lambda **_kwargs: bad_ticks,
    )
    monkeypatch.setattr(
        "lumina_core.birth.news_enricher.enrich_ticks_with_news",
        lambda ticks, **_kwargs: ticks,
    )
    monkeypatch.setattr(
        "lumina_core.birth.certificate_pipeline.expand_birth_data",
        lambda **_kwargs: DataExpansionResult(
            train_ticks=[],
            holdout_ticks=[],
            all_ticks=bad_ticks,
            split=purged_train_holdout_split(bad_ticks, holdout_pct=0.2),
            days_back=90,
            step_index=1,
            real_data_pct=99.0,
            exhausted=True,
        ),
    )

    result = engine.run_birth_phase(target_trades=100, force=True, prefer_real_data_only=True)

    assert result["status"] == "history_unavailable"
    progress_path = tmp_path / "state" / "lumina_birth_progress.json"
    payload = json.loads(progress_path.read_text(encoding="utf-8"))
    assert payload.get("phase") == "holdout_preflight_failed"


@pytest.mark.unit
def test_reuse_data_manifest_skips_tick_load_and_expansion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticks = _three_regime_calendar_ticks(days=300, ticks_per_day=10)
    split = purged_train_holdout_split(ticks, holdout_pct=0.2)

    from lumina_core.birth.tick_cache_persist import save_split_cache, save_ticks_cache

    save_ticks_cache(tmp_path, ticks)
    save_split_cache(tmp_path, split=split, holdout_pct=0.2)

    load_calls: list[int] = []
    expand_calls: list[int] = []

    def _load_historical_ticks(**_kwargs) -> list[dict]:
        load_calls.append(1)
        return _calendar_ticks(days=300, ticks_per_day=10, holdout_neutral_only=True)

    def _expand(**_kwargs) -> DataExpansionResult:
        expand_calls.append(1)
        raise AssertionError("expand_birth_data should not run on manifest reuse")

    trainer = _FakePpoTrainer()
    v2_engine = BirthPhaseEngineV2(
        runtime=SimpleNamespace(),
        ppo_trainer=trainer,
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    train_hash = v2_engine._train_hash(split.train)
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=trainer,
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    engine.birth_config = BirthV2Config(
        curriculum=BirthCurriculumConfig(
            rollout_chunk_trades=5,
            max_rollouts_per_stage=1,
            data_expansion_steps=(90, 180),
        ),
        trade_budget_cap=200,
        holdout_pct=0.2,
        certificate_thresholds=BirthCertificateThresholds(min_holdout_trades=5, min_regimes=3),
    )

    data_manifest = {
        "train_hash": train_hash,
        "preflight_ok": True,
        "real_data_pct": 99.0,
        "holdout_regimes": ["NEUTRAL", "TREND_DOWN", "TREND_UP"],
    }

    from lumina_core.birth.checkpoint import save_checkpoint

    save_checkpoint(
        tmp_path,
        cumulative_trades=50,
        ppo_steps=100,
        training_mode="certified",
        stages_passed=["stage1_trend", "stage2_range", "stage3_mixed"],
        curriculum_stage="stage4_polish",
        data_manifest=data_manifest,
        phase="certificate_failed",
    )

    monkeypatch.setattr("lumina_core.birth.data_pipeline.load_historical_ticks", _load_historical_ticks)
    monkeypatch.setattr("lumina_core.birth.certificate_pipeline.expand_birth_data", _expand)
    monkeypatch.setattr(
        "lumina_core.birth.news_enricher.enrich_ticks_with_news",
        lambda loaded_ticks, **_kwargs: loaded_ticks,
    )
    monkeypatch.setattr(
        "lumina_core.birth.stage_training_loop.mine_winning_patterns",
        lambda **_kwargs: PatternMineResult(
            patterns=[{"reward": 1.0, "observation": {"vector": [5000.0]}} for _ in range(120)],
            wins=120,
            scanned=150,
            regimes_seen={"TREND_UP", "TREND_DOWN", "NEUTRAL"},
        ),
    )
    monkeypatch.setattr(
        "lumina_core.birth.stage_training_loop.run_policy_rollout",
        lambda **_kwargs: SimRolloutResult(
            trades=5,
            wins=2,
            hold_signals=40,
            total_signals=100,
            total_pnl=1.0,
            trajectories=[{"reward": 1.0, "observation": {"vector": [5000.0]}} for _ in range(10)],
            pnl_series=[1.0],
            constitution_violations=0,
            regimes_seen={"NEUTRAL"},
            partial_complete=True,
            rollout_steps=100,
        ),
    )
    monkeypatch.setattr(
        "lumina_core.birth.certificate_pipeline.evaluate_holdout_certificate",
        lambda **_kwargs: {
            "certificate_passed": False,
            "failure_reasons": ["sharpe:0.0/0.5"],
            "sharpe": 0.0,
            "winrate": 0.5,
            "total_trades": 10,
            "max_drawdown_pct": 1.0,
            "real_data_pct": 99.0,
        },
    )

    result = engine.run_birth_phase(
        target_trades=100,
        force=False,
        prefer_real_data_only=True,
        reuse_data_manifest=True,
    )

    assert load_calls == [], "cached ticks should skip load_historical_ticks"
    assert expand_calls == [], "manifest reuse should skip preflight expansion"
    assert result["status"] in {"certificate_failed", "completed", "history_unavailable"}


@pytest.mark.unit
def test_resume_checkpoint_skips_tick_load_without_reuse_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auto cache reuse on checkpoint resume must not require reuse_data_manifest=True."""
    ticks = _three_regime_calendar_ticks(days=300, ticks_per_day=10)
    split = purged_train_holdout_split(ticks, holdout_pct=0.2)

    from lumina_core.birth.tick_cache_persist import save_split_cache, save_ticks_cache

    save_ticks_cache(tmp_path, ticks)
    save_split_cache(tmp_path, split=split, holdout_pct=0.2)

    load_calls: list[int] = []
    expand_calls: list[int] = []
    progress_writes: list[dict] = []

    def _load_historical_ticks(**_kwargs) -> list[dict]:
        load_calls.append(1)
        return _calendar_ticks(days=300, ticks_per_day=10, holdout_neutral_only=True)

    def _expand(**_kwargs) -> DataExpansionResult:
        expand_calls.append(1)
        raise AssertionError("expand_birth_data should not run on resume cache hit")

    def _capture_progress(_root, **kwargs) -> None:
        progress_writes.append(dict(kwargs))

    trainer = _FakePpoTrainer()
    v2_engine = BirthPhaseEngineV2(
        runtime=SimpleNamespace(),
        ppo_trainer=trainer,
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    train_hash = v2_engine._train_hash(split.train)
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=trainer,
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    engine.birth_config = BirthV2Config(
        curriculum=BirthCurriculumConfig(
            rollout_chunk_trades=5,
            max_rollouts_per_stage=1,
            data_expansion_steps=(90, 180),
        ),
        trade_budget_cap=200,
        holdout_pct=0.2,
        certificate_thresholds=BirthCertificateThresholds(min_holdout_trades=5, min_regimes=3),
    )

    data_manifest = {
        "train_hash": train_hash,
        "preflight_ok": True,
        "real_data_pct": 99.0,
        "holdout_regimes": ["NEUTRAL", "TREND_DOWN", "TREND_UP"],
    }

    from lumina_core.birth.checkpoint import save_checkpoint

    policy_path = tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_bytes(b"policy")

    save_checkpoint(
        tmp_path,
        cumulative_trades=140,
        ppo_steps=1500,
        training_mode="certified",
        stages_passed=[],
        curriculum_stage="stage1_trend",
        data_manifest=data_manifest,
        phase="curriculum_learning",
        policy_path=str(policy_path),
    )

    monkeypatch.setattr("lumina_core.birth.data_pipeline.load_historical_ticks", _load_historical_ticks)
    monkeypatch.setattr("lumina_core.birth.certificate_pipeline.expand_birth_data", _expand)
    monkeypatch.setattr("lumina_core.birth.birth_phase_orchestrator.write_birth_progress", _capture_progress)
    monkeypatch.setattr(
        "lumina_core.birth.news_enricher.enrich_ticks_with_news",
        lambda loaded_ticks, **_kwargs: loaded_ticks,
    )
    monkeypatch.setattr(
        "lumina_core.birth.stage_training_loop.mine_winning_patterns",
        lambda **_kwargs: PatternMineResult(
            patterns=[{"reward": 1.0, "observation": {"vector": [5000.0]}} for _ in range(120)],
            wins=120,
            scanned=150,
            regimes_seen={"TREND_UP", "TREND_DOWN", "NEUTRAL"},
        ),
    )
    monkeypatch.setattr(
        "lumina_core.birth.engine.BirthPhaseEngineV2._run_stage_research_loop",
        lambda self, **_kwargs: {
            "status": "completed",
            "total_trades": self.cumulative_trades,
            "ppo_steps": self.ppo_steps,
        },
    )
    monkeypatch.setattr(
        "lumina_core.birth.certificate_pipeline.evaluate_holdout_certificate",
        lambda **_kwargs: {
            "certificate_passed": True,
            "regimes_covered": ["TREND_UP", "TREND_DOWN", "NEUTRAL"],
            "oos_sharpe": 0.6,
            "oos_winrate": 0.55,
            "holdout_trades": 60,
            "real_data_pct": 99.0,
        },
    )

    result = engine.run_birth_phase(
        target_trades=100,
        force=False,
        prefer_real_data_only=True,
        reuse_data_manifest=False,
    )

    assert load_calls == [], "resume cache hit should skip load_historical_ticks"
    assert expand_calls == [], "resume cache hit should skip preflight expansion"
    assert progress_writes, "engine should write progress on resume"
    first_write = progress_writes[0]
    assert first_write.get("ppo_steps") == 1500
    assert first_write.get("cumulative_trades") == 140
    assert first_write.get("needs_attention") is False
    assert result["status"] in {"completed", "certificate_failed", "history_unavailable"}

