"""Post-cutover canary window — auto restore on DD/violation (K13)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lumina_core.evolution.cutover import restore_champion


@dataclass(slots=True)
class CanaryConfig:
    max_trades: int = 10
    dd_limit: float = 0.02
    window_sec: int = 3600


def canary_should_restore(
    *,
    trades: int,
    drawdown: float,
    constitution_violations: int,
    cfg: CanaryConfig | None = None,
) -> bool:
    conf = cfg or CanaryConfig()
    if int(constitution_violations) > 0:
        return True
    if float(drawdown) >= float(conf.dd_limit):
        return True
    _ = trades
    return False


def observe_canary(
    workspace: str | object,
    *,
    freeze_id: str,
    trades: int,
    drawdown: float,
    constitution_violations: int = 0,
    cfg: CanaryConfig | None = None,
) -> dict[str, Any]:
    if not canary_should_restore(
        trades=trades,
        drawdown=drawdown,
        constitution_violations=constitution_violations,
        cfg=cfg,
    ):
        return {"restore_invoked": False, "reason": "canary_ok"}
    restored = restore_champion(str(workspace), freeze_id)
    from lumina_core.evolution.council import compose_dossier
    from lumina_core.evolution.council_notify import notify_council

    notify_council(
        str(workspace),
        "real",
        compose_dossier(
            question="canary breach — champion restored from freeze",
            twin_values_ok=True,
            constitution_violations=int(constitution_violations),
            risk_dd=float(drawdown),
            swarm_fitness_delta=0.0,
            evolution_proof_passed=False,
        ),
    )
    return {
        "restore_invoked": bool(restored.get("restored")),
        "reason": "canary_breach",
        "restore": restored,
    }
