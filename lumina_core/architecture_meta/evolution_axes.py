"""M3: Evolution axes catalog — what may evolve, under which gates.

SSOT for operator honesty: DNA ≠ architecture ≠ code-evolution ≠ hyperparams.
No axis may silently mutate REAL capital paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lumina_core.architecture_meta.meta_agent_approval import (
    is_real_like_capital,
    meta_agent_approval_snapshot,
)


@dataclass(frozen=True, slots=True)
class EvolutionAxis:
    axis_id: str
    label: str
    mutates_live_repo: bool
    mutates_trading_behavior: bool
    default_enabled: bool
    auto_in_sim: bool
    auto_in_real: bool
    requires_human_promotion: bool
    sandbox_required: bool
    related_approval_surface: str
    notes: str


EVOLUTION_AXES: tuple[EvolutionAxis, ...] = (
    EvolutionAxis(
        axis_id="dna_json",
        label="DNA / genome JSON mutation",
        mutates_live_repo=False,
        mutates_trading_behavior=True,
        default_enabled=True,
        auto_in_sim=True,
        auto_in_real=False,
        requires_human_promotion=True,
        sandbox_required=True,
        related_approval_surface="dna_promotion",
        notes="SandboxedMutationExecutor; PromotionGate for REAL-bound champions.",
    ),
    EvolutionAxis(
        axis_id="hyperparams",
        label="Hyperparameter challengers",
        mutates_live_repo=False,
        mutates_trading_behavior=True,
        default_enabled=True,
        auto_in_sim=True,
        auto_in_real=False,
        requires_human_promotion=True,
        sandbox_required=True,
        related_approval_surface="dna_promotion",
        notes="SIM challengers ok; REAL needs human approve chain.",
    ),
    EvolutionAxis(
        axis_id="architecture",
        label="Architecture source patches (ADR-0030)",
        mutates_live_repo=True,
        mutates_trading_behavior=False,
        default_enabled=False,
        auto_in_sim=False,
        auto_in_real=False,
        requires_human_promotion=True,
        sandbox_required=True,
        related_approval_surface="architecture_promotion",
        notes="Disabled by default; human APPROVED marker; never auto-apply.",
    ),
    EvolutionAxis(
        axis_id="code_evolution",
        label="Trading code evolution prototype (H5)",
        mutates_live_repo=False,
        mutates_trading_behavior=True,
        default_enabled=False,
        auto_in_sim=False,
        auto_in_real=False,
        requires_human_promotion=True,
        sandbox_required=True,
        related_approval_surface="code_evolution_apply",
        notes="Sandbox store only; forbid REAL capital apply.",
    ),
    EvolutionAxis(
        axis_id="curriculum_recovery",
        label="Birth curriculum / recovery params",
        mutates_live_repo=False,
        mutates_trading_behavior=True,
        default_enabled=True,
        auto_in_sim=True,
        auto_in_real=False,
        requires_human_promotion=False,
        sandbox_required=False,
        related_approval_surface="phase_advance",
        notes="Bounded organism autonomy in Birth/SIM; capital gates untouched.",
    ),
    EvolutionAxis(
        axis_id="twin_training",
        label="Approval Twin training discipline (H4)",
        mutates_live_repo=False,
        mutates_trading_behavior=False,
        default_enabled=True,
        auto_in_sim=True,
        auto_in_real=False,
        requires_human_promotion=False,
        sandbox_required=False,
        related_approval_surface="twin_judgment",
        notes="Judgment only; subordinate to REAL multi-gate.",
    ),
    EvolutionAxis(
        axis_id="risk_nudge_sim",
        label="SIM risk nudges (non-capital)",
        mutates_live_repo=False,
        mutates_trading_behavior=True,
        default_enabled=True,
        auto_in_sim=True,
        auto_in_real=False,
        requires_human_promotion=False,
        sandbox_required=False,
        related_approval_surface="twin_judgment",
        notes="Config risk_nudge_modes exclude real; never opens capital aperture.",
    ),
    EvolutionAxis(
        axis_id="strategy_research_lab",
        label="Strategy research lab (catalog + invent + champion-challenger)",
        mutates_live_repo=False,
        mutates_trading_behavior=True,
        default_enabled=True,
        auto_in_sim=True,
        auto_in_real=False,
        requires_human_promotion=True,
        sandbox_required=True,
        related_approval_surface="dna_promotion",
        notes="Catalog seeds + LLM/oracle/neuro via truthful fitness SSOT; never REAL auto.",
    ),
    EvolutionAxis(
        axis_id="schema_extension",
        label="Organism schema namespace (org_* columns)",
        mutates_live_repo=False,
        mutates_trading_behavior=False,
        default_enabled=False,
        auto_in_sim=False,
        auto_in_real=False,
        requires_human_promotion=True,
        sandbox_required=True,
        related_approval_surface="code_evolution_apply",
        notes="Never ALTER core tables; organism_extensions.sqlite3 only. ADR-0045.",
    ),
    EvolutionAxis(
        axis_id="challenger_venue",
        label="Champion/challenger internal paper venue",
        mutates_live_repo=False,
        mutates_trading_behavior=True,
        default_enabled=False,
        auto_in_sim=False,
        auto_in_real=False,
        requires_human_promotion=True,
        sandbox_required=True,
        related_approval_surface="code_evolution_apply",
        notes="Live tape, zero NT/broker; Steve gates SIM then REAL cutover. ADR-0045.",
    ),
)


def axis_by_id(axis_id: str) -> EvolutionAxis | None:
    aid = str(axis_id or "").strip()
    for a in EVOLUTION_AXES:
        if a.axis_id == aid:
            return a
    return None


def axis_allowed_for_mode(axis_id: str, *, capital_mode: str | None) -> dict[str, Any]:
    """Whether this axis may run (auto or at all) under capital_mode."""
    axis = axis_by_id(axis_id)
    mode = str(capital_mode or "sim").strip().lower() or "sim"
    real = is_real_like_capital(mode)
    if axis is None:
        return {"allowed": False, "reason": "unknown_axis", "axis_id": axis_id, "capital_mode": mode}

    if real:
        if axis.auto_in_real:
            return {
                "allowed": True,
                "auto": True,
                "reason": "axis_auto_in_real",
                "axis_id": axis.axis_id,
                "capital_mode": mode,
            }
        if axis.requires_human_promotion:
            return {
                "allowed": True,
                "auto": False,
                "reason": "human_promotion_only_in_real",
                "axis_id": axis.axis_id,
                "capital_mode": mode,
            }
        return {
            "allowed": False,
            "auto": False,
            "reason": "axis_blocked_in_real",
            "axis_id": axis.axis_id,
            "capital_mode": mode,
        }

    # Non-REAL
    if not axis.default_enabled and axis.axis_id in (
        "architecture",
        "code_evolution",
        "schema_extension",
        "challenger_venue",
    ):
        return {
            "allowed": True,
            "auto": False,
            "reason": "axis_disabled_by_default_manual_only",
            "axis_id": axis.axis_id,
            "capital_mode": mode,
            "default_enabled": False,
        }
    return {
        "allowed": True,
        "auto": bool(axis.auto_in_sim),
        "reason": "axis_ok_non_real",
        "axis_id": axis.axis_id,
        "capital_mode": mode,
    }


def evolution_axes_snapshot(*, capital_mode: str | None = "sim") -> dict[str, Any]:
    """Full M3 board + embedded M2 approval snapshot."""
    mode = str(capital_mode or "sim")
    axes = []
    for a in EVOLUTION_AXES:
        decision = axis_allowed_for_mode(a.axis_id, capital_mode=mode)
        axes.append(
            {
                "axis_id": a.axis_id,
                "label": a.label,
                "mutates_live_repo": a.mutates_live_repo,
                "mutates_trading_behavior": a.mutates_trading_behavior,
                "default_enabled": a.default_enabled,
                "auto_in_sim": a.auto_in_sim,
                "auto_in_real": a.auto_in_real,
                "requires_human_promotion": a.requires_human_promotion,
                "sandbox_required": a.sandbox_required,
                "related_approval_surface": a.related_approval_surface,
                "notes": a.notes,
                "mode_decision": decision,
            }
        )
    return {
        "schema": "evolution_axes_v1",
        "capital_mode": mode,
        "real_like": is_real_like_capital(mode),
        "axes": axes,
        "meta_agent_approval": meta_agent_approval_snapshot(capital_mode=mode),
        "invariants": [
            "Architecture never auto-applies",
            "No evolution axis auto-arms REAL capital",
            "Live-repo mutations require human promotion",
            "Code-evolution applies to sandbox store only",
        ],
    }
