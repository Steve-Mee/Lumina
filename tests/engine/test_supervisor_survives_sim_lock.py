"""A SIM thought-log lock error must not end the supervisor thread."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.engine.agent_contracts import _append_immutable_decision_log
from lumina_core.engine.runtime_workers_facade import tick_failure_is_fatal, trade_mode_of
from lumina_core.state.state_manager import _lock_key


def test_sim_modes_keep_the_next_tick() -> None:
    assert tick_failure_is_fatal("sim") is False
    assert tick_failure_is_fatal("paper") is False
    assert tick_failure_is_fatal("sim_real_guard") is False


def test_real_and_unknown_modes_end_the_loop() -> None:
    assert tick_failure_is_fatal("real") is True
    assert tick_failure_is_fatal("") is True
    assert tick_failure_is_fatal("birth") is True


def test_trade_mode_prefers_app_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_MODE", "real")
    app = SimpleNamespace(config=SimpleNamespace(trade_mode="sim"), engine=None)
    assert trade_mode_of(app) == "sim"


def test_lock_key_ignores_deleted_final_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock = tmp_path / ".locks" / "thought_log.jsonl.lock"

    def _deleted(self: Path, *args: object, **kwargs: object) -> Path:
        del self, args, kwargs
        return Path(r"D:\$Extend\$Deleted\thought_log.jsonl.lock")

    monkeypatch.setattr(Path, "resolve", _deleted)
    key = _lock_key(lock)
    assert "$deleted" not in key
    assert "thought_log.jsonl.lock" in key


def test_lock_key_refuses_a_deleted_absolute_path() -> None:
    with pytest.raises(OSError, match="deleted lock path"):
        _lock_key(Path(r"\\?\D:\$Extend\$Deleted\thought_log.jsonl.lock"))


def test_sim_decision_log_oserror_returns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_MODE", "sim")

    def _boom(*_args: object, **_kwargs: object) -> dict[str, str]:
        raise PermissionError(5, "Access is denied", r"\\?\D:\$Extend\$Deleted")

    monkeypatch.setattr(
        "lumina_core.engine.agent_contracts.get_audit_logger",
        lambda: SimpleNamespace(append=_boom),
    )
    _append_immutable_decision_log({"agent": "probe"})


def test_real_decision_log_oserror_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_MODE", "real")

    def _boom(*_args: object, **_kwargs: object) -> dict[str, str]:
        raise PermissionError(5, "Access is denied", r"\\?\D:\$Extend\$Deleted")

    monkeypatch.setattr(
        "lumina_core.engine.agent_contracts.get_audit_logger",
        lambda: SimpleNamespace(append=_boom),
    )
    with pytest.raises(PermissionError):
        _append_immutable_decision_log({"agent": "probe"})
