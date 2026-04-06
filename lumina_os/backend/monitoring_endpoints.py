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

    kill_switch = bool(
        (snap.get("lumina_risk_kill_switch_active") or {}).get("value", 0)
    )
    ws_connected = bool(
        (snap.get("lumina_websocket_connected") or {}).get("value", 1)
    )
    uptime_s: float = float((snap.get("_meta") or {}).get("uptime_s", 0.0))

    issues: list[str] = []
    if kill_switch:
        issues.append("kill_switch_active")
    if not ws_connected:
        issues.append("websocket_disconnected")

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
