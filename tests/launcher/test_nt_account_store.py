"""Demo binds. Real is stored beside it. The token and the trade mode stay."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.broker.ninjatrader.account_names import NtAccountRejected, validate_account_pair
from lumina_launcher.services.nt_account_store import (
    first_seal_account_block,
    read_nt_accounts,
    write_nt_accounts,
)

_CONFIG = "mode: sim\r\nbroker:\r\n  ninjatrader:\r\n    account_name: Sim101\r\n    enabled: true\r\n"


def _pair(tmp_path: Path, *, token: str = "fabric-token-keep") -> tuple[Path, Path]:
    config = tmp_path / "config.yaml"
    config.write_bytes(_CONFIG.encode("utf-8"))
    fabric = tmp_path / "fabric.json"
    fabric.write_text(
        json.dumps({"AccountName": "Sim101", "AuthToken": token, "GatewayMode": "nt"}) + "\n",
        encoding="utf-8",
    )
    return config, fabric


def test_validate_refuses_paper_real_and_empty_and_same_name() -> None:
    with pytest.raises(NtAccountRejected):
        validate_account_pair("DEMO5042070", "")
    with pytest.raises(NtAccountRejected):
        validate_account_pair("DEMO5042070", "Sim101")
    with pytest.raises(NtAccountRejected):
        validate_account_pair("DEMO5042070", "demo5042070")
    with pytest.raises(NtAccountRejected):
        validate_account_pair("LiveAcct", "APEX12345")
    demo, real = validate_account_pair(" DEMO5042070 ", "APEX12345")
    assert demo == "DEMO5042070"
    assert real == "APEX12345"


def test_empty_real_does_not_touch_files(tmp_path: Path) -> None:
    config, fabric = _pair(tmp_path)
    before_config = config.read_bytes()
    before_fabric = fabric.read_bytes()
    with pytest.raises(NtAccountRejected):
        write_nt_accounts(tmp_path, "DEMO5042070", "", fabric_path=fabric)
    assert config.read_bytes() == before_config
    assert fabric.read_bytes() == before_fabric


def test_write_keeps_token_mode_and_does_not_bind_real(tmp_path: Path) -> None:
    config, fabric = _pair(tmp_path)
    result = write_nt_accounts(tmp_path, "DEMO5042070", "APEX12345", fabric_path=fabric)
    written = json.loads(fabric.read_text(encoding="utf-8"))
    raw = config.read_bytes()
    assert written["AuthToken"] == "fabric-token-keep"
    assert written["AccountName"] == "DEMO5042070"
    assert written["RealAccountName"] == "APEX12345"
    assert written["GatewayMode"] == "nt"
    assert b"account_name: DEMO5042070" in raw
    assert b"mode: sim" in raw
    assert b"\r\n" in raw
    assert b"APEX12345" not in raw
    assert b"RealAccountName" not in raw
    assert result["pair_complete"] is True
    assert result["real_bound"] is False
    assert result["saved"] is True
    dumped = json.dumps(result)
    assert "AuthToken" not in result
    assert "fabric-token-keep" not in dumped


def test_write_restores_both_files_when_token_would_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, fabric = _pair(tmp_path, token="original-token")
    before_config = config.read_bytes()
    before_fabric = fabric.read_bytes()
    import lumina_launcher.services.nt_account_store as store

    real_loads = store.json.loads
    seen = {"n": 0}

    def wrapped(text: str, *args: object, **kwargs: object) -> object:
        seen["n"] += 1
        data = real_loads(text, *args, **kwargs)
        if seen["n"] >= 2 and isinstance(data, dict) and "AuthToken" in data:
            data = dict(data)
            data["AuthToken"] = "mutated"
        return data

    monkeypatch.setattr(store.json, "loads", wrapped)
    with pytest.raises(NtAccountRejected):
        write_nt_accounts(tmp_path, "DEMO5042070", "APEX12345", fabric_path=fabric)
    assert config.read_bytes() == before_config
    assert fabric.read_bytes() == before_fabric


def test_read_reports_misaligned_names_without_the_token(tmp_path: Path) -> None:
    config, fabric = _pair(tmp_path)
    config.write_bytes(_CONFIG.replace("Sim101", "DEMO5042070").encode("utf-8"))
    snap = read_nt_accounts(tmp_path, fabric_path=fabric)
    assert snap["names_aligned"] is False
    assert snap["pair_complete"] is False
    assert "DEMO5042070" in snap["pair_error"]
    assert "Sim101" in snap["pair_error"]
    assert "AuthToken" not in snap


def test_first_seal_blocks_only_before_setup_is_complete(tmp_path: Path) -> None:
    _, fabric = _pair(tmp_path)
    blocked = first_seal_account_block(tmp_path, setup_complete=False, fabric_path=fabric)
    assert "Control Center" in blocked
    assert first_seal_account_block(tmp_path, setup_complete=True, fabric_path=fabric) == ""
