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

_ADAPTIVE_INTELLIGENCE_LATEST = Path(
    os.getenv("ADAPTIVE_INTELLIGENCE_STATUS_PATH", "state/adaptive_intelligence_status.json")
)
_ADAPTIVE_INTELLIGENCE_HISTORY = Path(
    os.getenv("ADAPTIVE_INTELLIGENCE_HISTORY_PATH", "state/adaptive_intelligence_events.jsonl")
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
from lumina_os.backend.monitoring_endpoints_helpers import (
    _build_adaptive_transition_summary,
    _check_api_key,
    _load_adaptive_history_rows,
    _require_service,
    set_observability_service,
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


# ── Internal helpers + split route handlers (global residual) ─────────────────
from lumina_os.backend.monitoring_endpoints_helpers import (  # noqa: E402,F401
    _build_adaptive_transition_summary,
    _check_api_key,
    _load_adaptive_history_rows,
    _require_service,
    set_observability_service,
)
from lumina_os.backend.monitoring_endpoints_ops import (  # noqa: E402
    get_admin_setup_snapshot,
    get_capital_aperture,
    get_monitoring_diagnostics,
    get_ops_data,
    get_react_dashboard_status,
    get_workspace_snapshot,
)

# Re-bind FastAPI routes onto extracted handlers (signatures keep Header/Query deps).
get_ops_data = router.get("/ops-data")(get_ops_data)
get_capital_aperture = router.get("/capital-aperture")(get_capital_aperture)
get_monitoring_diagnostics = router.get("/diagnostics")(get_monitoring_diagnostics)
get_workspace_snapshot = router.get("/workspace-snapshot")(get_workspace_snapshot)
get_react_dashboard_status = router.get("/react-dashboard-status")(get_react_dashboard_status)
get_admin_setup_snapshot = router.get("/admin-setup-snapshot")(get_admin_setup_snapshot)
