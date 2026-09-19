"""Awakening bounded context — eyes open, prefer-better, no substitution (ADR-0049)."""

from lumina_core.maturity.awakening.law import (
    N_B_MIN,
    AwakeningPassResult,
    AwakeningSnapshot,
    evaluate_awakening_exit,
    evaluate_awakening_pass,
    snapshot_from_workspace,
)
__all__ = [
    "N_B_MIN",
    "AwakeningPassResult",
    "AwakeningSnapshot",
    "evaluate_awakening_exit",
    "evaluate_awakening_pass",
    "snapshot_from_workspace",
]
