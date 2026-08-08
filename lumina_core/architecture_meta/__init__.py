"""Architecture Meta layer — next evolution: proposes own architecture improvements via sandboxed mutations.

Radically simple + measurable.
Full constitution + human-in-the-loop promotion gates (fail-closed).
Default disabled. Agents propose; humans (Final Arbitration) promote.

M1: scanner + dry pipeline + journal (never auto-apply)
M2: meta_agent_approval SSOT
M3: evolution_axes catalog

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
    "run_architecture_meta_dry_cycle",
    "architecture_meta_status",
    "meta_agent_approval_snapshot",
    "evolution_axes_snapshot",
]

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

    Prefer :func:`run_architecture_meta_dry_cycle` for real filesystem scans (M1).
    Returns proposals only when enabled. Does NOT apply anything.
    """
    from .pipeline import run_architecture_meta_dry_cycle

    # If caller passed explicit scan counts, keep lightweight synthetic path
    has_counts = any(
        k in scan_kwargs
        for k in (
            "god_file_count",
            "boundary_violations",
            "pydantic_model_count",
            "avg_module_loc",
        )
    )
    if has_counts:
        ctrl = ArchitectureMetaController(
            enabled=enabled,
            **{
                k: v
                for k, v in scan_kwargs.items()
                if k in ("max_proposals_per_scan", "max_patch_lines", "min_health_delta")
            },
        )
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
            "auto_apply": False,
        }

    return run_architecture_meta_dry_cycle(
        enabled=enabled,
        workspace_root=scan_kwargs.get("workspace_root"),
        repo_root=scan_kwargs.get("repo_root"),
        write_journal=bool(scan_kwargs.get("write_journal", False)),
        capital_mode=str(scan_kwargs.get("capital_mode", "sim")),
    )


def run_architecture_meta_dry_cycle(**kwargs):
    from .pipeline import run_architecture_meta_dry_cycle as _cycle

    return _cycle(**kwargs)


def architecture_meta_status(**kwargs):
    from .pipeline import architecture_meta_status as _status

    return _status(**kwargs)


def meta_agent_approval_snapshot(**kwargs):
    from .meta_agent_approval import meta_agent_approval_snapshot as _snap

    return _snap(**kwargs)


def evolution_axes_snapshot(**kwargs):
    from .evolution_axes import evolution_axes_snapshot as _snap

    return _snap(**kwargs)
