"""Playground school law (ADR-0050). Five green SIM days. No JSON, no shadow fill, no Birth tape."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lumina_core.maturity.apprenticeship.days import N_D_MIN

N_D_SCHOOL = int(N_D_MIN)
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
    baseline_zip_sha: str = ""
    birth_sha: str = ""
    envelope_sealed: bool = False
    envelope_breached: bool = False
    envelope_telemetry: str = "ok"
    breakeven_source: str = ""
    fallback_breakeven_wr: float | None = None
    deck_live: bool = False
    mode: str = ""
    first_fill: bool = False
    first_fill_source: str = ""
    green_days: int = 0


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
    green_days = int(snap.green_days)
    clock_open = green_days < N_D_SCHOOL

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

    telemetry = str(snap.envelope_telemetry or "ok")
    if telemetry not in {"ok", "not_required"}:
        blockers.append("envelope_telemetry_missing")
    elif snap.envelope_sealed and telemetry == "ok":
        proofs.append("envelope_telemetry")

    if not snap.deck_live:
        blockers.append("deck_not_live")
    else:
        proofs.append("deck_live")

    mode = str(snap.mode or "").strip().lower()
    if mode not in SIM_MODES:
        blockers.append(f"mode_not_sim={mode or 'missing'}")
    else:
        proofs.append("mode_sim_fail_closed")

    if not snap.policy_only:
        blockers.append("skill_not_policy_only")
    else:
        proofs.append("policy_only")

    if green_days < N_D_SCHOOL:
        blockers.append(f"green_days={green_days} < {N_D_SCHOOL}")
    else:
        proofs.append("green_days>=5")

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
        "envelope_telemetry": telemetry,
        "breakeven_source": snap.breakeven_source,
        "fallback_breakeven_wr": snap.fallback_breakeven_wr,
        "deck_live": snap.deck_live,
        "mode": mode,
        "first_fill": snap.first_fill,
        "first_fill_source": snap.first_fill_source,
        "green_days": green_days,
        "green_days_need": N_D_SCHOOL,
        "note": "Playground school: five green SIM session days of the living policy (ADR-0050)",
    }
    return PlaygroundPassResult(
        passed=passed,
        blockers=tuple(blockers),
        proofs=tuple(proofs),
        clock_open=clock_open and not passed,
        detail=detail,
    )


def _measured_occupancy(root: Path, prog: dict[str, Any], *, n_p: int) -> float | None:
    """Occupancy file first. A stored number with no sample is not a measurement."""
    from lumina_core.maturity.playground.crawl import crawl_totals
    from lumina_core.maturity.playground.habitat import OCCUPANCY_REL

    path = root / OCCUPANCY_REL
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = None
        if isinstance(raw, dict):
            measured = _f(raw.get("occupancy"))
            if measured is not None:
                return measured
    sampled = int(n_p) > 0 or int(crawl_totals(root).get("total_bars") or 0) > 0
    if not sampled:
        return None
    return _f(prog.get("occupancy"))


def snapshot_from_workspace(workspace_root: Path | str) -> PlaygroundSnapshot:
    from lumina_core.maturity.playground.crawl import bars_are_flowing
    from lumina_core.maturity.playground.envelope import assess_envelope
    from lumina_core.maturity.playground.fills import first_honest_fill
    from lumina_core.maturity.playground.habitat import live_breakeven_wr
    from lumina_core.maturity.playground.progress import load_playground_progress
    from lumina_core.maturity.playground.tape import tape_breakeven_wr, tape_skill_metrics

    root = Path(workspace_root)
    prog = load_playground_progress(root)
    metrics = tape_skill_metrics(root)
    fill = first_honest_fill(root)
    fill_source = str((fill or {}).get("source") or "")
    n_p = int(metrics.get("n_p") or 0)
    flowing = bars_are_flowing(root)
    envelope = assess_envelope(
        root,
        n_p=n_p,
        bars_flowing=flowing,
        latched_breach=bool(prog.get("envelope_breached")),
    )
    be_wr, be_source = tape_breakeven_wr(root)
    if n_p <= 0:
        gate_be = None
        be_source = "no_closes"
    else:
        gate_be = be_wr
    return PlaygroundSnapshot(
        n_p=n_p,
        n_plant=int(metrics.get("n_plant") or 0),
        occupancy=_measured_occupancy(root, prog, n_p=n_p),
        skill_wr=_f(metrics.get("skill_wr")),
        breakeven_wr=gate_be,
        mean_r=_f(metrics.get("mean_r")),
        median_loss_r=_f(metrics.get("median_loss_r")),
        freeze_ok=bool(prog.get("freeze_ok")),
        policy_only=bool(metrics.get("policy_only")),
        child_sha=str(prog.get("child_sha") or ""),
        awakening_child_sha=str(prog.get("awakening_child_sha") or ""),
        baseline_zip_sha=_baseline_zip_sha(root),
        birth_sha=str(prog.get("birth_sha") or ""),
        envelope_sealed=bool(envelope["sealed"]),
        envelope_breached=bool(envelope["breached"]),
        envelope_telemetry=str(envelope["telemetry"]),
        breakeven_source=be_source,
        fallback_breakeven_wr=live_breakeven_wr(root),
        deck_live=bool(prog.get("deck_live")),
        mode=str(prog.get("mode") or ""),
        first_fill=fill is not None,
        first_fill_source=fill_source,
        green_days=_green_days(root),
    )


def evaluate_playground_exit(
    workspace_root: Path | str,
) -> tuple[bool, list[str], dict[str, Any]]:
    result = evaluate_playground_pass(snapshot_from_workspace(workspace_root))
    learned = result.to_learned()
    missing = list(result.blockers) if not result.passed else []
    return result.passed, missing, learned


def _green_days(root: Path) -> int:
    from lumina_core.maturity.playground.school_days import green_day_streak

    return int(green_day_streak(root))


def _awakening_child_loaded(snap: PlaygroundSnapshot) -> bool:
    """The loaded zip is the First Watch baseline. That zip may be the Birth plant."""
    child = str(snap.child_sha or "")
    awake = str(snap.awakening_child_sha or "")
    baseline = str(snap.baseline_zip_sha or "")
    if not child or not awake or not baseline:
        return False
    return child == awake == baseline


def _baseline_zip_sha(root: Path) -> str:
    from lumina_core.maturity.awakening.baseline import seal_matches_disk

    seal = seal_matches_disk(root)
    return str(seal.get("zip_sha256") or "")


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
