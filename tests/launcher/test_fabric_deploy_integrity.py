"""Tests for Fabric DLL deploy integrity (stub rejection, marker checks)."""

from __future__ import annotations

from pathlib import Path

from lumina_launcher.services.fabric_deploy_integrity import (
    NT_BRIDGE_MIN_BYTES,
    NT_BRIDGE_REQUIRED_MARKERS,
    pick_best_nt_bridge,
    verify_nt_bridge_dll,
)
from lumina_launcher.services.setup_persist import write_fabric_json_defaults


def test_verify_rejects_missing(tmp_path: Path) -> None:
    rep = verify_nt_bridge_dll(tmp_path / "missing.dll")
    assert rep["ok"] is False
    assert rep["reason"] == "missing_file"


def test_verify_rejects_tiny_stub(tmp_path: Path) -> None:
    p = tmp_path / "Lumina.Fabric.NtBridge.dll"
    # Hollow stub: large enough name but no product types.
    payload = b"MZ" + b"\x00" * 100 + b"FabricNtHost" + b"\x00" * 500
    p.write_bytes(payload)
    rep = verify_nt_bridge_dll(p)
    assert rep["ok"] is False
    assert "too_small" in str(rep["reason"]) or "missing_types" in str(rep["reason"])


def test_verify_accepts_synthetic_product_markers(tmp_path: Path) -> None:
    p = tmp_path / "Lumina.Fabric.NtBridge.dll"
    body = b"MZ" + b"\x00" * (NT_BRIDGE_MIN_BYTES + 64)
    for m in NT_BRIDGE_REQUIRED_MARKERS:
        body += m.encode("ascii") + b"\x00"
    p.write_bytes(body)
    rep = verify_nt_bridge_dll(p)
    assert rep["ok"] is True
    assert rep["size"] >= NT_BRIDGE_MIN_BYTES
    assert not rep["missing_markers"]


def test_pick_best_prefers_largest_ok(tmp_path: Path) -> None:
    small = tmp_path / "a" / "Lumina.Fabric.NtBridge.dll"
    large = tmp_path / "b" / "Lumina.Fabric.NtBridge.dll"
    small.parent.mkdir()
    large.parent.mkdir()

    def write_ok(path: Path, pad: int) -> None:
        body = b"MZ" + b"\x00" * (NT_BRIDGE_MIN_BYTES + pad)
        for m in NT_BRIDGE_REQUIRED_MARKERS:
            body += m.encode("ascii") + b"\x00"
        path.write_bytes(body)

    write_ok(small, 10)
    write_ok(large, 5000)
    best = pick_best_nt_bridge([small, large])
    assert best == large


def test_write_fabric_json_migrates_legacy_sim(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "fabric.json"
    target.write_text('{"GatewayMode": "sim", "AuthToken": "t"}', encoding="utf-8")
    import lumina_launcher.services.setup_persist as sp

    monkeypatch.setattr(sp, "fabric_json_path", lambda: target)
    write_fabric_json_defaults(path=target, auth_token="t")
    import json

    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["GatewayMode"] == "nt"
