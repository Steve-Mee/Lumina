"""Stage pass receipt types + small pure helpers."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from lumina_core.birth.curriculum import CurriculumStage

ORDERED_STAGE_VALUES = (
    CurriculumStage.STAGE1_TREND.value,
    CurriculumStage.STAGE2_RANGE.value,
    CurriculumStage.STAGE3_MIXED.value,
    CurriculumStage.STAGE4_VIABLE_PLANT.value,
    CurriculumStage.STAGE5_PROBE_HANDOFF.value,
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
    # Stage-2 skill split (pilot vs plant) — integrity re-eval must use same SSOT.
    policy_trades: int | None = None
    policy_wins: int | None = None
    plant_trades: int | None = None
    plant_wins: int | None = None
    closes_stop: int = 0
    closes_target: int = 0
    closes_time_stop: int = 0
    closes_flatten: int = 0
    closes_unknown: int = 0
    schema: str = ""
    median_loss_r: float | None = None
    mean_r: float | None = None
    occupancy: float | None = None
    edge: float | None = None
    p_ft: float | None = None
    e_mech: float | None = None
    geometry_net_rr: float | None = None
    unique_calendar_days: int | None = None
    oos_sharpe: float | None = None
    oos_dd_pct: float | None = None

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
                policy_trades=(
                    max(0, int(raw["policy_trades"]))
                    if raw.get("policy_trades") is not None
                    else None
                ),
                policy_wins=(
                    max(0, int(raw["policy_wins"]))
                    if raw.get("policy_wins") is not None
                    else None
                ),
                plant_trades=(
                    max(0, int(raw["plant_trades"]))
                    if raw.get("plant_trades") is not None
                    else None
                ),
                plant_wins=(
                    max(0, int(raw["plant_wins"]))
                    if raw.get("plant_wins") is not None
                    else None
                ),
                closes_stop=max(0, int(raw.get("closes_stop", 0) or 0)),
                closes_target=max(0, int(raw.get("closes_target", 0) or 0)),
                closes_time_stop=max(0, int(raw.get("closes_time_stop", 0) or 0)),
                closes_flatten=max(0, int(raw.get("closes_flatten", 0) or 0)),
                closes_unknown=max(0, int(raw.get("closes_unknown", 0) or 0)),
                schema=str(raw.get("schema", "") or ""),
                median_loss_r=(
                    float(raw["median_loss_r"])
                    if raw.get("median_loss_r") is not None
                    else None
                ),
                mean_r=float(raw["mean_r"]) if raw.get("mean_r") is not None else None,
                occupancy=(
                    float(raw["occupancy"]) if raw.get("occupancy") is not None else None
                ),
                edge=float(raw["edge"]) if raw.get("edge") is not None else None,
                p_ft=float(raw["p_ft"]) if raw.get("p_ft") is not None else None,
                e_mech=float(raw["e_mech"]) if raw.get("e_mech") is not None else None,
                geometry_net_rr=(
                    float(raw["geometry_net_rr"])
                    if raw.get("geometry_net_rr") is not None
                    else None
                ),
                unique_calendar_days=(
                    max(0, int(raw["unique_calendar_days"]))
                    if raw.get("unique_calendar_days") is not None
                    else None
                ),
                oos_sharpe=(
                    float(raw["oos_sharpe"]) if raw.get("oos_sharpe") is not None else None
                ),
                oos_dd_pct=(
                    float(raw["oos_dd_pct"]) if raw.get("oos_dd_pct") is not None else None
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
