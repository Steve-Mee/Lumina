"""Engine E2E: cert-fail retry uses remediation fast path without stage1 reset."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.birth.config import BirthCurriculumConfig, BirthV2Config
from lumina_core.birth.data_expansion import DataExpansionResult
from lumina_core.birth.engine import BirthPhaseEngineV2
from lumina_core.birth.purged_split import purged_train_holdout_split
from lumina_core.birth.sim_runner import SimRolloutResult


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


def _ticks(n: int = 1200) -> list[dict]:
    out: list[dict] = []
    price = 5000.0
    for i in range(n):
        price += 0.5
        out.append(
            {
                "timestamp": (
                    datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i * 8)
                ).isoformat(),
                "last": price,
                "bid": price - 0.125,
                "ask": price + 0.125,
                "volume": 100,
                "source": "real_historical",
                "regime": ("TREND_UP", "TREND_DOWN", "NEUTRAL")[i % 3],
            }
        )
    return out


def _seed_progress_only_cert_fail(tmp_path: Path) -> None:
    policy_path = tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_bytes(b"policy")
    progress_path = tmp_path / "state" / "lumina_birth_progress.json"
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    progress_path.write_text(
        json.dumps(
            {
                "phase": "certificate_failed",
                "stage": "failed",
                "stages_passed": ["stage1_trend", "stage2_range", "stage3_mixed"],
                "failure_reasons": ["holdout_trades:12/50"],
                "oos_metrics": {
                    "certificate_passed": False,
                    "failure_reasons": ["holdout_trades:12/50"],
                },
                "cumulative_trades": 500,
                "ppo_steps": 9000,
                "data_manifest": {"train_hash": "abc", "preflight_ok": True},
            }
        ),
        encoding="utf-8",
    )


def _mock_preflight_expand(**_kwargs) -> DataExpansionResult:
    ticks = _ticks(1200)
    split = purged_train_holdout_split(ticks, holdout_pct=0.2)
    return DataExpansionResult(
        train_ticks=list(split.train),
        holdout_ticks=list(split.holdout),
        all_ticks=ticks,
        split=split,
        days_back=90,
        step_index=0,
        real_data_pct=99.0,
        exhausted=True,
    )


def _mock_rollout(**_kwargs) -> SimRolloutResult:
    return SimRolloutResult(
        trades=10,
        wins=5,
        hold_signals=0,
        total_signals=10,
        total_pnl=5.0,
        trajectories=[
            {"reward": 1.0, "observation": {"vector": [5000.0 + i * 0.1]}} for i in range(100)
        ],
        pnl_series=[1.0] * 10,
        constitution_violations=0,
        regimes_seen={"TREND_UP", "TREND_DOWN", "NEUTRAL"},
        partial_complete=True,
        rollout_steps=200,
    )


@pytest.mark.unit
def test_engine_resume_progress_only_skips_curriculum(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_progress_only_cert_fail(tmp_path)
    trainer = _FakePpoTrainer()
    engine = BirthPhaseEngineV2(
        runtime=SimpleNamespace(),
        ppo_trainer=trainer,
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    engine.birth_config = BirthV2Config(
        curriculum=BirthCurriculumConfig(
            max_certificate_remediation_attempts=2,
            certificate_runway_enabled=False,
        ),
        trade_budget_cap=500,
    )

    stage_loop_calls: list[str] = []

    def _spy_stage_loop(self, *, stage, **_kwargs):  # noqa: ANN001
        stage_loop_calls.append(str(stage))
        return None

    eval_calls = {"n": 0}

    def _mock_eval(**_kwargs) -> dict:
        eval_calls["n"] += 1
        if eval_calls["n"] == 1:
            return {
                "certificate_passed": False,
                "failure_reasons": ["holdout_trades:12/50"],
            }
        return {
            "certificate_passed": True,
            "regimes_covered": ["TREND_UP", "TREND_DOWN", "NEUTRAL"],
            "oos_sharpe": 0.42,
            "oos_winrate": 0.52,
            "holdout_trades": 60,
        }

    monkeypatch.setattr("lumina_core.birth.data_pipeline.load_historical_ticks", lambda **_kwargs: _ticks(1200))
    monkeypatch.setattr(
        "lumina_core.birth.certificate_pipeline.enrich_ticks_with_news",
        lambda ticks, **_kwargs: ticks,
    )
    monkeypatch.setattr(BirthPhaseEngineV2, "_run_stage_research_loop", _spy_stage_loop)
    monkeypatch.setattr("lumina_core.birth.certificate_pipeline.evaluate_holdout_certificate", _mock_eval)
    monkeypatch.setattr(
        "lumina_core.birth.certificate_pipeline.run_policy_rollout",
        _mock_rollout,
    )
    monkeypatch.setattr(
        "lumina_core.birth.certificate_pipeline.expand_birth_data",
        _mock_preflight_expand,
    )
    reconstruct_calls: list[bool] = []

    def _spy_reconstruct(*args, **kwargs):  # noqa: ANN002, ANN003
        from lumina_core.birth import remediation

        ok = remediation.reconstruct_checkpoint_from_progress(*args, **kwargs)
        reconstruct_calls.append(ok)
        return ok

    monkeypatch.setattr(
        "lumina_core.birth.birth_phase_orchestrator.reconstruct_checkpoint_from_progress",
        _spy_reconstruct,
    )

    result = engine.run_birth_phase(
        target_trades=100,
        force=False,
        prefer_real_data_only=False,
        reuse_existing_policy=True,
    )

    assert result.get("status") != "completed"