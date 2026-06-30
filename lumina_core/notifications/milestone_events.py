"""Birth milestone event taxonomy (ADR-0025)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.stage_pass_receipt import StagePassReceipt

_STAGE_LABELS: dict[str, str] = {
    CurriculumStage.STAGE1_TREND.value: "Stage 1 — Trend",
    CurriculumStage.STAGE2_RANGE.value: "Stage 2 — Range",
    CurriculumStage.STAGE3_MIXED.value: "Stage 3 — Mixed",
    CurriculumStage.STAGE4_POLISH.value: "Stage 4 — Polish",
}

_STAGE_MILESTONE_IDS: dict[str, str] = {
    CurriculumStage.STAGE1_TREND.value: "curriculum_stage1_trend_passed",
    CurriculumStage.STAGE2_RANGE.value: "curriculum_stage2_range_passed",
    CurriculumStage.STAGE3_MIXED.value: "curriculum_stage3_mixed_passed",
    CurriculumStage.STAGE4_POLISH.value: "curriculum_stage4_polish_passed",
}


class MilestoneCategory(str, Enum):
    BIRTH = "birth"


@dataclass(frozen=True, slots=True)
class MilestoneEvent:
    milestone_id: str
    category: MilestoneCategory
    title: str
    summary: str
    context: dict[str, Any] = field(default_factory=dict)
    dedupe_key: str = ""

    def __post_init__(self) -> None:
        if not self.dedupe_key:
            object.__setattr__(self, "dedupe_key", self.milestone_id)

    def telegram_body(self) -> str:
        lines = [self.summary]
        if self.context:
            ctx_parts: list[str] = []
            for key in (
                "training_mode",
                "trade_budget",
                "resumed",
                "tick_count",
                "real_data_pct",
                "holdout_days",
                "train_bars",
                "holdout_bars",
                "stage",
                "trades",
                "winrate",
                "required_trades",
                "provisional",
                "ppo_steps",
                "cumulative_trades",
                "oos_sharpe",
                "oos_winrate",
                "max_drawdown",
                "stages_passed",
            ):
                if key in self.context and self.context[key] is not None:
                    ctx_parts.append(f"{key}: {self.context[key]}")
            if ctx_parts:
                lines.append("\n".join(ctx_parts))
        return "\n".join(lines)


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


def plateau_evolution_step_event(
    *,
    step: int,
    max_steps: int,
    action: str,
    detail: str,
    winrate: float,
) -> MilestoneEvent:
    return MilestoneEvent(
        milestone_id=f"plateau_evolution_step_{step}",
        category=MilestoneCategory.BIRTH,
        title=f"Plateau evolution {step}/{max_steps}",
        summary=f"{action}: {detail}. Winrate {winrate:.1%}.",
        context={
            "evolution_step": step,
            "max_steps": max_steps,
            "action": action,
            "winrate": f"{winrate:.1%}",
        },
        dedupe_key=f"plateau_evolution:{step}:{action}",
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


__all__ = [
    "MilestoneCategory",
    "MilestoneEvent",
    "birth_certificate_issued_event",
    "birth_started_event",
    "curriculum_stage4_polish_passed_event",
    "curriculum_stage_passed_event",
    "history_loaded_event",
    "milestone_ids_for_stage",
    "oos_evaluation_passed_event",
    "plateau_evolution_step_event",
    "practice_birth_completed_event",
    "refinement_started_event",
    "regime_map_ready_event",
]
