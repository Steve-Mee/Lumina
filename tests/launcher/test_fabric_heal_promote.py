"""Heal promote must never overwrite product NtBridge with a stub .new."""

from __future__ import annotations

from pathlib import Path

from lumina_launcher.services.fabric_deploy_integrity import (
    NT_BRIDGE_MIN_BYTES,
    NT_BRIDGE_REQUIRED_MARKERS,
)
from lumina_launcher.services.fabric_heal import promote_staged_dlls


def _write_product(path: Path, *, pad: int = 64) -> None:
    body = b"MZ" + b"\x00" * (NT_BRIDGE_MIN_BYTES + pad)
    for m in NT_BRIDGE_REQUIRED_MARKERS:
        body += m.encode("ascii") + b"\x00"
    path.write_bytes(body)


def test_promote_quarantines_stub_bridge_new(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "lumina_launcher.services.fabric_heal.is_ninjatrader_running",
        lambda: False,
    )
    custom = tmp_path / "Custom"
    custom.mkdir()
    product = custom / "Lumina.Fabric.NtBridge.dll"
    _write_product(product, pad=1000)
    product_size = product.stat().st_size
    staged = custom / "Lumina.Fabric.NtBridge.dll.new"
    staged.write_bytes(b"MZ" + b"\x00" * 500 + b"FabricNtHost")

    promoted = promote_staged_dlls(custom)
    assert product.is_file()
    assert product.stat().st_size == product_size
    assert not staged.is_file()
    q = custom / "Lumina.Fabric.NtBridge.dll.new.STUB_DISABLE"
    assert q.is_file()
    assert "Lumina.Fabric.NtBridge.dll" not in " ".join(Path(p).name for p in promoted)


def test_promote_accepts_larger_product_new(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "lumina_launcher.services.fabric_heal.is_ninjatrader_running",
        lambda: False,
    )
    custom = tmp_path / "Custom"
    custom.mkdir()
    product = custom / "Lumina.Fabric.NtBridge.dll"
    _write_product(product, pad=10)
    staged = custom / "Lumina.Fabric.NtBridge.dll.new"
    _write_product(staged, pad=5000)
    staged_size = staged.stat().st_size

    promote_staged_dlls(custom)
    assert product.is_file()
    assert product.stat().st_size == staged_size
    assert not staged.is_file()
