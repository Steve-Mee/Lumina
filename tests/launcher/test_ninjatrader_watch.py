"""NT update watch: auto-heal Custom without killing NinjaTrader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from lumina_launcher.services import ninjatrader_watch as watch


class _Report:
    def __init__(self, overall: str = "red") -> None:
        self.overall = overall
        self.target = "127.0.0.1:50051"
        self.summary = "mocked"
        self.checks: list[Any] = []


def _fp(path: Path, *, size: int = 10, mtime_ns: int = 1) -> dict[str, Any]:
    return {"path": str(path), "size": size, "mtime_ns": mtime_ns}


def test_watch_auto_heals_without_fingerprint_change(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    exe = tmp_path / "NinjaTrader.exe"
    exe.write_bytes(b"x")
    fp = _fp(exe)
    monkeypatch.setattr(watch, "resolve_nt_exe", lambda: exe)
    monkeypatch.setattr(watch, "fingerprint_nt_exe", lambda _p: fp)
    monkeypatch.setattr(watch, "read_nt_fingerprint", lambda _r=None: fp)
    monkeypatch.setattr(watch, "write_nt_fingerprint", lambda *_a, **_k: None)
    monkeypatch.setattr(watch, "is_halt_active", lambda _r=None: False)
    healed: list[dict[str, Any]] = []

    def _ensure(*, build_if_nt_stopped: bool = True) -> dict[str, Any]:
        healed.append({"build_if_nt_stopped": build_if_nt_stopped})
        return {
            "ok": True,
            "csproj_changed": True,
            "built": True,
            "nt_running": False,
            "inject": {"status": "already_present+sanitized"},
            "build": {"status": "built", "isolated": []},
        }

    monkeypatch.setattr(
        "lumina_launcher.services.fabric_heal.ensure_custom_compile_ready",
        _ensure,
    )
    probed: list[int] = []
    monkeypatch.setattr(
        watch,
        "run_fabric_connection_diagnostics",
        lambda **_k: probed.append(1) or _Report("red"),
    )
    halted: list[int] = []
    monkeypatch.setattr(watch, "set_halt", lambda **_k: halted.append(1))

    result = watch.check_ninjatrader_update_and_reprobe(tmp_path)
    assert result["action"] == "healed"
    assert result["changed"] is False
    assert healed == [{"build_if_nt_stopped": True}]
    assert probed == []
    assert halted == []
    assert result["auto_heal"]["built"] is True


def test_watch_healed_waiting_nt_does_not_halt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    exe = tmp_path / "NinjaTrader.exe"
    exe.write_bytes(b"x")
    monkeypatch.setattr(watch, "resolve_nt_exe", lambda: exe)
    monkeypatch.setattr(watch, "fingerprint_nt_exe", lambda _p: _fp(exe, size=99))
    monkeypatch.setattr(watch, "read_nt_fingerprint", lambda _r=None: _fp(exe, size=1))
    monkeypatch.setattr(watch, "write_nt_fingerprint", lambda *_a, **_k: None)
    monkeypatch.setattr(watch, "is_halt_active", lambda _r=None: False)
    monkeypatch.setattr(
        "lumina_launcher.services.fabric_heal.ensure_custom_compile_ready",
        lambda **_k: {
            "ok": True,
            "csproj_changed": True,
            "built": True,
            "nt_running": False,
            "inject": {"status": "injected+sanitized"},
            "build": {"status": "built"},
        },
    )
    monkeypatch.setattr(
        "lumina_launcher.services.fabric_heal.is_ninjatrader_running",
        lambda: False,
    )
    monkeypatch.setattr(
        watch,
        "run_fabric_connection_diagnostics",
        lambda **_k: _Report("red"),
    )
    halted: list[int] = []
    monkeypatch.setattr(watch, "set_halt", lambda **_k: halted.append(1))

    result = watch.check_ninjatrader_update_and_reprobe(tmp_path)
    assert result["changed"] is True
    assert result["action"] == "healed_waiting_nt"
    assert halted == []
    assert result.get("halt") is False or result.get("halt") is None or result["halt"] is False


def test_watch_halts_when_nt_running_and_probe_red(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    exe = tmp_path / "NinjaTrader.exe"
    exe.write_bytes(b"x")
    monkeypatch.setattr(watch, "resolve_nt_exe", lambda: exe)
    monkeypatch.setattr(watch, "fingerprint_nt_exe", lambda _p: _fp(exe, size=99))
    monkeypatch.setattr(watch, "read_nt_fingerprint", lambda _r=None: _fp(exe, size=1))
    monkeypatch.setattr(watch, "write_nt_fingerprint", lambda *_a, **_k: None)
    monkeypatch.setattr(watch, "is_halt_active", lambda _r=None: False)
    monkeypatch.setattr(
        "lumina_launcher.services.fabric_heal.ensure_custom_compile_ready",
        lambda **_k: {
            "ok": True,
            "csproj_changed": True,
            "built": False,
            "nt_running": True,
            "inject": {"status": "already_present+sanitized"},
            "build": {"status": "skipped_nt_running"},
        },
    )
    monkeypatch.setattr(
        "lumina_launcher.services.fabric_heal.is_ninjatrader_running",
        lambda: True,
    )
    monkeypatch.setattr(
        watch,
        "run_fabric_connection_diagnostics",
        lambda **_k: _Report("red"),
    )
    halted: list[dict[str, Any]] = []
    monkeypatch.setattr(watch, "set_halt", lambda **k: halted.append(k))

    result = watch.check_ninjatrader_update_and_reprobe(tmp_path)
    assert result["action"] == "halt"
    assert result["needs_repair"] is True
    assert halted
    assert halted[0]["reason"] == "ninjatrader_update_fabric_failed"
