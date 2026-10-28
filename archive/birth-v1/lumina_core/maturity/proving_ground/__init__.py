"""Proving Ground bounded context — driving test before capital (ADR-0052)."""

from lumina_core.maturity.proving_ground.law import (
    N_G_MIN,
    ProvingGroundPassResult,
    ProvingGroundSnapshot,
    evaluate_proving_ground_exit,
    evaluate_proving_ground_pass,
    snapshot_from_workspace,
)

__all__ = [
    "N_G_MIN",
    "ProvingGroundPassResult",
    "ProvingGroundSnapshot",
    "evaluate_proving_ground_exit",
    "evaluate_proving_ground_pass",
    "snapshot_from_workspace",
]
