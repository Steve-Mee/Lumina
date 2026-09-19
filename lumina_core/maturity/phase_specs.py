"""Phase specifications + exit proof evaluators (organism continuum)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lumina_core.maturity.continuum import load_continuum
from lumina_core.maturity.maturation_progress import (
    MaturationPhase,
    load_maturation_progress,
)
from lumina_core.maturity.maturity_config import load_maturity_config


@dataclass(frozen=True, slots=True)
class PhaseSpec:
    id: str
    label: str
    human_goal: str
    next_id: str | None
    entry_requires: tuple[str, ...] = ()
    """Prior phase ids that must be completed."""


PHASE_SPECS: dict[str, PhaseSpec] = {
    MaturationPhase.GENESIS.value: PhaseSpec(
        id="genesis",
        label="Genesis",
        human_goal="Contract, vault, fabric — delivery room ready.",
        next_id="birth",
    ),
    MaturationPhase.BIRTH.value: PhaseSpec(
        id="birth",
        label="Birth",
        human_goal="Survive: breathe, sense market, closed training loop.",
        next_id="awakening",
        entry_requires=("genesis",),
    ),
    MaturationPhase.AWAKENING.value: PhaseSpec(
        id="awakening",
        label="Awakening",
        human_goal="Open eyes: prefer better than frozen π*, see regimes, recover. STABLE + n_B≥500.",
        next_id="playground",
        entry_requires=("birth",),
    ),
    MaturationPhase.PLAYGROUND.value: PhaseSpec(
        id="playground",
        label="Playground",
        human_goal="Crawl in NT SIM: first honest fill, n_P≥150, WR≥geometry BE, mean R≥0.",
        next_id="apprenticeship",
        entry_requires=("awakening",),
    ),
    MaturationPhase.APPRENTICESHIP.value: PhaseSpec(
        id="apprenticeship",
        label="Apprenticeship",
        human_goal="Walk: 5 green SIM days under sim_real_guard, Sharpe≥0.20, DD≤12%.",
        next_id="proving_ground",
        entry_requires=("playground",),
    ),
    MaturationPhase.PROVING_GROUND.value: PhaseSpec(
        id="proving_ground",
        label="Proving Ground",
        human_goal="Driving test: cert OOS 48%/0.35/8% + shadow + PromotionGate. No REAL.",
        next_id="real",
        entry_requires=("apprenticeship",),
    ),
    MaturationPhase.REAL.value: PhaseSpec(
        id="real",
        label="REAL",
        human_goal="Profession: live capital under fail-closed constitution.",
        next_id=None,
        entry_requires=("proving_ground",),
    ),
}


def can_start_phase(workspace_root: Path | str, phase: str) -> tuple[bool, str]:
    spec = PHASE_SPECS.get(phase)
    if spec is None:
        return False, f"Unknown phase: {phase}"
    data = load_continuum(workspace_root)
    completed = set(data.get("completed_phases") or [])
    for req in spec.entry_requires:
        if req not in completed:
            if req == "birth" and _birth_ok(workspace_root):
                continue
            if req == "genesis":
                continue
            return False, f"Requires completed phase: {req}"
    if phase in completed and phase != MaturationPhase.REAL.value:
        return True, "re-run_allowed"
    active = data.get("active_phase")
    if active and active != phase:
        return False, f"Another phase is active: {active}"
    return True, "ok"


def _birth_ok(workspace_root: Path | str) -> bool:
    """H7 / ADR-0046: Foundation exit SSOT — artifacts-only is not enough."""
    try:
        from lumina_core.maturity.birth_exit import is_birth_exit_sufficient

        return bool(is_birth_exit_sufficient(workspace_root))
    except Exception:
        return False


def evaluate_exit_proofs(workspace_root: Path | str, phase: str) -> tuple[bool, list[str], dict[str, Any]]:
    """Return (passed, missing_proofs, learned_snapshot). Strict by default."""
    root = Path(workspace_root)
    progress = load_maturation_progress(root)
    reached = set(progress.milestones_reached)
    learned: dict[str, Any] = {"milestones": list(reached)}

    if phase == MaturationPhase.GENESIS.value:
        setup_ok = (root / "state" / "lumina_setup_complete.json").is_file()
        signed = "genesis_contract_signed" in reached
        genesis_proofs: list[str] = []
        if signed:
            genesis_proofs.append("genesis_contract_signed")
        if setup_ok:
            genesis_proofs.append("setup_complete")
        genesis_ok = signed or setup_ok
        genesis_missing: list[str] = [] if genesis_ok else ["genesis_contract_signed"]
        learned["setup_complete"] = setup_ok
        learned["exit_proofs"] = genesis_proofs
        return genesis_ok, genesis_missing, learned

    if phase == MaturationPhase.BIRTH.value:
        # ADR-0036 / H7: survival exit only — never Perfect Birth or REAL gates
        from lumina_core.maturity.birth_exit import evaluate_birth_exit
        from lumina_core.maturity.continuum import _birth_learned_snapshot

        decision = evaluate_birth_exit(root)
        learned.update(_birth_learned_snapshot(root))
        learned["birth_exit"] = decision.to_dict()
        learned["exit_proofs"] = list(decision.proofs)
        return decision.exited, list(decision.missing), learned

    if phase == MaturationPhase.AWAKENING.value:
        from lumina_core.maturity.awakening.law import evaluate_awakening_exit

        return evaluate_awakening_exit(root)

    if phase == MaturationPhase.PLAYGROUND.value:
        from lumina_core.maturity.playground.law import evaluate_playground_exit

        return evaluate_playground_exit(root)

    if phase == MaturationPhase.APPRENTICESHIP.value:
        from lumina_core.maturity.apprenticeship.law import evaluate_apprenticeship_exit

        return evaluate_apprenticeship_exit(root)

    if phase == MaturationPhase.PROVING_GROUND.value:
        from lumina_core.maturity.proving_ground.law import evaluate_proving_ground_exit

        return evaluate_proving_ground_exit(root)

    if phase not in PHASE_SPECS:
        return False, ["unknown_phase"], learned

    if phase == MaturationPhase.REAL.value:
        ok = "human_real_approval" in reached
        missing = [] if ok else ["human_real_approval"]
        try:
            from lumina_core.maturity.maturation_progress import maturation_eligible_for_real

            eligible, blockers = maturation_eligible_for_real(root)
            learned["real_eligible"] = eligible
            learned["blockers"] = blockers
            if not eligible:
                missing.extend(blockers)
                ok = False
        except Exception:
            pass
        return ok, missing, learned

    return False, ["unknown_phase"], learned


def hub_payload(workspace_root: Path | str) -> dict[str, Any]:
    """Operator hub DTO for Genesis-like inter-phase screen."""
    from lumina_core.maturity.continuum import (
        clear_expired_pending_advance,
        load_continuum,
        next_phase_id as _next,
        pending_advance_public,
    )

    root = Path(workspace_root)
    # M7: fail-closed TTL hygiene on every hub poll
    try:
        clear_expired_pending_advance(root)
    except Exception:
        pass
    data = load_continuum(root)
    cfg = load_maturity_config()
    completed = list(data.get("completed_phases") or [])
    active = data.get("active_phase")
    nxt = _next(completed)
    focus = active or nxt or MaturationPhase.REAL.value
    rec = (data.get("phase_records") or {}).get(focus) or {}
    last_completed = completed[-1] if completed else None
    last_rec = (
        (data.get("phase_records") or {}).get(last_completed) or {}
        if last_completed
        else {}
    )

    proofs_ok, missing, learned_eval = evaluate_exit_proofs(root, focus) if focus else (False, [], {})
    focus_learned = rec.get("learned") or {}
    if focus in {
        MaturationPhase.AWAKENING.value,
        MaturationPhase.PLAYGROUND.value,
        MaturationPhase.APPRENTICESHIP.value,
        MaturationPhase.PROVING_GROUND.value,
    } and learned_eval:
        focus_learned = {**focus_learned, **learned_eval}
    specs = {
        pid: {
            "id": s.id,
            "label": s.label,
            "human_goal": s.human_goal,
            "next_id": s.next_id,
            "entry_requires": list(s.entry_requires),
        }
        for pid, s in PHASE_SPECS.items()
    }
    soft_legacy = bool((last_rec.get("learned") or {}).get("soft_complete"))
    pending = data.get("pending_advance")
    pending_public = pending_advance_public(pending if isinstance(pending, dict) else None)
    telegram_advance = {
        "mode_is_telegram": str(data.get("advance_mode") or "") == "telegram",
        "pending": pending_public,
        "configured_ttl_sec": int(cfg.telegram_advance_token_ttl_sec),
        "reissue_available": bool(
            str(data.get("advance_mode") or "") == "telegram"
            and nxt
            and nxt != "real"
        ),
    }
    honesty: dict[str, Any] = {}
    try:
        from lumina_core.maturity.continuum_honesty import continuum_honesty_snapshot

        honesty = continuum_honesty_snapshot(root)
    except Exception as exc:
        honesty = {"schema": "continuum_honesty_v1", "error": str(exc), "honesty_ok": False}

    return {
        "advance_mode": data.get("advance_mode") or "manual",
        "active_phase": active,
        "completed_phases": completed,
        "next_phase": nxt,
        "focus_phase": focus,
        "phase_records": data.get("phase_records") or {},
        "pending_advance": pending_public,
        "telegram_advance": telegram_advance,
        "last_completed": last_completed,
        "learned": last_rec.get("learned") or learned_eval,
        "focus_learned": focus_learned,
        "focus_status": rec.get("status") or "pending",
        "progress_pct": rec.get("progress_pct"),
        "progress_message": rec.get("message"),
        "exit_eval": {"ok": proofs_ok, "missing": missing},
        "phase_specs": specs,
        "can_start_next": can_start_phase(root, nxt)[0] if nxt else False,
        "real_requires_human": True,
        "strict_mode": cfg.strict_exit_proofs,
        "experimental_soft_complete": cfg.experimental_soft_complete,
        "soft_legacy_complete": soft_legacy,
        "telegram_token_ttl_sec": cfg.telegram_advance_token_ttl_sec,
        "updated_at": data.get("updated_at"),
        # M6: READY / Birth-exit / REAL eligibility honesty (SSOT for Phase Hub UI)
        "honesty": honesty,
        "birth_exit_exited": bool((honesty.get("birth_exit") or {}).get("exited")),
        "ready_for_real": bool((honesty.get("ready_for_real") or {}).get("ready")),
        "real_eligible": bool((honesty.get("real_eligible") or {}).get("eligible")),
        "next_honest_steps": list(honesty.get("next_honest_steps") or []),
        "conflation_warnings": list(honesty.get("conflation_warnings") or []),
    }
