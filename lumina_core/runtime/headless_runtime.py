# CANONICAL IMPLEMENTATION – Lumina v51
# HeadlessRuntime: deterministic, non-UI trade-loop runner for CI/CD and smoke validation.
# Outputs structured JSON summary to stdout + state/last_run_summary.json.
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from lumina_core.engine.stress_suite_runner import StressSuiteRunner
from lumina_core.evolution.simulator_data_support import (  # noqa: F401
    require_real_simulator_data_strict,
)
from lumina_core.runtime.headless_config import parse_duration_minutes
from lumina_core.runtime.headless_runtime_loop import (
    _check_session_guard,  # noqa: F401
    _count_evolution_proposals,  # noqa: F401
    _count_observability_alerts,  # noqa: F401
    _resolve_summary_path,  # noqa: F401
    _validate_broker,
    execute_headless_run,
    persist_headless_summary,
)
from lumina_core.runtime.headless_ticks import (
    _generate_synthetic_ticks,
    _run_simulation,
)

# Mutable module attrs — tests monkeypatch ``_SUMMARY_PATH`` on this module.
_DEFAULT_SUMMARY_PATH = Path("state/last_run_summary.json")
_SUMMARY_PATH = _DEFAULT_SUMMARY_PATH

# Re-exports for public/test import paths.
__all__ = [
    "HeadlessRuntime",
    "parse_duration_minutes",
    "_generate_synthetic_ticks",
    "_run_simulation",
    "_validate_broker",
]


class HeadlessRuntime:
    """
    Deterministic headless trading runtime for smoke-test and CI/CD validation.

    Usage::

        runtime = HeadlessRuntime()
        summary = runtime.run(duration_minutes=15, mode="paper", broker_mode="paper")
        # summary is also printed to stdout as JSON and saved to
        # state/last_run_summary.json

    With an ApplicationContainer (optional; enables richer metrics)::

        container = create_application_container()
        runtime = HeadlessRuntime(container=container)
        summary = runtime.run(duration_minutes=5, mode="paper", broker_mode="live")
    """

    def __init__(self, container: Any | None = None) -> None:
        self._container = container
        self._logger = logging.getLogger("lumina.headless")
        self._stress_runner = StressSuiteRunner()

    def run(
        self,
        duration_minutes: int | float = 15,
        mode: str = "paper",
        broker_mode: str = "paper",
        aggressive_sim: bool = False,
        overnight_sim: bool = False,
        stability_check: bool = False,
    ) -> dict[str, Any]:
        """
        Execute the headless trade loop for ``duration_minutes`` of simulated time.

        The simulation is deterministic and fast (sub-second for standard
        durations when no sleep is involved).  ``duration_minutes`` governs
        how many ticks are processed (proportional to typical CME session
        activity), not wall-clock wait time. When ``require_real_simulator_data``
        is enabled for neuroevolution, ticks are loaded from historical OHLC
        via ``MarketDataService`` (Crosstrade) instead of synthetic prices.

        Args:
            duration_minutes: Simulated session length in minutes (e.g. 15, 5).
            mode: Trading mode label – "paper" | "sim" | "real".
            broker_mode: Broker backend – "paper" | "live".
            aggressive_sim: When True in SIM mode, enforce long learning run profile.
            overnight_sim: When True in SIM mode, force 4-hour equivalent simulation.
            stability_check: When True, force SIM stability aggregation at end.

        Returns:
            Structured summary dict (also written to stdout and to disk).
        """
        return execute_headless_run(
            self,
            duration_minutes=duration_minutes,
            mode=mode,
            broker_mode=broker_mode,
            aggressive_sim=aggressive_sim,
            overnight_sim=overnight_sim,
            stability_check=stability_check,
        )

    def _persist(
        self,
        summary: dict[str, Any],
        *,
        summary_path: Path,
        archive_enabled: bool,
        archive_dir: Path,
    ) -> None:
        persist_headless_summary(
            self._logger,
            summary,
            summary_path=summary_path,
            archive_enabled=archive_enabled,
            archive_dir=archive_dir,
        )
