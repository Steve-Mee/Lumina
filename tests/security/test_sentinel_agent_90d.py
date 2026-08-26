"""90d Sentinel agent: allowlist, containment, weak tokens, thresholds."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.cyber_sentinel import (
    activate_containment,
    assert_fabric_token_safe,
    clear_containment,
    client_ip_allowed,
    evaluate_client_access,
    is_containment_active,
    observe_auth_failure,
    observe_unauthorized_producer,
    read_containment,
    resolve_uvicorn_ssl,
    status_snapshot,
)
from lumina_core.sentinel_agent import SentinelAgent


def test_ip_allowlist_cidr() -> None:
    assert client_ip_allowed("10.1.2.3", allowlist_raw="10.0.0.0/8")
    assert not client_ip_allowed("11.0.0.1", allowlist_raw="10.0.0.0/8")
    assert client_ip_allowed("127.0.0.1", allowlist_raw="10.0.0.0/8")


def test_weak_token_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LUMINA_FABRIC_ALLOW_SIM_DEV_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="sim-dev-token"):
        assert_fabric_token_safe("sim-dev-token", mode_context="sim")
    with pytest.raises(RuntimeError, match="Weak Fabric token"):
        assert_fabric_token_safe("sim-dev-token", mode_context="real")
    monkeypatch.setenv("LUMINA_FABRIC_ALLOW_SIM_DEV_TOKEN", "true")
    assert_fabric_token_safe("sim-dev-token", mode_context="sim")
    assert_fabric_token_safe("prod-grade-token-value", mode_context="real")


def test_containment_blocks_remote_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_WORKSPACE", str(tmp_path))
    clear_containment(workspace_root=tmp_path)
    assert evaluate_client_access("8.8.8.8", workspace_root=tmp_path) is None  # no allowlist
    activate_containment(
        reason="test",
        code="TEST",
        workspace_root=tmp_path,
    )
    assert is_containment_active(tmp_path)
    veto = evaluate_client_access("8.8.8.8", workspace_root=tmp_path)
    assert veto is not None
    assert veto.code == "CONTAINMENT_ACTIVE"
    assert evaluate_client_access("127.0.0.1", workspace_root=tmp_path) is None
    clear_containment(workspace_root=tmp_path, reason="test_done")
    assert not is_containment_active(tmp_path)


def test_allowlist_enforced_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_IP_ALLOWLIST", "192.168.1.0/24")
    assert evaluate_client_access("192.168.1.50") is None
    veto = evaluate_client_access("203.0.113.9")
    assert veto is not None
    assert veto.code == "IP_NOT_ALLOWLISTED"
    monkeypatch.delenv("LUMINA_IP_ALLOWLIST", raising=False)


def test_auth_burst_activates_containment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_WORKSPACE", str(tmp_path))
    clear_containment(workspace_root=tmp_path)
    # Drive threshold without waiting real time (direct activate is covered; here use loop).
    import lumina_core.cyber_sentinel as cs

    monkeypatch.setattr(cs, "_AUTH_FAIL_THRESHOLD", 3)
    with cs._lock:
        cs._auth_fails.clear()
    for i in range(3):
        observe_auth_failure(principal="x", reason=f"fail{i}", workspace_root=tmp_path)
    assert is_containment_active(tmp_path)
    assert read_containment(tmp_path).code == "AUTH_BURST"
    clear_containment(workspace_root=tmp_path)


def test_bus_unauthorized_observe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_WORKSPACE", str(tmp_path))
    clear_containment(workspace_root=tmp_path)
    import lumina_core.cyber_sentinel as cs

    monkeypatch.setattr(cs, "_BUS_UNAUTHORIZED_THRESHOLD", 2)
    with cs._lock:
        cs._bus_rejects.clear()
    observe_unauthorized_producer(topic="t", producer="evil1", workspace_root=tmp_path)
    observe_unauthorized_producer(topic="t", producer="evil2", workspace_root=tmp_path)
    assert is_containment_active(tmp_path)
    clear_containment(workspace_root=tmp_path)


def test_sentinel_agent_tick_no_trade_actions(tmp_path: Path) -> None:
    agent = SentinelAgent(workspace_root=tmp_path)
    snap = agent.tick()
    assert snap["capital_path"] == "untouched"
    assert snap["trade_actions"] == []
    assert snap["trades_forbidden"] is True
    assert "containment" in snap


def test_resolve_uvicorn_ssl_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LUMINA_API_TLS_CERT", raising=False)
    monkeypatch.delenv("LUMINA_API_TLS_KEY", raising=False)
    assert resolve_uvicorn_ssl() is None


def test_status_snapshot_shape(tmp_path: Path) -> None:
    snap = status_snapshot(tmp_path)
    assert snap["domain"] == "network_token_only"
    assert "windows" in snap
    assert "thresholds" in snap
