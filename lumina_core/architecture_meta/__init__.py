"""Architecture Meta layer — next evolution: proposes own architecture improvements via sandboxed mutations.

Radically simple + measurable.
Full constitution + human-in-the-loop promotion gates (fail-closed).
Default disabled. Agents propose; humans (Final Arbitration) promote.

See docs/adr/0030-architecture-meta-controller.md.
"""

from __future__ import annotations

__all__ = [
    "ArchHealthSnapshot",
    "ArchMutationProposal",
    "ArchMutationType",
    "ArchSandboxResult",
    "ArchitectureMetaController",
    "ArchitectureMutationSandbox",
    "ArchitectureConstitution",
    "run_architecture_meta_dry_scan",
]

# Lazy imports to keep surface small
from .controller import (
    ArchHealthSnapshot,
    ArchMutationProposal,
    ArchMutationType,
    ArchitectureMetaController,
)
from .sandbox import ArchSandboxResult, ArchitectureMutationSandbox
from .constitution import ArchitectureConstitution


def run_architecture_meta_dry_scan(*, enabled: bool = False, **scan_kwargs) -> dict:
    """Minimal public entrypoint for dry / nightly hook (gated).

    Returns {'proposals': [...], 'snapshot': ..., 'metrics': ...}
    Does NOT apply anything. Human gate lives in caller / promotion_gate.
    """
    ctrl = ArchitectureMetaController(enabled=enabled, **{k: v for k, v in scan_kwargs.items() if hasattr(ArchitectureMetaController, k)})
    # Build a minimal synthetic snapshot if not supplied
    snap = ctrl.build_snapshot(
        god_file_count=scan_kwargs.get("god_file_count", 1),
        boundary_violations=scan_kwargs.get("boundary_violations", 0),
        pydantic_model_count=scan_kwargs.get("pydantic_model_count", 12),
        ruff_violations_core=scan_kwargs.get("ruff_violations_core", 3),
        avg_module_loc=scan_kwargs.get("avg_module_loc", 410.0),
        todo_density=scan_kwargs.get("todo_density", 0.6),
        total_core_loc=scan_kwargs.get("total_core_loc", 14000),
    )
    proposals = ctrl.propose(snap) if enabled else []
    return {
        "snapshot": snap,
        "proposals": proposals,
        "metrics": ctrl.metrics_payload(),
        "enabled": enabled,
    }
