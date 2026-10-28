"""REAL-mode promotion helpers for generation_runner (global residual)."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def apply_real_mode_shadow_promotion(
    orchestrator: Any,
    *,
    winner_dna: Any,
    winner_fitness: float,
    previous_fitness: float,
    twin_confidence: float,
    twin_risk_flags: Any,
    generation_metrics: dict[str, Any],
    signed: Any,
    generation_ok: bool,
    shadow_runner: Any,
    mode: str = "real",
) -> dict[str, Any]:
    """Execute shadow validation + gated promotion for REAL mode."""
    veto_check: dict[str, Any] = {
        "is_blocked": False,
        "reason": "no_veto",
        "active_veto_records": [],
    }
    shadow_status = "not_required"
    shadow_passed = False
    shadow_days_completed = 0
    shadow_days_target = 0
    shadow_total_pnl = 0.0
    promotion_gate: dict[str, Any] = {}

    shadow_decision = orchestrator._run_shadow_validation_gate(
        dna=winner_dna,
        winner_fitness=winner_fitness,
        nightly_report=generation_metrics,
        signed=signed,
        generation_ok=generation_ok,
        shadow_runner=shadow_runner,
    )
    promoted = bool(shadow_decision.get("promote_now", False))
    veto_check = dict(shadow_decision.get("veto_check", veto_check) or veto_check)
    veto_blocked = bool(shadow_decision.get("veto_blocked", False))
    shadow_status = str(shadow_decision.get("shadow_status", shadow_status))
    shadow_passed = bool(shadow_decision.get("shadow_passed", False))
    shadow_days_completed = int(shadow_decision.get("shadow_days_completed", 0) or 0)
    shadow_days_target = int(shadow_decision.get("shadow_days_target", 0) or 0)
    shadow_total_pnl = float(shadow_decision.get("shadow_total_pnl", 0.0) or 0.0)
    promotion_gate = dict(shadow_decision.get("promotion_gate", {}) or {})

    gated_promotion = orchestrator._guard.is_confidence_gated_promotion(
        winner_dna,
        twin_confidence,
        shadow_passed,
        winner_fitness,
        previous_fitness,
        twin_risk_flags=twin_risk_flags,
    )
    promoted = bool(promoted and gated_promotion)

    if shadow_status in {"passed", "failed", "vetoed"}:
        fail_reasons = list(promotion_gate.get("fail_reasons", []) or [])
        gate_reason = str(fail_reasons[0]) if fail_reasons else ""
        orchestrator._send_promotion_status_telegram(
            dna_hash=winner_dna.hash,
            promoted=promoted,
            reason=gate_reason,
        )
        try:
            from lumina_launcher.core.workspace_root import resolve_birth_workspace_root
            from lumina_core.maturity.milestone_hooks import (
                hook_promotion_gate_passed,
                hook_shadow_validation_passed,
            )

            workspace = resolve_birth_workspace_root()
            if shadow_passed:
                hook_shadow_validation_passed(
                    workspace,
                    shadow_status=shadow_status,
                    dna_hash=winner_dna.hash,
                )
            if bool(promotion_gate.get("promoted", False)):
                hook_promotion_gate_passed(
                    workspace,
                    mode=mode,
                    dna_hash=winner_dna.hash,
                )
        except Exception:
            pass

    return {
        "promoted": promoted,
        "veto_check": veto_check,
        "veto_blocked": veto_blocked,
        "shadow_status": shadow_status,
        "shadow_passed": shadow_passed,
        "shadow_days_completed": shadow_days_completed,
        "shadow_days_target": shadow_days_target,
        "shadow_total_pnl": shadow_total_pnl,
        "promotion_gate": promotion_gate,
    }
