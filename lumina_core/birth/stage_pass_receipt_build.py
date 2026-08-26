"""Build stage pass receipts and audits."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig, BRO_ENGINE_VERSION
from lumina_core.birth.curriculum import (
    CurriculumStage,
    StageResult,
    stage1_winrate_pass_threshold,
    stage_pass_trades,
)
from lumina_core.birth.stage_pass_receipt_types import StagePassReceipt
from lumina_core.birth.stage_pass_receipt_verify import audit_curriculum_integrity
from lumina_core.birth.stage_scorecard import pass_criteria_for_stage, parse_curriculum_stage
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_pass_receipt")

def receipt_from_stage_result(
    stage: CurriculumStage,
    result: StageResult,
    *,
    cfg: BirthCurriculumConfig,
    hold_signals: int | None = None,
    total_signals: int | None = None,
    range_hold_signals: int | None = None,
    range_total_signals: int | None = None,
    range_flat_bars: int | None = None,
    edgescore: float | None = None,
    policy_entropy: float | None = None,
    stage_total_pnl: float | None = None,
    rolling_winrate: float | None = None,
    rolling_winrate_source: str | None = None,
    rolling_window_trades_covered: int | None = None,
    hygiene_wr_source: str | None = None,
    policy_trades: int | None = None,
    policy_wins: int | None = None,
    plant_trades: int | None = None,
    plant_wins: int | None = None,
    geometry_net_rr: float | None = None,
    unique_calendar_days: int | None = None,
) -> StagePassReceipt:
    required = stage_pass_trades(stage, cfg)
    criteria = pass_criteria_for_stage(stage, cfg=cfg)
    winrate = float(result.wins) / float(max(1, result.trades))
    hold_ratio = float(result.hold_ratio)
    tot = int(total_signals) if total_signals is not None else max(1, int(result.trades) * 20)
    holds = (
        int(hold_signals)
        if hold_signals is not None
        else int(round(hold_ratio * tot))
    )
    range_flat = float(result.range_flat_ratio)
    range_rt = int(result.range_round_trips)
    range_total = (
        int(range_total_signals)
        if range_total_signals is not None
        else (max(50, int(result.trades) * 10) if range_flat > 0 or range_rt > 0 else 0)
    )
    range_flat_b = (
        int(range_flat_bars)
        if range_flat_bars is not None
        else int(round(range_flat * max(1, range_total))) if range_total else 0
    )
    range_hold = (
        int(range_hold_signals)
        if range_hold_signals is not None
        else int(round(float(result.range_hold_ratio) * max(1, range_total))) if range_total else 0
    )
    return StagePassReceipt(
        stage=stage.value,
        trades=int(result.trades),
        wins=int(result.wins),
        winrate=round(winrate, 6),
        required_trades=required,
        pass_criteria_id=criteria.id,
        provisional=bool(result.provisional),
        passed_at=datetime.now(timezone.utc).isoformat(),
        engine_version=BRO_ENGINE_VERSION,
        message=str(result.message or ""),
        winrate_gate=(
            float(criteria.metric_target)
            if stage in {CurriculumStage.STAGE1_TREND, CurriculumStage.STAGE3_MIXED}
            and criteria.metric_target is not None
            else None
        ),
        hold_ratio=round(hold_ratio, 6),
        range_flat_ratio=round(range_flat, 6),
        range_round_trips=range_rt,
        range_total_signals=range_total,
        range_hold_signals=range_hold,
        range_flat_bars=range_flat_b,
        hold_signals=holds,
        total_signals=tot,
        edgescore=(float(edgescore) if edgescore is not None else None),
        policy_entropy=(float(policy_entropy) if policy_entropy is not None else None),
        stage_total_pnl=(float(stage_total_pnl) if stage_total_pnl is not None else None),
        rolling_winrate=(float(rolling_winrate) if rolling_winrate is not None else None),
        rolling_winrate_source=(
            str(rolling_winrate_source) if rolling_winrate_source is not None else None
        ),
        rolling_window_trades_covered=(
            max(0, int(rolling_window_trades_covered))
            if rolling_window_trades_covered is not None
            else None
        ),
        hygiene_wr_source=(str(hygiene_wr_source) if hygiene_wr_source is not None else None),
        policy_trades=(max(0, int(policy_trades)) if policy_trades is not None else None),
        policy_wins=(max(0, int(policy_wins)) if policy_wins is not None else None),
        plant_trades=(max(0, int(plant_trades)) if plant_trades is not None else None),
        plant_wins=(max(0, int(plant_wins)) if plant_wins is not None else None),
        closes_stop=max(0, int(getattr(result, "closes_stop", 0) or 0)),
        closes_target=max(0, int(getattr(result, "closes_target", 0) or 0)),
        closes_time_stop=max(0, int(getattr(result, "closes_time_stop", 0) or 0)),
        closes_flatten=max(0, int(getattr(result, "closes_flatten", 0) or 0)),
        closes_unknown=max(0, int(getattr(result, "closes_unknown", 0) or 0)),
        schema=str(getattr(result, "schema", "") or "foundation_v2"),
        median_loss_r=getattr(result, "median_loss_r", None),
        mean_r=getattr(result, "mean_r", None),
        occupancy=float(getattr(result, "occupancy", 0.0) or 0.0),
        edge=getattr(result, "edge", None),
        p_ft=getattr(result, "p_ft", None),
        e_mech=getattr(result, "e_mech", None),
        geometry_net_rr=(
            float(geometry_net_rr)
            if geometry_net_rr is not None
            else (
                float(result.net_rr)
                if getattr(result, "net_rr", None) is not None
                else None
            )
        ),
        unique_calendar_days=(
            max(0, int(unique_calendar_days))
            if unique_calendar_days is not None
            else (
                int(result.unique_calendar_days)
                if getattr(result, "unique_calendar_days", None) is not None
                else None
            )
        ),
        oos_sharpe=(
            float(result.oos_sharpe)
            if getattr(result, "oos_sharpe", None) is not None
            else None
        ),
        oos_dd_pct=(
            float(result.oos_dd_pct)
            if getattr(result, "oos_dd_pct", None) is not None
            else None
        ),
    )


def build_stage_pass_audit(
    *,
    stages_passed: list[str],
    stage_pass_receipts: list[StagePassReceipt],
    progress: dict[str, Any],
    cfg: BirthCurriculumConfig,
    training_mode: str = "certified",
) -> dict[str, Any]:
    audit = audit_curriculum_integrity(
        stages_passed=list(stages_passed),
        stage_pass_receipts=list(stage_pass_receipts),
        cfg=cfg,
        training_mode=training_mode,
    )
    curriculum_stage = str(progress.get("curriculum_stage", "") or "")
    stage = parse_curriculum_stage(curriculum_stage)
    live_winrate: float | None = None
    if progress.get("stage_winrate") is not None:
        try:
            live_winrate = float(progress.get("stage_winrate"))
        except (TypeError, ValueError):
            live_winrate = None
    elif progress.get("stage_wins") is not None and progress.get("stage_trades"):
        try:
            trades = max(1, int(progress.get("stage_trades", 0) or 0))
            wins = int(progress.get("stage_wins", 0) or 0)
            live_winrate = wins / trades
        except (TypeError, ValueError):
            live_winrate = None

    mismatch = not audit.ok
    detail_parts: list[str] = []
    if stages_passed and not stage_pass_receipts:
        mismatch = True
        detail_parts.append("stages_passed_without_receipts")
    wr_gate = stage1_winrate_pass_threshold(cfg)
    if stage == CurriculumStage.STAGE1_TREND and live_winrate is not None and live_winrate < wr_gate:
        if CurriculumStage.STAGE1_TREND.value in stages_passed:
            mismatch = True
            detail_parts.append(
                f"stage1_in_stages_passed_but_live_winrate={live_winrate:.2%}"
            )

    receipts_payload = [r.to_dict() for r in stage_pass_receipts]
    return {
        "integrity_ok": audit.ok and not mismatch,
        "stages_passed": list(stages_passed),
        "verified_stages_passed": list(audit.stages_passed),
        "stage_pass_receipts": receipts_payload,
        "invalid_reasons": list(audit.invalid_reasons) + detail_parts,
        "curriculum_stage": curriculum_stage,
        "live_winrate": live_winrate,
        "integrity_mismatch": mismatch,
        "integrity_mismatch_detail": "; ".join(detail_parts) if detail_parts else None,
    }
