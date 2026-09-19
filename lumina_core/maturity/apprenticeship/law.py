"""Apprenticeship pass law (ADR-0051). AND-gates, fail-closed, no backtest/JSON cheat."""
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
from lumina_core.maturity.apprenticeship.days import N_D_MIN
from lumina_core.maturity.post_birth_skill_gates import (
    RISK_DD_MAX_PCT,
    RISK_SHARPE_MIN,
    risk_discipline,
)

N_A_MIN = int(POLICY_EDGE_MIN_TRADES)
REQUIRED_MODE = "sim_real_guard"


@dataclass(frozen=True, slots=True)
class ApprenticeshipSnapshot:
    n_a: int = 0
    n_plant: int = 0
    n_d: int = 0
    occupancy: float | None = None
    median_loss_r: float | None = None
    sharpe: float | None = None
    dd_pct: float | None = None
    freeze_ok: bool = False
    policy_only: bool = False
    playground_completed: bool = False
    child_sha: str = ""
    playground_child_sha: str = ""
    birth_sha: str = ""
    envelope_sealed: bool = False
    envelope_breached: bool = False
    deck_live: bool = False
    mode: str = ""
    recovery_ok: bool = False
    risk_events: int = 0
    var_breach_count: int = 0
    daily_kill: bool = False


@dataclass(frozen=True, slots=True)
class ApprenticeshipPassResult:
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


def evaluate_apprenticeship_pass(snap: ApprenticeshipSnapshot) -> ApprenticeshipPassResult:
    blockers: list[str] = []
    proofs: list[str] = []
    n_a = int(snap.n_a)
    n_d = int(snap.n_d)
    clock_open = n_a < N_A_MIN or n_d < N_D_MIN

    if not snap.playground_completed:
        blockers.append("playground_not_completed")
    else:
        proofs.append("playground_completed")

    if not snap.freeze_ok:
        blockers.append("birth_freeze_violated")
    else:
        proofs.append("birth_freeze_intact")

    if not _playground_child_loaded(snap):
        blockers.append("playground_child_not_loaded")
    else:
        proofs.append("playground_child_loaded")

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
    if mode != REQUIRED_MODE:
        blockers.append(f"mode_not_sim_real_guard={mode or 'missing'}")
    else:
        proofs.append("mode_sim_real_guard")

    if not snap.policy_only:
        blockers.append("skill_not_policy_only")
    else:
        proofs.append("policy_only")

    if n_a < N_A_MIN:
        blockers.append(f"n_A={n_a} < {N_A_MIN}")
    else:
        proofs.append("n_A>=150")

    if n_d < N_D_MIN:
        blockers.append(f"n_D={n_d} < {N_D_MIN}")
    else:
        proofs.append("n_D>=5")

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

    risk = risk_discipline(sharpe=snap.sharpe, max_dd_pct=snap.dd_pct)
    if not risk.passed:
        blockers.extend(risk.blockers or ["risk_discipline"])
    else:
        proofs.append("risk_discipline")

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
        "n_a": n_a,
        "n_plant": int(snap.n_plant),
        "n_d": n_d,
        "occupancy": snap.occupancy,
        "median_loss_r": snap.median_loss_r,
        "sharpe": snap.sharpe,
        "dd_pct": snap.dd_pct,
        "sharpe_min": RISK_SHARPE_MIN,
        "dd_max_pct": RISK_DD_MAX_PCT,
        "freeze_ok": snap.freeze_ok,
        "policy_only": snap.policy_only,
        "playground_completed": snap.playground_completed,
        "child_sha": snap.child_sha,
        "playground_child_sha": snap.playground_child_sha,
        "birth_sha": snap.birth_sha,
        "envelope_sealed": snap.envelope_sealed,
        "envelope_breached": snap.envelope_breached,
        "deck_live": snap.deck_live,
        "mode": mode,
        "recovery_ok": snap.recovery_ok,
        "risk_events": int(snap.risk_events),
        "var_breach_count": int(snap.var_breach_count),
        "daily_kill": bool(snap.daily_kill),
        "risk_discipline": risk.to_dict(),
        "note": "Apprenticeship: walk — multi-day SIM under REAL rules (ADR-0051)",
    }
    return ApprenticeshipPassResult(
        passed=passed,
        blockers=tuple(blockers),
        proofs=tuple(proofs),
        clock_open=clock_open and not passed,
        detail=detail,
    )


def snapshot_from_workspace(workspace_root: Path | str) -> ApprenticeshipSnapshot:
    from lumina_core.maturity.apprenticeship.days import tape_day_metrics
    from lumina_core.maturity.apprenticeship.progress import load_apprenticeship_progress
    from lumina_core.maturity.apprenticeship.tape import tape_skill_metrics
    from lumina_core.maturity.continuum import load_continuum
    from lumina_core.maturity.playground.envelope import envelope_sealed_for_pass

    root = Path(workspace_root)
    prog = load_apprenticeship_progress(root)
    metrics = tape_skill_metrics(root)
    days = tape_day_metrics(root)
    completed = set(load_continuum(root).get("completed_phases") or [])
    return ApprenticeshipSnapshot(
        n_a=int(metrics.get("n_a") or 0),
        n_plant=int(metrics.get("n_plant") or 0),
        n_d=int(days.get("n_d") or 0),
        occupancy=_f(prog.get("occupancy")),
        median_loss_r=_f(metrics.get("median_loss_r")),
        sharpe=_f(days.get("sharpe")),
        dd_pct=_f(days.get("dd_pct")),
        freeze_ok=bool(prog.get("freeze_ok")),
        policy_only=bool(metrics.get("policy_only")),
        playground_completed="playground" in completed,
        child_sha=str(prog.get("child_sha") or ""),
        playground_child_sha=str(prog.get("playground_child_sha") or ""),
        birth_sha=str(prog.get("birth_sha") or ""),
        envelope_sealed=envelope_sealed_for_pass(root),
        envelope_breached=bool(prog.get("envelope_breached")),
        deck_live=bool(prog.get("deck_live")),
        mode=str(prog.get("mode") or ""),
        recovery_ok=bool(prog.get("recovery_ok")),
        risk_events=int(prog.get("risk_events") or 0),
        var_breach_count=int(prog.get("var_breach_count") or 0),
        daily_kill=bool(prog.get("daily_kill")),
    )


def evaluate_apprenticeship_exit(
    workspace_root: Path | str,
) -> tuple[bool, list[str], dict[str, Any]]:
    result = evaluate_apprenticeship_pass(snapshot_from_workspace(workspace_root))
    learned = result.to_learned()
    missing = list(result.blockers) if not result.passed else []
    return result.passed, missing, learned


def _playground_child_loaded(snap: ApprenticeshipSnapshot) -> bool:
    child = str(snap.child_sha or "")
    play = str(snap.playground_child_sha or "")
    birth = str(snap.birth_sha or "")
    if not child or not play or not birth:
        return False
    if child != play:
        return False
    return child != birth


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
