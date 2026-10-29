"""Read the latest nightly monitoring mutation report. Missing evidence is a fail."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from lumina_research.agents.objects import as_object_dict
from lumina_research.monitoring.acceptance import (
    MUTATION_EQUIVALENT_MAX_FRAC,
    MUTATION_KILL_RATE_MIN,
    MUTATION_MIN_MUTANTS,
)
from lumina_research.monitoring.types import ContinuityRefused

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MUTATION_REPORTS: tuple[Path, ...] = (
    _REPO_ROOT / "experiments" / "reports" / "phase5_empirical_mutation.json",
    _REPO_ROOT / "experiments" / "reports" / "phase4_mutation.json",
)


@dataclass(frozen=True, slots=True)
class MutationFloorResult:
    passed: bool
    kill_rate: float | None
    n_mutants: int
    n_non_equivalent: int
    n_excluded: int
    n_killed: int
    observed: str
    required: str
    path: str


def resolve_mutation_report(
    explicit: Path | None = None,
    *,
    state_dir: Path | None = None,
) -> Path | None:
    """Prefer an explicit path, then state_dir/mutation.json, then committed nightly reports."""
    if explicit is not None:
        return explicit
    if state_dir is not None:
        local = state_dir / "mutation.json"
        if local.is_file():
            return local
    for path in DEFAULT_MUTATION_REPORTS:
        if path.is_file():
            return path
    return None


def evaluate_mutation_floor(path: Path | None) -> MutationFloorResult:
    """Fail closed if the report is missing, malformed, or below Steve's 0.80 floor."""
    required = (
        f"kill_rate>={MUTATION_KILL_RATE_MIN} n_mutants>={MUTATION_MIN_MUTANTS} "
        f"equivalent_frac<={MUTATION_EQUIVALENT_MAX_FRAC}"
    )
    if path is None:
        return MutationFloorResult(
            passed=False,
            kill_rate=None,
            n_mutants=0,
            n_non_equivalent=0,
            n_excluded=0,
            n_killed=0,
            observed="missing",
            required=required,
            path="",
        )
    if not path.is_file():
        return MutationFloorResult(
            passed=False,
            kill_rate=None,
            n_mutants=0,
            n_non_equivalent=0,
            n_excluded=0,
            n_killed=0,
            observed="missing",
            required=required,
            path=str(path),
        )
    try:
        loaded: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return MutationFloorResult(
            passed=False,
            kill_rate=None,
            n_mutants=0,
            n_non_equivalent=0,
            n_excluded=0,
            n_killed=0,
            observed=f"invalid:{type(exc).__name__}",
            required=required,
            path=str(path),
        )
    mapping = as_object_dict(loaded)
    if mapping is None:
        return MutationFloorResult(
            passed=False,
            kill_rate=None,
            n_mutants=0,
            n_non_equivalent=0,
            n_excluded=0,
            n_killed=0,
            observed="invalid:not_object",
            required=required,
            path=str(path),
        )
    try:
        kill_rate = _ratio(mapping.get("kill_rate"), "kill_rate")
        n_mutants = _count(mapping.get("n_mutants"), "n_mutants")
        n_killed = _count(mapping.get("n_killed"), "n_killed")
        n_excluded = _count(mapping.get("n_excluded"), "n_excluded")
        raw_non_eq = mapping.get("n_non_equivalent")
        n_non_equivalent = n_mutants - n_excluded if raw_non_eq is None else _count(raw_non_eq, "n_non_equivalent")
    except ContinuityRefused as exc:
        return MutationFloorResult(
            passed=False,
            kill_rate=None,
            n_mutants=0,
            n_non_equivalent=0,
            n_excluded=0,
            n_killed=0,
            observed=f"invalid:{exc}",
            required=required,
            path=str(path),
        )
    equivalent_frac = 0.0 if n_mutants <= 0 else n_excluded / float(n_mutants)
    passed = (
        n_mutants >= MUTATION_MIN_MUTANTS
        and n_non_equivalent >= MUTATION_MIN_MUTANTS
        and kill_rate >= MUTATION_KILL_RATE_MIN
        and equivalent_frac <= MUTATION_EQUIVALENT_MAX_FRAC
    )
    observed = (
        f"kill_rate={kill_rate:.4f} n_mutants={n_mutants} "
        f"n_non_equivalent={n_non_equivalent} equivalent_frac={equivalent_frac:.4f}"
    )
    return MutationFloorResult(
        passed=passed,
        kill_rate=kill_rate,
        n_mutants=n_mutants,
        n_non_equivalent=n_non_equivalent,
        n_excluded=n_excluded,
        n_killed=n_killed,
        observed=observed,
        required=required,
        path=str(path),
    )


def _ratio(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContinuityRefused(f"{name} must be a number")
    number = float(value)
    if number < 0.0 or number > 1.0:
        raise ContinuityRefused(f"{name} must be in [0, 1]")
    return number


def _count(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContinuityRefused(f"{name} must be an int")
    if value < 0:
        raise ContinuityRefused(f"{name} must be >= 0")
    return value
