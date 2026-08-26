"""TelegramGateway disk offset + outbound rate limit."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from lumina_core.notifications.telegram_gateway import TelegramGateway, reset_telegram_gateway_for_tests
from lumina_core.notifications.telegram_journal import list_records
from lumina_core.notifications.telegram_notifier import TelegramNotifier, reset_telegram_notifier_for_tests


def test_poll_offset_persists_across_instances(tmp_path: Path) -> None:
    reset_telegram_gateway_for_tests()
    a = TelegramGateway(workspace_root=tmp_path, min_interval_sec=0, max_per_hour=100)
    assert a.load_offset() == 0
    a.save_offset(42)
    b = TelegramGateway(workspace_root=tmp_path, min_interval_sec=0, max_per_hour=100)
    assert b.load_offset() == 42
    b.save_offset(41)
    assert b.load_offset() == 42


def test_rate_limit_drops_non_bypass(tmp_path: Path) -> None:
    gw = TelegramGateway(
        workspace_root=tmp_path,
        min_interval_sec=60,
        max_per_hour=12,
        bypass_kinds=("promotion", "freeze", "real_safety"),
    )
    ok1, reason1 = gw.try_reserve_send("twin_escalation")
    assert ok1 is True
    assert reason1 is None
    ok2, reason2 = gw.try_reserve_send("twin_escalation")
    assert ok2 is False
    assert reason2 == "rate_limited"
    ok3, reason3 = gw.try_reserve_send("freeze")
    assert ok3 is True
    assert reason3 is None
    ok4, reason4 = gw.try_reserve_send("real_safety")
    assert ok4 is True
    assert reason4 is None
    ok5, reason5 = gw.try_reserve_send("promotion")
    assert ok5 is True
    assert reason5 is None


def test_hour_cap(tmp_path: Path) -> None:
    gw = TelegramGateway(
        workspace_root=tmp_path,
        min_interval_sec=0,
        max_per_hour=2,
        bypass_kinds=("freeze",),
    )
    assert gw.try_reserve_send("milestone")[0] is True
    assert gw.try_reserve_send("milestone")[0] is True
    assert gw.try_reserve_send("milestone") == (False, "rate_limited")
    assert gw.try_reserve_send("freeze")[0] is True


def test_notifier_journals_rate_limited_drop(tmp_path: Path, monkeypatch) -> None:
    reset_telegram_gateway_for_tests()
    reset_telegram_notifier_for_tests()
    gw = TelegramGateway(
        workspace_root=tmp_path,
        min_interval_sec=60,
        max_per_hour=12,
        bypass_kinds=("promotion", "freeze", "real_safety"),
    )
    monkeypatch.setattr(
        "lumina_core.notifications.telegram_notifier.get_telegram_gateway",
        lambda workspace_root=None: gw,
    )
    journal_path = tmp_path / "tg.jsonl"
    monkeypatch.setattr(
        "lumina_core.notifications.telegram_journal.resolve_journal_path",
        lambda workspace_root=None: journal_path,
    )

    class _Bot:
        async def send_message(self, **_kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(message_id=7)

    n = TelegramNotifier(api_token="tok", chat_id="1")
    n.configure_workspace(tmp_path)
    n._get_bot = lambda: _Bot()  # type: ignore[method-assign]
    assert n.send_message("hello", kind="milestone") is True
    assert n.send_message("again", kind="milestone") is False
    rows = list_records(limit=20, path=journal_path)
    assert any(r.get("delivered") is True for r in rows)
    assert any(r.get("drop_reason") == "rate_limited" for r in rows)
