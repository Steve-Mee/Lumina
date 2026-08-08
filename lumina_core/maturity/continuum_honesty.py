"""M6: continuum / READY / Birth-exit honesty board for Phase Hub.

Single operator-facing SSOT that prevents conflating:
- Birth exit (survival — H7/ADR-0036)
- READY_FOR_REAL (apprenticeship multi-day green streak)
- REAL eligibility (promotion + Perfect Birth + human approval chain)

Fail-closed posture: never invent readiness; surface gaps and soft-complete flags.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.maturity.continuum import load_continuum, next_phase_id
from lumina_core.maturity.maturation_progress import (
    REAL_ELIGIBILITY_MILESTONES,
    load_maturation_progress,
    maturation_eligible_for_real,
)
from lumina_core.maturity.phase_specs import PHASE_SPECS, evaluate_exit_proofs

logger = get_logger("lumina.maturity.continuum_honesty")

SCHEMA = "continuum_honesty_v1"


def _ready_for_real_status(workspace_root: Path) -> dict[str, Any]:
    """Honest READY_FOR_REAL: milestone and/or last stability report — never invents."""
    progress = load_maturation_progress(workspace_root)
    reached = set(progress.milestones_reached)
    milestone = "sim_real_guard_stable" in reached
    report_ready = False
    report_detail: dict[str, Any] = {}
    report_path = workspace_root / "state" / "sim_stability_report.json"
    if report_path.is_file():
        try:
            import json

            raw = json.loads(report_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                report_ready = bool(raw.get("READY_FOR_REAL"))
                report_detail = {
                    "path": str(report_path),
                    "READY_FOR_REAL": report_ready,
                    "consecutive_green_days": raw.get("consecutive_green_days"),
                    "updated_at": raw.get("generated_at") or raw.get("timestamp"),
                }
        except Exception:
            report_detail = {"path": str(report_path), "error": "unreadable"}
    ready = bool(milestone or report_ready)
    return {
        "ready": ready,
        "milestone_sim_real_guard_stable": milestone,
        "stability_report": report_detail,
        "note": (
            "READY_FOR_REAL is apprenticeship multi-day SIM stability — "
            "not Birth exit and not automatic REAL capital arm."
        ),
    }


def _soft_complete_flags(continuum: dict[str, Any]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    records = continuum.get("phase_records") or {}
    if not isinstance(records, dict):
        return flags
    for phase_id, rec in records.items():
        if not isinstance(rec, dict):
            continue
        learned = rec.get("learned") if isinstance(rec.get("learned"), dict) else {}
        if learned.get("soft_complete") or rec.get("soft_complete"):
            flags.append(
                {
                    "phase": str(phase_id),
                    "source": "phase_record.learned.soft_complete",
                    "severity": "warning",
                    "message": (
                        f"Phase '{phase_id}' was marked complete under experimental soft mode — "
                        "not a strict production exit proof."
                    ),
                }
            )
    return flags


def _continuum_milestone_drift(
    workspace_root: Path,
    continuum: dict[str, Any],
) -> list[dict[str, Any]]:
    """Detect desync between continuum completed_phases and milestones/artifacts."""
    drifts: list[dict[str, Any]] = []
    completed = set(continuum.get("completed_phases") or [])
    progress = load_maturation_progress(workspace_root)
    reached = set(progress.milestones_reached)

    # Birth exit vs continuum
    try:
        from lumina_core.maturity.birth_exit import evaluate_birth_exit

        be = evaluate_birth_exit(workspace_root)
        if be.exited and "birth" not in completed:
            drifts.append(
                {
                    "code": "birth_exit_without_continuum",
                    "severity": "info",
                    "message": (
                        "Birth exit proofs present but continuum has not marked birth complete — "
                        "hub should call mark_birth_complete_from_artifacts."
                    ),
                }
            )
        if "birth" in completed and not be.exited:
            drifts.append(
                {
                    "code": "continuum_birth_without_exit_proofs",
                    "severity": "warning",
                    "message": (
                        "Continuum lists birth completed but Birth exit SSOT reports not exited — "
                        "possible soft/manual complete; verify artifacts."
                    ),
                }
            )
    except Exception as exc:
        drifts.append(
            {
                "code": "birth_exit_eval_error",
                "severity": "warning",
                "message": f"birth_exit_eval_failed:{exc}",
            }
        )

    if "birth_certificate_issued" in reached and "birth" not in completed:
        drifts.append(
            {
                "code": "certificate_milestone_without_continuum_birth",
                "severity": "info",
                "message": "Certificate milestone present; continuum birth phase not yet completed.",
            }
        )

    if "sim_real_guard_stable" in reached and "apprenticeship" not in completed:
        drifts.append(
            {
                "code": "ready_milestone_without_apprenticeship_phase",
                "severity": "info",
                "message": (
                    "READY_FOR_REAL milestone present but apprenticeship not in continuum completed — "
                    "run or re-evaluate apprenticeship exit proofs."
                ),
            }
        )

    if "promotion_gate_passed" in reached and "proving_ground" not in completed:
        drifts.append(
            {
                "code": "promotion_without_proving_ground_phase",
                "severity": "info",
                "message": "Promotion milestone present; proving_ground not marked complete on continuum.",
            }
        )

    return drifts


def _next_honest_steps(
    workspace_root: Path,
    *,
    focus: str | None,
    birth_exited: bool,
    ready: bool,
    real_eligible: bool,
    real_blockers: list[str],
    exit_missing: list[str],
) -> list[str]:
    steps: list[str] = []
    if not birth_exited:
        steps.append(
            "Complete Birth survival loop (artifacts / curriculum / certificate) — "
            "not Perfect Birth KPIs."
        )
        return steps

    focus_id = str(focus or next_phase_id(load_continuum(workspace_root).get("completed_phases") or []) or "")
    if focus_id and exit_missing:
        steps.append(
            f"Close exit proofs for focus phase '{focus_id}': " + ", ".join(exit_missing[:8])
        )
    if focus_id == "apprenticeship" and not ready:
        steps.append(
            "Apprenticeship: run multi-day SIM until READY_FOR_REAL "
            "(sim_real_guard_stable / consecutive green days)."
        )
    if focus_id in {"proving_ground", "real"} or ready:
        if not real_eligible:
            steps.append(
                "REAL still blocked: " + ("; ".join(real_blockers[:6]) if real_blockers else "eligibility gaps")
            )
        else:
            steps.append(
                "REAL eligibility milestones met — still requires explicit human approve-real + mode switch "
                "(fail-closed; no auto arm)."
            )
    if not steps:
        steps.append("Continue next continuum phase from hub; capital gates remain fail-closed.")
    return steps


def continuum_honesty_snapshot(workspace_root: Path | str) -> dict[str, Any]:
    """Operator-facing honesty board (M6) for Phase Hub / maturity APIs."""
    root = Path(workspace_root)
    continuum = load_continuum(root)
    completed = list(continuum.get("completed_phases") or [])
    active = continuum.get("active_phase")
    nxt = next_phase_id(completed)
    focus = active or nxt

    birth_exit_block: dict[str, Any] = {}
    birth_exited = False
    try:
        from lumina_core.maturity.birth_exit import birth_exit_status_payload

        birth_exit_block = birth_exit_status_payload(root)
        birth_exited = bool(birth_exit_block.get("exited"))
    except Exception as exc:
        birth_exit_block = {"error": str(exc), "exited": False}

    ready_block = _ready_for_real_status(root)
    real_eligible, real_blockers = maturation_eligible_for_real(root)

    exit_ok, exit_missing, exit_learned = (False, [], {})
    if focus:
        try:
            exit_ok, exit_missing, exit_learned = evaluate_exit_proofs(root, str(focus))
        except Exception as exc:
            exit_missing = [f"exit_eval_error:{exc}"]

    soft = _soft_complete_flags(continuum)
    drifts = _continuum_milestone_drift(root, continuum)

    conflation_warnings: list[str] = []
    if birth_exited and not ready_block["ready"]:
        conflation_warnings.append(
            "Birth exit ≠ READY_FOR_REAL — newborn survived training loop only."
        )
    if ready_block["ready"] and not real_eligible:
        conflation_warnings.append(
            "READY_FOR_REAL ≠ REAL capital — still need promotion/Perfect Birth/human chain."
        )
    pb_flag = (root / "state" / "perfect_birth_complete.flag").is_file()
    if pb_flag and not birth_exited:
        conflation_warnings.append(
            "Perfect Birth flag present without Birth exit SSOT — investigate hollow/out-of-order state."
        )

    honesty_ok = (
        len([d for d in drifts if d.get("severity") == "warning"]) == 0
        and len(soft) == 0
        and "error" not in birth_exit_block
    )

    return {
        "schema": SCHEMA,
        "honesty_ok": honesty_ok,
        "focus_phase": focus,
        "next_phase": nxt,
        "completed_phases": completed,
        "active_phase": active,
        "birth_exit": birth_exit_block,
        "ready_for_real": ready_block,
        "real_eligible": {
            "eligible": bool(real_eligible),
            "blockers": list(real_blockers),
            "required_milestones": list(REAL_ELIGIBILITY_MILESTONES),
            "note": "REAL still needs human approve-real + mode switch after eligibility.",
        },
        "focus_exit_eval": {
            "ok": bool(exit_ok),
            "missing": list(exit_missing),
            "learned_keys": sorted(exit_learned.keys()) if isinstance(exit_learned, dict) else [],
        },
        "soft_complete_flags": soft,
        "continuum_vs_milestones_drift": drifts,
        "conflation_warnings": conflation_warnings,
        "next_honest_steps": _next_honest_steps(
            root,
            focus=str(focus) if focus else None,
            birth_exited=birth_exited,
            ready=bool(ready_block.get("ready")),
            real_eligible=bool(real_eligible),
            real_blockers=list(real_blockers),
            exit_missing=list(exit_missing),
        ),
        "phase_goals": {
            pid: {"label": s.label, "human_goal": s.human_goal}
            for pid, s in PHASE_SPECS.items()
        },
    }


__all__ = [
    "SCHEMA",
    "continuum_honesty_snapshot",
]
