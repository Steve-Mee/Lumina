"""Curriculum stage pass evaluation — Foundation AND-gates (ADR-0046)."""
from __future__ import annotations

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum_types import CurriculumStage, StageResult, stage_pass_trades
from lumina_core.birth.foundation_metrics import (
    FOUNDATION_SCHEMA,
    SETTLEMENT_MIN_SHARE,
    occupancy_ratio,
)
from lumina_core.birth.foundation_pass import evaluate_foundation_pass
from lumina_core.birth.foundation_stages import is_foundation_stage, is_legacy_intra_birth_stage


def _settlement_pass_leg(
    cfg: BirthCurriculumConfig | None,
    *,
    trades: int,
    required: int,
    closes_stop: int,
    closes_target: int,
    closes_time_stop: int,
    closes_flatten: int,
    closes_unknown: int,
    ssot_pending: bool = False,
) -> tuple[bool, str, float]:
    from lumina_core.birth.starship_edgescore_core import evaluate_settlement_honesty

    if bool(ssot_pending):
        # Resume of a stage that already had closes, but close-reason SSOT was
        # zeroed. Do not emit settlement_share=0.00; do not invent closes.
        return True, "ssot_pending_resume", -1.0

    ok, share, reason = evaluate_settlement_honesty(
        closes_stop=int(closes_stop),
        closes_target=int(closes_target),
        closes_time_stop=int(closes_time_stop),
        closes_flatten=int(closes_flatten),
        closes_unknown=int(closes_unknown),
        trades=int(trades),
        required=int(required),
        min_share=float(
            getattr(cfg, "settlement_min_decisive_share", SETTLEMENT_MIN_SHARE)
            or SETTLEMENT_MIN_SHARE
        )
        if cfg
        else SETTLEMENT_MIN_SHARE,
    )
    if cfg is not None and not bool(getattr(cfg, "settlement_honesty_enabled", True)):
        return True, "disabled", float(share or 1.0)
    return bool(ok), str(reason), float(share or 0.0)


def evaluate_stage_pass(
    stage: CurriculumStage,
    *,
    trades: int,
    wins: int,
    hold_signals: int,
    total_signals: int,
    range_hold_signals: int = 0,
    range_total_signals: int = 0,
    range_flat_bars: int = 0,
    range_round_trips: int = 0,
    constitution_violations: int,
    target_trades: int,
    cfg: BirthCurriculumConfig | None = None,
    provisional: bool = False,
    allow_provisional: bool = False,
    oracle_patterns: int = 0,
    buffer_size: int = 0,
    oracle_soft_min_patterns: int = 100,
    stage_val_sharpe: float = 0.0,
    stage_val_max_drawdown_pct: float = 100.0,
    rolling_winrate: float | None = None,
    policy_entropy: float | None = None,
    stage_total_pnl: float | None = None,
    ppo_steps: int = 0,
    policy_trades: int | None = None,
    policy_wins: int | None = None,
    plant_trades: int | None = None,
    plant_wins: int | None = None,
    consecutive_rolling_pass_windows: int = 0,
    closes_stop: int = 0,
    closes_target: int = 0,
    closes_time_stop: int = 0,
    closes_flatten: int = 0,
    closes_unknown: int = 0,
    pnl_series: list[float] | None = None,
    stop_pct: float | None = None,
    ref_price: float | None = None,
    geometry_net_rr: float | None = None,
    first_touch_hit_rate: float | None = None,
    median_loss_r: float | None = None,
    mean_r: float | None = None,
    occupancy: float | None = None,
    unique_calendar_days: int | None = None,
    oos_sharpe: float | None = None,
    oos_dd_pct: float | None = None,
    r_series: list[float] | None = None,
    settlement_ssot_pending: bool = False,
) -> StageResult:
    """Foundation pass law. Rolling WR / EdgeScore / WR floors are HUD-only."""
    hold_ratio = float(hold_signals) / float(max(1, total_signals))
    range_hold_ratio = float(range_hold_signals) / float(max(1, range_total_signals))
    range_flat_ratio = float(range_flat_bars) / float(max(1, range_total_signals))
    volume = int(trades)
    volume_wins = int(wins)
    if policy_trades is not None:
        skill_n = int(policy_trades)
        skill_w = int(policy_wins) if policy_wins is not None else 0
    else:
        skill_n = volume
        skill_w = volume_wins
    _ = (
        rolling_winrate,
        consecutive_rolling_pass_windows,
        plant_trades,
        plant_wins,
        oracle_patterns,
        buffer_size,
        oracle_soft_min_patterns,
        stage_total_pnl,
        target_trades,
    )
    occ = occupancy
    # S1 occupancy is plant-flat, not HOLD%. Do not invent 0.0 from trend signals.
    if occ is None and stage != CurriculumStage.STAGE1_TREND:
        occ_signals = int(range_total_signals) if int(range_total_signals) > 0 else int(total_signals)
        occ_flat = int(range_flat_bars)
        occ = occupancy_ratio(flat_bars=occ_flat, total_signals=occ_signals)

    if cfg is not None:
        required = stage_pass_trades(stage, cfg)
    else:
        required = max(50, min(100, max(1, int(target_trades))))

    settle_ok, settle_reason, settle_share = _settlement_pass_leg(
        cfg,
        trades=trades,
        required=required,
        closes_stop=closes_stop,
        closes_target=closes_target,
        closes_time_stop=closes_time_stop,
        closes_flatten=closes_flatten,
        closes_unknown=closes_unknown,
        ssot_pending=bool(settlement_ssot_pending),
    )
    entropy_alive = True
    if cfg is not None:
        from lumina_core.birth.starship_edgescore_core import policy_entropy_alive

        entropy_alive = policy_entropy_alive(
            policy_entropy, cfg=cfg, ppo_steps=int(ppo_steps)
        )

    days = unique_calendar_days
    from lumina_core.birth.foundation_metrics import build_foundation_snapshot

    if stage == CurriculumStage.STAGE5_PROBE_HANDOFF:
        oos_s = oos_sharpe if oos_sharpe is not None else float(stage_val_sharpe)
        oos_d = oos_dd_pct if oos_dd_pct is not None else float(stage_val_max_drawdown_pct)
    else:
        oos_s = oos_sharpe
        oos_d = oos_dd_pct

    snap = build_foundation_snapshot(
        trades=volume,
        wins=volume_wins,
        skill_trades=skill_n,
        skill_wins=skill_w,
        pnl_series=list(pnl_series) if pnl_series else None,
        r_series=list(r_series) if r_series is not None else None,
        stop_pct=stop_pct,
        ref_price=ref_price,
        net_rr=geometry_net_rr,
        p_ft=first_touch_hit_rate,
        median_loss_r_value=median_loss_r,
        mean_r_value=mean_r,
        occupancy=occ,
        settlement_ok=settle_ok,
        settlement_share=settle_share,
        constitution_violations=int(constitution_violations),
        entropy_alive=entropy_alive,
        unique_calendar_days=int(days) if days is not None else 0,
        oos_sharpe=oos_s,
        oos_dd_pct=oos_d,
    )

    passed = False
    message = ""
    if is_legacy_intra_birth_stage(stage):
        passed = False
        message = f"legacy_intra_birth_stage_rejected:{stage.value}"
    elif is_foundation_stage(stage):
        need_rt = max(3, required // 10)
        decision = evaluate_foundation_pass(
            stage,
            snap,
            round_trips=int(range_round_trips),
            required_round_trips=need_rt,
        )
        passed = decision.passed
        message = f"{decision.message} settle={settle_reason}"
    else:
        passed = False
        message = f"unknown_stage:{stage.value}"

    # PRACTICE-only soft pass. Certified never graduates via oracle/gen0.
    soft_provisional = False
    if allow_provisional and not passed:
        passed = False
        message = f"{message} (practice_soft_pass_disabled_under_foundation)"

    _ = provisional  # HUD may still flag gen0; cannot set passed.
    return StageResult(
        stage=stage,
        trades=trades,
        wins=wins,
        hold_ratio=hold_ratio,
        passed=passed,
        message=message,
        provisional=soft_provisional,
        range_hold_ratio=range_hold_ratio,
        range_flat_ratio=range_flat_ratio,
        range_round_trips=int(range_round_trips),
        closes_stop=int(closes_stop),
        closes_target=int(closes_target),
        closes_time_stop=int(closes_time_stop),
        closes_flatten=int(closes_flatten),
        closes_unknown=int(closes_unknown),
        occupancy=snap.occupancy,
        median_loss_r=snap.median_loss_r,
        mean_r=snap.mean_r,
        edge=snap.edge,
        p_ft=snap.p_ft,
        e_mech=snap.e_mech,
        net_rr=snap.net_rr,
        unique_calendar_days=snap.unique_calendar_days,
        oos_sharpe=snap.oos_sharpe,
        oos_dd_pct=snap.oos_dd_pct,
        schema=FOUNDATION_SCHEMA,
        settlement_ok=snap.settlement_ok,
        settlement_share=snap.settlement_share,
        entropy_alive=snap.entropy_alive,
        replay_ok=snap.replay_ok,
        progress_fields=dict(snap.to_progress_fields()),
    )
