"""M1: Architecture meta dry pipeline — observe → propose → journal (never apply).

Human promotion remains in ArchPromotionGate. This module never mutates live code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.architecture_meta.controller import (
    ArchitectureMetaController,
    ArchMutationProposal,
)
from lumina_core.architecture_meta.journal import append_architecture_event, tail_architecture_events
from lumina_core.architecture_meta.scanner import (
    scan_architecture_counts,
    scan_counts_as_kwargs,
)
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.architecture_meta.pipeline")


def proposal_is_actionable(proposal: ArchMutationProposal | dict[str, Any]) -> bool:
    """Actionable = non-empty unified diff + real target path (not inventory-only)."""
    if isinstance(proposal, dict):
        diff = str(proposal.get("diff") or "")
        target = str(proposal.get("target_file") or "")
    else:
        diff = str(proposal.diff or "")
        target = str(proposal.target_file or "")
    if not diff.strip() or len(diff.strip()) < 10:
        return False
    if not target.endswith(".py"):
        return False
    if target.startswith("(") or "inventory" in target.lower():
        return False
    return True


def proposal_public(p: ArchMutationProposal) -> dict[str, Any]:
    return {
        "proposal_id": p.proposal_id,
        "mutation_type": p.mutation_type.value if hasattr(p.mutation_type, "value") else str(p.mutation_type),
        "target_file": p.target_file,
        "description": p.description,
        "expected_delta": p.expected_delta,
        "rationale": p.rationale,
        "before_score": p.before_score,
        "constitution_passed": p.constitution_passed,
        "sandbox_passed": p.sandbox_passed,
        "actionable": proposal_is_actionable(p),
        "has_diff": bool((p.diff or "").strip()),
        "diff_preview": (p.diff or "")[:400],
    }


def run_architecture_meta_dry_cycle(
    *,
    enabled: bool = False,
    workspace_root: Path | str | None = None,
    repo_root: Path | str | None = None,
    max_proposals_per_scan: int = 2,
    max_patch_lines: int = 80,
    min_health_delta: float = 0.15,
    write_journal: bool = True,
    capital_mode: str = "sim",
) -> dict[str, Any]:
    """Full M1 dry cycle. Never applies patches. Optional journal under workspace."""
    root = Path(repo_root) if repo_root else None
    counts = scan_architecture_counts(root)
    ctrl = ArchitectureMetaController(
        enabled=bool(enabled),
        max_proposals_per_scan=int(max_proposals_per_scan),
        max_patch_lines=int(max_patch_lines),
        min_health_delta=float(min_health_delta),
    )
    snap = ctrl.build_snapshot(**scan_counts_as_kwargs(counts))
    proposals = ctrl.propose(snap) if enabled else []
    public = [proposal_public(p) for p in proposals]
    actionable = [p for p in public if p.get("actionable")]
    inventory_only = [p for p in public if not p.get("actionable")]

    result: dict[str, Any] = {
        "schema": "architecture_meta_cycle_v1",
        "enabled": bool(enabled),
        "auto_apply": False,
        "apply_blocked_reason": "architecture_meta never auto-applies; human APPROVED marker required",
        "capital_mode": capital_mode,
        "snapshot": {
            "arch_health_score": snap.arch_health_score,
            "is_healthy": snap.is_healthy,
            "god_file_count": snap.god_file_count,
            "boundary_violations": snap.boundary_violations,
            "pydantic_model_count": snap.pydantic_model_count,
            "avg_module_loc": snap.avg_module_loc,
            "todo_density": snap.todo_density,
            "total_core_loc": snap.total_core_loc,
            "timestamp": snap.timestamp,
        },
        "scan": {
            "module_count": counts.module_count,
            "god_files": list(counts.god_files),
            "total_core_loc": counts.total_core_loc,
        },
        "proposals": public,
        "actionable_count": len(actionable),
        "inventory_only_count": len(inventory_only),
        "metrics": ctrl.metrics_payload(),
    }

    if write_journal:
        try:
            append_architecture_event(
                {
                    "action": "dry_cycle",
                    "enabled": bool(enabled),
                    "health": snap.arch_health_score,
                    "proposals": len(public),
                    "actionable": len(actionable),
                    "capital_mode": capital_mode,
                },
                workspace_root=workspace_root,
            )
            result["journal_written"] = True
        except Exception as exc:
            logger.debug("arch_meta.journal_failed: %s", exc)
            result["journal_written"] = False
            result["journal_error"] = str(exc)[:200]

    return result


def architecture_meta_status(
    *,
    workspace_root: Path | str | None = None,
    repo_root: Path | str | None = None,
    capital_mode: str = "sim",
    enabled: bool | None = None,
) -> dict[str, Any]:
    """Status board for operators (scan + last journal + axes/approval embeds)."""
    from lumina_core.architecture_meta.evolution_axes import evolution_axes_snapshot
    from lumina_core.architecture_meta.meta_agent_approval import meta_agent_approval_snapshot

    cfg_enabled = bool(enabled) if enabled is not None else False
    am: dict[str, Any] = {}
    try:
        import yaml  # type: ignore

        cfg_path = Path(repo_root or Path(__file__).resolve().parents[2]) / "config.yaml"
        if cfg_path.is_file():
            raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            evo = raw.get("evolution") if isinstance(raw, dict) else {}
            am = dict((evo or {}).get("architecture_meta") or raw.get("architecture_meta") or {})
            if enabled is None:
                cfg_enabled = bool(am.get("enabled", False))
    except Exception:
        am = {}

    cycle = run_architecture_meta_dry_cycle(
        enabled=cfg_enabled,
        workspace_root=workspace_root,
        repo_root=repo_root,
        write_journal=False,
        capital_mode=capital_mode,
        max_proposals_per_scan=int(am.get("max_proposals_per_scan", 2) if isinstance(am, dict) else 2),
    )
    recent = tail_architecture_events(workspace_root=workspace_root, limit=10)
    return {
        "schema": "architecture_meta_status_v1",
        "enabled": cfg_enabled,
        "auto_apply": False,
        "require_human_approval": True,
        "cycle": cycle,
        "recent_journal": recent,
        "meta_agent_approval": meta_agent_approval_snapshot(capital_mode=capital_mode),
        "evolution_axes": evolution_axes_snapshot(capital_mode=capital_mode),
        "invariants": [
            "No architecture auto-apply",
            "No meta-agent REAL capital auto-approve",
            "Actionable proposals require real non-empty diffs",
        ],
    }
