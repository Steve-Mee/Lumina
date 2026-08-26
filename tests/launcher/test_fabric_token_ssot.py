"""Fabric token SSOT — host fabric.json wins over stale process env (dual-truth)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.broker.ninjatrader import fabric_secret as fsb
from lumina_launcher.services.setup_persist_fabric import (
    read_fabric_json_auth_token,
    resolve_fabric_token_ssot,
)


@pytest.mark.unit
def test_resolve_prefers_fabric_json_when_env_diverges(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fj = tmp_path / "fabric.json"
    fj.write_text(
        json.dumps(
            {
                "BindHost": "127.0.0.1",
                "BindPort": 50051,
                "AuthToken": "host-ssot-token-with-enough-entropy-xyz",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LUMINA_FABRIC_TOKEN", "stale-short")
    monkeypatch.setattr(fsb, "fabric_json_path", lambda: fj)

    resolved = resolve_fabric_token_ssot(heal_process_env=True, prefer_host_json=True)
    assert resolved["ok"] is True
    assert resolved["token"] == "host-ssot-token-with-enough-entropy-xyz"
    assert resolved["mismatch"] is True
    assert resolved["healed_process_env"] is True
    assert resolved["source"] in {"fabric_json_healed_env", "fabric_json"}
    import os

    assert os.environ["LUMINA_FABRIC_TOKEN"] == "host-ssot-token-with-enough-entropy-xyz"


@pytest.mark.unit
def test_resolve_env_when_json_absent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    missing = tmp_path / "missing-fabric.json"
    monkeypatch.setenv("LUMINA_FABRIC_TOKEN", "env-only-token-abcdefghijklmnop")
    monkeypatch.setattr(fsb, "fabric_json_path", lambda: missing)
    resolved = resolve_fabric_token_ssot(heal_process_env=False, prefer_host_json=True)
    assert resolved["token"] == "env-only-token-abcdefghijklmnop"
    assert resolved["source"] == "process_env"
    assert resolved["mismatch"] is False


@pytest.mark.unit
def test_diag_resolve_token_heals_stale_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from lumina_launcher.services import fabric_diag_preflight as pre

    fj = tmp_path / "fabric.json"
    fj.write_text(
        json.dumps({"AuthToken": "json-host-token-0123456789abcdef"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("LUMINA_FABRIC_TOKEN", "wrong")
    monkeypatch.setattr(fsb, "fabric_json_path", lambda: fj)
    tok = pre._resolve_token()
    assert tok == "json-host-token-0123456789abcdef"


@pytest.mark.unit
def test_read_fabric_json_auth_token_empty(tmp_path: Path) -> None:
    assert read_fabric_json_auth_token(tmp_path / "nope.json") == ""
