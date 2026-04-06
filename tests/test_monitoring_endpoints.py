# CANONICAL IMPLEMENTATION – v50 Living Organism
"""Unit tests for the monitoring_endpoints FastAPI router.

Coverage:
  - GET /api/monitoring/health        — regime fields, status logic, issue list
  - GET /api/monitoring/metrics       — Prometheus text (no auth required)
  - GET /api/monitoring/metrics/json  — JSON snapshot (requires API key)
  - GET /api/monitoring/regime/history — history query delegation + auth
  - 503 when observability service not injected
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Add lumina_os/ to sys.path so `backend.*` imports resolve.
_LUMINA_OS_PATH = Path(__file__).resolve().parents[1] / "lumina_os"
if str(_LUMINA_OS_PATH) not in sys.path:
    sys.path.insert(0, str(_LUMINA_OS_PATH))

from backend.monitoring_endpoints import router, set_observability_service  # noqa: E402  # type: ignore[import-untyped]

# ── Minimal test app ──────────────────────────────────────────────────────────

_test_app = FastAPI()
_test_app.include_router(router)
_client = TestClient(_test_app, raise_server_exceptions=True)


# ── Snapshot factory ──────────────────────────────────────────────────────────

def _make_snap(
    *,
    regime: str = "TRENDING",
    risk_state: str = "NORMAL",
    confidence: float = 0.78,
    fast_path_weight: float = 0.65,
    override_count: float = 0.0,
    kill_switch: float = 0.0,
    ws_connected: float = 1.0,
    uptime_s: float = 42.0,
) -> dict[str, Any]:
    snap: dict[str, Any] = {
        "_meta": {"uptime_s": uptime_s, "generated_at": time.time()},
        f'lumina_regime_current{{regime="{regime}",risk_state="{risk_state}"}}': {
            "name": "lumina_regime_current",
            "type": "gauge",
            "value": 1.0,
            "labels": {"regime": regime, "risk_state": risk_state},
            "updated_at": time.time(),
        },
        f'lumina_regime_confidence{{regime="{regime}"}}': {
            "name": "lumina_regime_confidence",
            "type": "gauge",
            "value": confidence,
            "labels": {"regime": regime},
            "updated_at": time.time(),
        },
        f'lumina_regime_fast_path_weight{{regime="{regime}"}}': {
            "name": "lumina_regime_fast_path_weight",
            "type": "gauge",
            "value": fast_path_weight,
            "labels": {"regime": regime},
            "updated_at": time.time(),
        },
        "lumina_risk_kill_switch_active": {
            "name": "lumina_risk_kill_switch_active",
            "type": "gauge",
            "value": kill_switch,
            "labels": {},
            "updated_at": time.time(),
        },
        "lumina_websocket_connected": {
            "name": "lumina_websocket_connected",
            "type": "gauge",
            "value": ws_connected,
            "labels": {},
            "updated_at": time.time(),
        },
    }
    if override_count > 0:
        snap[f'lumina_regime_high_risk_overrides_total{{regime="{regime}"}}'] = {
            "name": "lumina_regime_high_risk_overrides_total",
            "type": "counter",
            "value": override_count,
            "labels": {"regime": regime},
            "updated_at": time.time(),
        }
    return snap


def _make_obs(snap: dict[str, Any] | None = None) -> MagicMock:
    obs = MagicMock()
    obs.snapshot.return_value = snap if snap is not None else _make_snap()
    obs.prometheus_text.return_value = "# HELP lumina_test test\n# TYPE lumina_test gauge\nlumina_test 1.0\n"
    obs.collector = MagicMock()
    obs.collector.query_history.return_value = []
    return obs


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_obs() -> Any:
    """Ensure the singleton is cleared between tests so no state leaks."""
    set_observability_service(None)
    yield
    set_observability_service(None)


# ── GET /api/monitoring/health ────────────────────────────────────────────────

def test_health_503_when_no_obs_service() -> None:
    resp = _client.get("/api/monitoring/health")
    assert resp.status_code == 503


def test_health_returns_all_regime_fields_for_normal_regime() -> None:
    obs = _make_obs(_make_snap(regime="TRENDING", risk_state="NORMAL", confidence=0.78, fast_path_weight=0.65))
    set_observability_service(obs)

    resp = _client.get("/api/monitoring/health")
    assert resp.status_code == 200
    body = resp.json()

    assert body["current_regime"] == "TRENDING"
    assert body["regime_risk_state"] == "NORMAL"
    assert abs(body["regime_confidence"] - 0.78) < 0.001
    assert abs(body["fast_path_weight"] - 0.65) < 0.001
    assert body["high_risk_override_count"] == 0
    assert body["status"] == "healthy"
    assert "high_risk_regime" not in body["issues"]


def test_health_high_risk_regime_adds_issue_and_degraded_status() -> None:
    obs = _make_obs(
        _make_snap(
            regime="NEWS_DRIVEN",
            risk_state="HIGH_RISK",
            confidence=0.91,
            fast_path_weight=0.82,
            override_count=3.0,
        )
    )
    set_observability_service(obs)

    resp = _client.get("/api/monitoring/health")
    assert resp.status_code == 200
    body = resp.json()

    assert body["current_regime"] == "NEWS_DRIVEN"
    assert body["regime_risk_state"] == "HIGH_RISK"
    assert abs(body["regime_confidence"] - 0.91) < 0.001
    assert body["high_risk_override_count"] == 3
    assert "high_risk_regime" in body["issues"]
    assert body["status"] == "degraded"


def test_health_kill_switch_gives_critical_status() -> None:
    obs = _make_obs(_make_snap(kill_switch=1.0))
    set_observability_service(obs)

    resp = _client.get("/api/monitoring/health")
    body = resp.json()

    assert body["status"] == "critical"
    assert "kill_switch_active" in body["issues"]


def test_health_websocket_down_gives_degraded_status() -> None:
    obs = _make_obs(_make_snap(ws_connected=0.0))
    set_observability_service(obs)

    resp = _client.get("/api/monitoring/health")
    body = resp.json()

    assert body["status"] == "degraded"
    assert "websocket_disconnected" in body["issues"]


def test_health_no_api_key_required() -> None:
    """Health endpoint must be reachable without authentication."""
    obs = _make_obs()
    set_observability_service(obs)

    # No X-API-Key header
    resp = _client.get("/api/monitoring/health")
    assert resp.status_code == 200


def test_health_uptime_forwarded_from_meta() -> None:
    obs = _make_obs(_make_snap(uptime_s=999.5))
    set_observability_service(obs)

    resp = _client.get("/api/monitoring/health")
    body = resp.json()
    assert abs(body["uptime_s"] - 999.5) < 0.1


# ── GET /api/monitoring/metrics (Prometheus, no auth) ─────────────────────────

def test_prometheus_metrics_200_without_auth() -> None:
    obs = _make_obs()
    set_observability_service(obs)

    resp = _client.get("/api/monitoring/metrics")
    assert resp.status_code == 200
    assert "lumina_test" in resp.text


def test_prometheus_metrics_503_when_no_service() -> None:
    resp = _client.get("/api/monitoring/metrics")
    assert resp.status_code == 503


# ── GET /api/monitoring/metrics/json (requires API key) ───────────────────────

def test_json_metrics_returns_401_without_key() -> None:
    obs = _make_obs()
    set_observability_service(obs)

    resp = _client.get("/api/monitoring/metrics/json")
    assert resp.status_code == 401


def test_json_metrics_returns_snapshot_with_key() -> None:
    snap = _make_snap(regime="RANGING", confidence=0.55)
    obs = _make_obs(snap)
    set_observability_service(obs)

    resp = _client.get("/api/monitoring/metrics/json", headers={"X-API-Key": "any-key"})
    assert resp.status_code == 200
    body = resp.json()
    assert 'lumina_regime_current{regime="RANGING",risk_state="NORMAL"}' in body
    assert abs(body['lumina_regime_confidence{regime="RANGING"}']['value'] - 0.55) < 0.001


# ── GET /api/monitoring/regime/history ────────────────────────────────────────

def test_regime_history_returns_401_without_key() -> None:
    obs = _make_obs()
    set_observability_service(obs)

    resp = _client.get("/api/monitoring/regime/history")
    assert resp.status_code == 401


def test_regime_history_returns_empty_list_when_no_rows() -> None:
    obs = _make_obs()
    obs.collector.query_history.return_value = []
    set_observability_service(obs)

    resp = _client.get("/api/monitoring/regime/history", headers={"X-API-Key": "k"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_regime_history_returns_rows_from_collector() -> None:
    history_rows = [
        {
            "ts": 1712400000.0,
            "name": "lumina_regime_current",
            "labels": {"regime": "TRENDING", "risk_state": "NORMAL"},
            "type": "gauge",
            "value": 1.0,
        },
        {
            "ts": 1712396400.0,
            "name": "lumina_regime_current",
            "labels": {"regime": "RANGING", "risk_state": "NORMAL"},
            "type": "gauge",
            "value": 1.0,
        },
    ]
    obs = _make_obs()
    obs.collector.query_history.return_value = history_rows
    set_observability_service(obs)

    resp = _client.get("/api/monitoring/regime/history", headers={"X-API-Key": "k"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["labels"]["regime"] == "TRENDING"
    assert body[1]["labels"]["regime"] == "RANGING"


def test_regime_history_passes_since_and_limit_to_collector() -> None:
    obs = _make_obs()
    set_observability_service(obs)

    _client.get(
        "/api/monitoring/regime/history?since=1712300000.0&limit=50",
        headers={"X-API-Key": "k"},
    )
    obs.collector.query_history.assert_called_once_with(
        "lumina_regime_current", since_ts=1712300000.0, limit=50
    )


def test_regime_history_503_when_no_service() -> None:
    resp = _client.get("/api/monitoring/regime/history", headers={"X-API-Key": "k"})
    assert resp.status_code == 503
