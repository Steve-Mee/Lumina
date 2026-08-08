"""REAL multi-gate SSOT (H2) — human + maturation + constitution; Twin never sole-authorizes.

Fail-closed. Twin judgment is allowed only *inside* gates (assisted/full_auto for DNA
proposals in SIM paths). REAL capital mode and REAL DNA promotion always require
explicit human approval and maturation eligibility.

Non-bypassable gates (all must pass for REAL capital):
1. Maturation ladder milestones (certificate, evolution proof, sim stability,
   promotion gate, perfect birth autonomy)
2. Explicit human REAL approval milestone (``human_real_approval``)
3. Capital aperture lineage + Final Arbitration on each order (admission)
4. REAL DNA promotion: ApprovalChain + require_human_approval mandatory
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.risk.real_multi_gate")

# Gates that Twin / full_auto must never short-circuit
REAL_GATE_IDS: tuple[str, ...] = (
    "maturation_eligible",
    "human_real_approval",
    "capital_aperture_lineage",
    "final_arbitration",
    "real_dna_human_approval_chain",
)

__all__ = [
    "REAL_GATE_IDS",
    "assert_twin_cannot_authorize_real_mode",
    "evaluate_real_capital_readiness",
    "real_dna_promotion_allowed",
    "real_mode_switch_allowed",
    "run_real_multi_gate_dry_run",
    "twin_judgment_subordinate_to_real_gates",
]


def evaluate_real_capital_readiness(
    workspace_root: Path | str,
) -> dict[str, Any]:
    """Full readiness snapshot for REAL capital (operator + API)."""
    root = Path(workspace_root)
    from lumina_core.maturity.maturation_progress import (
        load_maturation_progress,
        maturation_eligible_for_real,
    )

    eligible, blockers = maturation_eligible_for_real(root)
    progress = load_maturation_progress(root)
    reached = set(progress.milestones_reached)
    human_ok = "human_real_approval" in reached
    live = "real_trading_live" in reached

    gate_results = {
        "maturation_eligible": {
            "ok": eligible,
            "blockers": list(blockers),
        },
        "human_real_approval": {
            "ok": human_ok,
            "blockers": [] if human_ok else ["Operator REAL approval not recorded"],
        },
        "capital_aperture_lineage": {
            "ok": True,
            "note": "Enforced per-order at admission (strict modes reject missing ctx)",
        },
        "final_arbitration": {
            "ok": True,
            "note": "Enforced per-order; no skip path",
        },
        "real_dna_human_approval_chain": {
            "ok": True,
            "note": "generation_runner + evolution API require human chain in REAL",
        },
    }
    all_ok = eligible and human_ok
    hard_blockers: list[str] = []
    if not eligible:
        hard_blockers.extend(blockers)
    if not human_ok:
        hard_blockers.append("Operator REAL approval required (POST /api/maturity/approve-real)")

    return {
        "ready_for_real_capital": all_ok,
        "maturation_eligible": eligible,
        "human_real_approval": human_ok,
        "real_trading_live": live,
        "blockers": hard_blockers,
        "gates": gate_results,
        "twin_can_bypass": False,
        "policy": {
            "twin_role": "judgment_inside_gates_only",
            "human_required_for_real_mode": True,
            "human_required_for_real_dna_promotion": True,
            "auto_evolve_never_arms_real": True,
        },
    }


def real_mode_switch_allowed(workspace_root: Path | str) -> tuple[bool, list[str]]:
    """Whether operator may switch deck/runtime to REAL capital mode."""
    snap = evaluate_real_capital_readiness(workspace_root)
    return bool(snap["ready_for_real_capital"]), list(snap["blockers"])


def run_real_multi_gate_dry_run(
    workspace_root: Path | str | None = None,
) -> dict[str, Any]:
    """T3: Read-only REAL multi-gate dry-run — never switches mode or arms capital.

    Reports maturation + human approve-real readiness, twin non-bypass, DNA promotion
    invariant, and aperture coverage soft status. Exit tooling uses this for CI/ops.
    """
    root = Path(workspace_root) if workspace_root else Path.cwd()
    readiness = evaluate_real_capital_readiness(root)
    switch_ok, switch_blockers = real_mode_switch_allowed(root)

    # Twin full_auto cannot sole-authorize REAL
    twin_floor = twin_judgment_subordinate_to_real_gates(
        twin_recommendation=True,
        twin_executable=True,
        twin_mode="full_auto",
        capital_mode="real",
    )
    twin_invariant_ok = (
        twin_floor.get("executable") is False
        and twin_floor.get("effective_recommendation") is False
        and twin_floor.get("real_capital_floor") is True
    )
    try:
        assert_twin_cannot_authorize_real_mode(
            twin_full_auto=True, twin_recommendation=True
        )
        twin_assert_ok = True
        twin_assert_error = None
    except AssertionError as exc:
        twin_assert_ok = False
        twin_assert_error = str(exc)

    # DNA promotion: REAL without human must fail
    dna_no_human_ok, dna_no_human_reason = real_dna_promotion_allowed(
        mode="real",
        require_human_approval=False,
        explicit_human_approval=True,
        base_promoted=True,
        has_approval_signatures=True,
    )
    dna_invariant = (dna_no_human_ok is False) and (
        "human" in str(dna_no_human_reason).lower()
    )

    # Aperture: soft status only (does not fail dry-run on thin samples)
    aperture: dict[str, Any] = {}
    try:
        from lumina_core.risk.capital_aperture_lineage import evaluate_aperture_coverage_gate

        aperture = evaluate_aperture_coverage_gate(workspace_root=root)
    except Exception as exc:
        aperture = {"ok": False, "reason": f"aperture_unavailable:{exc}"}

    # T4: REAL recon config gate (defaults assume recon ON for capital-risk modes)
    recon: dict[str, Any] = {}
    try:
        from lumina_core.engine.trade_reconciler.real_recon_gate import (
            evaluate_real_broker_recon_gate,
        )

        recon = evaluate_real_broker_recon_gate(
            trade_mode="real",
            reconcile_fills=True,
            reconciliation_method="websocket",
            reconciliation_timeout_seconds=15.0,
        )
    except Exception as exc:
        recon = {"ok": False, "failures": [f"recon_gate_error:{exc}"]}

    checks = {
        "twin_cannot_authorize_real": twin_invariant_ok and twin_assert_ok,
        "real_dna_requires_human": dna_invariant,
        "readiness_loaded": isinstance(readiness, dict),
        "twin_can_bypass_flag_false": readiness.get("twin_can_bypass") is False,
        "real_recon_config_defaults_ok": bool(recon.get("ok")),
    }
    all_invariants = all(checks.values())
    # dry_run "ready_for_real" mirrors switch — informational only
    return {
        "schema": "real_multi_gate_dry_run_v1",
        "ok": all_invariants,  # invariants hold (not "ready for REAL")
        "ready_for_real_capital": bool(readiness.get("ready_for_real_capital")),
        "mode_switch_allowed": bool(switch_ok),
        "blockers": list(switch_blockers),
        "invariants": checks,
        "twin_floor": twin_floor,
        "twin_assert_error": twin_assert_error,
        "dna_promotion_without_human": {
            "allowed": dna_no_human_ok,
            "reason": dna_no_human_reason,
            "must_be_false": True,
            "invariant_ok": dna_invariant,
        },
        "readiness": readiness,
        "aperture_coverage": {
            "ok": aperture.get("ok"),
            "soft_pass": aperture.get("soft_pass"),
            "reason": aperture.get("reason"),
            "sample_size": aperture.get("sample_size"),
            "lineage_coverage_pct": aperture.get("lineage_coverage_pct"),
            "message": aperture.get("message"),
        },
        "broker_recon": recon,
        "policy": {
            "never_arms_real": True,
            "never_calls_approve_real": True,
            "twin_role": "judgment_inside_gates_only",
            "timeout_fill_no_economic_ledger": True,
            "next_step_if_not_ready": (
                "Complete maturation milestones + POST /api/maturity/approve-real "
                "before any REAL mode switch; keep reconcile_fills=true for REAL."
            ),
        },
        "gate_ids": list(REAL_GATE_IDS),
    }


def real_dna_promotion_allowed(
    *,
    mode: str,
    require_human_approval: bool,
    explicit_human_approval: bool = False,
    base_promoted: bool,
    has_approval_signatures: bool = False,
) -> tuple[bool, str]:
    """Fail-closed REAL DNA promotion eligibility (generation path).

    Twin recommendation is intentionally *not* a parameter — it cannot authorize.
    Human proof = require_human_approval AND (signatures | explicit flag);
    ApprovalChain.verify remains the cryptographic check when proceeding.
    """
    m = str(mode or "").strip().lower()
    if m != "real":
        return True, "not_real_mode"
    if not require_human_approval:
        return False, "real_human_approval_mandatory"
    if not base_promoted:
        return False, "promotion_not_eligible_before_approval"
    if not (explicit_human_approval or has_approval_signatures):
        return False, "explicit_human_approval_or_signatures_required"
    return True, "ok_proceed_to_approval_chain"


def twin_judgment_subordinate_to_real_gates(
    *,
    twin_recommendation: bool,
    twin_executable: bool,
    twin_mode: str | None,
    capital_mode: str | None,
) -> dict[str, Any]:
    """Prove Twin cannot sole-authorize REAL capital operations.

    Returns effective authority fields for consumers (deck, generation, birth).
    """
    from lumina_core.evolution.twin_mode_types import apply_mode_authority, canonicalize_twin_mode

    cap = str(capital_mode or "sim").strip().lower()
    # Track D: capital floor is inside apply_mode_authority (REAL never executable).
    auth = apply_mode_authority(
        raw_recommendation=bool(twin_recommendation),
        mode=twin_mode,
        capital_mode=cap,
    )
    real_capital = bool(auth.get("real_capital_floor"))
    return {
        **auth,
        "capital_mode": cap,
        "twin_mode": canonicalize_twin_mode(twin_mode),
        "real_capital_floor": real_capital,
        "reason": (
            "twin_cannot_authorize_real_capital" if real_capital else "mode_authority"
        ),
        "raw_recommendation": bool(twin_recommendation),
        "raw_executable": bool(twin_executable),
    }


def assert_twin_cannot_authorize_real_mode(
    *,
    twin_full_auto: bool,
    twin_recommendation: bool,
) -> None:
    """Invariant check for tests/ops — twin alone never yields real mode switch OK."""
    result = twin_judgment_subordinate_to_real_gates(
        twin_recommendation=twin_recommendation or twin_full_auto,
        twin_executable=True,
        twin_mode="full_auto" if twin_full_auto else "shadow",
        capital_mode="real",
    )
    if result.get("effective_recommendation") or result.get("executable"):
        raise AssertionError("H2 invariant broken: Twin authorized REAL capital")
