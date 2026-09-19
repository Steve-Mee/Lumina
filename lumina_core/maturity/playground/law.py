"""Playground pass law (ADR-0050). AND-gates, fail-closed, no JSON/Birth-tape cheat."""
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
from lumina_core.maturity.post_birth_skill_gates import economic_viability

N_P_MIN = int(POLICY_EDGE_MIN_TRADES)
SIM_MODES = frozenset({"sim", "sim_real_guard"})


@dataclass(frozen=True, slots=True)
class PlaygroundSnapshot:
    n_p: int = 0
    n_plant: int = 0
    occupancy: float | None = None
    skill_wr: float | None = None
    breakeven_wr: float | None = None
    mean_r: float | None = None
    median_loss_r: float | None = None
    freeze_ok: bool = False
    policy_only: bool = False
    child_sha: str = ""
    awakening_child_sha: str = ""
    birth_sha: str = ""
    envelope_sealed: bool = False
    envelope_breached: bool = False
    deck_live: bool = False
    mode: str = ""
    first_fill: bool = False
    first_fill_source: str = ""


@dataclass(frozen=True, slots=True)
class PlaygroundPassResult:
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


def evaluate_playground_pass(snap: PlaygroundSnapshot) -> PlaygroundPassResult:
    blockers: list[str] = []
    proofs: list[str] = []
    n_p = int(snap.n_p)
    clock_open = n_p < N_P_MIN

    if not snap.freeze_ok:
        blockers.append("birth_freeze_violated")
    else:
        proofs.append("birth_freeze_intact")

    if not _awakening_child_loaded(snap):
        blockers.append("awakening_child_not_loaded")
    else:
        proofs.append("awakening_child_loaded")

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
    if mode not in SIM_MODES:
        blockers.append(f"mode_not_sim={mode or 'missing'}")
    else:
        proofs.append("mode_sim_fail_closed")

    if not snap.first_fill or str(snap.first_fill_source or "") not in {
        "orderpath",
        "ops_place_order",
        "venue_fill",
    }:
        blockers.append("first_honest_fill")
    else:
        proofs.append("first_honest_fill")

    if not snap.policy_only:
        blockers.append("skill_not_policy_only")
    else:
        proofs.append("policy_only")

    if n_p < N_P_MIN:
        blockers.append(f"n_P={n_p} < {N_P_MIN}")
    else:
        proofs.append("n_P>=150")

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

    econ = economic_viability(
        mean_r=snap.mean_r,
        skill_wr=snap.skill_wr,
        breakeven_wr=snap.breakeven_wr,
    )
    if not econ.passed:
        blockers.extend(econ.blockers or ["economic_viability"])
    else:
        proofs.append("economic_viability")

    passed = not blockers
    detail = {
        "n_p": n_p,
        "n_plant": int(snap.n_plant),
        "occupancy": snap.occupancy,
        "skill_wr": snap.skill_wr,
        "breakeven_wr": snap.breakeven_wr,
        "mean_r": snap.mean_r,
        "median_loss_r": snap.median_loss_r,
        "freeze_ok": snap.freeze_ok,
        "policy_only": snap.policy_only,
        "child_sha": snap.child_sha,
        "awakening_child_sha": snap.awakening_child_sha,
        "birth_sha": snap.birth_sha,
        "envelope_sealed": snap.envelope_sealed,
        "envelope_breached": snap.envelope_breached,
        "deck_live": snap.deck_live,
        "mode": mode,
        "first_fill": snap.first_fill,
        "first_fill_source": snap.first_fill_source,
        "economic_viability": econ.to_dict(),
        "note": "Playground: first contact — crawl in NT SIM, WR≥BE, mean R≥0 (ADR-0050)",
    }
    return PlaygroundPassResult(
        passed=passed,
        blockers=tuple(blockers),
        proofs=tuple(proofs),
        clock_open=clock_open and not passed,
        detail=detail,
    )


def snapshot_from_workspace(workspace_root: Path | str) -> PlaygroundSnapshot:
    from lumina_core.maturity.playground.envelope import envelope_sealed_for_pass
    from lumina_core.maturity.playground.fills import first_honest_fill
    from lumina_core.maturity.playground.progress import load_playground_progress
    from lumina_core.maturity.playground.tape import tape_skill_metrics

    root = Path(workspace_root)
    prog = load_playground_progress(root)
    metrics = tape_skill_metrics(root)
    fill = first_honest_fill(root)
    fill_source = str((fill or {}).get("source") or "")
    return PlaygroundSnapshot(
        n_p=int(metrics.get("n_p") or 0),
        n_plant=int(metrics.get("n_plant") or 0),
        occupancy=_f(prog.get("occupancy")),
        skill_wr=_f(metrics.get("skill_wr")),
        breakeven_wr=_f(prog.get("breakeven_wr")),
        mean_r=_f(metrics.get("mean_r")),
        median_loss_r=_f(metrics.get("median_loss_r")),
        freeze_ok=bool(prog.get("freeze_ok")),
        policy_only=bool(metrics.get("policy_only")),
        child_sha=str(prog.get("child_sha") or ""),
        awakening_child_sha=str(prog.get("awakening_child_sha") or ""),
        birth_sha=str(prog.get("birth_sha") or ""),
        envelope_sealed=envelope_sealed_for_pass(root),
        envelope_breached=bool(prog.get("envelope_breached")),
        deck_live=bool(prog.get("deck_live")),
        mode=str(prog.get("mode") or ""),
        first_fill=fill is not None,
        first_fill_source=fill_source,
    )


def evaluate_playground_exit(
    workspace_root: Path | str,
) -> tuple[bool, list[str], dict[str, Any]]:
    result = evaluate_playground_pass(snapshot_from_workspace(workspace_root))
    learned = result.to_learned()
    missing = list(result.blockers) if not result.passed else []
    return result.passed, missing, learned


def _awakening_child_loaded(snap: PlaygroundSnapshot) -> bool:
    child = str(snap.child_sha or "")
    awake = str(snap.awakening_child_sha or "")
    birth = str(snap.birth_sha or "")
    if not child or not awake or not birth:
        return False
    if child != awake:
        return False
    return child != birth


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
