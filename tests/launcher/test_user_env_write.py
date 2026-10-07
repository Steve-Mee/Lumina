"""User env writes must not spawn PowerShell or block on HWND_BROADCAST."""

from __future__ import annotations

import sys

import pytest

from lumina_launcher.services import setup_persist_fabric as sp


class _FakeKey:
    def __init__(self, store: dict[str, str]) -> None:
        self.store = store

    def __enter__(self) -> _FakeKey:
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False


class _FakeWinreg:
    HKEY_CURRENT_USER = object()
    KEY_READ = 1
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self, store: dict[str, str]) -> None:
        self.store = store
        self.writes: list[str] = []

    def OpenKey(self, *_args: object, **_kwargs: object) -> _FakeKey:
        return _FakeKey(self.store)

    def QueryValueEx(self, key: _FakeKey, name: str) -> tuple[str, int]:
        if name not in key.store:
            raise FileNotFoundError(name)
        return key.store[name], self.REG_SZ

    def SetValueEx(self, key: _FakeKey, name: str, _reserved: int, _kind: int, value: str) -> None:
        key.store[name] = value
        self.writes.append(value)


def test_windows_user_env_skips_rewrite_and_does_not_spawn_powershell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = {"LUMINA_FABRIC_TOKEN": "already-set"}
    fake = _FakeWinreg(store)
    broadcasts: list[str] = []
    monkeypatch.setattr(sp, "_broadcast_environment_change", lambda: broadcasts.append("go"))
    monkeypatch.setitem(sys.modules, "winreg", fake)

    assert sp._write_windows_user_env("LUMINA_FABRIC_TOKEN", "already-set") is True
    assert fake.writes == []
    assert broadcasts == []

    assert sp._write_windows_user_env("LUMINA_FABRIC_TOKEN", "next-token") is True
    assert fake.writes == ["next-token"]
    assert broadcasts == ["go"]


def test_set_user_env_updates_process_and_skips_registry_off_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sp.sys, "platform", "linux")
    monkeypatch.delenv("LUMINA_FABRIC_TOKEN", raising=False)
    assert sp.set_user_environment_variable("LUMINA_FABRIC_TOKEN", "session-token") is True
    assert sp.os.environ["LUMINA_FABRIC_TOKEN"] == "session-token"


def test_set_user_env_rejects_empty() -> None:
    assert sp.set_user_environment_variable("", "x") is False
    assert sp.set_user_environment_variable("LUMINA_FABRIC_TOKEN", "  ") is False
