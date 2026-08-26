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
        human_goal="Open eyes: prefer better policies, regime awareness, recovery.",
        next_id="playground",
        entry_requires=("birth",),
    ),
    MaturationPhase.PLAYGROUND.value: PhaseSpec(
        id="playground",
        label="Playground",
        human_goal="Crawl safely in SIM: deck, envelope, first sim order.",
        next_id="apprenticeship",
        entry_requires=("awakening",),
    ),
    MaturationPhase.APPRENTICESHIP.value: PhaseSpec(
        id="apprenticeship",
        label="Apprenticeship",
        human_goal="Practice: multi-day SIM stability, never-stop recovery.",
        next_id="proving_ground",
        entry_requires=("playground",),
    ),
    MaturationPhase.PROVING_GROUND.value: PhaseSpec(
        id="proving_ground",
        label="Proving Ground",
        human_goal="Driving test: shadow validation + promotion gate.",
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
    cfg = load_maturity_config()
    soft = bool(cfg.experimental_soft_complete) and not cfg.strict_exit_proofs
    continuum = load_continuum(root)
    rec = (continuum.get("phase_records") or {}).get(phase) or {}

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
        proofs: list[str] = []
        evo = "evolution_proof_passed" in reached or _evolution_proof_file(root)
        if evo:
            proofs.append("evolution_proof_passed")
        twin_samples = _twin_sample_count(root)
        min_twin = cfg.awakening_min_twin_samples
        twin_ok = twin_samples >= min_twin
        learned["twin_samples"] = twin_samples
        learned["twin_min_required"] = min_twin
        learned["twin_ok"] = twin_ok
        if twin_ok:
            proofs.append("twin_observability")

        # Hard: evolution evidence AND twin samples (when min > 0)
        ok = evo and (twin_ok if min_twin > 0 else True)
        # Alternate: evo + birth cert when twin store absent and min samples would block forever
        twin_file_missing = not (root / "state" / "twin_mode_metrics_summary.json").is_file()
        if not ok and evo and twin_file_missing and "birth_certificate_issued" in reached:
            # Still require twin when min_twin > 0 unless soft lab mode
            if soft:
                ok = True
                proofs.append("soft_twin_absent")
                learned["soft_complete"] = True

        if soft and not ok:
            if rec.get("awakening_eval_ok") or (
                "birth_certificate_issued" in reached and _birth_ok(root)
            ):
                ok = True
                learned["soft_complete"] = True
                proofs.append("soft_complete")

        missing: list[str] = []
        if not evo:
            missing.append("evolution_proof_passed")
        if min_twin > 0 and not twin_ok and not (soft and twin_file_missing):
            missing.append(f"twin_samples>={min_twin}")
        if ok:
            missing = []
        return ok, missing, {**learned, "exit_proofs": proofs}

    if phase == MaturationPhase.PLAYGROUND.value:
        missing = []
        if "deck_unlocked" not in reached:
            missing.append("deck_unlocked")
        sealed = _sim_envelope_sealed(root)
        learned["sim_envelope_sealed"] = sealed
        if not sealed:
            missing.append("sim_envelope_sealed")

        first_order = "first_sim_order_placed" in reached
        probe_ok = bool((rec.get("probe") or {}).get("ok")) if isinstance(rec.get("probe"), dict) else False
        learned["first_sim_order"] = first_order
        learned["probe_ok"] = probe_ok
        if cfg.playground_require_first_order and not first_order and not probe_ok:
            missing.append("first_sim_order_placed")

        ok = len(missing) == 0
        if soft and not ok and rec.get("playground_eval_ok"):
            ok = True
            missing = []
            learned["soft_complete"] = True
        return ok, missing, learned

    if phase == MaturationPhase.APPRENTICESHIP.value:
        ok = "sim_real_guard_stable" in reached
        missing = [] if ok else ["sim_real_guard_stable"]
        learned["stable"] = ok
        if soft and not ok and rec.get("apprenticeship_eval_ok"):
            ok = True
            missing = []
            learned["soft_complete"] = True
        return ok, missing, learned

    if phase == MaturationPhase.PROVING_GROUND.value:
        ok = "promotion_gate_passed" in reached or "shadow_validation_passed" in reached
        if cfg.proving_require_promotion_or_shadow:
            # Prefer promotion; shadow alone OK if milestone present
            pass
        missing = [] if ok else ["promotion_gate_passed"]
        if soft and not ok and rec.get("proving_eval_ok"):
            ok = True
            missing = []
            learned["soft_complete"] = True
        return ok, missing, learned

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


def _twin_sample_count(workspace_root: Path) -> int:
    summary = workspace_root / "state" / "twin_mode_metrics_summary.json"
    if not summary.is_file():
        return 0
    try:
        import json

        raw = json.loads(summary.read_text(encoding="utf-8"))
        return int(raw.get("samples", 0) or 0)
    except Exception:
        return 0


def _twin_samples_ok(workspace_root: Path, min_samples: int | None = None) -> bool:
    n = min_samples if min_samples is not None else load_maturity_config().awakening_min_twin_samples
    return _twin_sample_count(workspace_root) >= n


def _evolution_proof_file(workspace_root: Path) -> bool:
    try:
        from lumina_core.birth.evolution_proof_gate import evolution_proof_passed

        return bool(evolution_proof_passed(workspace_root))
    except Exception:
        return False


def _sim_envelope_sealed(workspace_root: Path) -> bool:
    try:
        from lumina_core.risk.sim_envelope import is_sim_envelope_sealed

        return bool(is_sim_envelope_sealed(workspace_root))
    except Exception:
        p = workspace_root / "state" / "sim_envelope_sealed.json"
        if p.is_file():
            try:
                import json

                raw = json.loads(p.read_text(encoding="utf-8"))
                return bool(raw.get("sealed"))
            except Exception:
                return True
        return False


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
    last_completed = completed[-1] if completed else MaturationPhase.GENESIS.value
    last_rec = (data.get("phase_records") or {}).get(last_completed) or {}

    proofs_ok, missing, learned_eval = evaluate_exit_proofs(root, focus) if focus else (False, [], {})
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
        "focus_learned": rec.get("learned") or {},
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
