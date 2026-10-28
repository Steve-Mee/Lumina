"""Shared Phase 4 test helpers. Synthetic only, no network."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from lumina_research.monitoring.config import ContinuityConfig, load_default_config
from lumina_research.monitoring.loop import ContinuityRuntime
from lumina_research.monitoring.synthetic import DEFAULT_OOS, seal_promotion_pair
from lumina_research.monitoring.types import Instrument, LiveSignal


def make_runtime(
    tmp_path: Path,
    *,
    config: ContinuityConfig | None = None,
    equity: float | None = None,
) -> ContinuityRuntime:
    return ContinuityRuntime(
        audit_path=tmp_path / "audit.jsonl",
        experiment_log_path=tmp_path / "experiments.jsonl",
        config=config,
        evolution_log_dir=tmp_path / "evolution-log",
        equity=equity,
    )


def admit_signal(
    runtime: ContinuityRuntime,
    hypothesis_id: str,
    *,
    trial_id: int,
    instrument: Instrument = "MES",
    quantity: float = 2.0,
    notional: float = 10_000.0,
    oos: Sequence[float] = DEFAULT_OOS,
    pbo: float = 0.12,
    dsr: float = 0.97,
    wfe: float = 0.7,
    n_oos_windows: int | None = None,
    purge_applied: bool = True,
    embargo_applied: bool = True,
    cost_applied: bool = True,
    regimes_complete: bool = True,
    passed: bool = True,
    reject_reasons: tuple[str, ...] = (),
) -> LiveSignal:
    candidate, validation = seal_promotion_pair(
        runtime.authority,
        hypothesis_id=hypothesis_id,
        config_id=hypothesis_id,
        trial_id=trial_id,
        instrument=instrument,
        quantity=quantity,
        notional=notional,
        oos=oos,
        pbo=pbo,
        dsr=dsr,
        wfe=wfe,
        n_oos_windows=n_oos_windows,
        purge_applied=purge_applied,
        embargo_applied=embargo_applied,
        cost_applied=cost_applied,
        regimes_complete=regimes_complete,
        passed=passed,
        reject_reasons=reject_reasons,
    )
    return runtime.admit(candidate, validation)


def default_config() -> ContinuityConfig:
    return load_default_config()
