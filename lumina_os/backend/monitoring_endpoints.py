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
from datetime import datetime, timezone
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
    build_adaptive_intelligence_block,
    build_adaptive_transition_summary,
    load_adaptive_history_rows,
    resolve_adaptive_history_path,
    resolve_adaptive_status_path,
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


def _repo_state_dir() -> Path:
    raw = os.getenv("LUMINA_STATE_DIR", "").strip()
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parents[2] / "state"


def _load_jsonl_file(path: Path, *, limit: int = 50) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    rows.append(parsed)
    except OSError:
        return []
    return rows[-limit:]


def _parse_iso(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _load_json_file(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _journal_sim_dir() -> Path:
    repo = Path(__file__).resolve().parents[2]
    raw = os.getenv("LUMINA_JOURNAL_SIM_DIR", "").strip()
    if raw:
        return Path(raw)
    return repo / "journal" / "sim"


def _latest_training_reports(*, limit: int = 10) -> list[dict[str, Any]]:
    journal_sim_dir = _journal_sim_dir()
    reports: list[dict[str, Any]] = []
    if not journal_sim_dir.is_dir():
        return reports
    for path in sorted(
        list(journal_sim_dir.glob("lumina_birth_training_*.json"))
        + list(journal_sim_dir.glob("first_boot_training_*.json"))
    ):
        payload = _load_json_file(path)
        if payload:
            payload["_run_type"] = "Background"
            payload["_path"] = str(path)
            reports.append(payload)
    for path in sorted(journal_sim_dir.glob("nightly_sim_*.json")):
        payload = _load_json_file(path)
        if payload:
            ts = _parse_iso(payload.get("timestamp"))
            run_type = "Weekend" if ts is not None and ts.weekday() >= 5 else "Daily Maintenance"
            payload["_run_type"] = run_type
            payload["_path"] = str(path)
            reports.append(payload)
    reports.sort(
        key=lambda row: _parse_iso(row.get("timestamp"))
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return reports[:limit]


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
    return {
        "twin_decisions": twin,
        "gate_rejections": gate,
        "shadow_runs": shadow,
        "daily_pnl_trend": daily_pnl,
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
