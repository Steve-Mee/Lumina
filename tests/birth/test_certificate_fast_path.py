"""Certificate failure fast-path resume integration tests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.timeout(30)

from lumina_core.birth.buffer_persist import save_buffer
from lumina_core.birth.checkpoint import save_checkpoint
from lumina_core.birth.config import BirthCurriculumConfig, BirthV2Config
from lumina_core.birth.curriculum import CurriculumStage, evaluate_stage_pass, ordered_stages
from lumina_core.birth.data_expansion import DataExpansionResult
from lumina_core.birth.fitness_vector import (
    BirthFitnessVector,
    receipt_checksum,
    write_fitness_vector,
)
from lumina_core.birth.foundation_metrics import FOUNDATION_SCHEMA, mechanical_ev_r
from lumina_core.birth.preflight import PreflightReport
from lumina_core.birth.data_pipeline import train_hash
from lumina_core.birth.engine import BirthPhaseEngineV2
from lumina_core.birth.purged_split import purged_train_holdout_split
from lumina_core.birth.stage_pass_receipt import receipt_from_stage_result
from tests.birth.honest_settlement import foundation_eval_kwargs, honest_closes
import importlib

from lumina_launcher.services.birth_service import BirthService

birth_runner_start_module = importlib.import_module("lumina_launcher.services.birth_runner_start")


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
                    datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i * 12)
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


def _foundation_receipts(cfg: BirthCurriculumConfig) -> list[dict]:
    p_ft = 0.28
    rr = 1.2
    e_mech = mechanical_ev_r(p_ft=p_ft, net_rr=rr)
    payloads = [
        (CurriculumStage.STAGE1_TREND, 160, 50),
        (CurriculumStage.STAGE2_RANGE, 260, 90),
        (CurriculumStage.STAGE3_MIXED, 400, 130),
        (CurriculumStage.STAGE4_VIABLE_PLANT, 120, 50),
        (CurriculumStage.STAGE5_PROBE_HANDOFF, 60, 25),
    ]
    receipts: list[dict] = []
    for stage, trades, wins in payloads:
        result = evaluate_stage_pass(
            stage,
            trades=trades,
            wins=wins,
            hold_signals=40,
            total_signals=max(200, trades),
            range_hold_signals=40,
            range_total_signals=200,
            range_flat_bars=90,
            range_round_trips=30,
            constitution_violations=0,
            target_trades=trades,
            cfg=cfg,
            policy_entropy=0.4,
            ppo_steps=800,
            occupancy=0.45,
            oos_sharpe=-1.0,
            oos_dd_pct=10.0,
            **honest_closes(trades),
            **foundation_eval_kwargs(
                unique_calendar_days=90,
                first_touch_hit_rate=p_ft,
                geometry_net_rr=rr,
                mean_r=float(e_mech),
            ),
        )
        assert result.passed, f"{stage.value}: {result.message}"
        receipts.append(receipt_from_stage_result(stage, result, cfg=cfg).to_dict())
    return receipts


def _write_fitness_for_s5(tmp_path: Path, receipts: list[dict]) -> None:
    from lumina_core.birth.stage_pass_receipt_types import StagePassReceipt

    s5_raw = next(r for r in receipts if r.get("stage") == "stage5_probe_handoff")
    parsed = StagePassReceipt.from_dict(s5_raw)
    assert parsed is not None
    payload = parsed.to_dict()
    write_fitness_vector(
        tmp_path,
        BirthFitnessVector(
            schema=FOUNDATION_SCHEMA,
            mean_r=float(payload.get("mean_r") or 0.0),
            edge=float(payload.get("edge") or 0.0),
            occupancy=float(payload.get("occupancy") or 0.0),
            oos_wr=0.4,
            oos_sharpe=-1.0,
            median_loss_r=float(payload.get("median_loss_r") or 1.1),
            s5_receipt_checksum=receipt_checksum(payload),
            trades=int(payload.get("trades") or 0),
        ),
    )


def _seed_certificate_failed_checkpoint(tmp_path: Path) -> None:
    cfg = BirthCurriculumConfig()
    receipts = _foundation_receipts(cfg)
    stages = [s.value for s in ordered_stages()]
    trajectories = [{"reward": 1.0, "observation": {"vector": [5000.0 + i * 0.1]}} for i in range(120)]
    buffer_path = save_buffer(tmp_path, trajectories)
    policy_path = tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_bytes(b"policy")
    ticks = _ticks(1200)
    split = purged_train_holdout_split(ticks, holdout_pct=0.2)
    manifest_train_hash = train_hash(split.train)
    save_checkpoint(
        tmp_path,
        cumulative_trades=500,
        ppo_steps=9000,
        training_mode="certified",
        stages_passed=list(stages),
        curriculum_stage="stage5_probe_handoff",
        policy_path=str(policy_path),
        stage_metrics={
            "stage_trades": 120,
            "stage_wins": 60,
            "patterns_mined": 80,
            "buffer_size": len(trajectories),
        },
        buffer_path=buffer_path,
        data_manifest={"train_hash": manifest_train_hash, "preflight_ok": True},
        phase="certificate_failed",
        remediation_attempt=1,
        stage_pass_receipts=receipts,
    )
    progress_path = tmp_path / "state" / "lumina_birth_progress.json"
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    progress_path.write_text(
        json.dumps(
            {
                "phase": "certificate_failed",
                "stage": "failed",
                "stages_passed": list(stages),
                "stage_pass_receipts": receipts,
                "failure_reasons": ["holdout_trades:12/50"],
                "oos_metrics": {
                    "certificate_passed": False,
                    "failure_reasons": ["holdout_trades:12/50"],
                },
                "data_manifest": {"train_hash": manifest_train_hash, "preflight_ok": True},
            }
        ),
        encoding="utf-8",
    )
    _write_fitness_for_s5(tmp_path, receipts)
    _ = split


@pytest.mark.unit
@pytest.mark.timeout(120)
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
        curriculum=BirthCurriculumConfig(
            max_certificate_remediation_attempts=2,
            certificate_runway_enabled=False,
            autonomous_recovery_enabled=False,
            phoenix_loop_enabled=False,
            plateau_detection_enabled=False,
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
        "lumina_core.birth.certificate_pipeline.assess_split_preflight",
        lambda *_args, **_kwargs: PreflightReport(
            ok=True,
            holdout_regimes=("TREND_UP", "TREND_DOWN", "NEUTRAL"),
            holdout_tick_count=240,
            holdout_days=5,
            train_regimes=("TREND_UP", "TREND_DOWN", "NEUTRAL"),
            estimated_holdout_trades=60,
            message="ok",
        ),
    )
    monkeypatch.setattr(
        "lumina_core.birth.certificate_pipeline.enrich_ticks_with_news",
        lambda ticks, **_kwargs: ticks,
    )
    monkeypatch.setattr(BirthPhaseEngineV2, "_run_stage_research_loop", _spy_stage_loop)
    for eval_site in (
        "lumina_core.birth.birth_phase_orchestrator.evaluate_holdout_certificate",
        "lumina_core.birth.certificate_pipeline.evaluate_holdout_certificate",
        "lumina_core.birth.certificate_evaluator.evaluate_holdout_certificate",
    ):
        monkeypatch.setattr(eval_site, _mock_eval)
    from lumina_core.birth.sim_runner import SimRolloutResult

    _mock_rollout = SimRolloutResult(
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
    _rollout_mock = lambda **_kwargs: _mock_rollout
    monkeypatch.setattr(
        "lumina_core.birth.certificate_pipeline.run_policy_rollout",
        _rollout_mock,
    )
    monkeypatch.setattr(
        "lumina_core.birth.certificate_evaluator.run_policy_rollout",
        _rollout_mock,
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

    monkeypatch.setattr(
        "lumina_core.birth.certificate_pipeline.expand_birth_data",
        _mock_preflight_expand,
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

    def _fake_start(_svc: BirthService, **kwargs: object) -> dict[str, str]:
        calls.append(dict(kwargs))
        return {"status": "started", "message": "ok"}

    monkeypatch.setattr(birth_runner_start_module, "start_birth", _fake_start)
    monkeypatch.setattr(
        "lumina_launcher.core.first_boot.FirstBootManager.clear_stale_for_certified_retry",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should not wipe")),
    )

    result = svc.retry_birth(target_trades=10000, wipe=False)

    assert result["status"] == "started"
    assert calls
    assert calls[0]["force"] is False
    assert calls[0]["continue_training"] is True
    assert calls[0]["reuse_data"] is True
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_retry_birth_reconstructs_checkpoint_from_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    policy_path = tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_bytes(b"policy")
    progress_path = tmp_path / "state" / "lumina_birth_progress.json"
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    progress_path.write_text(
        json.dumps(
            {
                "phase": "certificate_failed",
                "stages_passed": [
                    "stage1_trend",
                    "stage2_range",
                    "stage3_mixed",
                    "stage4_viable_plant",
                    "stage5_probe_handoff",
                ],
                "failure_reasons": ["oos_sharpe:0.1/0.35"],
                "cumulative_trades": 500,
                "ppo_steps": 9000,
            }
        ),
        encoding="utf-8",
    )
    calls: list[dict[str, object]] = []

    def _fake_start(_svc: BirthService, **kwargs: object) -> dict[str, str]:
        calls.append(dict(kwargs))
        return {"status": "started", "message": "ok"}

    monkeypatch.setattr(birth_runner_start_module, "start_birth", _fake_start)
    monkeypatch.setattr(
        "lumina_launcher.core.first_boot.FirstBootManager.clear_stale_for_certified_retry",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should not wipe")),
    )

    result = svc.retry_birth(target_trades=10000, wipe=False)

    assert result["status"] == "started"
    assert (tmp_path / "state" / "lumina_birth_checkpoint.json").is_file()
    assert calls[0]["force"] is False
    assert calls[0]["continue_training"] is True
    assert calls[0]["reuse_data"] is True
    BirthService._instance = None  # type: ignore[attr-defined]
