"""Verify stage pass receipts and curriculum integrity."""
from __future__ import annotations


from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import (
    CurriculumStage,
    evaluate_stage_pass,
)
from lumina_core.birth.stage_pass_receipt_types import (
    CurriculumIntegrityAudit,
    StagePassReceipt,
    receipt_for_stage,
    receipt_message_is_soft_pass,
)
from lumina_core.birth.stage_scorecard import parse_curriculum_stage
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_pass_receipt")

def verify_stage_pass_receipt(
    stage: CurriculumStage,
    receipt: StagePassReceipt | None,
    *,
    cfg: BirthCurriculumConfig,
    training_mode: str,
    allow_provisional: bool | None = None,
) -> tuple[bool, str]:
    from lumina_core.birth.foundation_metrics import FOUNDATION_SCHEMA
    from lumina_core.birth.foundation_stages import is_legacy_intra_birth_stage

    if receipt is None:
        return False, "missing_receipt"
    if receipt.stage != stage.value:
        return False, f"receipt_stage_mismatch expected={stage.value} got={receipt.stage}"
    if is_legacy_intra_birth_stage(stage):
        return False, f"legacy_intra_birth_stage:{stage.value}"
    if str(getattr(receipt, "schema", "") or "") != FOUNDATION_SCHEMA:
        return False, "missing_or_invalid_foundation_schema"
    if getattr(receipt, "median_loss_r", None) is None:
        return False, "missing_median_loss_r"
    if getattr(receipt, "mean_r", None) is None:
        return False, "missing_mean_r"
    if stage != CurriculumStage.STAGE1_TREND and getattr(receipt, "occupancy", None) is None:
        return False, "missing_occupancy"
    mode = str(training_mode).strip().lower()
    provisional_ok = bool(allow_provisional) if allow_provisional is not None else (
        mode == "practice"
    )
    if mode == "certified":
        provisional_ok = False
    if receipt.provisional and not provisional_ok:
        return False, "provisional_not_allowed_in_certified_mode"
    if mode == "certified" and receipt_message_is_soft_pass(receipt.message):
        return False, "soft_oracle_pass_not_allowed_in_certified_mode"

    hold_ratio = float(getattr(receipt, "hold_ratio", 0.0) or 0.0)
    range_flat = float(getattr(receipt, "range_flat_ratio", 0.0) or 0.0)
    range_rt = int(getattr(receipt, "range_round_trips", 0) or 0)
    range_total = int(getattr(receipt, "range_total_signals", 0) or 0)
    range_hold = int(getattr(receipt, "range_hold_signals", 0) or 0)
    range_flat_bars = int(getattr(receipt, "range_flat_bars", 0) or 0)
    hold_signals = int(getattr(receipt, "hold_signals", 0) or 0)
    total_signals = int(getattr(receipt, "total_signals", 0) or 0)
    if total_signals <= 0:
        total_signals = max(1, int(receipt.trades) * 20)
    if hold_signals <= 0 and hold_ratio > 0:
        hold_signals = int(round(hold_ratio * total_signals))

    reeval = evaluate_stage_pass(
        stage,
        trades=receipt.trades,
        wins=receipt.wins,
        hold_signals=max(0, hold_signals),
        total_signals=max(1, total_signals),
        range_hold_signals=max(0, range_hold),
        range_total_signals=max(0, range_total),
        range_flat_bars=max(0, range_flat_bars),
        range_round_trips=max(0, range_rt),
        constitution_violations=0,
        target_trades=receipt.required_trades,
        cfg=cfg,
        provisional=False,
        allow_provisional=False,
        rolling_winrate=None,
        policy_entropy=getattr(receipt, "policy_entropy", None),
        policy_trades=getattr(receipt, "policy_trades", None),
        policy_wins=getattr(receipt, "policy_wins", None),
        plant_trades=getattr(receipt, "plant_trades", None),
        plant_wins=getattr(receipt, "plant_wins", None),
        closes_stop=int(getattr(receipt, "closes_stop", 0) or 0),
        closes_target=int(getattr(receipt, "closes_target", 0) or 0),
        closes_time_stop=int(getattr(receipt, "closes_time_stop", 0) or 0),
        closes_flatten=int(getattr(receipt, "closes_flatten", 0) or 0),
        closes_unknown=int(getattr(receipt, "closes_unknown", 0) or 0),
        median_loss_r=getattr(receipt, "median_loss_r", None),
        mean_r=getattr(receipt, "mean_r", None),
        occupancy=getattr(receipt, "occupancy", None) if getattr(receipt, "occupancy", None) is not None else range_flat,
        first_touch_hit_rate=getattr(receipt, "p_ft", None),
        geometry_net_rr=getattr(receipt, "geometry_net_rr", None),
        unique_calendar_days=getattr(receipt, "unique_calendar_days", None),
        oos_sharpe=getattr(receipt, "oos_sharpe", None),
        oos_dd_pct=getattr(receipt, "oos_dd_pct", None),
    )
    if not reeval.passed:
        return False, f"re_eval_failed:{reeval.message}"
    if receipt_message_is_soft_pass(reeval.message):
        return False, "re_eval_soft_pass_rejected"
    return True, "ok"


def truncate_stages_to_verified(
    stages_passed: list[str],
    receipts: list[StagePassReceipt],
    *,
    cfg: BirthCurriculumConfig,
    training_mode: str,
) -> tuple[list[str], list[StagePassReceipt], list[str]]:
    """Keep only prefix of stages_passed with valid receipts."""
    kept_stages: list[str] = []
    kept_receipts: list[StagePassReceipt] = []
    invalid_reasons: list[str] = []
    for stage_value in stages_passed:
        stage = parse_curriculum_stage(stage_value)
        if stage is None:
            invalid_reasons.append(f"unknown_stage:{stage_value}")
            break
        receipt = receipt_for_stage(receipts, stage_value)
        ok, reason = verify_stage_pass_receipt(
            stage,
            receipt,
            cfg=cfg,
            training_mode=training_mode,
        )
        if not ok:
            invalid_reasons.append(f"{stage_value}:{reason}")
            break
        kept_stages.append(stage_value)
        if receipt is not None:
            kept_receipts.append(receipt)
    return kept_stages, kept_receipts, invalid_reasons


def audit_curriculum_integrity(
    *,
    stages_passed: list[str],
    stage_pass_receipts: list[StagePassReceipt],
    cfg: BirthCurriculumConfig,
    training_mode: str,
) -> CurriculumIntegrityAudit:
    if not stages_passed:
        return CurriculumIntegrityAudit(
            ok=True,
            stages_passed=[],
            stage_pass_receipts=[],
            invalid_reasons=[],
            reset_applied=False,
        )
    kept_stages, kept_receipts, invalid_reasons = truncate_stages_to_verified(
        list(stages_passed),
        list(stage_pass_receipts),
        cfg=cfg,
        training_mode=training_mode,
    )
    reset_applied = kept_stages != list(stages_passed) or len(kept_receipts) != len(
        [s for s in stages_passed if s in kept_stages]
    )
    if invalid_reasons:
        logger.warning(
            "birth.curriculum_integrity_reset before=%s after=%s reasons=%s",
            stages_passed,
            kept_stages,
            invalid_reasons,
        )
    return CurriculumIntegrityAudit(
        ok=len(invalid_reasons) == 0,
        stages_passed=kept_stages,
        stage_pass_receipts=kept_receipts,
        invalid_reasons=invalid_reasons,
        reset_applied=reset_applied,
    )
