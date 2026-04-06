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

import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from fastapi.responses import PlainTextResponse

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])

# ── Service singleton injected at FastAPI startup ─────────────────────────────
_obs_service: Any = None


def _metric_value(snapshot: dict[str, Any], key: str, default: float = 0.0) -> float:
    entry = snapshot.get(key) or {}
    try:
        return float(entry.get("value", default))
    except (TypeError, ValueError, AttributeError):
        return float(default)


def _find_metric_entry(snapshot: dict[str, Any], prefix: str, **labels: str) -> dict[str, Any]:
    for key, entry in snapshot.items():
        if key == "_meta" or not key.startswith(prefix):
            continue
        entry_labels = entry.get("labels") if isinstance(entry, dict) else None
        if not isinstance(entry_labels, dict):
            continue
        if all(str(entry_labels.get(name)) == value for name, value in labels.items()):
            return entry
    return {}


def _extract_regime_summary(snapshot: dict[str, Any]) -> dict[str, Any]:
    current_label = "UNKNOWN"
    current_risk_state = "UNKNOWN"
    current_active = _find_metric_entry(snapshot, "lumina_regime_current")
    if current_active:
        labels = current_active.get("labels") or {}
        current_label = str(labels.get("regime", "UNKNOWN"))
        current_risk_state = str(labels.get("risk_state", "UNKNOWN"))

    regime_confidence = 0.0
    if current_label != "UNKNOWN":
        regime_confidence = _metric_value(
            snapshot,
            f'lumina_regime_confidence{{regime="{current_label}"}}',
            0.0,
        )

    fast_path_weight = 0.0
    if current_label != "UNKNOWN":
        fast_path_weight = _metric_value(
            snapshot,
            f'lumina_regime_fast_path_weight{{regime="{current_label}"}}',
            0.0,
        )

    high_risk_override_count = 0
    if current_label != "UNKNOWN":
        override_entry = _find_metric_entry(
            snapshot,
            "lumina_regime_high_risk_overrides_total",
            regime=current_label,
        )
        try:
            high_risk_override_count = int(float((override_entry or {}).get("value", 0.0)))
        except (TypeError, ValueError):
            high_risk_override_count = 0

    return {
        "current_regime": current_label,
        "regime_risk_state": current_risk_state,
        "regime_confidence": regime_confidence,
        "fast_path_weight": fast_path_weight,
        "high_risk_override_count": high_risk_override_count,
    }


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
    return obs.snapshot()


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
    since: Optional[float] = Query(
        None, description="Unix timestamp lower bound (inclusive)"
    ),
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
    since: Optional[float] = Query(
        None, description="Unix timestamp lower bound (inclusive)"
    ),
    limit: int = Query(100, ge=1, le=1000, description="Maximum rows to return"),
    x_api_key: Optional[str] = Header(None),
) -> list[dict[str, Any]]:
    _check_api_key(x_api_key)
    obs = _require_service()
    collector = getattr(obs, "collector", None)
    if collector is None:
        return []
    return collector.query_history("lumina_regime_current", since_ts=since, limit=limit)  # type: ignore[union-attr]


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
