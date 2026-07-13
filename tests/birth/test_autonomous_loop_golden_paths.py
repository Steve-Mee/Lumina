"""Golden-path tests for autonomous birth recovery loops (engine + EventBus)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.birth.birth_bus_choreography import (
    TOPIC_ADAPTATION_APPLIED,
    TOPIC_AUTONOMY_DECISION,
    TOPIC_META_PLAN,
    TOPIC_REMEDIATION_CYCLE,
    latest_for_correlation,
    publish_snapshot,
)
from lumina_core.birth.birth_bus_client import BirthBusClient
from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig, BirthV2Config
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.engine import BirthPhaseEngineV2
from lumina_core.birth.organism_autonomy import RecoveryDispatch
from lumina_core.birth.sim_runner import SimRolloutResult


class _FakePpoTrainer:
    def update_from_buffer(self, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace()


def _trend_ticks(n: int) -> list[dict]:
    return [{"price": 5000.0 + i * 0.1, "regime": "TREND_UP"} for i in range(n)]


def _stall_rollout(**_kwargs: object) -> SimRolloutResult:
    return SimRolloutResult(
        trades=15,
        wins=2,
        hold_signals=92,
        total_signals=100,
        total_pnl=0.2,
        trajectories=[{"reward": 0.2, "observation": {"vector": [5000.0]}} for _ in range(20)],
        pnl_series=[0.2],
        constitution_violations=0,
        regimes_seen={"TREND_UP"},
        partial_complete=True,
        rollout_steps=200,
    )


def _engine_adaptive_cfg(**overrides: object) -> BirthV2Config:
    base = dict(
        stage1_trend_trades=100,
        rollout_chunk_trades=20,
        stage1_winrate_stagnation_rollouts=2,
        certified_stage_stall_wall_sec=300,
        certified_max_rollouts_per_stage=500,
        allow_provisional_pass=False,
        checkpoint_interval_sec=3600,
        wall_behavior="adaptive",
        max_stage_retries=3,
        max_adaptation_tiers=4,
        exploration_chunk_size=8,
        auto_expand_on_adaptation=False,
        autonomous_recovery_enabled=True,
        meta_controller_enabled=False,
        adaptation_enabled=True,
    )
    base.update(overrides)
    return BirthV2Config(
        curriculum=BirthCurriculumConfig(**base),
        trade_budget_cap=5000,
    )


@pytest.mark.meta_controller
@pytest.mark.unit
def test_golden_adaptive_stall_to_continue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = BirthPhaseEngineV2(
        runtime=SimpleNamespace(),
        ppo_trainer=_FakePpoTrainer(),
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    engine.birth_config = _engine_adaptive_cfg()
    for i in range(300):
        engine.buffer.add({"reward": 1.0, "observation": {"vector": [5000.0 + i * 0.01]}})

    tick = {"value": 1_000_000.0}
    rollout_calls = {"n": 0}

    def _fake_time() -> float:
        tick["value"] += 400.0
        return tick["value"]

    def _rollout(**kwargs: object) -> SimRolloutResult:
        rollout_calls["n"] += 1
        return _stall_rollout(**kwargs)

    monkeypatch.setattr("lumina_core.birth.stage_training_loop.time.time", _fake_time)
    monkeypatch.setattr("lumina_core.birth.stage_training_loop.run_policy_rollout", _rollout)
    monkeypatch.setattr(engine, "_stop_requested", lambda: rollout_calls["n"] >= 20)
    monkeypatch.setattr(
        "lumina_core.birth.stage_training_loop.mine_winning_patterns",
        lambda **_kwargs: __import__(
            "lumina_core.birth.pattern_miner", fromlist=["PatternMineResult"]
        ).PatternMineResult(patterns=[], wins=0, scanned=0, regimes_seen=set()),
    )
    monkeypatch.setattr(
        "lumina_core.birth.stage_training_loop.expand_birth_data",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no expand")),
    )

    result = engine._run_stage_research_loop(
        stage=CurriculumStage.STAGE1_TREND,
        stage_index=0,
        stage_ticks=_trend_ticks(600),
        train_ticks=_trend_ticks(600),
        holdout_ticks=_trend_ticks(120),
        target=100,
        stage_progress_pct=25.0,
        training_mode="certified",
        ppo_steps_per_update=1000,
        polish_ppo_timesteps=1000,
        trade_budget_cap=500,
        prefer_real=True,
        start_price=5000.0,
    )

    assert result is not None
    assert result.get("status") != "stage_stalled"


@pytest.mark.unit
def test_golden_remediation_cycle_to_continue(birth_bus_client: BirthBusClient) -> None:
    client = birth_bus_client
    cfg = BirthCurriculumConfig(stall_remediation_enabled=True)
    client.cfg = cfg
    client.registry.sync_curriculum_cfg(cfg)

    stage = CurriculumStage.STAGE1_TREND
    if client.remediation_can_start(stage):
        client.remediation_begin_cycle(
            stage,
            winrate_at_start=0.35,
            max_cycles=3,
            cycle=1,
        )
    assert client.bus.latest(TOPIC_REMEDIATION_CYCLE) is not None


@pytest.mark.unit
def test_golden_plateau_meta_bus_choreography(birth_bus_client: BirthBusClient) -> None:
    client = birth_bus_client
    stage = CurriculumStage.STAGE2_RANGE
    snap, _ = client.meta_observe(
        stage,
        winrate_history=[0.25, 0.24, 0.23],
        reward_history=[0.05, 0.04],
        stage_trades=300,
        required_trades=500,
        patterns_mined=0,
        buffer_size=64,
        escalation_level=0,
        strong_recovery_mode=False,
        strong_recovery_attempts=0,
        low_velocity_attempts=2,
        data_exhausted=False,
        range_flat_ratio=0.18,
        range_round_trips=25,
    )
    plan = client.meta_decide(stage, snap, trigger="periodic")
    assert plan is not None
    latest = client.bus.latest(TOPIC_META_PLAN)
    assert latest is not None


@pytest.mark.unit
def test_golden_phoenix_never_stop(birth_bus_client: BirthBusClient) -> None:
    cfg = BirthCurriculumConfig(
        autonomous_recovery_enabled=True,
        phoenix_loop_enabled=True,
        phoenix_max_cycles=12,
    )
    client = BirthBusClient(
        EventBus(),
        cfg,
        BirthRewardConfig(),
    )
    decision = client.autonomy_evaluate_terminal_stall(
        CurriculumStage.STAGE1_TREND,
        pending={"terminal_stall_reason": "stall_remediation_exhausted"},
        stage_trades=500,
        required=600,
        constitution_violations=0,
        fitness_signal=0.38,
        remediation_cycles_exhausted=True,
        plateau_exhausted=True,
    )
    assert decision.dispatch == RecoveryDispatch.PHOENIX_RESUME
    assert client.bus.latest(TOPIC_AUTONOMY_DECISION) is not None


@pytest.mark.unit
def test_golden_bus_multi_handler_correlation() -> None:
    bus = EventBus()
    cfg = BirthCurriculumConfig(
        meta_controller_enabled=True,
        adaptation_enabled=True,
        wall_behavior="adaptive",
        autonomous_recovery_enabled=True,
    )
    client = BirthBusClient(bus, cfg, BirthRewardConfig())
    cid = "golden-cid-001"

    publish_snapshot(
        bus,
        producer="test",
        correlation_id=cid,
        signal="meta_observe",
        stage="stage1_trend",
        context={
            "winrate_history": [0.3, 0.29],
            "reward_history": [0.1, 0.09],
            "stage_trades": 120,
            "required_trades": 500,
            "patterns_mined": 0,
            "buffer_size": 64,
            "escalation_level": 0,
            "strong_recovery_mode": False,
            "strong_recovery_attempts": 0,
            "low_velocity_attempts": 0,
            "data_exhausted": False,
            "stage": "stage1_trend",
        },
    )
    client.registry.pop_response(cid)

    snap, _ = client.meta_observe(
        CurriculumStage.STAGE1_TREND,
        winrate_history=[0.3, 0.29],
        reward_history=[0.1, 0.09],
        stage_trades=120,
        required_trades=500,
        patterns_mined=0,
        buffer_size=64,
        escalation_level=0,
        strong_recovery_mode=False,
        strong_recovery_attempts=0,
        low_velocity_attempts=0,
        data_exhausted=False,
    )
    client.meta_decide(CurriculumStage.STAGE1_TREND, snap, trigger="periodic")

    result = client.adaptation_try_recovery(
        CurriculumStage.STAGE1_TREND,
        failure_key="stall",
        trigger_type="stall",
        stage_trades=120,
        required=500,
        current_winrate=0.29,
        winrate_history=[0.3, 0.29],
        original_rollout_chunk=250,
        rollout_chunk_trades=20,
        trade_budget_remaining=1000,
        terminal_blocked=False,
        constitution_blocked=False,
    )
    if result.get("applied"):
        assert latest_for_correlation(bus, TOPIC_ADAPTATION_APPLIED, cid) is not None or bus.latest(
            TOPIC_ADAPTATION_APPLIED
        )

    client.autonomy_evaluate_terminal_stall(
        CurriculumStage.STAGE1_TREND,
        pending={"terminal_stall_reason": "stage_stalled"},
        stage_trades=120,
        required=500,
        constitution_violations=0,
        fitness_signal=0.30,
        recommended_recovery_action="expand_data",
    )

    assert bus.latest(TOPIC_META_PLAN) is not None
    assert bus.latest(TOPIC_AUTONOMY_DECISION) is not None
