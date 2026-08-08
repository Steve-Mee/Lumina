"""Phoenix no-lift dispatch helpers (kept out of organism_autonomy import boundary)."""
from __future__ import annotations

from typing import Any


def try_no_lift_phoenix_decision(
    *,
    cfg: Any,
    autonomy_state: Any,
    stall_reason: str,
) -> Any:
    """Start a bounded phoenix cycle when no-lift brake fires."""
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
