"""Certificate failure fast-path resume integration tests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.birth.buffer_persist import save_buffer
from lumina_core.birth.checkpoint import save_checkpoint
from lumina_core.birth.config import BirthCurriculumConfig, BirthV2Config
from lumina_core.birth.engine import BirthPhaseEngineV2
from lumina_core.birth.purged_split import purged_train_holdout_split
from lumina_launcher.services.birth_service import BirthService


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
                "timestamp": f"2026-01-01T{i:04d}:00Z",
                "last": price,
                "bid": price - 0.125,
                "ask": price + 0.125,
                "volume": 100,
                "source": "real_historical",
                "regime": ("TREND_UP", "TREND_DOWN", "NEUTRAL")[i % 3],
            }
        )
    return out


def _seed_certificate_failed_checkpoint(tmp_path: Path) -> None:
    trajectories = [{"reward": 1.0, "observation": {"vector": [5000.0 + i * 0.1]}} for i in range(120)]
    buffer_path = save_buffer(tmp_path, trajectories)
    policy_path = tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_bytes(b"policy")
    ticks = _ticks(1200)
    split = purged_train_holdout_split(ticks, holdout_pct=0.2)
    save_checkpoint(
        tmp_path,
        cumulative_trades=500,
        ppo_steps=9000,
        training_mode="certified",
        stages_passed=["stage1_trend", "stage2_range", "stage3_mixed"],
        curriculum_stage="stage4_polish",
        policy_path=str(policy_path),
        stage_metrics={
            "stage_trades": 120,
            "stage_wins": 60,
            "patterns_mined": 80,
            "buffer_size": len(trajectories),
        },
        buffer_path=buffer_path,
        data_manifest={"train_hash": "abc", "preflight_ok": True},
        phase="certificate_failed",
        remediation_attempt=1,
    )
    progress_path = tmp_path / "state" / "lumina_birth_progress.json"
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    progress_path.write_text(
        json.dumps(
            {
                "phase": "certificate_failed",
                "stage": "failed",
                "failure_reasons": ["holdout_trades:12/50"],
                "oos_metrics": {
                    "certificate_passed": False,
                    "failure_reasons": ["holdout_trades:12/50"],
                },
                "data_manifest": {"train_hash": "abc", "preflight_ok": True},
            }
        ),
        encoding="utf-8",
    )
    _ = split


@pytest.mark.unit
def test_certificate_failed_resume_uses_remediation_fast_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_certificate_failed_checkpoint(tmp_path)
    trainer = _FakePpoTrainer()
    engine = BirthPhaseEngineV2(
        runtime=SimpleNamespace(),
        ppo_trainer=trainer,
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    engine.birth_config = BirthV2Config(
        curriculum=BirthCurriculumConfig(max_certificate_remediation_attempts=2),
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

    monkeypatch.setattr("lumina_core.birth.engine.load_historical_ticks", lambda **_kwargs: _ticks(1200))
    monkeypatch.setattr(
        "lumina_core.birth.engine.enrich_ticks_with_news",
        lambda ticks, **_kwargs: ticks,
    )
    monkeypatch.setattr(BirthPhaseEngineV2, "_run_stage_research_loop", _spy_stage_loop)
    monkeypatch.setattr("lumina_core.birth.engine.evaluate_holdout_certificate", _mock_eval)
    monkeypatch.setattr(
        "lumina_core.birth.engine.run_policy_rollout",
        lambda **_kwargs: __import__(
            "lumina_core.birth.sim_runner", fromlist=["SimRolloutResult"]
        ).SimRolloutResult(
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
        ),
    )
    monkeypatch.setattr(
        "lumina_core.birth.engine.expand_birth_data",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected expand")),
    )

    result = engine.run_birth_phase(
        target_trades=100,
        force=False,
        prefer_real_data_only=False,
        reuse_existing_policy=True,
    )

    assert stage_loop_calls == []
    assert result.get("status") == "completed"
    progress = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert progress.get("phase") in {"certificate_issued", "certificate_remediation", "completed"}


@pytest.mark.unit
def test_retry_birth_preserves_checkpoint_and_continues_training(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    _seed_certificate_failed_checkpoint(tmp_path)
    calls: list[dict[str, object]] = []

    def _fake_start(**kwargs: object) -> dict[str, str]:
        calls.append(dict(kwargs))
        return {"status": "started", "message": "ok"}

    monkeypatch.setattr(svc, "start_birth", _fake_start)
    monkeypatch.setattr(
        "lumina_launcher.core.first_boot.FirstBootManager.clear_stale_for_certified_retry",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should not wipe")),
    )

    result = svc.retry_birth(target_trades=10000, wipe=False)

    assert result["status"] == "started"
    assert calls
    assert calls[0]["force"] is False
    assert calls[0]["continue_training"] is True
    BirthService._instance = None  # type: ignore[attr-defined]
