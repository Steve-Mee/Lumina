"""Fabric auth probe classification + link supervisor basics."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lumina_core.broker.ninjatrader.fabric_auth_probe import (
    FabricProbeResult,
    probe_fabric_auth,
    remediation_for_probe,
)
from lumina_core.broker.ninjatrader.fabric_link_supervisor import FabricLinkSupervisor


@pytest.mark.unit
def test_remediation_auth_failed_mentions_token_not_only_start_nt() -> None:
    msg = remediation_for_probe(
        FabricProbeResult(ok=False, code="AUTH_FAILED", message="Invalid fabric token", target="127.0.0.1:50051")
    )
    assert "token" in msg.lower() or "Token" in msg
    assert "Repair" in msg or "repair" in msg.lower() or "herstart" in msg.lower()
    # Must not be only "start NT" when host is the problem of auth
    assert "Invalid fabric token" in msg or "auth" in msg.lower() or "token" in msg.lower()


@pytest.mark.unit
def test_remediation_connection_refused_mentions_start() -> None:
    msg = remediation_for_probe(
        FabricProbeResult(ok=False, code="CONNECTION_REFUSED", message="refused", target="127.0.0.1:50051")
    )
    assert "50051" in msg or "NinjaTrader" in msg or "LUMINA" in msg


@pytest.mark.unit
def test_probe_auth_failed_classifies(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeClient:
        def __init__(self, _cfg: object) -> None:
            self.last_connect_code = "AUTH_FAILED"
            self.last_connect_error = "Invalid fabric token"
            self.session_id = None
            self.account_name = ""

        def connect(self) -> bool:
            return False

        def disconnect(self) -> None:
            return None

    monkeypatch.setattr(
        "lumina_core.broker.ninjatrader.fabric_client.FabricGrpcClient",
        _FakeClient,
    )
    # FabricConfig.from_engine_config with minimal config
    cfg = SimpleNamespace(
        ninjatrader_fabric_host="127.0.0.1",
        ninjatrader_fabric_port=50051,
        ninjatrader_fabric_auth_token_env="LUMINA_FABRIC_TOKEN",
        ninjatrader_nt8_api_key="brain-token-value",
        fabric_heartbeat_interval_ms=1000,
        fabric_heartbeat_timeout_ms=5000,
        fabric_command_timeout_seconds=10,
        fabric_connect_timeout_seconds=5,
    )
    result = probe_fabric_auth(config=cfg, mode_context="sim")
    assert result.ok is False
    assert result.code == "AUTH_FAILED"
    assert "token" in result.message.lower() or "Token" in result.message or "auth" in result.message.lower()


@pytest.mark.unit
def test_supervisor_try_connect_once_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class _OkClient:
        def __init__(self, cfg: object) -> None:
            self.config = cfg
            self.is_connected = False
            self.session_id = "sess-1"
            self.account_name = "Sim101"
            self.last_connect_code = ""
            self.last_connect_error = ""

        def connect(self) -> bool:
            self.is_connected = True
            self.last_connect_code = "OK"
            return True

        def disconnect(self) -> None:
            self.is_connected = False

    monkeypatch.setattr(
        "lumina_core.broker.ninjatrader.fabric_client.FabricGrpcClient",
        _OkClient,
    )
    sup = FabricLinkSupervisor()
    sup.configure_from_engine_config(
        SimpleNamespace(
            ninjatrader_fabric_host="127.0.0.1",
            ninjatrader_fabric_port=50051,
            ninjatrader_fabric_auth_token_env="LUMINA_FABRIC_TOKEN",
            ninjatrader_nt8_api_key="tok",
            fabric_heartbeat_interval_ms=1000,
            fabric_heartbeat_timeout_ms=5000,
            fabric_command_timeout_seconds=10,
            fabric_connect_timeout_seconds=5,
        )
    )
    assert sup._try_connect_once() is True
    assert sup.get_client() is not None
    st = sup.status()
    assert st.connected is True
    assert st.session_id == "sess-1"
    sup.stop()


@pytest.mark.unit
def test_supervisor_resets_backoff_when_nt_returns(monkeypatch: pytest.MonkeyPatch) -> None:
    """When NT process returns after being gone, reconnect ASAP (avoid SAFE_MODE lag)."""
    calls = {"n": 0}

    class _FlipClient:
        def __init__(self, cfg: object) -> None:
            self.config = cfg
            self.is_connected = False
            self.session_id = "s2"
            self.account_name = "Sim101"
            self.last_connect_code = ""
            self.last_connect_error = ""

        def connect(self) -> bool:
            calls["n"] += 1
            # First attempt fails, second succeeds after NT-back reset path
            if calls["n"] < 2:
                self.last_connect_code = "CONNECTION_REFUSED"
                self.last_connect_error = "stream lost"
                return False
            self.is_connected = True
            self.last_connect_code = "OK"
            return True

        def disconnect(self) -> None:
            self.is_connected = False

    monkeypatch.setattr(
        "lumina_core.broker.ninjatrader.fabric_client.FabricGrpcClient",
        _FlipClient,
    )
    alive = {"v": False}
    monkeypatch.setattr(
        FabricLinkSupervisor,
        "_nt_process_alive",
        staticmethod(lambda: alive["v"]),
    )

    sup = FabricLinkSupervisor()
    sup.configure_from_engine_config(
        SimpleNamespace(
            ninjatrader_fabric_host="127.0.0.1",
            ninjatrader_fabric_port=50051,
            ninjatrader_fabric_auth_token_env="LUMINA_FABRIC_TOKEN",
            ninjatrader_nt8_api_key="tok",
            fabric_heartbeat_interval_ms=1000,
            fabric_heartbeat_timeout_ms=5000,
            fabric_command_timeout_seconds=10,
            fabric_connect_timeout_seconds=5,
        )
    )
    # NT down → connect fail
    assert sup._try_connect_once() is False
    # NT back → connect ok
    alive["v"] = True
    assert sup._try_connect_once() is True
    assert sup.get_client() is not None
    sup.stop()


@pytest.mark.unit
def test_supervisor_auth_fail_marks_down(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BadClient:
        def __init__(self, cfg: object) -> None:
            self.config = cfg
            self.is_connected = False
            self.session_id = None
            self.account_name = ""
            self.last_connect_code = "AUTH_FAILED"
            self.last_connect_error = "Invalid fabric token"

        def connect(self) -> bool:
            return False

        def disconnect(self) -> None:
            return None

    inv = MagicMock()
    monkeypatch.setattr(
        "lumina_core.broker.ninjatrader.fabric_client.FabricGrpcClient",
        _BadClient,
    )
    monkeypatch.setattr(
        "lumina_launcher.services.fabric_link_certificate.invalidate_certificate",
        inv,
        raising=False,
    )
    # Patch where supervisor imports it
    monkeypatch.setattr(
        "lumina_launcher.services.fabric_link_certificate.invalidate_certificate",
        inv,
    )

    sup = FabricLinkSupervisor()
    sup.configure_from_engine_config(
        SimpleNamespace(
            ninjatrader_fabric_host="127.0.0.1",
            ninjatrader_fabric_port=50051,
            ninjatrader_fabric_auth_token_env="LUMINA_FABRIC_TOKEN",
            ninjatrader_nt8_api_key="tok",
            fabric_heartbeat_interval_ms=1000,
            fabric_heartbeat_timeout_ms=5000,
            fabric_command_timeout_seconds=10,
            fabric_connect_timeout_seconds=5,
        )
    )
    assert sup._try_connect_once() is False
    assert sup.get_client() is None
    assert sup.status().last_error_code == "AUTH_FAILED"
