"""M5 non-birth modularization LOC guards."""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1] / "lumina_core"
_LOC_LIMIT = 400

_MODULES = [
    "notifications/milestone_events.py",
    "notifications/milestone_event_types.py",
    "notifications/milestone_events_birth.py",
    "notifications/milestone_events_plateau.py",
    "evolution/twin_metrics_store.py",
    "evolution/twin_metrics_types.py",
    "code_evolution/pipeline.py",
    "code_evolution/pipeline_process.py",
    "code_evolution/pipeline_finalize.py",
    "rl/infinite_simulator.py",
    "rl/infinite_simulator_ops.py",
    "rl/infinite_simulator_worker.py",
]


def _loc(path: Path) -> int:
    return sum(1 for _ in path.open(encoding="utf-8"))


@pytest.mark.unit
def test_m5_nonbirth_modules_under_loc_bar() -> None:
    for name in _MODULES:
        path = _ROOT / name
        assert path.is_file(), name
        n = _loc(path)
        assert n <= _LOC_LIMIT, f"{name} LOC {n} > {_LOC_LIMIT}"


@pytest.mark.unit
def test_m5_nonbirth_public_imports() -> None:
    from lumina_core.code_evolution.pipeline import CodeEvolutionPipeline
    from lumina_core.evolution.twin_metrics_store import (
        HIGH_CONF_THRESHOLD,
        TwinMetricsStore,
        TwinModeMetricsSnapshot,
    )
    from lumina_core.notifications.milestone_events import (
        birth_started_event,
        plateau_entered_event,
    )
    from lumina_core.rl.infinite_simulator import InfiniteSimulator

    assert HIGH_CONF_THRESHOLD == 0.8
    assert TwinMetricsStore is not None
    assert TwinModeMetricsSnapshot is not None
    assert birth_started_event(training_mode="sim", trade_budget=1).milestone_id
    assert plateau_entered_event(stage_trades=1, winrate=0.4, pass_target=0.45)
    assert issubclass(CodeEvolutionPipeline, object)
    assert InfiniteSimulator is not None
