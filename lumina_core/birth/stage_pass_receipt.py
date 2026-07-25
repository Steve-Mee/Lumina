"""Immutable stage graduation receipts (fail-closed curriculum integrity)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig, BRO_ENGINE_VERSION
from lumina_core.birth.curriculum import (
    CurriculumStage,
    StageResult,
    evaluate_stage_pass,
    stage1_winrate_pass_threshold,
    stage_pass_trades,
)
from lumina_core.birth.stage_scorecard import pass_criteria_for_stage, parse_curriculum_stage
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_pass_receipt")

ORDERED_STAGE_VALUES = (
    CurriculumStage.STAGE1_TREND.value,
    CurriculumStage.STAGE2_RANGE.value,
    CurriculumStage.STAGE3_MIXED.value,
    CurriculumStage.STAGE5_PROFIT_VAL.value,
    CurriculumStage.STAGE6_RISK_DISCIPLINE.value,
    CurriculumStage.STAGE7_HOLDOUT_PROFILE.value,
)


@dataclass(slots=True)
class StagePassReceipt:
    stage: str
    trades: int
    wins: int
    winrate: float
    required_trades: int
    pass_criteria_id: str
    provisional: bool
    passed_at: str
    engine_version: str
    message: str = ""
    winrate_gate: float | None = None
    # Raptor v8: persist stage2/3 metrics so integrity re-eval does not amnesia.
    hold_ratio: float = 0.0
    range_flat_ratio: float = 0.0
    range_round_trips: int = 0
    range_total_signals: int = 0
    range_hold_signals: int = 0
    range_flat_bars: int = 0
    hold_signals: int = 0
    total_signals: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> StagePassReceipt | None:
        if not isinstance(raw, dict):
            return None
        stage = str(raw.get("stage", "") or "").strip().lower()
        if not stage:
            return None
        try:
            return cls(
                stage=stage,
                trades=max(0, int(raw.get("trades", 0) or 0)),
                wins=max(0, int(raw.get("wins", 0) or 0)),
                winrate=float(raw.get("winrate", 0.0) or 0.0),
                required_trades=max(0, int(raw.get("required_trades", 0) or 0)),
                pass_criteria_id=str(raw.get("pass_criteria_id", "") or ""),
                provisional=bool(raw.get("provisional", False)),
                passed_at=str(raw.get("passed_at", "") or ""),
                engine_version=str(raw.get("engine_version", "") or ""),
                message=str(raw.get("message", "") or ""),
                winrate_gate=(
                    float(raw["winrate_gate"])
                    if raw.get("winrate_gate") is not None
                    else None
                ),
                hold_ratio=float(raw.get("hold_ratio", 0.0) or 0.0),
                range_flat_ratio=float(raw.get("range_flat_ratio", 0.0) or 0.0),
                range_round_trips=max(0, int(raw.get("range_round_trips", 0) or 0)),
                range_total_signals=max(0, int(raw.get("range_total_signals", 0) or 0)),
                range_hold_signals=max(0, int(raw.get("range_hold_signals", 0) or 0)),
                range_flat_bars=max(0, int(raw.get("range_flat_bars", 0) or 0)),
                hold_signals=max(0, int(raw.get("hold_signals", 0) or 0)),
                total_signals=max(0, int(raw.get("total_signals", 0) or 0)),
            )
        except (TypeError, ValueError):
            return None


def parse_stage_pass_receipts(raw: Any) -> list[StagePassReceipt]:
    if not isinstance(raw, list):
        return []
    out: list[StagePassReceipt] = []
    for item in raw:
        receipt = StagePassReceipt.from_dict(item) if isinstance(item, dict) else None
        if receipt is not None:
            out.append(receipt)
    return out


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
    )


_SOFT_PASS_MARKERS = (
    "oracle_soft_pass",
    "gen0_provisional",
    "oracle_gen0_research_pass",
)


def receipt_message_is_soft_pass(message: str) -> bool:
    text = str(message or "").lower()
    return any(marker in text for marker in _SOFT_PASS_MARKERS)


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
    # Stage1: hard winrate gate must hold for certified (and any non-provisional receipt).
    if stage == CurriculumStage.STAGE1_TREND and not provisional_ok:
        wr_gate = float(
            receipt.winrate_gate
            if receipt.winrate_gate is not None
            else stage1_winrate_pass_threshold(cfg)
        )
        if float(receipt.winrate) < wr_gate:
            return False, f"stage1_winrate_below_gate wr={receipt.winrate:.4f} gate={wr_gate:.4f}"
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
        rolling_winrate=float(receipt.winrate),
    )
    if not reeval.passed:
        return False, f"re_eval_failed:{reeval.message}"
    if not provisional_ok and receipt_message_is_soft_pass(reeval.message):
        return False, "re_eval_soft_pass_rejected"
    return True, "ok"


def receipt_for_stage(receipts: list[StagePassReceipt], stage_value: str) -> StagePassReceipt | None:
    target = str(stage_value or "").strip().lower()
    for receipt in reversed(receipts):
        if receipt.stage == target:
            return receipt
    return None


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


@dataclass(slots=True)
class CurriculumIntegrityAudit:
    ok: bool
    stages_passed: list[str]
    stage_pass_receipts: list[StagePassReceipt]
    invalid_reasons: list[str]
    reset_applied: bool

    def to_progress_fields(self) -> dict[str, Any]:
        return {
            "curriculum_integrity_ok": self.ok,
            "curriculum_integrity_reset": self.reset_applied,
            "curriculum_integrity_reasons": list(self.invalid_reasons),
        }


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


def fresh_stage_metrics_for_stage(stage: CurriculumStage) -> dict[str, Any]:
    """Reset per-stage counters when advancing curriculum."""
    return {
        "stage_trades": 0,
        "stage_wins": 0,
        "stage_hold_signals": 0,
        "stage_total_signals": 0,
        "stage_range_hold_signals": 0,
        "stage_range_total_signals": 0,
        "stage_range_flat_bars": 0,
        "stage_range_round_trips": 0,
        "stage_range_flat_ratio": 0.0,
        "patterns_mined": 0,
        "curriculum_stage_scope": stage.value,
    }
