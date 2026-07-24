"""Unit tests for fabric connection diagnostics (no CrossTrade)."""

from __future__ import annotations

from typing import Any

import pytest

from lumina_launcher.services import fabric_connection_diagnostics as diag


def test_token_and_tcp_fail_closed_without_host(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    monkeypatch.delenv("LUMINA_FABRIC_TOKEN", raising=False)
    monkeypatch.delenv("LUMINA_NT8_API_KEY", raising=False)
    monkeypatch.setattr(diag, "_fabric_json_path", lambda: tmp_path / "missing.json")
    monkeypatch.setattr(diag, "_load_broker_config", lambda: {"live_provider": "crosstrade"})
    monkeypatch.setattr(diag, "_tcp_check", lambda host, port, timeout=2.0: (False, "refused"))

    report = diag.run_fabric_connection_diagnostics(include_safe_mode=False)
    assert report.overall == "red"
    ids = {c.id: c.status for c in report.checks}
    assert ids["token_present"] == "fail"
    assert ids["port_listen"] == "fail"
    assert any("LUMINA_FABRIC_TOKEN" in r or "Fabric host" in r for r in report.remediation)


def test_rejects_non_localhost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_FABRIC_TOKEN", "tok")
    monkeypatch.setattr(diag, "_load_fabric_json", lambda: {"BindHost": "8.8.8.8", "BindPort": 50051, "GatewayMode": "sim"})
    monkeypatch.setattr(
        diag,
        "_load_broker_config",
        lambda: {
            "live_provider": "ninjatrader",
            "ninjatrader": {"enabled": True, "fabric": {"host": "8.8.8.8", "port": 50051}},
        },
    )
    report = diag.run_fabric_connection_diagnostics(include_safe_mode=False)
    assert report.overall == "red"
    assert any(c.id == "port_listen" and c.status == "fail" for c in report.checks)
    assert "localhost" in " ".join(c.message for c in report.checks).lower() or any(
        "localhost" in r.lower() for r in report.remediation
    )


def test_report_to_dict_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_FABRIC_TOKEN", "tok-test")
    monkeypatch.setattr(diag, "_load_fabric_json", lambda: {"GatewayMode": "sim", "BindHost": "127.0.0.1", "BindPort": 50051})
    monkeypatch.setattr(
        diag,
        "_load_broker_config",
        lambda: {"live_provider": "ninjatrader", "ninjatrader": {"enabled": True, "fabric": {"host": "127.0.0.1", "port": 50051}}},
    )
    monkeypatch.setattr(diag, "_tcp_check", lambda host, port, timeout=2.0: (False, "down"))
    d = diag.run_fabric_connection_diagnostics(include_safe_mode=False).to_dict()
    assert d["overall"] in {"green", "amber", "red"}
    assert "checks" in d and isinstance(d["checks"], list)
    assert d["target"] == "127.0.0.1:50051"
