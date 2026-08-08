"""Birth-lifecycle milestone event builders (M5 extract)."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.stage_pass_receipt import StagePassReceipt
from lumina_core.notifications.milestone_event_types import (
    MilestoneCategory,
    MilestoneEvent,
    _STAGE_LABELS,
    _STAGE_MILESTONE_IDS,
)

def birth_started_event(
    *,
    training_mode: str,
    trade_budget: int,
    resumed: bool = False,
) -> MilestoneEvent:
    mode = str(training_mode or "certified").strip().lower()
    summary = (
        f"Birth Phase v2 gestart ({mode} mode). "
        f"Trade budget: {int(trade_budget):,}."
    )
    if resumed:
        summary += " Hervat vanaf checkpoint."
    return MilestoneEvent(
        milestone_id="birth_started",
        category=MilestoneCategory.BIRTH,
        title="Birth gestart",
        summary=summary,
        context={
            "training_mode": mode,
            "trade_budget": int(trade_budget),
            "resumed": resumed,
        },
    )


def history_loaded_event(
    *,
    tick_count: int,
    real_data_pct: float,
    max_real_days: int = 0,
) -> MilestoneEvent:
    days_part = f"{int(max_real_days)} dagen, " if max_real_days > 0 else ""
    return MilestoneEvent(
        milestone_id="history_loaded",
        category=MilestoneCategory.BIRTH,
        title="Marktdata geladen",
        summary=(
            f"{days_part}{int(tick_count):,} ticks geladen "
            f"({float(real_data_pct):.0f}% real data)."
        ),
        context={
            "tick_count": int(tick_count),
            "real_data_pct": f"{float(real_data_pct):.1f}%",
        },
    )


def regime_map_ready_event(
    *,
    tick_count: int,
    train_bars: int,
    holdout_bars: int,
    holdout_days: int,
    real_data_pct: float,
) -> MilestoneEvent:
    return MilestoneEvent(
        milestone_id="regime_map_ready",
        category=MilestoneCategory.BIRTH,
        title="Regime map klaar",
        summary=(
            f"Holdout split klaar: {int(tick_count):,} ticks "
            f"({int(train_bars):,} train / {int(holdout_bars):,} holdout), "
            f"{int(holdout_days)} holdout-dagen."
        ),
        context={
            "tick_count": int(tick_count),
            "train_bars": int(train_bars),
            "holdout_bars": int(holdout_bars),
            "holdout_days": int(holdout_days),
            "real_data_pct": f"{float(real_data_pct):.1f}%",
        },
    )


def curriculum_stage4_polish_passed_event(
    *,
    stages_passed: list[str],
    cumulative_trades: int,
) -> MilestoneEvent:
    stages = ", ".join(stages_passed) if stages_passed else "none"
    return MilestoneEvent(
        milestone_id="curriculum_stage4_polish_passed",
        category=MilestoneCategory.BIRTH,
        title="Stage 4 — Polish voltooid",
        summary=(
            f"Curriculum stages 1–3 afgerond ({stages}). "
            f"PPO polish start ({int(cumulative_trades):,} trades)."
        ),
        context={
            "stages_passed": stages,
            "cumulative_trades": int(cumulative_trades),
        },
    )


def curriculum_stage_passed_event(
    stage: CurriculumStage | str,
    receipt: StagePassReceipt,
) -> MilestoneEvent:
    stage_value = stage.value if isinstance(stage, CurriculumStage) else str(stage).strip().lower()
    milestone_id = _STAGE_MILESTONE_IDS.get(stage_value, f"curriculum_{stage_value}_passed")
    label = _STAGE_LABELS.get(stage_value, stage_value)
    provisional_note = " (provisional)" if receipt.provisional else ""
    return MilestoneEvent(
        milestone_id=milestone_id,
        category=MilestoneCategory.BIRTH,
        title=f"{label} voltooid",
        summary=(
            f"{label} geslaagd{provisional_note}: "
            f"{receipt.trades}/{receipt.required_trades} trades, "
            f"winrate {receipt.winrate:.1%}."
        ),
        context={
            "stage": stage_value,
            "trades": receipt.trades,
            "winrate": f"{receipt.winrate:.1%}",
            "required_trades": receipt.required_trades,
            "provisional": receipt.provisional,
        },
    )


def refinement_started_event(
    *,
    cumulative_trades: int,
    ppo_steps: int,
) -> MilestoneEvent:
    return MilestoneEvent(
        milestone_id="refinement_started",
        category=MilestoneCategory.BIRTH,
        title="PPO polish gestart",
        summary=(
            f"Final PPO polish (stage 4): "
            f"{int(cumulative_trades):,} cumulative trades, "
            f"{int(ppo_steps):,} PPO steps."
        ),
        context={
            "cumulative_trades": int(cumulative_trades),
            "ppo_steps": int(ppo_steps),
        },
    )


def oos_evaluation_passed_event(*, eval_result: dict[str, Any]) -> MilestoneEvent:
    sharpe = eval_result.get("oos_sharpe", eval_result.get("sharpe"))
    winrate = eval_result.get("oos_winrate", eval_result.get("winrate"))
    max_dd = eval_result.get("max_drawdown", eval_result.get("oos_max_drawdown"))
    return MilestoneEvent(
        milestone_id="oos_evaluation_passed",
        category=MilestoneCategory.BIRTH,
        title="OOS eval geslaagd",
        summary="Out-of-sample certificate thresholds gehaald.",
        context={
            "oos_sharpe": sharpe,
            "oos_winrate": f"{float(winrate):.1%}" if winrate is not None else None,
            "max_drawdown": max_dd,
        },
    )


def birth_certificate_issued_event(
    *,
    eval_result: dict[str, Any],
    stages_passed: list[str],
    cumulative_trades: int,
    ppo_steps: int,
) -> MilestoneEvent:
    sharpe = eval_result.get("oos_sharpe")
    winrate = eval_result.get("oos_winrate")
    stages = ", ".join(stages_passed) if stages_passed else "none"
    return MilestoneEvent(
        milestone_id="birth_certificate_issued",
        category=MilestoneCategory.BIRTH,
        title="Birth Certificate v2",
        summary=(
            f"Birth Certificate v2 uitgegeven. "
            f"{int(cumulative_trades):,} trades, {int(ppo_steps):,} PPO steps."
        ),
        context={
            "stages_passed": stages,
            "cumulative_trades": int(cumulative_trades),
            "ppo_steps": int(ppo_steps),
            "oos_sharpe": sharpe,
            "oos_winrate": f"{float(winrate):.1%}" if winrate is not None else None,
        },
    )


def learning_breakthrough_event(
    *,
    winrate: float,
    prior_mean: float,
    delta: float,
) -> MilestoneEvent:
    return MilestoneEvent(
        milestone_id="learning_breakthrough",
        category=MilestoneCategory.BIRTH,
        title="Learning breakthrough",
        summary=(
            f"Winrate lifted to {winrate:.1%} (+{delta:.1%} vs recent mean {prior_mean:.1%})."
        ),
        context={
            "winrate": f"{winrate:.1%}",
            "prior_mean": f"{prior_mean:.1%}",
            "delta": f"{delta:.1%}",
        },
    )


def trade_budget_milestone_event(*, pct: int, cumulative_trades: int, cap: int) -> MilestoneEvent:
    return MilestoneEvent(
        milestone_id=f"trade_budget_{pct}",
        category=MilestoneCategory.BIRTH,
        title=f"Trade budget {pct}%",
        summary=f"{cumulative_trades:,} / {cap:,} trades ({pct}% of budget).",
        context={
            "cumulative_trades": int(cumulative_trades),
            "trade_budget_cap": int(cap),
            "pct": int(pct),
        },
        dedupe_key=f"trade_budget:{pct}",
    )


def evolution_proof_passed_event(*, oos_winrate: float, lift: float | None) -> MilestoneEvent:
    lift_str = f"{lift:.1%}" if lift is not None else "n/a"
    return MilestoneEvent(
        milestone_id="evolution_proof_passed",
        category=MilestoneCategory.BIRTH,
        title="Evolution Proof passed",
        summary=f"Post-birth fitness confirmed. OOS winrate {oos_winrate:.1%}, lift {lift_str}.",
        context={"oos_winrate": f"{oos_winrate:.1%}", "lift": lift_str},
    )


def evolution_proof_failed_event(*, reasons: list[str]) -> MilestoneEvent:
    return MilestoneEvent(
        milestone_id="evolution_proof_failed",
        category=MilestoneCategory.BIRTH,
        title="Evolution Proof failed",
        summary="Continue refinement before REAL. " + "; ".join(reasons[:3]),
        context={"reasons": "; ".join(reasons)},
    )


def birth_gate_warning_event(*, threshold: float, recommended: float) -> MilestoneEvent:
    return MilestoneEvent(
        milestone_id="birth_gate_warning",
        category=MilestoneCategory.BIRTH,
        title="Birth winrate gate below recommended",
        summary=(
            f"Stage 1 gate set to {threshold:.0%} (recommended {recommended:.0%}). "
            "REAL requires Evolution Proof + OOS ≥48%."
        ),
        context={"threshold": f"{threshold:.0%}", "recommended": f"{recommended:.0%}"},
    )


def practice_birth_completed_event(
    *,
    cumulative_trades: int,
    ppo_steps: int,
    policy_path: str = "",
) -> MilestoneEvent:
    summary = (
        f"Practice Birth voltooid (geen certificate): "
        f"{int(cumulative_trades):,} trades, {int(ppo_steps):,} PPO steps."
    )
    ctx: dict[str, Any] = {
        "cumulative_trades": int(cumulative_trades),
        "ppo_steps": int(ppo_steps),
    }
    if policy_path:
        ctx["policy_path"] = policy_path
    return MilestoneEvent(
        milestone_id="practice_birth_completed",
        category=MilestoneCategory.BIRTH,
        title="Practice Birth klaar",
        summary=summary,
        context=ctx,
    )


def milestone_ids_for_stage(stage: str) -> str | None:
    return _STAGE_MILESTONE_IDS.get(str(stage).strip().lower())



