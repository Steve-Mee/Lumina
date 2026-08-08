"""Curriculum stage pass evaluation (gates + soft provisional rules)."""
from __future__ import annotations

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum_types import (
    CurriculumStage,
    StageResult,
    stage1_winrate_pass_threshold,
    stage_pass_trades,
)

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
) -> StageResult:
    winrate = float(wins) / float(max(1, trades))
    hold_ratio = float(hold_signals) / float(max(1, total_signals))
    range_hold_ratio = float(range_hold_signals) / float(max(1, range_total_signals))
    range_flat_ratio = float(range_flat_bars) / float(max(1, range_total_signals))
    if cfg is not None:
        required = stage_pass_trades(stage, cfg)
    else:
        required = max(50, min(100, max(1, int(target_trades))))
    passed = False
    message = ""

    if stage == CurriculumStage.STAGE1_TREND:
        wr_gate = stage1_winrate_pass_threshold(cfg) if cfg is not None else 0.45
        use_rolling = bool(getattr(cfg, "stage1_use_rolling_pass", True)) if cfg else True
        roll_window = int(getattr(cfg, "stage1_rolling_pass_window", 500) or 500) if cfg else 500
        roll = float(rolling_winrate) if rolling_winrate is not None else winrate
        edgescore_on = bool(getattr(cfg, "stage1_edgescore_enabled", False)) if cfg else False
        if edgescore_on and cfg is not None:
            from lumina_core.birth.starship_birth import evaluate_stage1_edgescore

            edge = evaluate_stage1_edgescore(
                trades=trades,
                wins=wins,
                hold_signals=hold_signals,
                total_signals=total_signals,
                constitution_violations=constitution_violations,
                required=required,
                cfg=cfg,
                entropy=policy_entropy,
                total_pnl=stage_total_pnl,
                rolling_winrate=rolling_winrate,
                ppo_steps=int(ppo_steps),
            )
            passed = edge.passed
            message = (
                f"trend edgescore {edge.message} recommended_wr={wr_gate:.0%} "
                f"(diagnostic only)"
            )
        else:
            lifetime_ok = winrate >= wr_gate
            rolling_ok = use_rolling and trades >= max(required, roll_window) and roll >= wr_gate
            wr_ok = lifetime_ok or rolling_ok
            passed = trades >= required and wr_ok and constitution_violations == 0
            gate_source = (
                "lifetime"
                if lifetime_ok
                else ("rolling" if rolling_ok else "neither")
            )
            message = (
                f"trend winrate={winrate:.2%} rolling={roll:.2%} trades={trades}/{required} "
                f"gate={wr_gate:.0%} source={gate_source} "
                f"constitution_violations={constitution_violations}"
            )
    elif stage == CurriculumStage.STAGE2_RANGE:
        s2_edge_on = bool(getattr(cfg, "stage2_edgescore_enabled", False)) if cfg else False
        if s2_edge_on and cfg is not None:
            from lumina_core.birth.starship_birth import evaluate_stage2_edgescore

            flat_metric = range_flat_ratio if range_total_signals >= 50 else hold_ratio
            edge = evaluate_stage2_edgescore(
                trades=trades,
                wins=wins,
                range_flat_ratio=flat_metric,
                range_round_trips=range_round_trips,
                range_total_signals=range_total_signals,
                constitution_violations=constitution_violations,
                required=required,
                cfg=cfg,
                entropy=policy_entropy,
                total_pnl=stage_total_pnl,
                ppo_steps=int(ppo_steps),
                rolling_winrate=rolling_winrate,
            )
            passed = edge.passed
            message = f"range edgescore {edge.message}"
        elif range_total_signals >= 50:
            metric = range_flat_ratio
            metric_label = "range_flat"
            min_round_trips = max(3, required // 10)
            passed = (
                trades >= required
                and 0.30 <= metric <= 0.70
                and range_round_trips >= min_round_trips
                and constitution_violations == 0
            )
            message = (
                f"{metric_label}_ratio={metric:.2%} round_trips={range_round_trips} "
                f"trades={trades}/{required} constitution_violations={constitution_violations} "
                f"(range_ticks={range_total_signals})"
            )
        else:
            metric = hold_ratio
            metric_label = "hold"
            passed = (
                trades >= required
                and 0.30 <= metric <= 0.70
                and constitution_violations == 0
            )
            message = (
                f"{metric_label}_ratio={metric:.2%} trades={trades}/{required} "
                f"constitution_violations={constitution_violations} "
                f"(range_ticks={range_total_signals})"
            )
    elif stage == CurriculumStage.STAGE3_MIXED:
        s3_edge_on = bool(getattr(cfg, "stage3_edgescore_enabled", False)) if cfg else False
        if s3_edge_on and cfg is not None:
            from lumina_core.birth.starship_birth import evaluate_stage3_edgescore

            edge = evaluate_stage3_edgescore(
                trades=trades,
                wins=wins,
                hold_signals=hold_signals,
                total_signals=total_signals,
                constitution_violations=constitution_violations,
                required=required,
                cfg=cfg,
                entropy=policy_entropy,
                total_pnl=stage_total_pnl,
                rolling_winrate=rolling_winrate,
                hold_ratio=hold_ratio,
                ppo_steps=int(ppo_steps),
            )
            passed = edge.passed
            message = f"mixed edgescore {edge.message}"
        else:
            # Foundation floor: mixed regime must retain skill + not pure-hold.
            wr_floor = float(getattr(cfg, "stage3_winrate_floor", 0.35) if cfg else 0.35)
            hold_cap = float(getattr(cfg, "stage3_hold_ratio_max", 0.70) if cfg else 0.70)
            use_rolling = bool(getattr(cfg, "stage3_use_rolling_pass", True)) if cfg else True
            roll_window = int(getattr(cfg, "stage1_rolling_pass_window", 500) or 500) if cfg else 500
            roll = float(rolling_winrate) if rolling_winrate is not None else winrate
            lifetime_ok = winrate >= wr_floor
            rolling_ok = use_rolling and trades >= min(required, roll_window) and roll >= wr_floor
            wr_ok = lifetime_ok or rolling_ok
            hold_ok = hold_ratio <= hold_cap
            passed = (
                trades >= required
                and constitution_violations == 0
                and wr_ok
                and hold_ok
            )
            wr_source = "lifetime" if lifetime_ok else ("rolling" if rolling_ok else "neither")
            message = (
                f"mixed wr={winrate:.2%} rolling={roll:.2%} hold={hold_ratio:.1%} "
                f"trades={trades}/{required} wr_floor={wr_floor:.0%} hold_cap={hold_cap:.0%} "
                f"source={wr_source} constitution_violations={constitution_violations}"
            )
    elif stage == CurriculumStage.STAGE5_PROFIT_VAL:
        wr_gate = float(getattr(cfg, "runway_stage5_winrate_pass", 0.40) if cfg else 0.40)
        hold_cap = float(getattr(cfg, "runway_stage5_hold_ratio_max", 0.55) if cfg else 0.55)
        passed = (
            trades >= required
            and winrate >= wr_gate
            and hold_ratio <= hold_cap
            and constitution_violations == 0
        )
        message = (
            f"runway5 winrate={winrate:.2%} hold={hold_ratio:.1%} "
            f"trades={trades}/{required} gate={wr_gate:.0%}"
        )
    elif stage == CurriculumStage.STAGE6_RISK_DISCIPLINE:
        wr_gate = float(getattr(cfg, "runway_stage6_winrate_min", 0.42) if cfg else 0.42)
        sharpe_min = float(getattr(cfg, "runway_stage6_sharpe_min", 0.20) if cfg else 0.20)
        dd_max = float(getattr(cfg, "runway_stage6_drawdown_max_pct", 12.0) if cfg else 12.0)
        passed = (
            trades >= required
            and winrate >= wr_gate
            and float(stage_val_sharpe) >= sharpe_min
            and float(stage_val_max_drawdown_pct) <= dd_max
            and constitution_violations == 0
        )
        message = (
            f"runway6 winrate={winrate:.2%} sharpe={stage_val_sharpe:.2f} "
            f"dd={stage_val_max_drawdown_pct:.1f}% trades={trades}/{required}"
        )
    elif stage == CurriculumStage.STAGE7_HOLDOUT_PROFILE:
        wr_gate = float(getattr(cfg, "runway_stage7_winrate_min", 0.45) if cfg else 0.45)
        passed = (
            trades >= required
            and winrate >= wr_gate
            and constitution_violations == 0
        )
        message = f"runway7 winrate={winrate:.2%} trades={trades}/{required} gate={wr_gate:.0%}"
    elif stage == CurriculumStage.STAGE4_POLISH:
        passed = True
        message = "polish complete"

    # Soft / research passes are PRACTICE-only. Certified mode must never graduate
    # via oracle pattern count alone (Raptor v5 — no backstage graduation).
    soft_provisional = False
    if allow_provisional and provisional and not passed and trades >= max(1, required // 4):
        passed = True
        soft_provisional = True
        message = f"{message} gen0_provisional"

    if (
        allow_provisional
        and not passed
        and oracle_patterns >= oracle_soft_min_patterns
        and buffer_size >= 256
        and trades >= max(1, required // 4)
    ):
        passed = True
        soft_provisional = True
        message = f"{message} oracle_soft_pass"

    if (
        allow_provisional
        and not passed
        and provisional
        and oracle_patterns >= oracle_soft_min_patterns
        and buffer_size >= max(80, oracle_soft_min_patterns)
        and trades >= 1
    ):
        passed = True
        soft_provisional = True
        message = f"{message} oracle_gen0_research_pass"

    return StageResult(
        stage=stage,
        trades=trades,
        wins=wins,
        hold_ratio=hold_ratio,
        passed=passed,
        message=message,
        provisional=bool(provisional) or soft_provisional,
        range_hold_ratio=range_hold_ratio,
        range_flat_ratio=range_flat_ratio,
        range_round_trips=int(range_round_trips),
    )


