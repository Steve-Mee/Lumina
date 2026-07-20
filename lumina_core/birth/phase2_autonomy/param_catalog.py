"""Safe birth recovery parameter catalog — never risk/capital keys."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.adaptive_parameter_manager import (
    AdaptiveParameterPatch,
    WallAdaptationState,
    compute_parameter_patch,
)
from lumina_core.birth.meta_controller import LearningHealth
from lumina_core.birth.phase2_autonomy.contracts import Phase2ParamAdjustmentProposal

# Birth recovery only (matches adaptive_parameter_manager clamp spirit).
BIRTH_SAFE_PARAM_CATALOG: dict[str, dict[str, float]] = {
    "winrate_trend_window": {"min": 5.0, "max": 24.0, "default": 12.0},
    "reward_trend_window": {"min": 5.0, "max": 24.0, "default": 12.0},
    "chunk_target": {"min": 1.0, "max": 50.0, "default": 8.0},
    "exploration_chunk_size": {"min": 1.0, "max": 50.0, "default": 8.0},
    "certified_stage_stall_wall_sec": {"min": 300.0, "max": 7200.0, "default": 600.0},
}

FORBIDDEN_PARAM_KEYS: frozenset[str] = frozenset(
    {
        "max_risk_percent",
        "drawdown_kill_percent",
        "kelly_fraction",
        "daily_loss_cap",
        "max_total_open_risk",
        "max_open_risk_per_instrument",
        "position_size",
        "leverage",
        "order_qty",
    }
)


def validate_param_changes(changes: dict[str, float | int]) -> list[str]:
    """Return violation tokens for out-of-catalog or out-of-bounds keys."""
    violations: list[str] = []
    for key, value in (changes or {}).items():
        k = str(key)
        if k in FORBIDDEN_PARAM_KEYS:
            violations.append(f"forbidden:{k}")
            continue
        if k not in BIRTH_SAFE_PARAM_CATALOG:
            violations.append(f"not_whitelisted:{k}")
            continue
        bounds = BIRTH_SAFE_PARAM_CATALOG[k]
        lo, hi = float(bounds["min"]), float(bounds["max"])
        try:
            v = float(value)
        except (TypeError, ValueError):
            violations.append(f"non_numeric:{k}")
            continue
        if v < lo or v > hi:
            violations.append(f"out_of_bounds:{k}={v}")
    return violations


def clamp_param_value(key: str, value: float | int) -> float | int | None:
    """Clamp a catalog key to bounds; return None if not whitelisted."""
    k = str(key)
    if k in FORBIDDEN_PARAM_KEYS or k not in BIRTH_SAFE_PARAM_CATALOG:
        return None
    bounds = BIRTH_SAFE_PARAM_CATALOG[k]
    lo, hi = float(bounds["min"]), float(bounds["max"])
    v = max(lo, min(hi, float(value)))
    if k.endswith("_window") or k in {
        "chunk_target",
        "exploration_chunk_size",
        "certified_stage_stall_wall_sec",
    }:
        return int(round(v))
    return v


def propose_param_adjustment(
    *,
    learning_health: LearningHealth | str = LearningHealth.FLAT,
    current_winrate_window: int = 12,
    current_reward_window: int = 12,
    cfg: Any | None = None,
    adaptation_tier: int = 0,
    post_volume_gate: bool = False,
    current_chunk_target: int | None = None,
) -> Phase2ParamAdjustmentProposal:
    """Build a bounded param proposal on top of compute_parameter_patch."""
    if cfg is None:
        from lumina_core.birth.config import BirthCurriculumConfig

        cfg = BirthCurriculumConfig()

    patch: AdaptiveParameterPatch = compute_parameter_patch(
        learning_health=learning_health,
        current_winrate_window=int(current_winrate_window),
        current_reward_window=int(current_reward_window),
        cfg=cfg,
        adaptation_tier=int(adaptation_tier),
        post_volume_gate=bool(post_volume_gate),
    )

    changes: dict[str, float | int] = {}
    if patch.winrate_trend_window is not None:
        clamped = clamp_param_value("winrate_trend_window", patch.winrate_trend_window)
        if clamped is not None:
            changes["winrate_trend_window"] = clamped
    if patch.reward_trend_window is not None:
        clamped = clamp_param_value("reward_trend_window", patch.reward_trend_window)
        if clamped is not None:
            changes["reward_trend_window"] = clamped
    if patch.chunk_target is not None:
        clamped = clamp_param_value("chunk_target", patch.chunk_target)
        if clamped is not None:
            changes["chunk_target"] = clamped
    elif current_chunk_target is not None and post_volume_gate:
        clamped = clamp_param_value("chunk_target", current_chunk_target)
        if clamped is not None:
            changes["chunk_target"] = clamped

    rationale = patch.rationale or "phase2_param_neutral"
    if patch.expand_data:
        rationale = f"{rationale};expand_data_hint" if rationale else "expand_data_hint"

    return Phase2ParamAdjustmentProposal(
        changes=changes,
        rationale=rationale,
        risk_touching=False,
    )


def apply_param_proposal_to_state(
    state: WallAdaptationState,
    proposal: Phase2ParamAdjustmentProposal,
) -> WallAdaptationState:
    """Apply gated param changes onto WallAdaptationState (in-memory, no restart)."""
    if not proposal.changes:
        return state
    violations = validate_param_changes(proposal.changes)
    if violations:
        return state
    wr = proposal.changes.get("winrate_trend_window")
    rw = proposal.changes.get("reward_trend_window")
    if wr is not None:
        state.effective_winrate_window = int(clamp_param_value("winrate_trend_window", wr) or wr)
    if rw is not None:
        state.effective_reward_window = int(clamp_param_value("reward_trend_window", rw) or rw)
    return state


__all__ = [
    "BIRTH_SAFE_PARAM_CATALOG",
    "FORBIDDEN_PARAM_KEYS",
    "apply_param_proposal_to_state",
    "clamp_param_value",
    "propose_param_adjustment",
    "validate_param_changes",
]
