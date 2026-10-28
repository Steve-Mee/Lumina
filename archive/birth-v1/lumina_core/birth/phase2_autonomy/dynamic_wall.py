"""Pure dynamic wall threshold proposals (regime + progress aware).

Does not replace wall_trigger_engine — only proposes clamped input adjustments
for evaluate_wall_trigger / handler context when Phase 2 gate allows.
"""

from __future__ import annotations

from typing import Any

from lumina_core.birth.phase2_autonomy.contracts import Phase2WallAdjustmentProposal

# Documented clamp bounds (ADR-0034)
STALL_WALL_MULT_MIN = 0.75
STALL_WALL_MULT_MAX = 1.50
STAGNATION_DELTA_MIN = -1
STAGNATION_DELTA_MAX = 2


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _normalize_regime(regime: str | None) -> str:
    raw = str(regime or "UNKNOWN").strip().upper()
    if not raw:
        return "UNKNOWN"
    if "TREND" in raw:
        return "TREND"
    if "RANGE" in raw or "CHOP" in raw or "SIDE" in raw:
        return "RANGE"
    if "MIX" in raw:
        return "MIXED"
    if raw in {"TREND", "RANGE", "MIXED", "UNKNOWN"}:
        return raw
    return "UNKNOWN"


def propose_dynamic_wall_adjustment(
    *,
    stage: str = "",
    stage_trades: int = 0,
    required: int = 0,
    winrate_slope: float = 0.0,
    winrate_stagnation_count: int = 0,
    hold_stagnation_count: int = 0,
    elapsed_stage_sec: float = 0.0,
    base_stall_wall_sec: float = 300.0,
    regime: str | None = None,
    cfg: Any | None = None,
) -> Phase2WallAdjustmentProposal:
    """Propose clamped wall threshold multipliers based on regime and progress.

    Pure function — no side effects, no gate evaluation.
    """
    req = max(1, int(required or 1))
    progress = max(0.0, min(2.0, float(stage_trades) / float(req)))
    regime_n = _normalize_regime(regime)
    base_wall = float(base_stall_wall_sec)
    if cfg is not None:
        try:
            base_wall = float(getattr(cfg, "certified_stage_stall_wall_sec", base_wall) or base_wall)
        except (TypeError, ValueError):
            pass
    base_wall = max(300.0, base_wall)

    mult = 1.0
    stagn_delta = 0
    parts: list[str] = []

    # Progress: early stage → slightly longer wall; far past gate → shorter patience
    if progress < 0.5:
        mult *= 1.15
        parts.append("early_progress_extend")
    elif progress >= 1.2:
        mult *= 0.90
        parts.append("past_gate_tighten")

    # Regime: range often needs more time; strong trend stagnation can tighten
    if regime_n == "RANGE":
        mult *= 1.10
        stagn_delta += 1
        parts.append("range_patience")
    elif regime_n == "TREND" and winrate_slope < -0.01:
        mult *= 0.95
        stagn_delta -= 0  # keep base; slope handled below
        parts.append("trend_negative_slope")
    elif regime_n == "MIXED":
        mult *= 1.05
        parts.append("mixed_mild_extend")

    # Slope / stagnation
    if winrate_slope < -0.02:
        mult *= 0.92
        stagn_delta = max(stagn_delta - 1, STAGNATION_DELTA_MIN)
        parts.append("negative_winrate_slope")
    elif winrate_slope > 0.02 and progress >= 0.8:
        mult *= 1.05
        stagn_delta += 1
        parts.append("improving_near_target")

    if winrate_stagnation_count >= 3 or hold_stagnation_count >= 3:
        mult *= 0.90
        parts.append("high_stagnation_tighten")

    # Elapsed vs base wall (time pressure)
    if base_wall > 0 and elapsed_stage_sec >= base_wall * 1.5:
        mult *= 0.88
        parts.append("long_elapsed_tighten")

    mult = _clamp(mult, STALL_WALL_MULT_MIN, STALL_WALL_MULT_MAX)
    stagn_delta = int(
        max(STAGNATION_DELTA_MIN, min(STAGNATION_DELTA_MAX, stagn_delta))
    )

    if not parts:
        parts.append("neutral_baseline")

    return Phase2WallAdjustmentProposal(
        stall_wall_sec_multiplier=round(mult, 4),
        stagnation_rollouts_delta=stagn_delta,
        regime=regime_n,
        progress_ratio=round(progress, 4),
        rationale=";".join(parts) + f";stage={stage or 'unknown'}",
        risk_touching=False,
    )


def apply_wall_adjustment_to_thresholds(
    *,
    base_stall_wall_sec: float,
    base_winrate_stagnation_rollouts: int,
    base_hold_stagnation_rollouts: int,
    proposal: Phase2WallAdjustmentProposal,
) -> dict[str, float | int]:
    """Materialize proposal into concrete thresholds for evaluate_wall_trigger context."""
    wall = max(
        300.0,
        float(base_stall_wall_sec) * float(proposal.stall_wall_sec_multiplier),
    )
    wr = max(1, int(base_winrate_stagnation_rollouts) + int(proposal.stagnation_rollouts_delta))
    hold = max(1, int(base_hold_stagnation_rollouts) + int(proposal.stagnation_rollouts_delta))
    return {
        "effective_stall_wall_sec": int(round(wall)),
        "effective_winrate_stagnation_rollouts": wr,
        "effective_hold_stagnation_rollouts": hold,
    }


__all__ = [
    "STAGNATION_DELTA_MAX",
    "STAGNATION_DELTA_MIN",
    "STALL_WALL_MULT_MAX",
    "STALL_WALL_MULT_MIN",
    "apply_wall_adjustment_to_thresholds",
    "propose_dynamic_wall_adjustment",
]
