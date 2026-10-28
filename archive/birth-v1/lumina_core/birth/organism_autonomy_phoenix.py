"""Phoenix no-lift dispatch helpers (kept out of organism_autonomy import boundary)."""
from __future__ import annotations

from typing import Any, Mapping


def _occupancy_fencepost_from_context(
    pending: Mapping[str, Any] | None,
    starship_context: Mapping[str, Any] | None,
) -> bool:
    from lumina_core.birth.foundation_occupancy_envelope import (
        occupancy_fencepost_blocks_expand,
    )

    pending_d = dict(pending or {})
    starship = dict(starship_context or {})
    occ_raw = starship.get("occupancy", pending_d.get("occupancy"))
    try:
        occupancy = float(occ_raw) if occ_raw is not None else None
    except (TypeError, ValueError):
        occupancy = None
    armed_raw = starship.get("occupancy_exam_armed", pending_d.get("occupancy_exam_armed"))
    armed = None if armed_raw is None else bool(armed_raw)
    return occupancy_fencepost_blocks_expand(
        occupancy=occupancy,
        occupancy_exam_armed=armed,
    )


def expansion_horizon_exhausted(
    pending: Mapping[str, Any] | None = None,
    starship_context: Mapping[str, Any] | None = None,
) -> bool:
    """True when 90→180→365 stall-expand is spent. Phoenix must not request expand."""
    pending_d = dict(pending or {})
    starship = dict(starship_context or {})
    if bool(starship.get("expansion_exhausted") or pending_d.get("expansion_exhausted")):
        return True
    step = int(starship.get("expansion_step") or pending_d.get("expansion_step") or 0)
    return step >= 2


def _fencepost_retry_decision(
    *,
    cfg: Any,
    autonomy_state: Any,
    stall_reason: str,
    pending: Mapping[str, Any] | None,
    starship_context: Mapping[str, Any] | None,
) -> Any:
    """Bounded autonomous retry_stage. Expand is never the fencepost fix."""
    from lumina_core.birth.organism_autonomy import AutonomyDecision, RecoveryDispatch

    pending_d = dict(pending or {})
    starship = dict(starship_context or {})
    retries = int(
        starship.get("retries_this_stage") or pending_d.get("retries_this_stage") or 0
    )
    max_retries = max(1, int(getattr(cfg, "max_stage_retries", 3) or 3))
    metrics = autonomy_state.to_metrics()
    metrics["occupancy_fencepost"] = True
    metrics["no_lift_phoenix"] = False
    metrics["retries_this_stage"] = retries
    if retries >= max_retries:
        return AutonomyDecision(
            dispatch=RecoveryDispatch.TERMINAL_NOTIFY_ONLY,
            needs_attention=True,
            retryable=False,
            stall_reason=stall_reason or "phoenix_cycle",
            recommended_action="retry_stage_or_wipe",
            autonomy_metrics=metrics,
            message=(
                "Occupancy exam fencepost — stage retries exhausted. "
                "Operator retry_stage or wipe. expand_data cannot unstick 0.25 chatter."
            ),
        )
    autonomy_state.autonomous_recovery_count += 1
    return AutonomyDecision(
        dispatch=RecoveryDispatch.PHOENIX_RESUME,
        needs_attention=False,
        retryable=True,
        stall_reason="occupancy_fencepost",
        recommended_action="retry_stage",
        autonomy_metrics=metrics,
        message=(
            "Occupancy exam fencepost — autonomous retry_stage "
            f"(sample reset {retries + 1}/{max_retries}). expand_data blocked."
        ),
    )


def try_no_lift_phoenix_decision(
    *,
    cfg: Any,
    autonomy_state: Any,
    stall_reason: str,
    pending: Mapping[str, Any] | None = None,
    starship_context: Mapping[str, Any] | None = None,
) -> Any:
    """Start a bounded phoenix cycle when no-lift brake fires."""
    if expansion_horizon_exhausted(pending, starship_context):
        return None
    pending_d = dict(pending or {})
    if str(pending_d.get("blocker_metric") or "") == "policy_sample":
        return _fencepost_retry_decision(
            cfg=cfg,
            autonomy_state=autonomy_state,
            stall_reason=stall_reason,
            pending=pending,
            starship_context=starship_context,
        )
    fencepost = _occupancy_fencepost_from_context(pending, starship_context)
    if fencepost:
        return _fencepost_retry_decision(
            cfg=cfg,
            autonomy_state=autonomy_state,
            stall_reason=stall_reason,
            pending=pending,
            starship_context=starship_context,
        )
    from lumina_core.birth.organism_autonomy import (
        AutonomyDecision,
        RecoveryDispatch,
        map_recommended_to_service_action,
    )
    from lumina_core.birth.phoenix_loop import (
        PHOENIX_CYCLE_REASON,
        begin_phoenix_cycle,
        select_phoenix_novelty,
    )

    novelty = select_phoenix_novelty(autonomy_state.phoenix, cfg=cfg)
    if novelty.value in {"expand_data", "widen_horizon"} and expansion_horizon_exhausted(
        pending, starship_context
    ):
        return None
    begin_phoenix_cycle(
        autonomy_state.phoenix,
        novelty=novelty,
        stall_reason=stall_reason or "no_lift_brake",
    )
    autonomy_state.autonomous_recovery_count += 1
    service_action = map_recommended_to_service_action(novelty.value)
    metrics = autonomy_state.to_metrics()
    metrics["phoenix_novelty"] = novelty.value
    metrics["no_lift_phoenix"] = True
    return AutonomyDecision(
        dispatch=RecoveryDispatch.PHOENIX_RESUME,
        needs_attention=False,
        retryable=True,
        stall_reason=PHOENIX_CYCLE_REASON,
        recommended_action=service_action,
        autonomy_metrics=metrics,
        message=(
            f"No-lift brake: bounded phoenix ({novelty.value}) "
            f"cycle {autonomy_state.phoenix.phoenix_count}/"
            f"{max(1, int(cfg.phoenix_max_cycles))}."
        ),
    )


def try_ladder_phoenix_decision(
    *,
    cfg: Any,
    autonomy_state: Any,
    stall_reason: str,
    recommended: str,
    curriculum_stage: str,
    circuit_breaker: bool,
    pending: Mapping[str, Any] | None = None,
    starship_context: Mapping[str, Any] | None = None,
) -> Any:
    """Phoenix after remediation/plateau exhaustion — never expand a closed horizon."""
    if expansion_horizon_exhausted(pending, starship_context):
        return None
    if _occupancy_fencepost_from_context(pending, starship_context):
        return _fencepost_retry_decision(
            cfg=cfg,
            autonomy_state=autonomy_state,
            stall_reason=stall_reason,
            pending=pending,
            starship_context=starship_context,
        )
    from lumina_core.birth.death_spiral_guard import (
        consume_novelty_budget,
        reset_after_novelty,
        should_widen_data_horizon,
    )
    from lumina_core.birth.organism_autonomy import (
        AutonomyDecision,
        RecoveryDispatch,
        map_recommended_to_service_action,
    )
    from lumina_core.birth.phoenix_loop import (
        PHOENIX_CYCLE_REASON,
        select_phoenix_novelty,
    )

    widen = should_widen_data_horizon(
        autonomy_state.death_spiral,
        phoenix_count=autonomy_state.phoenix.phoenix_count,
        cfg=cfg,
    )
    novelty = select_phoenix_novelty(
        autonomy_state.phoenix,
        cfg=cfg,
        circuit_breaker=widen or circuit_breaker,
    ).value
    if novelty in {"expand_data", "widen_horizon"} and expansion_horizon_exhausted(
        pending, starship_context
    ):
        return None
    if consume_novelty_budget(autonomy_state.death_spiral) or widen:
        reset_after_novelty(autonomy_state.death_spiral, cfg=cfg)
        autonomy_state.autonomous_recovery_count += 1
        service_action = map_recommended_to_service_action(
            "widen_horizon" if novelty == "widen_horizon" else recommended
        )
        if novelty in {"expand_data", "widen_horizon"}:
            service_action = "expand_and_retry"
        metrics = autonomy_state.to_metrics()
        metrics["phoenix_novelty"] = novelty
        metrics["curriculum_stage"] = curriculum_stage
        return AutonomyDecision(
            dispatch=RecoveryDispatch.PHOENIX_RESUME,
            needs_attention=False,
            retryable=True,
            stall_reason=PHOENIX_CYCLE_REASON,
            recommended_action=service_action,
            checkpoint_patch=None,
            autonomy_metrics=metrics,
            message=f"Phoenix cycle requested: {novelty}",
        )
    return None
