"""M2: Meta-agent approval SSOT — fail-closed capital and architecture gates.

No meta-agent may auto-arm REAL capital or auto-apply architecture patches.
Coordinates Twin / code-evolution / DNA promotion policies into one surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

REAL_LIKE = frozenset({"real", "live", "prod", "production", "sim_real_guard"})


def is_real_like_capital(mode: str | None) -> bool:
    return str(mode or "").strip().lower() in REAL_LIKE


@dataclass(frozen=True, slots=True)
class ApprovalSurface:
    """One approval surface meta-agents may touch."""

    surface_id: str
    label: str
    auto_allowed_modes: tuple[str, ...]
    requires_human: bool
    may_touch_real_capital: bool
    notes: str


# Canonical catalog — extend carefully; fail-closed defaults.
APPROVAL_SURFACES: tuple[ApprovalSurface, ...] = (
    ApprovalSurface(
        surface_id="architecture_promotion",
        label="Architecture patch promotion (ADR-0030)",
        auto_allowed_modes=(),
        requires_human=True,
        may_touch_real_capital=False,
        notes="APPROVED marker only; never auto-apply even in SIM.",
    ),
    ApprovalSurface(
        surface_id="code_evolution_apply",
        label="Trading code-evolution sandbox apply (H5)",
        auto_allowed_modes=("sim", "paper", "birth"),
        requires_human=True,
        may_touch_real_capital=False,
        notes="Sandbox store only; Twin may assist; REAL blocked.",
    ),
    ApprovalSurface(
        surface_id="twin_judgment",
        label="Approval Twin judgment (H4)",
        auto_allowed_modes=("sim", "paper", "birth"),
        requires_human=False,
        may_touch_real_capital=False,
        notes="full_auto never for REAL capital; subordinate to multi-gate.",
    ),
    ApprovalSurface(
        surface_id="dna_promotion",
        label="DNA / challenger promotion",
        auto_allowed_modes=("sim", "paper"),
        requires_human=True,
        may_touch_real_capital=False,
        notes="Human chain for REAL; SIM may use twin+promotion gate.",
    ),
    ApprovalSurface(
        surface_id="real_capital_mode",
        label="REAL capital mode switch",
        auto_allowed_modes=(),
        requires_human=True,
        may_touch_real_capital=True,
        notes="Explicit human only; multi-gate + maturation (H2).",
    ),
    ApprovalSurface(
        surface_id="phase_advance",
        label="Maturation phase advance",
        auto_allowed_modes=("sim", "paper", "birth"),
        requires_human=False,
        may_touch_real_capital=False,
        notes="auto_evolve ok until REAL; REAL always hub confirm.",
    ),
)


def surface_by_id(surface_id: str) -> ApprovalSurface | None:
    sid = str(surface_id or "").strip()
    for s in APPROVAL_SURFACES:
        if s.surface_id == sid:
            return s
    return None


def meta_agent_may_auto_approve(
    surface_id: str,
    *,
    capital_mode: str | None,
    human_approved: bool = False,
    twin_effective: bool = False,
) -> dict[str, Any]:
    """Whether a meta-agent may auto-approve without further human action.

    Fail-closed: unknown surface → deny. REAL-like capital → deny unless
    surface explicitly may_touch_real_capital AND human_approved.
    """
    surface = surface_by_id(surface_id)
    mode = str(capital_mode or "sim").strip().lower() or "sim"
    real = is_real_like_capital(mode)

    if surface is None:
        return {
            "allowed": False,
            "reason": "unknown_surface",
            "surface_id": surface_id,
            "capital_mode": mode,
            "real_like": real,
        }

    if human_approved and not real:
        return {
            "allowed": True,
            "reason": "human_approved",
            "surface_id": surface.surface_id,
            "capital_mode": mode,
            "real_like": real,
            "requires_human": surface.requires_human,
        }

    if real:
        # REAL: only explicit human on surfaces that may touch capital (mode switch)
        if surface.may_touch_real_capital and human_approved:
            return {
                "allowed": True,
                "reason": "human_approved_real",
                "surface_id": surface.surface_id,
                "capital_mode": mode,
                "real_like": True,
            }
        return {
            "allowed": False,
            "reason": "real_capital_requires_human",
            "surface_id": surface.surface_id,
            "capital_mode": mode,
            "real_like": True,
            "requires_human": True,
        }

    # Architecture: never auto
    if surface.surface_id == "architecture_promotion":
        return {
            "allowed": False,
            "reason": "architecture_never_auto_apply",
            "surface_id": surface.surface_id,
            "capital_mode": mode,
            "real_like": False,
            "requires_human": True,
        }

    if surface.requires_human and not human_approved:
        # Twin assist only where twin_effective and surface allows non-human path later
        if twin_effective and surface.surface_id in ("code_evolution_apply", "dna_promotion"):
            return {
                "allowed": False,
                "reason": "human_or_explicit_twin_policy_required",
                "surface_id": surface.surface_id,
                "capital_mode": mode,
                "real_like": False,
                "twin_note": "Twin may recommend; apply_gate owns final allow",
            }
        return {
            "allowed": False,
            "reason": "human_required",
            "surface_id": surface.surface_id,
            "capital_mode": mode,
            "real_like": False,
            "requires_human": True,
        }

    # Non-human surfaces in SIM/birth/paper (e.g. twin_judgment, phase_advance)
    allowed_modes = {m.lower() for m in surface.auto_allowed_modes}
    if mode in allowed_modes or (not allowed_modes and not surface.requires_human):
        # twin_judgment / phase_advance
        if not surface.auto_allowed_modes and surface.requires_human:
            return {
                "allowed": False,
                "reason": "no_auto_modes",
                "surface_id": surface.surface_id,
                "capital_mode": mode,
                "real_like": False,
            }
        if surface.auto_allowed_modes and mode not in allowed_modes:
            return {
                "allowed": False,
                "reason": f"mode_{mode}_not_in_auto_allowed",
                "surface_id": surface.surface_id,
                "capital_mode": mode,
                "real_like": False,
            }
        return {
            "allowed": True,
            "reason": "meta_auto_allowed_non_real",
            "surface_id": surface.surface_id,
            "capital_mode": mode,
            "real_like": False,
        }

    return {
        "allowed": False,
        "reason": "policy_deny",
        "surface_id": surface.surface_id,
        "capital_mode": mode,
        "real_like": False,
    }


def meta_agent_approval_snapshot(*, capital_mode: str | None = "sim") -> dict[str, Any]:
    """Operator-facing snapshot of all approval surfaces for current capital mode."""
    mode = str(capital_mode or "sim")
    surfaces = []
    for s in APPROVAL_SURFACES:
        decision = meta_agent_may_auto_approve(s.surface_id, capital_mode=mode)
        surfaces.append(
            {
                "surface_id": s.surface_id,
                "label": s.label,
                "requires_human": s.requires_human,
                "may_touch_real_capital": s.may_touch_real_capital,
                "auto_allowed_modes": list(s.auto_allowed_modes),
                "notes": s.notes,
                "auto_decision": decision,
            }
        )
    return {
        "schema": "meta_agent_approval_v1",
        "capital_mode": mode,
        "real_like": is_real_like_capital(mode),
        "invariants": [
            "No meta-agent auto-arms REAL capital",
            "Architecture patches never auto-apply",
            "Code-evolution apply is sandbox-store only (H5)",
            "Twin full_auto is birth/SIM judgment only (H4)",
        ],
        "surfaces": surfaces,
    }
