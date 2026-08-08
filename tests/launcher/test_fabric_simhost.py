"""SimHost auto-start for SIM Fabric diagnostics."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from lumina_launcher.services import fabric_simhost as simhost
from lumina_launcher.services import fabric_connection_diagnostics as diag


def test_resolve_simhost_exe_finds_release_build() -> None:
    root = Path(__file__).resolve().parents[2]
    exe = simhost.resolve_simhost_exe(root)
    # Build artifact present in this workspace (Release net48).
    if exe is None:
        pytest.skip("SimHost executable not built (requires Release build artifact)")
    assert exe.name == "Lumina.Execution.Fabric.SimHost.exe"
    assert exe.is_file()


def test_ensure_simhost_rejects_non_localhost() -> None:
    result = simhost.ensure_simhost_listening(host="8.8.8.8", port=50051)
    assert result["ok"] is False
    assert result["status"] == "rejected"
    assert result["listening"] is False


def test_diagnostics_auto_starts_simhost_when_port_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LUMINA_FABRIC_TOKEN", "tok-auto")
    monkeypatch.setattr(
        diag,
        "_load_fabric_json",
        lambda: {"GatewayMode": "sim", "BindHost": "127.0.0.1", "BindPort": 50051, "AccountName": "Sim101"},
    )
    monkeypatch.setattr(
        diag,
        "_load_broker_config",
        lambda: {
            "live_provider": "ninjatrader",
            "ninjatrader": {"enabled": True, "fabric": {"host": "127.0.0.1", "port": 50051}},
        },
    )

    monkeypatch.setattr(diag, "_tcp_check", lambda host, port, timeout=2.0: (False, "refused"))

    ensure_calls: list[dict[str, Any]] = []

    def fake_ensure(**kwargs: Any) -> dict[str, Any]:
        ensure_calls.append(kwargs)
        return {
            "ok": True,
            "status": "aligned",
            "message": "SimHost started and authenticated",
            "listening": True,
            "authenticated": True,
            "started": True,
            "pid": 12345,
        }

    monkeypatch.setattr(
        "lumina_launcher.services.fabric_simhost.ensure_simhost_token_aligned",
        fake_ensure,
    )

    monkeypatch.setattr(
        "lumina_launcher.services.fabric_connection_diagnostics.run_live_checks",
        lambda **kwargs: None,
    )

    report = diag.run_fabric_connection_diagnostics(include_safe_mode=False)
    assert ensure_calls, "token-aligned auto-start must run for SIM localhost"
    port_check = next(c for c in report.checks if c.id == "port_listen")
    assert port_check.status == "pass"


def test_token_aligned_restarts_mismatched_simhost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_FABRIC_TOKEN", "brain-token")
    monkeypatch.setattr(simhost, "tcp_open", lambda host, port, timeout=0.75: True)
    auth_calls = {"n": 0}

    def fake_probe(host: str, port: int, token: str, timeout_sec: float = 4.0) -> tuple[bool, str]:
        auth_calls["n"] += 1
        # First probe fails (stale host); after restart, succeeds.
        if auth_calls["n"] == 1:
            return False, "auth_rejected"
        return True, "authenticated"

    monkeypatch.setattr(simhost, "probe_fabric_auth", fake_probe)
    monkeypatch.setattr(simhost, "find_simhost_pids_on_port", lambda port: [4242])
    stops: list[Any] = []

    def fake_stop(**kwargs: Any) -> dict[str, Any]:
        stops.append(kwargs)
        return {"ok": True, "killed": [4242]}

    monkeypatch.setattr(simhost, "stop_simhost", fake_stop)
    monkeypatch.setattr(
        simhost,
        "ensure_simhost_listening",
        lambda **kwargs: {
            "ok": True,
            "status": "listening",
            "listening": True,
            "started": True,
            "pid": 99,
        },
    )

    result = simhost.ensure_simhost_token_aligned(
        host="127.0.0.1",
        port=50051,
        token="brain-token",
    )
    assert stops, "mismatched SimHost must be stopped"
    assert result["ok"] is True
    assert result["authenticated"] is True
    assert result.get("restarted") is True
    assert auth_calls["n"] >= 2
