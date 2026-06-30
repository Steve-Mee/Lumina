from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault(
    "TRADER_LEAGUE_DATABASE_URL",
    f"sqlite:///{Path(__file__).parent / 'test_trader_league.db'}",
)
os.environ.setdefault(
    "TRADER_LEAGUE_RECONCILIATION_STATUS_FILE",
    str(Path(__file__).parent / "test_reconciliation_status.json"),
)
os.environ.setdefault("LUMINA_JWT_SECRET_KEY", "lumina_test_jwt_secret_key_min_len_32")

from fastapi.testclient import TestClient  # noqa: E402

from backend.app import app  # noqa: E402
from backend.core_websocket import CoreLiveTelemetryReader  # noqa: E402
from backend import core_websocket as core_ws_module  # noqa: E402


@pytest.fixture(autouse=True)
def reset_operator_mode_override() -> None:
    core_ws_module._operator_mode_override = None
    yield
    core_ws_module._operator_mode_override = None


@pytest.fixture()
def state_dir(tmp_path: Path) -> Path:
    sd = tmp_path / "state"
    sd.mkdir()
    (sd / "monitoring_runtime_metrics.json").write_text(
        json.dumps(
            {
                "timestamp": "2026-05-19T12:00:00Z",
                "mode": "sim",
                "account_equity": 100_000.0,
                "consecutive_losses": 0,
            }
        ),
        encoding="utf-8",
    )
    (sd / "evolution_log.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "status": "proposed",
                        "hash": "abc123",
                        "timestamp": "2026-05-19T11:00:00Z",
                        "challengers": [{"name": "alpha"}, {"name": "beta"}],
                    }
                ),
                json.dumps(
                    {
                        "status": "approved",
                        "hash": "def456",
                        "timestamp": "2026-05-19T10:00:00Z",
                        "challengers": [],
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return sd


def test_core_live_telemetry_reader_includes_live_trading(state_dir: Path) -> None:
    (state_dir / "monitoring_runtime_metrics.json").write_text(
        json.dumps(
            {
                "timestamp": "2026-05-19T12:00:00Z",
                "mode": "sim",
                "account_equity": 100_000.0,
                "live_position_qty": 2,
                "daily_pnl": 150.0,
                "open_pnl": 45.0,
                "consecutive_losses": 1,
                "pending_reconciliations": 0,
                "last_trades": [
                    {
                        "ts": "2026-05-19T11:55:00Z",
                        "signal": "BUY",
                        "entry": 5200.0,
                        "exit": 5205.0,
                        "qty": 2,
                        "pnl": 10.0,
                        "confluence": 0.72,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (state_dir / "lumina_sim_state.json").write_text(
        json.dumps(
            {
                "live_position_qty": 2,
                "sim_position_qty": 2,
                "last_entry_price": 5200.0,
                "live_trade_signal": "BUY",
                "current_dream": {
                    "signal": "BUY",
                    "confidence": 0.81,
                    "reason": "Trend continuation after pullback",
                    "why_no_trade": "",
                    "confluence_score": 0.72,
                    "stop": 5188.0,
                    "target": 5220.0,
                    "chosen_strategy": "momentum_breakout",
                },
            }
        ),
        encoding="utf-8",
    )

    reader = CoreLiveTelemetryReader(state_dir=state_dir)
    payload = reader.build_snapshot(obs=None)

    assert payload["live_trading"] is not None
    assert payload["live_trading"]["position"]["live_qty"] == 2
    assert payload["live_trading"]["active_signal"]["signal"] == "BUY"
    assert payload["live_trading"]["active_signal"]["confidence"] == 0.81
    assert len(payload["live_trading"]["last_trades"]) == 1
    assert payload["live_trading"]["current_dream"]["signal"] == "BUY"
    assert payload["live_trading"]["runtime_state"]["sim_position_qty"] == 2


def test_core_live_telemetry_reader_null_live_trading_when_no_state(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty_state"
    empty_dir.mkdir()
    reader = CoreLiveTelemetryReader(state_dir=empty_dir)
    payload = reader.build_snapshot(obs=None)
    assert payload["live_trading"] is None


def test_core_live_telemetry_reader_includes_adaptive_intelligence(state_dir: Path) -> None:
    adaptive_payload = {
        "topic": "inference.adaptive_intelligence.state",
        "timestamp": "2026-05-19T12:05:00Z",
        "payload": {
            "tier": "standard",
            "mode": "auto",
            "reasoning_mode": "chain_of_thought",
            "degraded_state": False,
            "status_reason": "",
            "recommended_model": "qwen2.5:7b",
            "recommended_provider": "ollama",
            "context_length": 8192,
            "last_probe_error": None,
        },
    }
    (state_dir / "adaptive_intelligence_status.json").write_text(
        json.dumps(adaptive_payload),
        encoding="utf-8",
    )
    (state_dir / "adaptive_intelligence_events.jsonl").write_text(
        json.dumps(adaptive_payload) + "\n",
        encoding="utf-8",
    )

    reader = CoreLiveTelemetryReader(state_dir=state_dir)
    payload = reader.build_snapshot(obs=None)

    assert payload["adaptive_intelligence"] is not None
    assert payload["adaptive_intelligence"]["status"]["tier"] == "standard"
    assert payload["adaptive_intelligence"]["transition_summary"]["is_transition"] is False
    assert payload["adaptive_intelligence"]["event_timestamp"] == "2026-05-19T12:05:00Z"


def test_core_live_telemetry_reader_null_adaptive_when_missing(state_dir: Path) -> None:
    reader = CoreLiveTelemetryReader(state_dir=state_dir)
    payload = reader.build_snapshot(obs=None)
    assert payload["adaptive_intelligence"] is None


def test_core_live_telemetry_reader_builds_snapshot(state_dir: Path) -> None:
    reader = CoreLiveTelemetryReader(state_dir=state_dir)
    payload = reader.build_snapshot(obs=None)

    assert payload["mode"] == "sim"
    assert payload["equity"] == 100_000.0
    assert payload["risk_level"] == "NORMAL"
    assert len(payload["active_mutations"]) == 1
    assert payload["active_mutations"][0]["hash"] == "abc123"
    assert payload["active_mutations"][0]["challenger_count"] == 2


def test_get_core_live_returns_telemetry(state_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backend.core_websocket.resolve_state_directory",
        lambda: state_dir,
    )
    monkeypatch.setenv("EVOLUTION_LOG_PATH", str(state_dir / "evolution_log.jsonl"))

    client = TestClient(app)
    response = client.get("/api/core/live")
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "telemetry"
    assert body["seq"] == 0
    assert body["payload"]["mode"] == "sim"
    assert body["payload"]["equity"] == 100_000.0
    assert body["payload"]["active_mutations"][0]["hash"] == "abc123"


def test_ws_core_live_streams_telemetry(state_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backend.core_websocket.resolve_state_directory",
        lambda: state_dir,
    )
    monkeypatch.setenv("EVOLUTION_LOG_PATH", str(state_dir / "evolution_log.jsonl"))

    client = TestClient(app)
    with client.websocket_connect("/ws/core/live") as ws:
        first = ws.receive_json()
        assert first["type"] == "telemetry"
        assert first["seq"] == 0
        assert first["payload"]["mode"] == "sim"
        assert first["payload"]["equity"] == 100_000.0
        assert first["payload"]["active_mutations"][0]["hash"] == "abc123"

        second = ws.receive_json()
        assert second["type"] == "telemetry"
        assert second["seq"] == 1


def test_ws_core_live_responds_to_ping(state_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backend.core_websocket.resolve_state_directory",
        lambda: state_dir,
    )
    monkeypatch.setenv("EVOLUTION_LOG_PATH", str(state_dir / "evolution_log.jsonl"))

    client = TestClient(app)
    with client.websocket_connect("/ws/core/live") as ws:
        ws.receive_json()
        ws.send_json({"type": "ping"})
        pong = ws.receive_json()
        assert pong["type"] == "pong"
        assert "ts" in pong


def test_post_core_mode_updates_live_telemetry(
    state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "backend.core_websocket.resolve_state_directory",
        lambda: state_dir,
    )
    monkeypatch.setenv("EVOLUTION_LOG_PATH", str(state_dir / "evolution_log.jsonl"))

    client = TestClient(app)
    with patch(
        "lumina_core.maturity.maturation_progress.maturation_eligible_for_real",
        return_value=(True, []),
    ):
        response = client.post("/api/core/mode", json={"mode": "real"})
    assert response.status_code == 200
    assert response.json() == {"ok": True, "mode": "real", "blockers": []}

    live = client.get("/api/core/live")
    assert live.status_code == 200
    assert live.json()["payload"]["mode"] == "real"


def test_core_live_telemetry_reader_includes_performance(state_dir: Path) -> None:
    (state_dir / "monitoring_runtime_metrics.json").write_text(
        json.dumps(
            {
                "timestamp": "2026-05-19T12:00:00Z",
                "mode": "sim",
                "account_equity": 101_000.0,
                "daily_pnl": 250.0,
                "open_pnl": 50.0,
                "equity_curve": [100_000.0, 100_500.0, 101_000.0],
                "pnl_history": [500.0, 500.0],
                "session_kpis": {
                    "winrate": 0.7,
                    "sharpe_annualized": 1.5,
                    "profit_factor": 2.0,
                    "max_drawdown_pct": -1.2,
                    "max_drawdown_usd": 300.0,
                    "realized_pnl_session": 1000.0,
                },
            }
        ),
        encoding="utf-8",
    )

    reader = CoreLiveTelemetryReader(state_dir=state_dir)
    payload = reader.build_snapshot(obs=None)

    assert payload["performance"] is not None
    assert payload["performance"]["source"] == "live"
    assert payload["performance"]["session_kpis"]["winrate"] == 0.7
    assert len(payload["performance"]["equity_series"]) == 3


def test_core_live_telemetry_reader_includes_fortress(state_dir: Path) -> None:
    (state_dir / "monitoring_runtime_metrics.json").write_text(
        json.dumps(
            {
                "timestamp": "2026-05-19T12:00:00Z",
                "mode": "real",
                "account_equity": 92_000.0,
                "account_balance": 100_000.0,
                "drawdown_pct": 8.0,
                "drawdown_kill_pct": 8.0,
                "mc_drawdown_pct": 4.2,
                "consecutive_losses": 2,
                "pending_reconciliations": 1,
            }
        ),
        encoding="utf-8",
    )

    class _ObsStub:
        def snapshot(self) -> dict[str, object]:
            return {
                "lumina_risk_kill_switch_active": {"value": 1.0},
            }

    reader = CoreLiveTelemetryReader(state_dir=state_dir)
    payload = reader.build_snapshot(obs=_ObsStub())

    assert payload["fortress"] is not None
    assert payload["fortress"]["drawdown_pct"] == 8.0
    assert payload["fortress"]["drawdown_kill_pct"] == 8.0
    assert payload["fortress"]["kill_switch_active"] is True
    assert payload["fortress"]["mc_drawdown_pct"] == 4.2
    assert payload["fortress"]["pending_reconciliations"] == 1


def test_core_live_telemetry_reader_null_fortress_when_no_state(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty_state"
    empty_dir.mkdir()
    reader = CoreLiveTelemetryReader(state_dir=empty_dir)
    payload = reader.build_snapshot(obs=None)
    assert payload["fortress"] is None


def test_post_core_mode_rejects_invalid_mode(
    state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "backend.core_websocket.resolve_state_directory",
        lambda: state_dir,
    )

    client = TestClient(app)
    response = client.post("/api/core/mode", json={"mode": "paper"})
    assert response.status_code == 422
