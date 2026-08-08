"""Helpers for headless runtime loop (global residual)."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from lumina_core.engine.sim_stability_checker import (
    append_history_entry_for_summary,
    format_stability_report,
    generate_stability_report,
)
from lumina_core.runtime.headless_config import _resolve_test_bypass_readiness_gate

logger = logging.getLogger(__name__)

def _resolve_summary_path(cfg: dict[str, Any]) -> Path:
    """Resolve summary path; honors monkeypatched ``headless_runtime._SUMMARY_PATH``."""
    import lumina_core.runtime.headless_runtime as hr

    env_path = os.getenv("LUMINA_HEADLESS_SUMMARY_PATH", "").strip()
    if env_path:
        return Path(env_path)

    if hr._SUMMARY_PATH != hr._DEFAULT_SUMMARY_PATH:
        return hr._SUMMARY_PATH

    cfg_path = str(cfg.get("summary_output_path", "")).strip()
    if cfg_path:
        return Path(cfg_path)
    return hr._SUMMARY_PATH

def _validate_broker(broker_mode: str) -> str:
    """
    Instantiate and connect the appropriate broker bridge.
    Returns a human-readable status string; never raises.
    """
    if broker_mode != "live":
        return "paper_ok"

    try:
        from lumina_core.broker.broker_bridge import broker_factory

        config = SimpleNamespace(
            broker_backend="live",
            broker_crosstrade_api_key=os.getenv("CROSSTRADE_TOKEN", "headless-validation-stub"),
            crosstrade_token=os.getenv("CROSSTRADE_TOKEN", "headless-validation-stub"),
            crosstrade_account=os.getenv("CROSSTRADE_ACCOUNT", "DEMO5042070"),
            broker_crosstrade_websocket_url=os.getenv("CROSSTRADE_WS_URL", "wss://app.crosstrade.io/ws/stream"),
            broker_crosstrade_base_url="https://app.crosstrade.io",
            crosstrade_fill_poll_url="",
        )
        broker = broker_factory(config=config)
        connected = broker.connect()
        return "live_connected" if connected else "live_connect_failed"
    except Exception as exc:
        logger.warning("Live broker validation error: %s", exc)
        return f"live_error:{type(exc).__name__}"

def _check_session_guard() -> int:
    """Return 1 if the current moment is outside the CME trading session, else 0."""
    try:
        from lumina_core.risk.session_guard import SessionGuard

        guard = SessionGuard()
        return 0 if guard.is_trading_session() else 1
    except Exception as exc:
        logger.debug("Session guard check skipped: %s", exc)
        return 0

def _count_evolution_proposals(container: Any | None) -> int:
    if container is None:
        return 0
    try:
        log_path = Path("state/evolution_log.jsonl")
        if not log_path.exists():
            return 0
        count = 0
        for line in log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict) and obj.get("status") in {"proposed", "pending"}:
                    count += 1
            except (json.JSONDecodeError, ValueError):
                pass
        return count
    except Exception:
        logging.exception("Unhandled broad exception fallback in lumina_core/runtime/headless_runtime_loop.py")
        return 0

def _count_observability_alerts(container: Any | None) -> int:
    if container is None:
        return 0
    try:
        obs = getattr(container, "observability_service", None)
        if obs is None:
            return 0
        collector = getattr(obs, "collector", None)
        if collector is None:
            return 0
        raw = collector.latest("lumina_alerts_sent_total")
        return int(raw) if raw is not None else 0
    except Exception:
        logging.exception("Unhandled broad exception fallback in lumina_core/runtime/headless_runtime_loop.py")
        return 0

def persist_headless_summary(
    runtime_logger: logging.Logger,
    summary: dict[str, Any],
    *,
    summary_path: Path,
    archive_enabled: bool,
    archive_dir: Path,
) -> None:
    """Write summary JSON to default path and optionally archive each run uniquely."""
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(summary, indent=2)
    summary_path.write_text(payload, encoding="utf-8")

    if archive_enabled:
        archive_dir.mkdir(parents=True, exist_ok=True)
        mode = str(summary.get("mode", "unknown")).strip().lower() or "unknown"
        broker_mode = str(summary.get("broker_mode", "unknown")).strip().lower() or "unknown"
        aggressive = "aggr" if bool(summary.get("aggressive_sim", False)) else "std"
        duration = int(float(summary.get("duration_minutes", 0.0) or 0.0))
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        archive_file = archive_dir / f"summary_{mode}_{broker_mode}_{duration}m_{aggressive}_{stamp}.json"
        archive_file.write_text(payload, encoding="utf-8")
        summary["summary_archive_path"] = str(archive_file)

    summary["summary_path"] = str(summary_path)
    payload = json.dumps(summary, indent=2)
    summary_path.write_text(payload, encoding="utf-8")
    print(payload, flush=True)
    runtime_logger.info(
        "HeadlessRuntime summary written → %s  (trades=%d  pnl=%.2f)",
        summary_path,
        summary.get("total_trades", 0),
        summary.get("pnl_realized", 0.0),
    )

def _financial_reporting(sim_learning: dict[str, Any], sim_realism: dict[str, Any]) -> dict[str, Any]:
    return {
        "learning_label": "Learning Fitness (niet productie-benchmark)",
        "realism_label": "Realism Adjusted (wel vergelijkbaar voor live readiness)",
        "metrics_for_readiness_gate": "realism",
        "parity_delta_pnl_realized": round(
            float(sim_learning.get("pnl_realized", 0.0) or 0.0)
            - float(sim_realism.get("pnl_realized", 0.0) or 0.0),
            2,
        ),
        "parity_delta_max_drawdown": round(
            float(sim_learning.get("max_drawdown", 0.0) or 0.0)
            - float(sim_realism.get("max_drawdown", 0.0) or 0.0),
            2,
        ),
        "parity_delta_sharpe_annualized": round(
            float(sim_learning.get("sharpe_annualized", 0.0) or 0.0)
            - float(sim_realism.get("sharpe_annualized", 0.0) or 0.0),
            4,
        ),
    }

def _apply_stability_and_bypass(
    summary: dict[str, Any],
    *,
    runtime_logger: logging.Logger,
) -> None:
    history_append = append_history_entry_for_summary(summary, source_path="state/last_run_summary.json")
    stability_report = generate_stability_report(limit=0)
    stability_report["history_append"] = history_append
    summary["stability_report"] = stability_report
    summary["READY_FOR_REAL"] = bool(stability_report.get("READY_FOR_REAL", False))
    summary["stability_status"] = str(stability_report.get("status", "RED"))
    if _resolve_test_bypass_readiness_gate():
        original_ready = bool(summary["READY_FOR_REAL"])
        original_status = str(summary["stability_status"])
        original_stress_gate = bool(summary.get("stress_ready_for_real_gate", False))
        summary["test_readiness_bypass"] = {
            "enabled": True,
            "original_ready_for_real": original_ready,
            "original_stability_status": original_status,
            "original_stress_ready_for_real_gate": original_stress_gate,
        }
        summary["READY_FOR_REAL"] = True
        summary["stability_status"] = "TEST_BYPASS"
        summary["stress_ready_for_real_gate"] = True
        stability_report["READY_FOR_REAL"] = True
        stability_report["ready_for_real"] = True
        stability_report["status"] = "TEST_BYPASS"
        stability_report["test_readiness_bypass"] = dict(summary["test_readiness_bypass"])
    rendered = format_stability_report(stability_report, color=True)
    runtime_logger.info("\n%s", rendered)
    print(rendered, flush=True)
