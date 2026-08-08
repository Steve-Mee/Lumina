"""Verify stage pass receipts and curriculum integrity."""
from __future__ import annotations


from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import (
    CurriculumStage,
    evaluate_stage_pass,
    stage1_winrate_pass_threshold,
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
    if receipt is None:
        return False, "missing_receipt"
    if receipt.stage != stage.value:
        return False, f"receipt_stage_mismatch expected={stage.value} got={receipt.stage}"
    mode = str(training_mode).strip().lower()
    # Certified: never accept provisional/soft oracle graduation.
    provisional_ok = bool(allow_provisional) if allow_provisional is not None else (
        mode == "practice"
    )
    if mode == "certified":
        provisional_ok = False
    if receipt.provisional and not provisional_ok:
        return False, "provisional_not_allowed_in_certified_mode"
    if mode == "certified" and receipt_message_is_soft_pass(receipt.message):
        return False, "soft_oracle_pass_not_allowed_in_certified_mode"
    # Stage1: hygiene WR when EdgeScore is the pass law; legacy vanity gate otherwise.
    edgescore_on = bool(getattr(cfg, "stage1_edgescore_enabled", False))
    if stage == CurriculumStage.STAGE1_TREND and not provisional_ok and not edgescore_on:
        wr_gate = float(
            receipt.winrate_gate
            if receipt.winrate_gate is not None
            else stage1_winrate_pass_threshold(cfg)
        )
        if float(receipt.winrate) < wr_gate:
            return False, f"stage1_winrate_below_gate wr={receipt.winrate:.4f} gate={wr_gate:.4f}"
    from lumina_core.birth.starship_birth import gate_rolling_winrate, rolling_wr_pass_eligible

    roll_window = int(getattr(cfg, "stage1_rolling_pass_window", 500) or 500)
    stored_roll = (
        float(receipt.rolling_winrate) if getattr(receipt, "rolling_winrate", None) is not None else None
    )
    stored_roll_src = getattr(receipt, "rolling_winrate_source", None)
    stored_roll_cov = int(getattr(receipt, "rolling_window_trades_covered", 0) or 0)
    gate_roll = gate_rolling_winrate(
        rolling_wr=stored_roll,
        source=stored_roll_src,
        covered=stored_roll_cov,
        window=roll_window,
    )
    if stage == CurriculumStage.STAGE1_TREND and not provisional_ok and edgescore_on:
        hygiene = float(getattr(cfg, "stage1_winrate_pass_floor", 0.35))
        lifetime_ok = float(receipt.winrate) >= hygiene
        rolling_ok = gate_roll is not None and float(gate_roll) >= hygiene
        if not (lifetime_ok or rolling_ok):
            return (
                False,
                f"stage1_hygiene_below_floor wr={receipt.winrate:.4f} "
                f"rolling={stored_roll if stored_roll is not None else 'n/a'} "
                f"eligible={rolling_wr_pass_eligible(source=stored_roll_src, covered=stored_roll_cov, window=roll_window)} "
                f"floor={hygiene:.4f}",
            )
    # Prefer stored range/hold metrics (Raptor v8). Parse legacy messages as fallback.
    hold_ratio = float(getattr(receipt, "hold_ratio", 0.0) or 0.0)
    range_flat = float(getattr(receipt, "range_flat_ratio", 0.0) or 0.0)
    range_rt = int(getattr(receipt, "range_round_trips", 0) or 0)
    range_total = int(getattr(receipt, "range_total_signals", 0) or 0)
    range_hold = int(getattr(receipt, "range_hold_signals", 0) or 0)
    range_flat_bars = int(getattr(receipt, "range_flat_bars", 0) or 0)
    hold_signals = int(getattr(receipt, "hold_signals", 0) or 0)
    total_signals = int(getattr(receipt, "total_signals", 0) or 0)
    if range_total <= 0 and "range_flat_ratio=" in str(receipt.message):
        # Legacy receipts: parse flat ratio + round_trips from message.
        import re

        m_flat = re.search(r"range_flat_ratio=([0-9.]+)%", receipt.message)
        m_rt = re.search(r"round_trips=(\d+)", receipt.message)
        m_ticks = re.search(r"range_ticks=(\d+)", receipt.message)
        if m_flat:
            range_flat = float(m_flat.group(1)) / 100.0
        if m_rt:
            range_rt = int(m_rt.group(1))
        if m_ticks:
            range_total = int(m_ticks.group(1))
        elif range_flat > 0:
            range_total = max(50, int(receipt.trades) * 10)
        range_flat_bars = int(round(range_flat * max(1, range_total)))
    if total_signals <= 0:
        total_signals = max(1, int(receipt.trades) * 20)
    if hold_signals <= 0 and hold_ratio > 0:
        hold_signals = int(round(hold_ratio * total_signals))
    if hold_ratio <= 0 and total_signals > 0 and hold_signals > 0:
        hold_ratio = float(hold_signals) / float(total_signals)
    # Stage3: derive hold from winrate message if needed
    if stage == CurriculumStage.STAGE3_MIXED and hold_ratio <= 0 and "hold=" in receipt.message:
        import re

        m_hold = re.search(r"hold=([0-9.]+)%", receipt.message)
        if m_hold:
            hold_ratio = float(m_hold.group(1)) / 100.0
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
        provisional=False if not provisional_ok else receipt.provisional,
        allow_provisional=provisional_ok,
        oracle_patterns=0 if not provisional_ok else 10_000,
        buffer_size=0 if not provisional_ok else 10_000,
        rolling_winrate=gate_roll,
        policy_entropy=getattr(receipt, "policy_entropy", None),
        stage_total_pnl=getattr(receipt, "stage_total_pnl", None),
    )
    if not reeval.passed:
        return False, f"re_eval_failed:{reeval.message}"
    if not provisional_ok and receipt_message_is_soft_pass(reeval.message):
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
