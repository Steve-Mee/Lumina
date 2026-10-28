"""Proving Ground pass law (ADR-0052). AND-gates, fail-closed, no Birth-JSON/audit cheat."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lumina_core.birth.foundation_metrics import (
    MEDIAN_LOSS_R_MAX,
    POLICY_EDGE_MIN_TRADES,
    S3_OCCUPANCY_MAX,
    S3_OCCUPANCY_MIN,
)
from lumina_core.maturity.post_birth_skill_gates import certificate_oos_walls
from lumina_core.maturity.proving_ground.exam import ALLOWED_SOURCES, MIN_FOLDS

N_G_MIN = int(POLICY_EDGE_MIN_TRADES)
SIM_MODES = frozenset({"sim", "sim_real_guard"})


@dataclass(frozen=True, slots=True)
class ProvingGroundSnapshot:
    n_g: int = 0
    n_plant: int = 0
    occupancy: float | None = None
    median_loss_r: float | None = None
    oos_wr: float | None = None
    oos_sharpe: float | None = None
    dd_pct: float | None = None
    freeze_ok: bool = False
    policy_only: bool = False
    apprenticeship_completed: bool = False
    child_sha: str = ""
    apprenticeship_child_sha: str = ""
    birth_sha: str = ""
    envelope_sealed: bool = False
    envelope_breached: bool = False
    deck_live: bool = False
    mode: str = ""
    recovery_ok: bool = False
    risk_events: int = 0
    var_breach_count: int = 0
    daily_kill: bool = False
    exam_source: str = ""
    exam_folds: int = 0
    exam_eval_only: bool = False
    holdout_b_only: bool = False
    shadow_this_run: bool = False
    promotion_this_run: bool = False
    promotion_criteria_passed: int = 0


@dataclass(frozen=True, slots=True)
class ProvingGroundPassResult:
    passed: bool
    blockers: tuple[str, ...]
    proofs: tuple[str, ...]
    clock_open: bool
    detail: dict[str, Any] = field(default_factory=dict)

    def to_learned(self) -> dict[str, Any]:
        learned = dict(self.detail)
        learned["pass_now"] = self.passed
        learned["clock_open"] = self.clock_open
        learned["blockers"] = list(self.blockers)
        learned["exit_proofs"] = list(self.proofs)
        return learned


def evaluate_proving_ground_pass(snap: ProvingGroundSnapshot) -> ProvingGroundPassResult:
    blockers: list[str] = []
    proofs: list[str] = []
    n_g = int(snap.n_g)
    clock_open = n_g < N_G_MIN

    if not snap.apprenticeship_completed:
        blockers.append("apprenticeship_not_completed")
    else:
        proofs.append("apprenticeship_completed")

    if not snap.freeze_ok:
        blockers.append("birth_freeze_violated")
    else:
        proofs.append("birth_freeze_intact")

    if not _apprenticeship_child_loaded(snap):
        blockers.append("apprenticeship_child_not_loaded")
    else:
        proofs.append("apprenticeship_child_loaded")

    if not snap.envelope_sealed:
        blockers.append("sim_envelope_sealed")
    else:
        proofs.append("sim_envelope_sealed")

    if snap.envelope_breached:
        blockers.append("envelope_breached")
    elif snap.envelope_sealed:
        proofs.append("envelope_not_breached")

    if not snap.deck_live:
        blockers.append("deck_not_live")
    else:
        proofs.append("deck_live")

    mode = str(snap.mode or "").strip().lower()
    if mode == "real":
        blockers.append("mode_real_halt")
    elif mode not in SIM_MODES:
        blockers.append(f"mode_not_sim={mode or 'missing'}")
    else:
        proofs.append("mode_sim_fail_closed")

    if not snap.policy_only:
        blockers.append("skill_not_policy_only")
    else:
        proofs.append("policy_only")

    if n_g < N_G_MIN:
        blockers.append(f"n_G={n_g} < {N_G_MIN}")
    else:
        proofs.append("n_G>=150")

    occ = snap.occupancy
    if occ is None:
        blockers.append("occupancy_missing")
    elif not (S3_OCCUPANCY_MIN - 1e-12 <= float(occ) <= S3_OCCUPANCY_MAX + 1e-12):
        blockers.append(f"occupancy={occ:.4f} not in {S3_OCCUPANCY_MIN:.2f}-{S3_OCCUPANCY_MAX:.2f}")
    else:
        proofs.append("occupancy_in_band")

    if snap.median_loss_r is None:
        blockers.append("median_loss_r_missing")
    elif float(snap.median_loss_r) > MEDIAN_LOSS_R_MAX + 1e-12:
        blockers.append(f"median_loss_r={snap.median_loss_r:.4f} > {MEDIAN_LOSS_R_MAX}")
    else:
        proofs.append("process_r")

    source = str(snap.exam_source or "").strip().lower()
    if source not in ALLOWED_SOURCES:
        blockers.append(f"exam_source={source or 'missing'}")
    else:
        proofs.append("exam_source_proving")
    if not snap.exam_eval_only:
        blockers.append("exam_not_eval_only")
    else:
        proofs.append("exam_eval_only")
    if int(snap.exam_folds) < MIN_FOLDS:
        blockers.append(f"exam_folds={int(snap.exam_folds)} < {MIN_FOLDS}")
    else:
        proofs.append("exam_folds>=5")
    if snap.holdout_b_only:
        blockers.append("exam_holdout_b_only")
    else:
        proofs.append("exam_not_holdout_b_only")

    cert = certificate_oos_walls(
        oos_wr=snap.oos_wr,
        oos_sharpe=snap.oos_sharpe,
        max_dd_pct=snap.dd_pct,
    )
    if not cert.passed:
        blockers.extend(cert.blockers or ["certificate_oos_walls"])
    else:
        proofs.append("certificate_oos_walls")

    if not snap.shadow_this_run:
        blockers.append("shadow_this_run")
    else:
        proofs.append("shadow_this_run")

    if not snap.promotion_this_run or int(snap.promotion_criteria_passed) < 4:
        blockers.append("promotion_gate_this_run")
    else:
        proofs.append("promotion_gate_this_run")

    constitution_hit = (
        int(snap.risk_events) > 0
        or int(snap.var_breach_count) > 0
        or bool(snap.daily_kill)
        or bool(snap.envelope_breached)
        or mode == "real"
    )
    if constitution_hit:
        blockers.append("constitution_violated")
    else:
        proofs.append("constitution_0")

    if not snap.recovery_ok:
        blockers.append("recovery_not_proven")
    else:
        proofs.append("recovery_ok")

    passed = not blockers
    detail = {
        "n_g": n_g,
        "n_plant": int(snap.n_plant),
        "occupancy": snap.occupancy,
        "median_loss_r": snap.median_loss_r,
        "oos_wr": snap.oos_wr,
        "oos_sharpe": snap.oos_sharpe,
        "dd_pct": snap.dd_pct,
        "freeze_ok": snap.freeze_ok,
        "policy_only": snap.policy_only,
        "apprenticeship_completed": snap.apprenticeship_completed,
        "child_sha": snap.child_sha,
        "apprenticeship_child_sha": snap.apprenticeship_child_sha,
        "birth_sha": snap.birth_sha,
        "envelope_sealed": snap.envelope_sealed,
        "envelope_breached": snap.envelope_breached,
        "deck_live": snap.deck_live,
        "mode": mode,
        "recovery_ok": snap.recovery_ok,
        "exam_source": source,
        "exam_folds": int(snap.exam_folds),
        "exam_eval_only": snap.exam_eval_only,
        "holdout_b_only": snap.holdout_b_only,
        "shadow_this_run": snap.shadow_this_run,
        "promotion_this_run": snap.promotion_this_run,
        "promotion_criteria_passed": int(snap.promotion_criteria_passed),
        "certificate_oos_walls": cert.to_dict(),
        "note": "Proving Ground: driving test — cert OOS + shadow + PromotionGate (ADR-0052)",
    }
    return ProvingGroundPassResult(
        passed=passed,
        blockers=tuple(blockers),
        proofs=tuple(proofs),
        clock_open=clock_open and not passed,
        detail=detail,
    )


def snapshot_from_workspace(workspace_root: Path | str) -> ProvingGroundSnapshot:
    from lumina_core.maturity.continuum import load_continuum
    from lumina_core.maturity.playground.envelope import envelope_sealed_for_pass
    from lumina_core.maturity.proving_ground.exam import exam_metrics
    from lumina_core.maturity.proving_ground.evidence import promotion_from_progress
    from lumina_core.maturity.proving_ground.progress import load_proving_ground_progress
    from lumina_core.maturity.proving_ground.shadow import shadow_from_progress
    from lumina_core.maturity.proving_ground.tape import tape_skill_metrics

    root = Path(workspace_root)
    prog = load_proving_ground_progress(root)
    metrics = tape_skill_metrics(root)
    exam = exam_metrics(root)
    promo = promotion_from_progress(prog)
    shadow = shadow_from_progress(prog)
    completed = set(load_continuum(root).get("completed_phases") or [])
    return ProvingGroundSnapshot(
        n_g=int(metrics.get("n_g") or 0),
        n_plant=int(metrics.get("n_plant") or 0),
        occupancy=_f(prog.get("occupancy")),
        median_loss_r=_f(metrics.get("median_loss_r")),
        oos_wr=_f(exam.get("oos_wr")),
        oos_sharpe=_f(exam.get("oos_sharpe")),
        dd_pct=_f(exam.get("dd_pct")),
        freeze_ok=bool(prog.get("freeze_ok")),
        policy_only=bool(metrics.get("policy_only")),
        apprenticeship_completed="apprenticeship" in completed,
        child_sha=str(prog.get("child_sha") or ""),
        apprenticeship_child_sha=str(prog.get("apprenticeship_child_sha") or ""),
        birth_sha=str(prog.get("birth_sha") or ""),
        envelope_sealed=envelope_sealed_for_pass(root),
        envelope_breached=bool(prog.get("envelope_breached")),
        deck_live=bool(prog.get("deck_live")),
        mode=str(prog.get("mode") or ""),
        recovery_ok=bool(prog.get("recovery_ok")),
        risk_events=int(prog.get("risk_events") or 0),
        var_breach_count=int(prog.get("var_breach_count") or 0),
        daily_kill=bool(prog.get("daily_kill")),
        exam_source=str(exam.get("exam_source") or ""),
        exam_folds=int(exam.get("exam_folds") or 0),
        exam_eval_only=bool(exam.get("exam_eval_only")),
        holdout_b_only=bool(exam.get("holdout_b_only")),
        shadow_this_run=bool(shadow.get("shadow_this_run")),
        promotion_this_run=bool(promo.get("promotion_this_run")),
        promotion_criteria_passed=int(promo.get("promotion_criteria_passed") or 0),
    )


def evaluate_proving_ground_exit(
    workspace_root: Path | str,
) -> tuple[bool, list[str], dict[str, Any]]:
    result = evaluate_proving_ground_pass(snapshot_from_workspace(workspace_root))
    learned = result.to_learned()
    missing = list(result.blockers) if not result.passed else []
    return result.passed, missing, learned


def _apprenticeship_child_loaded(snap: ProvingGroundSnapshot) -> bool:
    child = str(snap.child_sha or "")
    apprentice = str(snap.apprenticeship_child_sha or "")
    birth = str(snap.birth_sha or "")
    if not child or not apprentice or not birth:
        return False
    if child != apprentice:
        return False
    return child != birth


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
