# CANONICAL IMPLEMENTATION – v50 Living Organism
"""FastAPI monitoring endpoints for Lumina v50 Observability Layer.

Endpoints
---------
GET /api/monitoring/metrics          – Prometheus text exposition format (v0.0.4)
GET /api/monitoring/metrics/json     – Full JSON metrics snapshot
GET /api/monitoring/health           – Structured health-check (kill-switch, WS, uptime)
GET /api/monitoring/metrics/history  – Historical values from SQLite (paginated)

The router is mounted in lumina_os/backend/app.py via:
    from backend.monitoring_endpoints import router as monitoring_router
    app.include_router(monitoring_router)
    set_observability_service(obs_instance)

/metrics is intentionally unauthenticated to support standard Prometheus scraping.
/metrics/json and /metrics/history require an API key (standard app auth).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Header, Query
from fastapi.responses import PlainTextResponse

try:
    from api.monitoring import LUMINA_UI_FIELDS, enrich_observability_snapshot_for_react_dashboard
except ImportError:  # pragma: no cover - fallback when PYTHONPATH excludes lumina_os root

    LUMINA_UI_FIELDS = (
        "trades_completed",
        "ppo_steps",
        "approval_twin_reward",
        "cpu",
        "gpu",
        "ram",
        "velocity",
        "phase",
        "historical_days",
        "synthetic_percent",
        "eta_minutes",
    )

    def enrich_observability_snapshot_for_react_dashboard(snapshot: dict[str, Any]) -> dict[str, Any]:
        return dict(snapshot)


router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])

# ── Service singleton injected at FastAPI startup ─────────────────────────────
_obs_service: Any = None
_ADAPTIVE_INTELLIGENCE_LATEST = Path(
    os.getenv("ADAPTIVE_INTELLIGENCE_STATUS_PATH", "state/adaptive_intelligence_status.json")
)
_ADAPTIVE_INTELLIGENCE_HISTORY = Path(
    os.getenv("ADAPTIVE_INTELLIGENCE_HISTORY_PATH", "state/adaptive_intelligence_events.jsonl")
)
from backend.adaptive_intelligence_snapshot import (
    build_adaptive_transition_summary,
    load_adaptive_history_rows,
)
from lumina_os.monitoring.snapshots import (
    extract_regime_summary as _extract_regime_summary,
    latest_training_reports as _latest_training_reports,
    load_json_file as _load_json_file,
    load_jsonl_file as _load_jsonl_file,
    metric_value as _metric_value,
    monitoring_paths as _monitoring_paths,
    repo_state_dir as _repo_state_dir,
)


def set_observability_service(service: Any) -> None:
    """Inject the ObservabilityService so all routes share the same instance."""
    global _obs_service
    _obs_service = service


def _require_service() -> Any:
    if _obs_service is None:
        raise HTTPException(
            status_code=503,
            detail="Observability service not yet initialised",
        )
    return _obs_service


def _load_adaptive_history_rows(*, limit: int = 100) -> list[dict[str, Any]]:
    return load_adaptive_history_rows(history_path=_ADAPTIVE_INTELLIGENCE_HISTORY, limit=limit)


def _build_adaptive_transition_summary(
    *,
    latest_record: dict[str, Any],
    previous_record: dict[str, Any] | None,
) -> dict[str, Any]:
    return build_adaptive_transition_summary(
        latest_record=latest_record,
        previous_record=previous_record,
    )


# ── Prometheus scrape endpoint (no auth – standard Prometheus convention) ─────


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    summary="Prometheus metrics",
    description="Return all Lumina metrics in Prometheus text exposition format (v0.0.4).",
    include_in_schema=True,
)
async def get_prometheus_metrics() -> PlainTextResponse:
    obs = _require_service()
    return PlainTextResponse(
        content=obs.prometheus_text(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


# ── JSON endpoints (require API key via shared app dependency) ─────────────────


@router.get(
    "/metrics/json",
    summary="JSON metrics snapshot",
    description="Return the full metrics snapshot as a structured JSON object.",
)
async def get_metrics_json(
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    _check_api_key(x_api_key)
    obs = _require_service()
    # Return full collector snapshot + canonical UI fields expected by the React dashboard.
    # Keep both `_lumina_ui` and `lumina_ui` aliases for compatibility.
    enriched = enrich_observability_snapshot_for_react_dashboard(obs.snapshot())
    ui_raw = enriched.get("_lumina_ui")
    ui = ui_raw if isinstance(ui_raw, dict) else {}

    canonical_ui: dict[str, Any] = {}
    for key in LUMINA_UI_FIELDS:
        canonical_ui[key] = ui.get(key)

    enriched["_lumina_ui"] = canonical_ui
    enriched["lumina_ui"] = canonical_ui
    return enriched


@router.get(
    "/health",
    summary="System health",
    description="Return a structured health summary including kill-switch state and WebSocket connectivity.",
)
async def get_health() -> dict[str, Any]:
    """No auth required – this endpoint is pinged by load balancers and Docker health checks."""
    obs = _require_service()
    snap = obs.snapshot()

    kill_switch = bool(_metric_value(snap, "lumina_risk_kill_switch_active", 0.0))
    ws_connected = bool(_metric_value(snap, "lumina_websocket_connected", 1.0))
    uptime_s: float = float((snap.get("_meta") or {}).get("uptime_s", 0.0))
    regime = _extract_regime_summary(snap)

    issues: list[str] = []
    if kill_switch:
        issues.append("kill_switch_active")
    if not ws_connected:
        issues.append("websocket_disconnected")
    if regime["regime_risk_state"] == "HIGH_RISK":
        issues.append("high_risk_regime")

    status = "healthy"
    if "kill_switch_active" in issues:
        status = "critical"
    elif issues:
        status = "degraded"

    return {
        "status": status,
        "uptime_s": uptime_s,
        "kill_switch_active": kill_switch,
        "websocket_connected": ws_connected,
        "current_regime": regime["current_regime"],
        "regime_risk_state": regime["regime_risk_state"],
        "regime_confidence": regime["regime_confidence"],
        "fast_path_weight": regime["fast_path_weight"],
        "high_risk_override_count": regime["high_risk_override_count"],
        "issues": issues,
        "ts": time.time(),
    }


@router.get(
    "/metrics/history",
    summary="Historical metric values",
    description="Retrieve historical values for a named metric from the SQLite store.",
)
async def get_metric_history(
    metric: str = Query(..., description="Exact metric name to query"),
    since: Optional[float] = Query(None, description="Unix timestamp lower bound (inclusive)"),
    limit: int = Query(200, ge=1, le=2000, description="Maximum rows to return"),
    x_api_key: Optional[str] = Header(None),
) -> list[dict[str, Any]]:
    _check_api_key(x_api_key)
    obs = _require_service()
    collector = getattr(obs, "collector", None)
    if collector is None:
        return []
    return collector.query_history(metric, since_ts=since, limit=limit)  # type: ignore[union-attr]


@router.get(
    "/regime/history",
    summary="Regime flip history",
    description=(
        "Retrieve recent regime-change events from the SQLite store. "
        "Returns rows where lumina_regime_current was recorded; "
        "filter to value==1.0 for active-regime transitions only."
    ),
)
async def get_regime_history(
    since: Optional[float] = Query(None, description="Unix timestamp lower bound (inclusive)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum rows to return"),
    x_api_key: Optional[str] = Header(None),
) -> list[dict[str, Any]]:
    _check_api_key(x_api_key)
    obs = _require_service()
    collector = getattr(obs, "collector", None)
    if collector is None:
        return []
    return collector.query_history("lumina_regime_current", since_ts=since, limit=limit)  # type: ignore[union-attr]


@router.get(
    "/adaptive-intelligence/latest",
    summary="Latest adaptive intelligence state",
    description="Read the latest adaptive intelligence state persisted by EventBus consumers.",
)
async def get_adaptive_intelligence_latest(
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    _check_api_key(x_api_key)
    if not _ADAPTIVE_INTELLIGENCE_LATEST.exists():
        return {}
    try:
        payload = json.loads(_ADAPTIVE_INTELLIGENCE_LATEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise HTTPException(status_code=500, detail="Adaptive intelligence latest state unreadable")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=500, detail="Adaptive intelligence latest payload invalid")
    history_rows = _load_adaptive_history_rows(limit=2)
    previous = history_rows[-2] if len(history_rows) >= 2 else None
    payload["transition_summary"] = _build_adaptive_transition_summary(
        latest_record=payload,
        previous_record=previous,
    )
    return payload


@router.get(
    "/adaptive-intelligence/history",
    summary="Adaptive intelligence transition history",
    description="Read recent adaptive intelligence events persisted by EventBus consumers.",
)
async def get_adaptive_intelligence_history(
    limit: int = Query(100, ge=1, le=2000, description="Maximum rows to return"),
    x_api_key: Optional[str] = Header(None),
) -> list[dict[str, Any]]:
    _check_api_key(x_api_key)
    return _load_adaptive_history_rows(limit=limit)


@router.get("/training-reports")
async def get_training_reports(
    limit: int = Query(10, ge=1, le=50),
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    _check_api_key(x_api_key)
    reports = _latest_training_reports(limit=limit)
    return {"reports": reports, "count": len(reports)}


@router.get("/logs/tail")
async def get_log_tail(
    limit: int = Query(50, ge=10, le=500),
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    _check_api_key(x_api_key)
    repo = Path(__file__).resolve().parents[2]
    log_path = repo / "logs" / "lumina_full_log.csv"
    lines: list[str] = []
    if log_path.is_file():
        try:
            content = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            lines = content[-limit:]
        except OSError:
            lines = []
    return {"path": str(log_path), "lines": lines}


@router.get("/stability-report")
async def get_stability_report(
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    _check_api_key(x_api_key)
    from lumina_core.engine.sim_stability_checker import generate_stability_report

    report = generate_stability_report()
    history_path = _repo_state_dir().parent / "state" / "sim_stability_history.jsonl"
    if not history_path.is_file():
        history_path = _repo_state_dir() / "sim_stability_history.jsonl"
    tail = _load_jsonl_file(history_path, limit=7)
    report["history_tail"] = [
        {
            "day": str(row.get("day", "")),
            "sharpe_annualized": float(row.get("sharpe_annualized", 0) or 0),
        }
        for row in tail
        if row.get("day")
    ]
    return report


@router.get("/ops-data")
async def get_ops_data(
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    _check_api_key(x_api_key)
    state = _repo_state_dir()
    twin = _load_jsonl_file(state / "monitoring_twin_decisions.jsonl", limit=20)
    gate = _load_jsonl_file(state / "monitoring_gate_rejections.jsonl", limit=50)
    shadow: dict[str, Any] = {}
    shadow_path = state / "evolution_shadow_runs.json"
    if shadow_path.is_file():
        try:
            parsed = json.loads(shadow_path.read_text(encoding="utf-8"))
            shadow = parsed if isinstance(parsed, dict) else {}
        except (OSError, json.JSONDecodeError):
            shadow = {}
    daily_pnl = _load_jsonl_file(state / "monitoring_daily_pnl.jsonl", limit=30)
    # Perfect Birth Phase KPIs (twin accuracy vs Steve, autonomy, alignment)
    twin_accuracy = _load_jsonl_file(state / "monitoring_twin_training.jsonl", limit=5)
    autonomy_rollup = _load_jsonl_file(state / "monitoring_autonomy_metrics.jsonl", limit=5)
    shadow_align = _load_jsonl_file(state / "monitoring_shadow_twin_alignment.jsonl", limit=10)
    # First-class Twin observability rollup (agreement/calibration/mode progress)
    twin_observability: dict[str, Any] = {}
    try:
        from lumina_core.evolution.twin_training_service import TwinTrainingService

        m = TwinTrainingService().metrics(decision_window=100, series_limit=14)
        twin_observability = {
            "mode": m.get("mode"),
            "authority": m.get("authority"),
            "twin_steve_agreement_pct": m.get("twin_steve_agreement_pct"),
            "twin_agreement_pct": m.get("twin_agreement_pct"),
            "rolling_agreement": m.get("rolling_agreement"),
            "agreement_over_time": m.get("agreement_over_time"),
            "risk_flags_caught": m.get("risk_flags_caught"),
            "risk_flags_missed": m.get("risk_flags_missed"),
            "risk_flags_catch_rate_pct": m.get("risk_flags_catch_rate_pct"),
            "calibration": m.get("calibration"),
            "mode_promotion_progress": m.get("mode_promotion_progress"),
            "mode_samples": m.get("mode_samples"),
            "reward": m.get("reward"),
            "avg_prediction_error": m.get("avg_prediction_error"),
        }
    except Exception:
        twin_observability = {}
    return {
        "twin_decisions": twin,
        "gate_rejections": gate,
        "shadow_runs": shadow,
        "daily_pnl_trend": daily_pnl,
        "perfect_birth_kpis": {
            "twin_accuracy_latest": twin_accuracy,
            "autonomy_rollup_latest": autonomy_rollup,
            "shadow_twin_alignment_latest": shadow_align,
            "twin_observability": twin_observability,
        },
        "twin_observability": twin_observability,
    }


@router.get("/diagnostics")
async def get_monitoring_diagnostics(
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    """JSONL tails and workspace paths for Command Deck monitoring deep panel."""
    _check_api_key(x_api_key)
    state = _repo_state_dir()
    repo = Path(__file__).resolve().parents[2]
    logs = repo / "logs"
    return {
        "paths": _monitoring_paths(),
        "structured_errors": _load_jsonl_file(logs / "structured_errors.jsonl", limit=25),
        "reasoning_latency": _load_jsonl_file(
            state / "monitoring_reasoning_latency.jsonl", limit=50
        ),
        "model_load_times": _load_jsonl_file(
            state / "monitoring_model_load_times.jsonl", limit=50
        ),
        "twin_training": _load_jsonl_file(state / "monitoring_twin_training.jsonl", limit=20),
        "gate_rejections": _load_jsonl_file(
            state / "monitoring_gate_rejections.jsonl", limit=30
        ),
    }


@router.get("/workspace-snapshot")
async def get_workspace_snapshot(
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    """System overview snapshot (monitoring tab A/B parity)."""
    _check_api_key(x_api_key)
    state = _repo_state_dir()
    repo = Path(__file__).resolve().parents[2]
    progress = _load_json_file(state / "lumina_birth_progress.json")
    if not progress:
        progress = _load_json_file(state / "first_boot_progress.json")
    config_payload = _load_json_file(repo / "config.yaml") or {}
    runtime_metrics = _load_json_file(state / "monitoring_runtime_metrics.json") or {}
    sim_state = _load_json_file(state / "lumina_sim_state.json") or {}
    return {
        "paths": _monitoring_paths(),
        "first_boot_progress": progress,
        "runtime_metrics": runtime_metrics,
        "sim_state": sim_state,
        "config_mode": str(config_payload.get("mode", "sim")),
        "config_first_boot": config_payload.get("first_boot") if isinstance(
            config_payload.get("first_boot"), dict
        ) else {},
    }


@router.get("/react-dashboard-status")
async def get_react_dashboard_status(
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    """Embedded React dashboard URL readiness (Streamlit iframe parity)."""
    _check_api_key(x_api_key)
    try:
        from lumina_os.monitoring.dashboard_helpers import DashboardPaths, embedded_react_ui_status
    except ImportError:
        return {
            "ready": False,
            "reason": "dashboard_views_unavailable",
            "react_url": os.getenv("LUMINA_REACT_DASHBOARD_URL", "").strip()
            or f"http://127.0.0.1:{os.getenv('LUMINA_REACT_DASHBOARD_PORT', '5173')}",
        }

    repo = Path(__file__).resolve().parents[2]
    base_url = os.getenv("LUMINA_BACKEND_URL", "http://127.0.0.1:8000").strip()
    paths = DashboardPaths(repo)
    status = embedded_react_ui_status(base_url, paths)
    return status if isinstance(status, dict) else {"ready": False, "react_url": ""}


@router.get("/admin-setup-snapshot")
async def get_admin_setup_snapshot(
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    """Read-only admin metrics (Streamlit admin tab parity)."""
    _check_api_key(x_api_key)
    from lumina_launcher.core.blank_reset import DELETE_TARGETS, PRESERVED_STATE_FILES, WIPE_DIRECTORIES

    repo = Path(__file__).resolve().parents[2]
    state = repo / "state"
    env_path = repo / ".env"
    config_path = repo / "config.yaml"

    env_subset: dict[str, str] = {}
    if env_path.is_file():
        for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key in {
                "TRADE_MODE",
                "LUMINA_MODE",
                "INSTRUMENT",
                "DASHBOARD_ENABLED",
                "LUMINA_RUNTIME_TRACE",
            }:
                env_subset[key] = "***" if "KEY" in key or "TOKEN" in key else value.strip()

    setup_complete = _load_json_file(state / "lumina_setup_complete.json") or {}
    config_yaml = _load_json_file(config_path) or {}
    first_boot = config_yaml.get("first_boot") if isinstance(config_yaml.get("first_boot"), dict) else {}

    return {
        "setup_completed": bool(setup_complete.get("completed")),
        "runtime_mode": env_subset.get("LUMINA_MODE") or env_subset.get("TRADE_MODE") or "unknown",
        "configured_first_boot_trades": first_boot.get("training_trades"),
        "setup_complete_json": setup_complete,
        "config_yaml_subset": {
            "mode": config_yaml.get("mode"),
            "first_boot": first_boot,
        },
        "env_subset": env_subset,
        "reset_manifest": {
            "wipe_directories": list(WIPE_DIRECTORIES),
            "delete_targets": list(DELETE_TARGETS),
            "preserved_state_files": list(PRESERVED_STATE_FILES),
        },
    }


# ── Internal helpers ──────────────────────────────────────────────────────────


def _check_api_key(x_api_key: Optional[str]) -> None:
    """
    Lightweight API-key guard for monitoring endpoints.

    The full auth stack lives in app.py; here we do a minimal presence check.
    A missing key returns 401 so scrapers without a key still get /metrics
    (unauthenticated) but cannot access the richer JSON endpoints.
    """
    if x_api_key is None:
        raise HTTPException(status_code=401, detail="API key required")
