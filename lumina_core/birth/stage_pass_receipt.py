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
    stage_pass_trades,
)
from lumina_core.birth.stage_scorecard import pass_criteria_for_stage, parse_curriculum_stage
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_pass_receipt")

ORDERED_STAGE_VALUES = (
    CurriculumStage.STAGE1_TREND.value,
    CurriculumStage.STAGE2_RANGE.value,
    CurriculumStage.STAGE3_MIXED.value,
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
) -> StagePassReceipt:
    required = stage_pass_trades(stage, cfg)
    criteria = pass_criteria_for_stage(stage, cfg=cfg)
    winrate = float(result.wins) / float(max(1, result.trades))
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
    )


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
    provisional_ok = bool(allow_provisional) if allow_provisional is not None else (
        str(training_mode).strip().lower() == "practice" or cfg.allow_provisional_pass
    )
    if receipt.provisional and not provisional_ok:
        return False, "provisional_not_allowed_in_certified_mode"
    reeval = evaluate_stage_pass(
        stage,
        trades=receipt.trades,
        wins=receipt.wins,
        hold_signals=0,
        total_signals=max(1, receipt.trades),
        constitution_violations=0,
        target_trades=receipt.required_trades,
        cfg=cfg,
        provisional=receipt.provisional,
        allow_provisional=provisional_ok,
    )
    if not reeval.passed:
        return False, f"re_eval_failed:{reeval.message}"
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
    if stage == CurriculumStage.STAGE1_TREND and live_winrate is not None and live_winrate < 0.45:
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
