"""Starship Birth Phase A — EdgeScore, entropy life-support, swarm-first, pause SSOT."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage, evaluate_stage_pass
from lumina_core.birth.policy_swarm import (
    PolicySwarmState,
    PolicySwarmVariant,
    PolicySwarmVariantResult,
    select_swarm_winner,
)
from lumina_core.birth.plateau_escalator import (
    PlateauState,
    begin_evolution_step,
    evolution_ladder_exhausted,
)
from lumina_core.birth.starship_birth import (
    build_pause_ssot_payload,
    compute_expectancy_proxy,
    edgescore_champion_min_trades,
    edgescore_from_swarm_result,
    effective_plateau_max_evolution_steps,
    evaluate_stage1_edgescore,
    evaluate_stage2_edgescore,
    evaluate_stage3_edgescore,
    is_edgescore_champion_eligible,
    policy_entropy_alive,
    sanitize_edgescore_champion,
    should_block_phoenix_until_swarm,
    should_force_exploration_burst,
    should_force_swarm_retearnament,
    should_hard_stop_training_after_swarm_reject,
    should_skip_plateau_ladder_theater,
    should_start_swarm_before_recovery,
    swarm_edgescore_lift,
    swarm_tournament_done,
    swarm_tournament_lift,
    tournament_lift_required_delta,
    tournament_score,
    write_pause_ssot,
)


@pytest.mark.unit
def test_edgescore_passes_without_vanity_winrate() -> None:
    cfg = BirthCurriculumConfig(
        stage1_edgescore_enabled=True,
        stage1_winrate_pass_floor=0.35,
        stage1_entropy_floor=0.05,
        stage1_hold_ratio_min=0.05,
        stage1_hold_ratio_max=0.85,
        stage1_expectancy_floor=-0.15,
    )
    # 40% WR — below 45% vanity gate, above 35% hygiene.
    edge = evaluate_stage1_edgescore(
        trades=250,
        wins=100,
        hold_signals=400,
        total_signals=1000,
        constitution_violations=0,
        required=200,
        cfg=cfg,
        entropy=0.20,
    )
    assert edge.passed is True
    result = evaluate_stage_pass(
        CurriculumStage.STAGE1_TREND,
        trades=250,
        wins=100,
        hold_signals=400,
        total_signals=1000,
        constitution_violations=0,
        target_trades=2000,
        cfg=cfg,
        policy_entropy=0.20,
    )
    assert result.passed is True
    assert "edgescore" in result.message


@pytest.mark.unit
def test_edgescore_fails_dead_entropy() -> None:
    cfg = BirthCurriculumConfig(stage1_edgescore_enabled=True, stage1_entropy_floor=0.05)
    edge = evaluate_stage1_edgescore(
        trades=250,
        wins=120,
        hold_signals=400,
        total_signals=1000,
        constitution_violations=0,
        required=200,
        cfg=cfg,
        entropy=0.0,
    )
    assert edge.passed is False
    assert edge.entropy_ok is False


@pytest.mark.unit
def test_edgescore_fails_constitution() -> None:
    cfg = BirthCurriculumConfig(stage1_edgescore_enabled=True)
    edge = evaluate_stage1_edgescore(
        trades=250,
        wins=120,
        hold_signals=400,
        total_signals=1000,
        constitution_violations=1,
        required=200,
        cfg=cfg,
        entropy=0.3,
    )
    assert edge.passed is False
    assert edge.constitution_ok is False


@pytest.mark.unit
def test_legacy_winrate_gate_when_edgescore_disabled() -> None:
    cfg = BirthCurriculumConfig(
        stage1_edgescore_enabled=False,
        stage1_winrate_pass_threshold=0.45,
        stage1_use_rolling_pass=False,
    )
    result = evaluate_stage_pass(
        CurriculumStage.STAGE1_TREND,
        trades=250,
        wins=100,  # 40%
        hold_signals=400,
        total_signals=1000,
        constitution_violations=0,
        target_trades=2000,
        cfg=cfg,
    )
    assert result.passed is False


@pytest.mark.unit
def test_entropy_life_support_triggers_on_dead_policy() -> None:
    cfg = BirthCurriculumConfig(
        starship_entropy_life_support_enabled=True,
        stage1_entropy_floor=0.05,
        stage1_hold_ratio_max=0.85,
    )
    assert policy_entropy_alive(0.0, cfg=cfg) is False
    assert should_force_exploration_burst(entropy=0.0, hold_ratio=0.4, cfg=cfg) is True
    assert should_force_exploration_burst(entropy=0.2, hold_ratio=0.95, cfg=cfg) is True
    assert should_force_exploration_burst(entropy=0.2, hold_ratio=0.4, cfg=cfg) is False


@pytest.mark.unit
def test_swarm_first_gates() -> None:
    cfg = BirthCurriculumConfig(
        starship_swarm_first_enabled=True,
        policy_swarm_enabled=True,
    )
    empty = PolicySwarmState()
    assert should_start_swarm_before_recovery(
        cfg=cfg, swarm_state=empty, allow_provisional=False
    )
    assert should_block_phoenix_until_swarm(
        cfg=cfg, swarm_state=empty, allow_provisional=False
    )
    done = PolicySwarmState(committed_variant_id="swarm_expectancy")
    assert not should_start_swarm_before_recovery(
        cfg=cfg, swarm_state=done, allow_provisional=False
    )
    assert not should_block_phoenix_until_swarm(
        cfg=cfg, swarm_state=done, allow_provisional=False
    )
    rejected = PolicySwarmState(rejected_no_lift=True)
    assert not should_start_swarm_before_recovery(
        cfg=cfg, swarm_state=rejected, allow_provisional=False
    )
    # Rejected no-lift blocks phoenix (attention path).
    assert should_block_phoenix_until_swarm(
        cfg=cfg, swarm_state=rejected, allow_provisional=False
    )


@pytest.mark.unit
def test_swarm_lift_gate_predicate() -> None:
    assert swarm_edgescore_lift(before_score=0.40, after_score=0.42, meaningful_delta=0.01)
    assert not swarm_edgescore_lift(before_score=0.40, after_score=0.405, meaningful_delta=0.01)


@pytest.mark.unit
def test_force_swarm_retearnament_once() -> None:
    cfg = BirthCurriculumConfig(starship_swarm_first_enabled=True, policy_swarm_enabled=True)
    done = PolicySwarmState(committed_variant_id="swarm_expectancy")
    assert should_force_swarm_retearnament(
        cfg=cfg,
        swarm_state=done,
        allow_provisional=False,
        hard_stop_armed=True,
        no_lift_brake=False,
        retearnament_used=False,
    )
    assert not should_force_swarm_retearnament(
        cfg=cfg,
        swarm_state=done,
        allow_provisional=False,
        hard_stop_armed=True,
        no_lift_brake=False,
        retearnament_used=True,
    )


@pytest.mark.unit
def test_edgescore_from_swarm_result_ranks_expectancy() -> None:
    cfg = BirthCurriculumConfig(stage1_edgescore_enabled=True)
    weak = edgescore_from_swarm_result(trades=100, wins=40, total_pnl=-20.0, cfg=cfg)
    strong = edgescore_from_swarm_result(trades=100, wins=45, total_pnl=40.0, cfg=cfg)
    assert strong > weak


@pytest.mark.unit
def test_tournament_score_apples_to_apples() -> None:
    """Baseline and variant must share the same scoring contract."""
    baseline = tournament_score(trades=200, wins=80, total_pnl=-10.0)
    variant = edgescore_from_swarm_result(
        trades=200, wins=80, total_pnl=-10.0, cfg=BirthCurriculumConfig()
    )
    assert baseline == variant
    assert tournament_score(trades=0, wins=0, total_pnl=0.0) == -1.0
    assert tournament_score(trades=100, wins=50, total_pnl=50.0) > baseline


@pytest.mark.unit
def test_swarm_reject_flag_roundtrips_metrics() -> None:
    from lumina_core.birth.config import BirthRewardConfig

    state = PolicySwarmState(
        rejected_no_lift=True,
        committed_variant_id="",
        active=True,
        champion_probe_active=True,
        champion_probe_trades=40,
        champion_probe_wins=16,
        champion_probe_pnl=2.0,
        variants=[
            PolicySwarmVariant(
                "swarm_expectancy",
                "Expectancy",
                BirthRewardConfig(),
                explore_multiplier=2.0,
                policy_path="/tmp/a.zip",
            )
        ],
    )
    restored = PolicySwarmState.from_metrics(state.to_metrics())
    assert restored.rejected_no_lift is True
    assert not restored.committed_variant_id
    assert restored.active is True
    assert restored.champion_probe_active is True
    assert len(restored.variants) == 1
    assert restored.variants[0].variant_id == "swarm_expectancy"
    assert restored.champion_probe_trades == 40


@pytest.mark.unit
def test_expectancy_proxy_ignores_usd_pnl_for_edgescore_scale() -> None:
    # EdgeScore floor (-0.15) is wr-0.50 scale; USD/trade must not change the gate metric.
    wr_proxy = compute_expectancy_proxy(wins=40, trades=100, total_pnl=None)
    with_usd = compute_expectancy_proxy(wins=40, trades=100, total_pnl=-135_800.0)
    assert wr_proxy == pytest.approx(-0.10)
    assert with_usd == pytest.approx(-0.10)


@pytest.mark.unit
def test_entropy_missing_fails_after_ppo_threshold() -> None:
    cfg = BirthCurriculumConfig(
        stage1_edgescore_enabled=True,
        starship_entropy_required_after_ppo_steps=500,
        stage1_entropy_floor=0.05,
    )
    cold = evaluate_stage1_edgescore(
        trades=250,
        wins=100,
        hold_signals=400,
        total_signals=1000,
        constitution_violations=0,
        required=200,
        cfg=cfg,
        entropy=None,
        total_pnl=10.0,
        ppo_steps=0,
    )
    assert cold.entropy_ok is True
    warm = evaluate_stage1_edgescore(
        trades=250,
        wins=100,
        hold_signals=400,
        total_signals=1000,
        constitution_violations=0,
        required=200,
        cfg=cfg,
        entropy=None,
        total_pnl=10.0,
        ppo_steps=500,
    )
    assert warm.entropy_ok is False
    assert policy_entropy_alive(None, cfg=cfg, ppo_steps=500) is False
    assert should_force_exploration_burst(
        entropy=None, hold_ratio=0.4, cfg=cfg, ppo_steps=500
    )


@pytest.mark.unit
def test_champion_accepted_resolves_tournament() -> None:
    cfg = BirthCurriculumConfig(starship_swarm_first_enabled=True, policy_swarm_enabled=True)
    rejected = PolicySwarmState(rejected_no_lift=True)
    assert swarm_tournament_done(rejected)
    assert should_block_phoenix_until_swarm(
        cfg=cfg, swarm_state=rejected, allow_provisional=False
    )
    accepted = PolicySwarmState(rejected_no_lift=False, champion_accepted=True)
    assert swarm_tournament_done(accepted)
    assert not should_block_phoenix_until_swarm(
        cfg=cfg, swarm_state=accepted, allow_provisional=False
    )


@pytest.mark.unit
def test_select_swarm_winner_prefer_expectancy() -> None:
    from lumina_core.birth.config import BirthRewardConfig

    baseline = BirthRewardConfig()
    state = PolicySwarmState(
        variants=[
            PolicySwarmVariant("a", "A", baseline),
            PolicySwarmVariant("b", "B", baseline),
        ],
        results={
            "a": PolicySwarmVariantResult("a", trades=100, wins=60, total_pnl=-50.0),
            "b": PolicySwarmVariantResult("b", trades=100, wins=50, total_pnl=80.0),
        },
    )
    # Winrate prefers a; expectancy prefers b.
    assert select_swarm_winner(state).variant_id == "a"
    assert select_swarm_winner(state, prefer_expectancy=True).variant_id == "b"


@pytest.mark.unit
def test_certified_evolution_ladder_compressed() -> None:
    cfg = BirthCurriculumConfig(
        plateau_max_evolution_steps=8,
        starship_certified_plateau_max_evolution_steps=4,
    )
    assert effective_plateau_max_evolution_steps(cfg, certified=True) == 4
    assert effective_plateau_max_evolution_steps(cfg, certified=False) == 8
    state = PlateauState(active=True, evolution_step=4)
    assert evolution_ladder_exhausted(state, max_steps=4) is True
    assert evolution_ladder_exhausted(state, max_steps=8) is False
    state2 = PlateauState(active=True, evolution_step=3)
    action = begin_evolution_step(
        state2, stage_trades=500, stage_wins=180, max_steps=4
    )
    assert action.value != "terminal_stall"
    action_term = begin_evolution_step(
        state2, stage_trades=500, stage_wins=180, max_steps=4
    )
    # After step 4, next begin is terminal.
    assert state2.evolution_step >= 4
    assert (
        evolution_ladder_exhausted(state2, max_steps=4)
        or action_term.value == "terminal_stall"
    )


@pytest.mark.unit
def test_pause_ssot_writes_both_files(tmp_path: Path) -> None:
    progress = {
        "stage": "training_running",
        "phase": "curriculum_learning",
        "curriculum_stage": "stage1_trend",
        "trades_done": 2753,
        "message": "old",
    }
    payload = build_pause_ssot_payload(progress=progress, message="stopped")
    assert payload["stage"] == "paused"
    assert payload["phase"] == "paused"
    assert payload["user_initiated_stop"] is True
    assert payload["curriculum_stage"] == "stage1_trend"
    write_pause_ssot(tmp_path, payload)
    birth = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    legacy = json.loads((tmp_path / "state" / "first_boot_progress.json").read_text(encoding="utf-8"))
    assert birth == legacy
    assert birth["user_initiated_stop"] is True


@pytest.mark.unit
def test_expectancy_proxy_winrate_centered() -> None:
    assert compute_expectancy_proxy(wins=5, trades=10, total_pnl=25.0) == pytest.approx(0.0)
    assert compute_expectancy_proxy(wins=4, trades=10, total_pnl=None) == pytest.approx(-0.1)


@pytest.mark.unit
def test_tournament_lift_statistical_floor() -> None:
    # n=100 → 0.5/sqrt(100)=0.05; config delta 0.01 → need 0.05
    need = tournament_lift_required_delta(trades=100, meaningful_delta=0.01)
    assert need == pytest.approx(0.05)
    assert swarm_edgescore_lift(
        before_score=0.40, after_score=0.44, meaningful_delta=0.01, trades=100
    ) is False
    assert swarm_edgescore_lift(
        before_score=0.40, after_score=0.46, meaningful_delta=0.01, trades=100
    ) is True


@pytest.mark.unit
def test_identical_frozen_windows_round_robin() -> None:
    windows = [[{"i": 0}], [{"i": 1}], [{"i": 2}]]
    state = PolicySwarmState(active=True, frozen_tick_windows=windows, frozen_window_count=3)
    assert state.next_frozen_window() == [{"i": 0}]
    assert state.next_frozen_window() == [{"i": 1}]
    assert state.next_frozen_window() == [{"i": 2}]
    assert state.next_frozen_window() == [{"i": 0}]
    state.frozen_window_cursor = 0
    assert state.next_frozen_window() == [{"i": 0}]


@pytest.mark.unit
def test_stage2_stage3_edgescore_pass_fail() -> None:
    cfg = BirthCurriculumConfig(
        stage2_edgescore_enabled=True,
        stage3_edgescore_enabled=True,
        stage1_entropy_floor=0.05,
        stage1_expectancy_floor=-0.15,
        stage3_winrate_floor=0.35,
        stage3_hold_ratio_max=0.70,
    )
    s2_ok = evaluate_stage2_edgescore(
        trades=200,
        wins=80,
        range_flat_ratio=0.45,
        range_round_trips=40,
        range_total_signals=200,
        constitution_violations=0,
        required=150,
        cfg=cfg,
        entropy=0.2,
        total_pnl=10.0,
    )
    assert s2_ok.passed is True
    s2_bad = evaluate_stage2_edgescore(
        trades=200,
        wins=80,
        range_flat_ratio=0.10,
        range_round_trips=0,
        range_total_signals=200,
        constitution_violations=0,
        required=150,
        cfg=cfg,
        entropy=0.2,
        total_pnl=10.0,
    )
    assert s2_bad.passed is False
    s3_ok = evaluate_stage3_edgescore(
        trades=200,
        wins=80,
        hold_signals=400,
        total_signals=1000,
        constitution_violations=0,
        required=150,
        cfg=cfg,
        entropy=0.2,
        total_pnl=10.0,
    )
    assert s3_ok.passed is True
    s3_hold = evaluate_stage3_edgescore(
        trades=200,
        wins=80,
        hold_signals=900,
        total_signals=1000,
        constitution_violations=0,
        required=150,
        cfg=cfg,
        entropy=0.2,
        total_pnl=10.0,
    )
    assert s3_hold.passed is False
    result = evaluate_stage_pass(
        CurriculumStage.STAGE2_RANGE,
        trades=400,
        wins=160,
        hold_signals=400,
        total_signals=1000,
        range_flat_bars=90,
        range_total_signals=200,
        range_round_trips=40,
        constitution_violations=0,
        target_trades=2000,
        cfg=cfg,
        policy_entropy=0.2,
        stage_total_pnl=10.0,
    )
    assert result.passed is True
    assert "edgescore" in result.message.lower()


@pytest.mark.unit
def test_skip_ladder_theater_after_freeze_or_accept() -> None:
    assert should_skip_plateau_ladder_theater(
        swarm_state=PolicySwarmState(champion_accepted=True)
    )
    assert should_skip_plateau_ladder_theater(
        swarm_state=PolicySwarmState(rejected_no_lift=True)
    )
    assert not should_skip_plateau_ladder_theater(swarm_state=PolicySwarmState())


@pytest.mark.unit
def test_birth_control_plane_import_smoke() -> None:
    from lumina_core.birth import birth_control_plane as bcp

    assert callable(bcp.should_start_swarm_before_recovery)
    assert callable(bcp.twin_continue_eligible)
    assert callable(bcp.should_skip_plateau_ladder_theater)
    assert bcp.twin_continue_eligible(
        cfg=BirthCurriculumConfig(starship_twin_continue_when_full_auto=True),
        twin_mode="full_auto",
        twin_executable=True,
        twin_confidence=0.9,
        swarm_resolved=True,
        constitution_risks=False,
    )
    assert not bcp.twin_continue_eligible(
        cfg=BirthCurriculumConfig(starship_twin_continue_when_full_auto=True),
        twin_mode="full_auto",
        twin_executable=True,
        twin_confidence=0.9,
        swarm_resolved=False,
        constitution_risks=False,
    )


@pytest.mark.unit
def test_swarm_tournament_resolved_excludes_reject_only() -> None:
    from lumina_core.birth.birth_control_plane import swarm_tournament_resolved

    rejected = PolicySwarmState(rejected_no_lift=True)
    assert swarm_tournament_done(rejected) is True
    assert swarm_tournament_resolved(swarm_state=rejected) is False
    accepted = PolicySwarmState(champion_accepted=True)
    assert swarm_tournament_resolved(swarm_state=accepted) is True
    committed = PolicySwarmState(committed_variant_id="swarm_expectancy")
    assert swarm_tournament_resolved(swarm_state=committed) is True


@pytest.mark.unit
def test_fail_closed_missing_frozen_windows() -> None:
    from lumina_core.birth.birth_control_plane import (
        fail_closed_missing_frozen_windows,
        require_frozen_windows_or_fail,
    )

    ok = PolicySwarmState(active=True, frozen_tick_windows=[[{"i": 1}]])
    assert require_frozen_windows_or_fail(ok) is True
    assert fail_closed_missing_frozen_windows(ok) is False

    missing = PolicySwarmState(active=True, frozen_tick_windows=[], variants=[])
    assert require_frozen_windows_or_fail(missing) is False
    assert fail_closed_missing_frozen_windows(missing) is True
    assert missing.active is False
    assert missing.rejected_no_lift is True

    empty_slice = PolicySwarmState(active=True, frozen_tick_windows=[[]])
    assert require_frozen_windows_or_fail(empty_slice) is False
    assert fail_closed_missing_frozen_windows(empty_slice) is True


@pytest.mark.unit
def test_skip_theater_blocks_remediation_predicate() -> None:
    """Reject/accept must skip ladder theater (stall remediation gated on same predicate)."""
    assert should_skip_plateau_ladder_theater(
        swarm_state=PolicySwarmState(rejected_no_lift=True),
        host_rejected_no_lift=True,
    )
    assert should_skip_plateau_ladder_theater(
        swarm_state=PolicySwarmState(),
        host_champion_accepted=True,
    )


@pytest.mark.unit
def test_hard_stop_training_after_swarm_reject() -> None:
    rejected = PolicySwarmState(rejected_no_lift=True)
    # First reject: soft path — re-tournament not yet used → no hard stop.
    assert not should_hard_stop_training_after_swarm_reject(
        swarm_state=rejected, host_rejected_no_lift=True, retearnament_used=False
    )
    # After re-tournament burned: hard stop.
    assert should_hard_stop_training_after_swarm_reject(
        swarm_state=rejected, host_rejected_no_lift=True, retearnament_used=True
    )
    assert not should_hard_stop_training_after_swarm_reject(
        swarm_state=PolicySwarmState(rejected_no_lift=True, champion_accepted=True),
        host_rejected_no_lift=True,
        host_champion_accepted=True,
        retearnament_used=True,
    )
    assert not should_hard_stop_training_after_swarm_reject(
        swarm_state=PolicySwarmState(),
    )
    from lumina_core.birth.birth_control_plane import should_hard_stop_training_after_swarm_reject as cp

    assert cp(swarm_state=rejected, host_rejected_no_lift=True, retearnament_used=True)


@pytest.mark.unit
def test_swarm_tournament_lift_alias() -> None:
    assert swarm_tournament_lift(
        before_score=0.40, after_score=0.46, meaningful_delta=0.01, trades=100
    ) is True
    assert swarm_edgescore_lift(
        before_score=0.40, after_score=0.46, meaningful_delta=0.01, trades=100
    ) is True
    assert swarm_tournament_lift is not swarm_edgescore_lift  # distinct wrappers


@pytest.mark.unit
def test_plateau_evolution_ladder_reexport() -> None:
    from lumina_core.birth import plateau_evolution_ladder as ladder
    from lumina_core.birth.plateau_escalator import (
        EvolutionAction,
        begin_evolution_step,
        evolution_ladder_exhausted,
    )

    assert EvolutionAction is ladder.EvolutionAction
    assert begin_evolution_step is ladder.begin_evolution_step
    state = PlateauState(active=True, evolution_step=0)
    action = begin_evolution_step(state, stage_trades=100, stage_wins=40, max_steps=4)
    assert action != EvolutionAction.TERMINAL
    assert state.evolution_step == 1
    state.evolution_step = 4
    assert evolution_ladder_exhausted(state, max_steps=4) is True


@pytest.mark.unit
def test_hard_stop_implies_no_fresh_pool_training() -> None:
    """Post re-tournament reject hard-stop must block further tick-pool training."""
    assert should_hard_stop_training_after_swarm_reject(
        swarm_state=PolicySwarmState(rejected_no_lift=True),
        host_rejected_no_lift=True,
        retearnament_used=True,
    )
    # Accept clears hard-stop — training may resume.
    assert not should_hard_stop_training_after_swarm_reject(
        swarm_state=PolicySwarmState(rejected_no_lift=True, champion_accepted=True),
        host_rejected_no_lift=True,
        host_champion_accepted=True,
        retearnament_used=True,
    )


@pytest.mark.unit
def test_edgescore_champion_min_trades_blocks_early_noise() -> None:
    cfg = BirthCurriculumConfig(
        plateau_best_policy_min_trades=200,
        stage1_winrate_pass_floor=0.35,
    )
    assert edgescore_champion_min_trades(200, cfg) == 200
    assert is_edgescore_champion_eligible(stage_trades=50, required=200, cfg=cfg) is False
    assert is_edgescore_champion_eligible(stage_trades=200, required=200, cfg=cfg) is True


@pytest.mark.unit
def test_publish_edgescore_champion_fields_null_until_locked() -> None:
    """Regression: pre-eligibility champion was published as 0.0 → UI '0%'."""
    from lumina_core.birth.starship_birth import publish_edgescore_champion_fields

    cfg = BirthCurriculumConfig(plateau_best_policy_min_trades=200)
    pending = publish_edgescore_champion_fields(
        best_edgescore=0.0,
        best_edgescore_at_trade=0,
        stage_trades=137,
        required=300,
        cfg=cfg,
    )
    assert pending["best_edgescore"] is None
    assert pending["edgescore_champion_locked"] is False
    assert pending["edgescore_champion_min_trades"] == 300

    locked = publish_edgescore_champion_fields(
        best_edgescore=0.334,
        best_edgescore_at_trade=320,
        stage_trades=400,
        required=300,
        cfg=cfg,
    )
    assert locked["best_edgescore"] == 0.334
    assert locked["edgescore_champion_locked"] is True


@pytest.mark.unit
def test_sanitize_poisoned_early_edgescore_champion() -> None:
    cfg = BirthCurriculumConfig(
        plateau_best_policy_min_trades=200,
        stage1_winrate_pass_floor=0.35,
    )
    # Live incident: best_edge=0.875 after ~6 min with best WR never above ~34%.
    best, at, cleared = sanitize_edgescore_champion(
        best_edgescore=0.875,
        best_edgescore_at_trade=40,
        best_winrate=0.0,
        required=200,
        cfg=cfg,
    )
    assert cleared is True
    assert best == 0.0
    assert at == 0
    # Inconsistent high edge vs sub-hygiene plateau WR (missing at_trade).
    best2, at2, cleared2 = sanitize_edgescore_champion(
        best_edgescore=0.875,
        best_edgescore_at_trade=0,
        best_winrate=0.3416,
        required=200,
        cfg=cfg,
    )
    assert cleared2 is True
    assert best2 == 0.0
    # Eligible consistent champion kept.
    best3, at3, cleared3 = sanitize_edgescore_champion(
        best_edgescore=0.59,
        best_edgescore_at_trade=250,
        best_winrate=0.40,
        required=200,
        cfg=cfg,
    )
    assert cleared3 is False
    assert best3 == 0.59
    assert at3 == 250


@pytest.mark.unit
def test_select_swarm_winner_prefer_tournament_score() -> None:
    from lumina_core.birth.config import BirthRewardConfig

    baseline = BirthRewardConfig()
    # Variant a: high expectancy, lower tournament blend.
    # Variant b: slightly lower expectancy but better WR → higher tournament_score.
    state = PolicySwarmState(
        variants=[
            PolicySwarmVariant("a", "A", baseline),
            PolicySwarmVariant("b", "B", baseline),
        ],
        results={
            # a: exp=1.0, wr=0.20 → tournament = 0.6*1.0 + 0.4*0.2 = 0.68
            "a": PolicySwarmVariantResult("a", trades=100, wins=20, total_pnl=100.0),
            # b: exp=0.5, wr=0.70 → tournament = 0.6*0.75 + 0.4*0.7 = 0.45+0.28 = 0.73
            "b": PolicySwarmVariantResult("b", trades=100, wins=70, total_pnl=50.0),
        },
    )
    assert select_swarm_winner(state, prefer_expectancy=True).variant_id == "a"
    assert select_swarm_winner(state, prefer_tournament_score=True).variant_id == "b"
    score_a = tournament_score(trades=100, wins=20, total_pnl=100.0)
    score_b = tournament_score(trades=100, wins=70, total_pnl=50.0)
    assert score_b > score_a
