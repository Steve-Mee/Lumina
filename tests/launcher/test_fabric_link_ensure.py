"""ensure_fabric_token_aligned_and_live unit tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lumina_core.broker.ninjatrader.fabric_secret import FabricSecret
from lumina_launcher.services.fabric_link_ensure import ensure_fabric_token_aligned_and_live


def _sec(token: str) -> FabricSecret:
    return FabricSecret(
        token=token,
        fingerprint="abcd" if token else "",
        source="process_env" if token else "empty",
        surfaces_aligned=bool(token),
        env_len=len(token),
        json_len=len(token),
        mismatch=False,
        healed=False,
    )


@pytest.mark.unit
def test_ensure_token_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    os.environ.pop("LUMINA_FABRIC_TOKEN", None)
    monkeypatch.setattr(
        "lumina_core.broker.ninjatrader.fabric_secret.read",
        lambda heal=True, prefer_host_json=True: _sec(""),
    )
    cfg = SimpleNamespace(ninjatrader_nt8_api_key="")
    out = ensure_fabric_token_aligned_and_live(
        engine_config=cfg,
        start_supervisor=False,
    )
    assert out["ok"] is False
    assert out["code"] == "TOKEN_EMPTY"


@pytest.mark.unit
def test_ensure_live_ok_via_supervisor(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    os.environ["LUMINA_FABRIC_TOKEN"] = "test-token-xyz"
    monkeypatch.setattr(
        "lumina_core.broker.ninjatrader.fabric_secret.write",
        lambda tok, source="", config_manager=None: {
            "ok": True,
            "process_env": True,
            "user_env": True,
            "fabric_json": "x",
        },
    )
    monkeypatch.setattr(
        "lumina_core.broker.ninjatrader.fabric_secret.read",
        lambda heal=True, prefer_host_json=True: _sec("test-token-xyz"),
    )

    class _Sup:
        def ensure_connected(self, timeout_seconds: float = 10.0) -> bool:
            return True

        def status(self) -> SimpleNamespace:
            return SimpleNamespace(
                to_dict=lambda: {
                    "connected": True,
                    "auth_ok": True,
                    "session_id": "s1",
                }
            )

    monkeypatch.setattr(
        "lumina_core.broker.ninjatrader.fabric_link_supervisor.ensure_fabric_link_supervisor",
        lambda *a, **k: _Sup(),
    )
    cfg = SimpleNamespace(
        ninjatrader_nt8_api_key="test-token-xyz",
        broker_live_provider="ninjatrader",
    )
    out = ensure_fabric_token_aligned_and_live(engine_config=cfg, start_supervisor=True)
    assert out["ok"] is True
    assert out["code"] == "OK"
    assert out["needs_nt_restart"] is False


@pytest.mark.unit
def test_ensure_auth_failed_needs_nt_restart(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    os.environ["LUMINA_FABRIC_TOKEN"] = "brain-tok"
    monkeypatch.setattr(
        "lumina_core.broker.ninjatrader.fabric_secret.write",
        lambda tok, source="", config_manager=None: {
            "ok": True,
            "process_env": True,
            "user_env": True,
            "fabric_json": "x",
        },
    )
    monkeypatch.setattr(
        "lumina_core.broker.ninjatrader.fabric_secret.read",
        lambda heal=True, prefer_host_json=True: _sec("brain-tok"),
    )

    class _Sup:
        def ensure_connected(self, timeout_seconds: float = 10.0) -> bool:
            return False

        def status(self) -> SimpleNamespace:
            return SimpleNamespace(to_dict=lambda: {"connected": False, "auth_ok": False})

    monkeypatch.setattr(
        "lumina_core.broker.ninjatrader.fabric_link_supervisor.ensure_fabric_link_supervisor",
        lambda *a, **k: _Sup(),
    )

    class _Probe:
        ok = False
        code = "AUTH_FAILED"
        message = "Invalid fabric token"

        def to_dict(self) -> dict:
            return {"ok": False, "code": self.code, "message": self.message}

    monkeypatch.setattr(
        "lumina_core.broker.ninjatrader.fabric_auth_probe.probe_fabric_auth",
        lambda **k: _Probe(),
    )
    monkeypatch.setattr(
        "lumina_core.broker.ninjatrader.fabric_auth_probe.remediation_for_probe",
        lambda p: "token mismatch restart NT",
    )
    inv = MagicMock()
    monkeypatch.setattr(
        "lumina_launcher.services.fabric_link_certificate.invalidate_certificate",
        inv,
    )

    cfg = SimpleNamespace(ninjatrader_nt8_api_key="brain-tok")
    out = ensure_fabric_token_aligned_and_live(engine_config=cfg, start_supervisor=True)
    assert out["ok"] is False
    assert out["code"] == "AUTH_FAILED"
    assert out["needs_nt_restart"] is True
    assert inv.called
