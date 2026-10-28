"""Fail-closed snapshot of Risk Core, gate floors, and bound Validation Gate."""

from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass
from pathlib import Path

from lumina_research import fitness as fitness_mod
from lumina_research.risk_core.config import load_default_config
from lumina_research.validation import gate as gate_mod
from lumina_research.validation import pipeline as pipeline_mod
from lumina_research.validation.thresholds import (
    FLOOR_DSR_PROBABILITY_MIN,
    FLOOR_MIN_OOS_WINDOWS,
    FLOOR_PBO_HARD_REJECT,
    FLOOR_PBO_WARNING,
    FLOOR_WFE_MIN,
)

_REPO = Path(__file__).resolve().parents[2]
_RESEARCH = Path(__file__).resolve().parents[1]
_LIMITS = _RESEARCH / "risk_core" / "limits.toml"
_THRESHOLDS_TOML = _RESEARCH / "validation" / "gate_thresholds.toml"
_THRESHOLDS_PY = _RESEARCH / "validation" / "thresholds.py"
_GATE_PY = _RESEARCH / "validation" / "gate.py"
_FITNESS_PY = _RESEARCH / "fitness.py"
_LIVE_RISK = _REPO / "lumina_core" / "risk"
_RESEARCH_RISK = _RESEARCH / "risk_core"

CANONICAL_DSR_MIN = 0.95
CANONICAL_WFE_MIN = 0.5
CANONICAL_PBO_HARD = 0.50
CANONICAL_PBO_WARN = 0.25
CANONICAL_MIN_OOS = 6
CANONICAL_RISK = (0.10, 0.02, 0.10, 4.0, 0.15, 30.0, 1.0)


class IntegrityError(RuntimeError):
    """Protected surface drifted or evolution tried to write it."""


@dataclass(frozen=True, slots=True)
class IntegritySnapshot:
    floors: tuple[float, ...]
    risk_file: tuple[float, ...]
    risk_live: tuple[float, ...]
    live_risk_hash: str
    research_risk_hash: str
    thresholds_toml_hash: str
    thresholds_py_hash: str
    gate_py_hash: str
    fitness_py_hash: str
    bound_gate_id: int
    bound_fitness_id: int
    evaluate_id: int
    compute_fitness_id: int


def capture_integrity() -> IntegritySnapshot:
    live = load_default_config()
    return IntegritySnapshot(
        floors=(
            float(FLOOR_DSR_PROBABILITY_MIN),
            float(FLOOR_WFE_MIN),
            float(FLOOR_PBO_HARD_REJECT),
            float(FLOOR_PBO_WARNING),
            float(FLOOR_MIN_OOS_WINDOWS),
        ),
        risk_file=_parse_limits(),
        risk_live=(
            float(live.max_position_pct),
            float(live.max_daily_loss_pct),
            float(live.max_total_drawdown_pct),
            float(live.leverage_cap),
            float(live.correlation_cluster_limit_pct),
            float(live.heartbeat_timeout_sec),
            float(live.min_quantity),
        ),
        live_risk_hash=_hash_tree(_LIVE_RISK),
        research_risk_hash=_hash_tree(_RESEARCH_RISK),
        thresholds_toml_hash=_hash_file(_THRESHOLDS_TOML),
        thresholds_py_hash=_hash_file(_THRESHOLDS_PY),
        gate_py_hash=_hash_file(_GATE_PY),
        fitness_py_hash=_hash_file(_FITNESS_PY),
        bound_gate_id=id(pipeline_mod.BOUND_GATE),
        bound_fitness_id=id(pipeline_mod.BOUND_FITNESS),
        evaluate_id=id(pipeline_mod.evaluate_candidate),
        compute_fitness_id=id(fitness_mod.compute_fitness),
    )


def assert_intact(snapshot: IntegritySnapshot) -> None:
    live = capture_integrity()
    if live.live_risk_hash != snapshot.live_risk_hash:
        raise IntegrityError("lumina_core/risk drifted")
    if live.research_risk_hash != snapshot.research_risk_hash:
        raise IntegrityError("research Risk Core drifted")
    if live.thresholds_toml_hash != snapshot.thresholds_toml_hash:
        raise IntegrityError("gate_thresholds.toml drifted")
    if live.thresholds_py_hash != snapshot.thresholds_py_hash:
        raise IntegrityError("thresholds.py drifted")
    if live.gate_py_hash != snapshot.gate_py_hash:
        raise IntegrityError("gate.py drifted")
    if live.fitness_py_hash != snapshot.fitness_py_hash:
        raise IntegrityError("fitness.py drifted")
    if live.floors != snapshot.floors:
        raise IntegrityError("gate floor constants drifted")
    if live.risk_file != snapshot.risk_file or live.risk_live != snapshot.risk_live:
        raise IntegrityError("Risk Core config drifted")
    assert_canonical_floors()
    assert_canonical_risk()
    if id(pipeline_mod.BOUND_GATE) != snapshot.bound_gate_id:
        raise IntegrityError("bound validation gate rebound")
    if id(gate_mod.passes_validation_gate) != snapshot.bound_gate_id:
        raise IntegrityError("validation gate monkeypatched")
    if id(pipeline_mod.evaluate_candidate) != snapshot.evaluate_id:
        raise IntegrityError("evaluate_candidate monkeypatched")
    if id(pipeline_mod.BOUND_FITNESS) != snapshot.bound_fitness_id:
        raise IntegrityError("bound fitness rebound")
    if id(fitness_mod.compute_fitness) != snapshot.compute_fitness_id:
        raise IntegrityError("compute_fitness monkeypatched")
    if pipeline_mod.BOUND_GATE is not gate_mod.passes_validation_gate:
        raise IntegrityError("validation gate monkeypatched")
    if pipeline_mod.BOUND_FITNESS is not fitness_mod.compute_fitness:
        raise IntegrityError("fitness monkeypatched")


def assert_canonical_floors() -> None:
    if FLOOR_DSR_PROBABILITY_MIN != CANONICAL_DSR_MIN:
        raise IntegrityError("dsr floor drifted")
    if FLOOR_WFE_MIN != CANONICAL_WFE_MIN:
        raise IntegrityError("wfe floor drifted")
    if FLOOR_PBO_HARD_REJECT != CANONICAL_PBO_HARD:
        raise IntegrityError("pbo hard floor drifted")
    if FLOOR_PBO_WARNING != CANONICAL_PBO_WARN:
        raise IntegrityError("pbo warning floor drifted")
    if FLOOR_MIN_OOS_WINDOWS != CANONICAL_MIN_OOS:
        raise IntegrityError("min OOS windows floor drifted")


def assert_canonical_risk() -> None:
    parsed = _parse_limits()
    if parsed != CANONICAL_RISK:
        raise IntegrityError("limits.toml drifted from canonical Risk Core values")
    live = load_default_config()
    live_vals = (
        float(live.max_position_pct),
        float(live.max_daily_loss_pct),
        float(live.max_total_drawdown_pct),
        float(live.leverage_cap),
        float(live.correlation_cluster_limit_pct),
        float(live.heartbeat_timeout_sec),
        float(live.min_quantity),
    )
    if live_vals != CANONICAL_RISK:
        raise IntegrityError("load_default_config drifted from canonical Risk Core values")


def refuse_protected_write(path: Path) -> None:
    del path
    raise IntegrityError("evolution cannot write Risk Core or gate thresholds")


def _parse_limits() -> tuple[float, ...]:
    with _LIMITS.open("rb") as handle:
        raw = tomllib.load(handle)
    return (
        float(raw["max_position_pct"]),
        float(raw["max_daily_loss_pct"]),
        float(raw["max_total_drawdown_pct"]),
        float(raw["leverage_cap"]),
        float(raw["correlation_cluster_limit_pct"]),
        float(raw["heartbeat_timeout_sec"]),
        float(raw["min_quantity"]),
    )


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
