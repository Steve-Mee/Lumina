"""Fabric Secret Bus — single write/read pipe unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.broker.ninjatrader import fabric_secret as fsb


@pytest.mark.unit
def test_fingerprint_stable() -> None:
    assert fsb.fingerprint("abc") == fsb.fingerprint("abc")
    assert len(fsb.fingerprint("abc")) == 16
    assert fsb.fingerprint("") == ""


@pytest.mark.unit
def test_read_heals_divergent_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fj = tmp_path / "fabric.json"
    host_tok = "host-ssot-token-with-enough-entropy-xyz12"
    fj.write_text(json.dumps({"AuthToken": host_tok}), encoding="utf-8")
    monkeypatch.setattr(fsb, "fabric_json_path", lambda: fj)
    monkeypatch.setenv("LUMINA_FABRIC_TOKEN", "stale-short")

    sec = fsb.read(heal=True)
    assert sec.token == host_tok
    assert sec.mismatch is True
    assert sec.healed is True
    assert sec.fingerprint == fsb.fingerprint(host_tok)
    import os

    assert os.environ["LUMINA_FABRIC_TOKEN"] == host_tok


@pytest.mark.unit
def test_write_commits_json_and_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fj = tmp_path / "fabric.json"
    monkeypatch.setattr(fsb, "fabric_json_path", lambda: fj)
    # write_fabric_json_defaults resolves path via setup_persist façade.
    monkeypatch.setattr(
        "lumina_launcher.services.setup_persist_fabric.fabric_json_path",
        lambda: fj,
    )
    monkeypatch.setattr(
        "lumina_launcher.services.setup_persist.fabric_json_path",
        lambda: fj,
    )
    monkeypatch.setattr(
        "lumina_launcher.services.setup_persist_fabric.set_user_environment_variable",
        lambda name, value: True,
    )
    tok = "new-written-token-abcdefghijklmnopqr"
    out = fsb.write(tok, source="test")
    assert out["ok"] is True
    assert out["fingerprint"] == fsb.fingerprint(tok)
    assert fj.is_file()
    data = json.loads(fj.read_text(encoding="utf-8"))
    assert data.get("AuthToken") == tok
    assert data.get("TokenFingerprint") == fsb.fingerprint(tok)
    import os

    assert os.environ["LUMINA_FABRIC_TOKEN"] == tok


@pytest.mark.unit
def test_resolve_legacy_dict_shape(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fj = tmp_path / "fabric.json"
    fj.write_text(json.dumps({"AuthToken": "legacy-shape-token-0123456789ab"}), encoding="utf-8")
    monkeypatch.setattr(fsb, "fabric_json_path", lambda: fj)
    monkeypatch.delenv("LUMINA_FABRIC_TOKEN", raising=False)
    d = fsb.resolve_fabric_token_ssot(heal_process_env=True)
    assert d["ok"] is True
    assert d["token"].startswith("legacy-shape")
    assert "fingerprint" in d
