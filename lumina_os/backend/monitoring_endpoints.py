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
_ADAPTIVE_TRANSITION_FIELDS = (
    "tier",
    "mode",
    "reasoning_mode",
    "degraded_state",
    "status_reason",
    "recommended_model",
    "recommended_provider",
    "context_length",
    "last_probe_error",
)


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


def _load_adaptive_history_rows(*, limit: int = 100) -> list[dict[str, Any]]:
    if not _ADAPTIVE_INTELLIGENCE_HISTORY.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with _ADAPTIVE_INTELLIGENCE_HISTORY.open("r", encoding="utf-8") as fh:
            for line in fh:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    rows.append(payload)
    except OSError:
        raise HTTPException(status_code=500, detail="Adaptive intelligence history unreadable")
    return rows[-max(1, int(limit)) :]


def _build_adaptive_transition_summary(
    *,
    latest_record: dict[str, Any],
    previous_record: dict[str, Any] | None,
) -> dict[str, Any]:
    latest_payload = latest_record.get("payload", {})
    if not isinstance(latest_payload, dict):
        return {"is_transition": False, "changed_fields": []}
    previous_payload = previous_record.get("payload", {}) if isinstance(previous_record, dict) else {}
    if not isinstance(previous_payload, dict):
        return {
            "is_transition": False,
            "changed_fields": [],
            "from_state": {},
            "to_state": {k: latest_payload.get(k) for k in _ADAPTIVE_TRANSITION_FIELDS},
        }
    changed = [k for k in _ADAPTIVE_TRANSITION_FIELDS if previous_payload.get(k) != latest_payload.get(k)]
    return {
        "is_transition": bool(changed),
        "changed_fields": changed,
        "from_state": {k: previous_payload.get(k) for k in changed},
        "to_state": {k: latest_payload.get(k) for k in changed},
    }


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
