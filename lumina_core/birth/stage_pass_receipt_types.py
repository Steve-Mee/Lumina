"""Stage pass receipt types + small pure helpers."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from lumina_core.birth.curriculum import CurriculumStage

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
    # Starship: EdgeScore integrity fields.
    edgescore: float | None = None
    policy_entropy: float | None = None
    stage_total_pnl: float | None = None
    # Hygiene evidence: rolling may alone satisfy EdgeScore hygiene when eligible.
    rolling_winrate: float | None = None
    rolling_winrate_source: str | None = None
    rolling_window_trades_covered: int | None = None
    hygiene_wr_source: str | None = None

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
                edgescore=(
                    float(raw["edgescore"]) if raw.get("edgescore") is not None else None
                ),
                policy_entropy=(
                    float(raw["policy_entropy"])
                    if raw.get("policy_entropy") is not None
                    else None
                ),
                stage_total_pnl=(
                    float(raw["stage_total_pnl"])
                    if raw.get("stage_total_pnl") is not None
                    else None
                ),
                rolling_winrate=(
                    float(raw["rolling_winrate"])
                    if raw.get("rolling_winrate") is not None
                    else None
                ),
                rolling_winrate_source=(
                    str(raw["rolling_winrate_source"])
                    if raw.get("rolling_winrate_source") is not None
                    else None
                ),
                rolling_window_trades_covered=(
                    max(0, int(raw["rolling_window_trades_covered"]))
                    if raw.get("rolling_window_trades_covered") is not None
                    else None
                ),
                hygiene_wr_source=(
                    str(raw["hygiene_wr_source"])
                    if raw.get("hygiene_wr_source") is not None
                    else None
                ),
            )
        except (TypeError, ValueError):
            return None


_SOFT_PASS_MARKERS = (
    "oracle_soft_pass",
    "gen0_provisional",
    "oracle_gen0_research_pass",
)


def parse_stage_pass_receipts(raw: Any) -> list[StagePassReceipt]:
    if not isinstance(raw, list):
        return []
    out: list[StagePassReceipt] = []
    for item in raw:
        receipt = StagePassReceipt.from_dict(item) if isinstance(item, dict) else None
        if receipt is not None:
            out.append(receipt)
    return out


def receipt_message_is_soft_pass(message: str) -> bool:
    text = str(message or "").lower()
    return any(marker in text for marker in _SOFT_PASS_MARKERS)


def receipt_for_stage(receipts: list[StagePassReceipt], stage_value: str) -> StagePassReceipt | None:
    target = str(stage_value or "").strip().lower()
    for receipt in reversed(receipts):
        if receipt.stage == target:
            return receipt
    return None


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
