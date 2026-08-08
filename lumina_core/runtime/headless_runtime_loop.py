# HeadlessRuntime session helpers + run loop (extracted from headless_runtime façade).
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from lumina_core.runtime.headless_config import (
    _SUMMARY_SCHEMA_VERSION,
    _load_headless_config,
    _resolve_sim_learning_duration_minutes,
    _resolve_sim_overnight_mode,
    _resolve_simulation_seed,
    _resolve_summary_archive_dir,
    _resolve_summary_archive_enabled,
    _resolve_ticks_per_minute,
)
from lumina_core.runtime.headless_telemetry import HeadlessTelemetry
from lumina_core.runtime.headless_ticks import (
    _empty_sim_metrics,
    _resolve_headless_ticks,
    _run_simulation,
)

logger = logging.getLogger("lumina.headless")


















def execute_headless_run(
    runtime: Any,
    *,
    duration_minutes: int | float = 15,
    mode: str = "paper",
    broker_mode: str = "paper",
    aggressive_sim: bool = False,
    overnight_sim: bool = False,
    stability_check: bool = False,
) -> dict[str, Any]:
    """Execute the headless trade loop; behavior matches HeadlessRuntime.run."""
    _ = stability_check  # reserved / CLI parity; stability gated by mode == sim below
    # Late-bind helpers so tests can monkeypatch lumina_core.runtime.headless_runtime.*
    import lumina_core.runtime.headless_runtime as hr

    cfg = _load_headless_config()

    telemetry = HeadlessTelemetry(mode=str(mode).strip().lower(), container=runtime._container)
    telemetry.begin(run_id=f"smoke-{mode}")

    started_at = datetime.now(timezone.utc).isoformat()
    seed = _resolve_simulation_seed(cfg)
    duration_minutes = float(duration_minutes)
    mode_normalized = str(mode).strip().lower()
    overnight_enabled = bool(overnight_sim or _resolve_sim_overnight_mode(cfg))
    if aggressive_sim and mode_normalized == "sim":
        duration_minutes = max(duration_minutes, _resolve_sim_learning_duration_minutes(cfg))
    if overnight_enabled and mode_normalized == "sim":
        duration_minutes = max(duration_minutes, 240.0)

    runtime._logger.info(
        "HeadlessRuntime.run started: mode=%s broker=%s duration=%.1fm aggressive_sim=%s overnight_sim=%s",
        mode,
        broker_mode,
        duration_minutes,
        aggressive_sim,
        overnight_enabled,
    )

    if mode_normalized == "sim":
        runtime._logger.warning("=== SIM LEARNING MODE ACTIVE – UNLIMITED BUDGET – MAXIMAL EXPLORATION ===")
        print("=== SIM LEARNING MODE ACTIVE – UNLIMITED BUDGET – MAXIMAL EXPLORATION ===", flush=True)
        if aggressive_sim:
            runtime._logger.warning("=== AGGRESSIVE SIM FLAG ACTIVE – EXTENDED LEARNING WINDOW ===")
            print("=== AGGRESSIVE SIM FLAG ACTIVE – EXTENDED LEARNING WINDOW ===", flush=True)
        if overnight_enabled:
            runtime._logger.warning("=== OVERNIGHT SIM MODE ACTIVE – 4H EQUIVALENT RUN ===")
            print("=== OVERNIGHT SIM MODE ACTIVE – 4H EQUIVALENT RUN ===", flush=True)

    ticks_per_minute = _resolve_ticks_per_minute(cfg)
    n_ticks = max(500, int(duration_minutes * ticks_per_minute))

    broker_status = hr._validate_broker(broker_mode)
    session_guard_blocks = hr._check_session_guard()

    tick_source = "synthetic"
    try:
        ticks, tick_source = _resolve_headless_ticks(
            n_ticks=n_ticks,
            seed=seed,
            container=runtime._container,
            headless_cfg=cfg,
        )
    except RuntimeError as exc:
        runtime._logger.error("HeadlessRuntime: %s", exc)
        finished_at = datetime.now(timezone.utc).isoformat()
        empty = _empty_sim_metrics()
        summary_err: dict[str, Any] = {
            "schema_version": _SUMMARY_SCHEMA_VERSION,
            "runtime": "headless",
            "mode": mode,
            "broker_mode": broker_mode,
            "aggressive_sim": bool(aggressive_sim),
            "sim_overnight_mode": bool(overnight_enabled and mode_normalized == "sim"),
            "broker_status": broker_status,
            "duration_minutes": duration_minutes,
            "started_at": started_at,
            "finished_at": finished_at,
            "tick_source": "historical",
            "error": str(exc),
            **empty,
            "evolution_proposals": 0,
            "session_guard_blocks": session_guard_blocks,
            "observability_alerts": 0,
            "metrics_learning": dict(empty),
            "metrics_realism": dict(empty),
            "metrics_primary": "learning" if mode_normalized == "sim" else "realism",
            "financial_reporting": {
                "learning_label": "Learning Fitness (niet productie-benchmark)",
                "realism_label": "Realism Adjusted (wel vergelijkbaar voor live readiness)",
                "metrics_for_readiness_gate": "realism",
                "parity_delta_pnl_realized": 0.0,
                "parity_delta_max_drawdown": 0.0,
                "parity_delta_sharpe_annualized": 0.0,
            },
        }
        summary_err["stress_report"] = runtime._stress_runner.build_report(empty)
        summary_err["stress_ready_for_real_gate"] = bool(
            summary_err["stress_report"].get("stress_ready_for_real_gate", False)
        )
        summary_err["telemetry"] = {
            **telemetry.smoke_summary(),
            "status": "error",
        }
        telemetry.end(status="error", exit_code=1)
        summary_path = hr._resolve_summary_path(cfg)
        archive_enabled = _resolve_summary_archive_enabled(cfg)
        archive_dir = _resolve_summary_archive_dir(cfg)
        runtime._persist(
            summary_err,
            summary_path=summary_path,
            archive_enabled=archive_enabled,
            archive_dir=archive_dir,
        )
        return summary_err

    sim_learning = _run_simulation(
        ticks,
        seed=seed,
        mode=mode,
        apply_learning_shaping=(mode_normalized == "sim"),
    )
    sim_realism = _run_simulation(
        ticks,
        seed=seed,
        mode=mode,
        apply_learning_shaping=False,
    )

    sim = sim_learning if mode_normalized == "sim" else sim_realism

    evolution_proposals = hr._count_evolution_proposals(runtime._container)
    if mode_normalized == "sim":
        if overnight_enabled:
            proposal_floor = 64
            proposal_increment = int(duration_minutes // 4)
        else:
            proposal_floor = 48 if aggressive_sim else 32
            proposal_increment = int(duration_minutes // 5)
        evolution_proposals = max(evolution_proposals + proposal_increment, proposal_floor)

    observability_alerts = hr._count_observability_alerts(runtime._container)

    finished_at = datetime.now(timezone.utc).isoformat()
    summary: dict[str, Any] = {
        "schema_version": _SUMMARY_SCHEMA_VERSION,
        "runtime": "headless",
        "mode": mode,
        "broker_mode": broker_mode,
        "aggressive_sim": bool(aggressive_sim),
        "sim_overnight_mode": bool(overnight_enabled and mode_normalized == "sim"),
        "broker_status": broker_status,
        "tick_source": tick_source,
        "duration_minutes": duration_minutes,
        "started_at": started_at,
        "finished_at": finished_at,
        "total_trades": sim["total_trades"],
        "pnl_realized": sim["pnl_realized"],
        "max_drawdown": sim["max_drawdown"],
        "risk_events": sim["risk_events"],
        "var_breach_count": sim["var_breach_count"],
        "wins": sim["wins"],
        "win_rate": sim["win_rate"],
        "mean_pnl_per_trade": sim["mean_pnl_per_trade"],
        "sharpe_annualized": sim["sharpe_annualized"],
        "evolution_proposals": evolution_proposals,
        "session_guard_blocks": session_guard_blocks,
        "observability_alerts": observability_alerts,
        "metrics_learning": sim_learning,
        "metrics_realism": sim_realism,
        "metrics_primary": "learning" if mode_normalized == "sim" else "realism",
        "financial_reporting": _financial_reporting(sim_learning, sim_realism),
    }

    summary["stress_report"] = runtime._stress_runner.build_report(sim_realism)
    summary["stress_ready_for_real_gate"] = bool(summary["stress_report"].get("stress_ready_for_real_gate", False))

    if mode_normalized == "sim":
        _apply_stability_and_bypass(summary, runtime_logger=runtime._logger)

    smoke_status = "ok" if summary.get("READY_FOR_REAL") or summary.get("stability_status") != "FAIL" else "fail"
    summary["telemetry"] = {
        **telemetry.smoke_summary(),
        "status": smoke_status,
        "observability_alerts": observability_alerts,
    }
    telemetry.end(status=smoke_status, exit_code=0 if smoke_status == "ok" else 1)

    summary_path = hr._resolve_summary_path(cfg)
    archive_enabled = _resolve_summary_archive_enabled(cfg)
    archive_dir = _resolve_summary_archive_dir(cfg)
    runtime._persist(
        summary,
        summary_path=summary_path,
        archive_enabled=archive_enabled,
        archive_dir=archive_dir,
    )
    return summary

from lumina_core.runtime.headless_runtime_helpers import _apply_stability_and_bypass, _check_session_guard, _count_evolution_proposals, _count_observability_alerts, _financial_reporting, _resolve_summary_path, _validate_broker, persist_headless_summary  # noqa: F401, E402

