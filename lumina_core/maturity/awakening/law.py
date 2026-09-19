"""Awakening pass law (ADR-0049). AND-gates, fail-closed, no WR-only cheat."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lumina_core.birth.foundation_metrics import (
    MEDIAN_LOSS_R_MAX,
    POLICY_EDGE_MIN_TRADES,
    S3_OCCUPANCY_MAX,
    S3_OCCUPANCY_MIN,
    S4_EDGE_MIN,
    S5_DD_MAX_PCT,
    S5_SHARPE_FLOOR,
)
from lumina_core.maturity.post_birth_skill_gates import (
    EVOLUTION_PROOF_LIFT_MIN,
    EVOLUTION_PROOF_OOS_WR_MIN,
)

N_B_MIN = 500
STABLE = "STABLE"
CLASS_INCONCLUSIVE = "INCONCLUSIVE"
CLASS_REGRESS = "GRIND_REGRESS"


@dataclass(frozen=True, slots=True)
class AwakeningSnapshot:
    n_b: int = 0
    n_plant: int = 0
    occupancy: float | None = None
    wr: float | None = None
    birth_oos_wr: float | None = None
    mean_r: float | None = None
    birth_mean_r: float | None = None
    edge: float | None = None
    median_loss_r: float | None = None
    sharpe: float | None = None
    dd_pct: float | None = None
    stable_class: str = CLASS_INCONCLUSIVE
    freeze_ok: bool = False
    policy_only: bool = False
    child_sha: str = ""
    init_sha: str = ""
    twin_watch_n: int = 0
    recovery_ok: bool = False
    regime_slices: tuple[str, ...] = ()
    regime_observed: tuple[str, ...] = ()
    tape_exhausted: bool = False
    proof_record_passed: bool = False


@dataclass(frozen=True, slots=True)
class AwakeningPassResult:
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


def evaluate_awakening_pass(snap: AwakeningSnapshot) -> AwakeningPassResult:
    blockers: list[str] = []
    proofs: list[str] = []
    n_b = int(snap.n_b)
    clock_open = n_b < N_B_MIN

    if not snap.freeze_ok:
        blockers.append("birth_freeze_violated")
    else:
        proofs.append("birth_freeze_intact")

    if not snap.policy_only:
        blockers.append("skill_not_policy_only")
    else:
        proofs.append("policy_only")

    if n_b < N_B_MIN:
        blockers.append(f"n_B={n_b} < {N_B_MIN}")
    else:
        proofs.append("n_B>=500")

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

    if n_b < int(POLICY_EDGE_MIN_TRADES):
        pass
    elif snap.edge is None:
        blockers.append("edge_missing")
    elif float(snap.edge) + 1e-12 < S4_EDGE_MIN:
        blockers.append(f"edge={snap.edge:.4f} < {S4_EDGE_MIN}")
    else:
        proofs.append("prefer_better_edge")

    if snap.mean_r is None or snap.birth_mean_r is None:
        blockers.append("mean_r_or_birth_mean_r_missing")
    elif float(snap.mean_r) + 1e-12 < float(snap.birth_mean_r):
        blockers.append(
            f"mean_r={snap.mean_r:.4f} < birth_mean_r={snap.birth_mean_r:.4f}"
        )
    else:
        proofs.append("prefer_better_mean_r")

    adr = _adr0026(snap)
    if adr is not None:
        blockers.append(adr)
    else:
        proofs.append("evolution_proof_passed")

    if str(snap.stable_class or "") != STABLE:
        blockers.append(f"stable_class={snap.stable_class or CLASS_INCONCLUSIVE}")
    else:
        if snap.sharpe is None or float(snap.sharpe) <= S5_SHARPE_FLOOR:
            blockers.append(f"sharpe={snap.sharpe} <= {S5_SHARPE_FLOOR}")
        elif snap.dd_pct is None or float(snap.dd_pct) > S5_DD_MAX_PCT + 1e-12:
            blockers.append(f"dd={snap.dd_pct} > {S5_DD_MAX_PCT}")
        else:
            proofs.append("STABLE")

    child = str(snap.child_sha or "")
    init = str(snap.init_sha or "")
    if not child or not init:
        blockers.append("child_or_init_sha_missing")
    elif child == init:
        blockers.append("child_sha_equals_init")
    else:
        proofs.append("no_substitution")

    if int(snap.twin_watch_n) < 1:
        blockers.append("twin_watch_missing")
    else:
        proofs.append("twin_watch")

    if not snap.recovery_ok:
        blockers.append("recovery_not_proven")
    else:
        proofs.append("recovery_ok")

    if not snap.regime_observed:
        blockers.append("regime_visibility_missing")
    else:
        proofs.append("regime_visibility")

    passed = not blockers
    detail = {
        "n_b": n_b,
        "n_plant": int(snap.n_plant),
        "occupancy": snap.occupancy,
        "wr": snap.wr,
        "birth_oos_wr": snap.birth_oos_wr,
        "lift": _lift(snap),
        "mean_r": snap.mean_r,
        "birth_mean_r": snap.birth_mean_r,
        "edge": snap.edge,
        "median_loss_r": snap.median_loss_r,
        "sharpe": snap.sharpe,
        "dd_pct": snap.dd_pct,
        "stable_class": snap.stable_class,
        "freeze_ok": snap.freeze_ok,
        "policy_only": snap.policy_only,
        "twin_watch_n": int(snap.twin_watch_n),
        "recovery_ok": snap.recovery_ok,
        "regime_slices": list(snap.regime_slices),
        "regime_observed": list(snap.regime_observed),
        "tape_exhausted": snap.tape_exhausted,
        "proof_record_passed": snap.proof_record_passed,
        "note": "Awakening: eyes open — prefer better, see regimes, recover (ADR-0049)",
    }
    return AwakeningPassResult(
        passed=passed,
        blockers=tuple(blockers),
        proofs=tuple(proofs),
        clock_open=clock_open and not passed,
        detail=detail,
    )


def _lift(snap: AwakeningSnapshot) -> float | None:
    if snap.wr is None or snap.birth_oos_wr is None:
        return None
    return float(snap.wr) - float(snap.birth_oos_wr)


def _adr0026(snap: AwakeningSnapshot) -> str | None:
    if snap.wr is None or snap.birth_oos_wr is None:
        return "adr0026_wr_missing"
    wr = float(snap.wr)
    birth = float(snap.birth_oos_wr)
    lift = wr - birth
    if wr + 1e-12 >= EVOLUTION_PROOF_OOS_WR_MIN:
        return None
    if lift + 1e-12 >= EVOLUTION_PROOF_LIFT_MIN:
        return None
    return (
        f"insufficient lift {lift:.1%} (need {EVOLUTION_PROOF_LIFT_MIN:.1%} "
        f"or OOS >= {EVOLUTION_PROOF_OOS_WR_MIN:.1%})"
    )


def snapshot_from_workspace(workspace_root: Path | str) -> AwakeningSnapshot:
    from lumina_core.birth.evolution_proof_gate import load_evolution_proof_record
    from lumina_core.birth.fitness_vector import load_fitness_vector
    from lumina_core.maturity.awakening.progress import load_awakening_progress
    from lumina_core.maturity.awakening.twin_watch import watch_count

    root = Path(workspace_root)
    prog = load_awakening_progress(root)
    rec = load_evolution_proof_record(root)
    vector = load_fitness_vector(root)
    slices_raw = prog.get("regime_slices") if prog else None
    slices: tuple[str, ...] = ()
    if isinstance(slices_raw, (list, tuple)):
        slices = tuple(str(s) for s in slices_raw if s)
    observed_raw = prog.get("regime_observed") if prog else None
    observed: tuple[str, ...] = ()
    if isinstance(observed_raw, (list, tuple)):
        observed = tuple(str(s) for s in observed_raw if s)
    elif isinstance((prog.get("regime_status") if prog else None), dict):
        status = prog.get("regime_status") or {}
        observed = tuple(k for k, v in status.items() if str(v) == "observed")

    wr = _f(prog.get("wr") if prog else None)
    if wr is None:
        wr = _f(rec.get("polish_oos_winrate") or rec.get("oos_winrate"))
    birth_wr = _f(prog.get("birth_oos_wr") if prog else None)
    if birth_wr is None:
        birth_wr = _f(rec.get("birth_exit_winrate"))
    if birth_wr is None and vector is not None:
        birth_wr = float(vector.oos_wr)
    birth_mean = _f(prog.get("birth_mean_r") if prog else None)
    if birth_mean is None and vector is not None:
        birth_mean = float(vector.mean_r)
    n_b = int(prog.get("n_b") or rec.get("holdout_trades") or 0)

    return AwakeningSnapshot(
        n_b=n_b,
        n_plant=int(prog.get("n_plant") or 0),
        occupancy=_f(prog.get("occupancy") if prog else None),
        wr=wr,
        birth_oos_wr=birth_wr,
        mean_r=_f(prog.get("mean_r") if prog else None),
        birth_mean_r=birth_mean,
        edge=_f(prog.get("edge") if prog else None),
        median_loss_r=_f(prog.get("median_loss_r") if prog else None),
        sharpe=_f(prog.get("sharpe") if prog else None),
        dd_pct=_f(prog.get("dd_pct") if prog else None),
        stable_class=str(prog.get("stable_class") or CLASS_INCONCLUSIVE),
        freeze_ok=bool(prog.get("freeze_ok")),
        policy_only=bool(prog.get("policy_only")),
        child_sha=str(prog.get("child_sha") or rec.get("child_sha256") or ""),
        init_sha=str(prog.get("init_sha") or rec.get("init_sha256") or ""),
        twin_watch_n=watch_count(root),
        recovery_ok=bool(prog.get("recovery_ok")),
        regime_slices=slices,
        regime_observed=observed,
        tape_exhausted=bool(prog.get("tape_exhausted")),
        proof_record_passed=bool(rec.get("passed")),
    )


def evaluate_awakening_exit(
    workspace_root: Path | str,
) -> tuple[bool, list[str], dict[str, Any]]:
    result = evaluate_awakening_pass(snapshot_from_workspace(workspace_root))
    learned = result.to_learned()
    missing = list(result.blockers) if not result.passed else []
    return result.passed, missing, learned


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
