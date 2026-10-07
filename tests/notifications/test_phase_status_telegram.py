"""Phase status Telegram: measured fields only, pass/fail matches the payload."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lumina_core.notifications.phase_status_notify import (
    forget_phase_status,
    notify_phase_handoff,
    notify_phase_status,
)
from lumina_core.notifications.phase_status_report import (
    fingerprint_phase_status,
    format_phase_status,
)
from lumina_core.notifications.telegram_gateway import DEFAULT_BYPASS_KINDS


def _notifier(sent: list[str]) -> MagicMock:
    telegram = MagicMock()

    def _send(message: str, **kwargs: object) -> bool:
        del kwargs
        sent.append(message)
        return True

    telegram.send_message.side_effect = _send
    return telegram


@pytest.mark.unit
def test_phase_status_bypasses_outbound_diary_cap() -> None:
    assert "phase_status" in DEFAULT_BYPASS_KINDS


@pytest.mark.unit
def test_progress_omits_absent_metrics_and_keeps_measured_values() -> None:
    title, body, kind = format_phase_status(
        "playground",
        kind="progress",
        message="Crawling · n_P 12/150",
        learned={"n_p": 12, "skill_wr": 0.412, "mean_r": None, "pass_now": False},
        missing=["n_P=12 < 150"],
    )
    assert kind == "progress"
    assert title == "Playground — tussenstand"
    assert "n_p: 12" in body
    assert "skill_wr: 0.412" in body
    assert "mean_r" not in body
    assert "sharpe" not in body
    assert "n_P=12 < 150" in body
    assert "pass_now: false" in body


@pytest.mark.unit
def test_pass_title_refused_when_proof_still_missing() -> None:
    title, body, kind = format_phase_status(
        "awakening",
        kind="passed",
        learned={"pass_now": False, "n_b": 40, "exit_proofs": ["birth_freeze_intact"]},
        missing=["n_B=40 < 500"],
    )
    assert kind == "failed"
    assert title == "Awakening gefaald"
    assert "n_B=40 < 500" in body
    assert "n_b: 40" in body
    assert "birth_freeze_intact" in body
    assert "Deels binnen" in body
    assert "Bewijs:" not in body


@pytest.mark.unit
def test_clean_pass_lists_proofs() -> None:
    title, body, kind = format_phase_status(
        "apprenticeship",
        kind="passed",
        learned={
            "pass_now": True,
            "n_d": 5,
            "sharpe": 0.22,
            "dd_pct": 4.5,
            "exit_proofs": ["five_green_days"],
            "blockers": [],
        },
    )
    assert kind == "passed"
    assert title == "Apprenticeship gehaald"
    assert "n_d: 5" in body
    assert "sharpe: 0.22" in body
    assert "dd_pct: 4.5" in body
    assert "Bewijs:" in body
    assert "five_green_days" in body
    assert "Ontbreekt:" not in body


@pytest.mark.unit
def test_playground_trade_count_buckets_do_not_spam() -> None:
    base = {
        "phase": "playground",
        "kind": "progress",
        "message": "Crawling · n_P 3/150",
        "learned": {"n_p": 3, "skill_wr": 0.411},
    }
    near = fingerprint_phase_status(
        "playground",
        kind="progress",
        message="Crawling · n_P 24/150",
        learned={"n_p": 24, "skill_wr": 0.414},
    )
    far = fingerprint_phase_status(
        "playground",
        kind="progress",
        message="Crawling · n_P 25/150",
        learned={"n_p": 25, "skill_wr": 0.414},
    )
    first = fingerprint_phase_status(**base)
    assert first == near
    assert first != far


@pytest.mark.unit
def test_awakening_cycle_messages_stay_distinct() -> None:
    first = fingerprint_phase_status(
        "awakening",
        kind="progress",
        message="Awakening cycle 1: holdout-meting",
        learned={"polish_oos_winrate": 0.41},
    )
    second = fingerprint_phase_status(
        "awakening",
        kind="progress",
        message="Awakening cycle 2: holdout-meting",
        learned={"polish_oos_winrate": 0.41},
    )
    assert first != second


@pytest.mark.unit
def test_notify_dedupes_identical_progress(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[str] = []
    monkeypatch.setattr(
        "lumina_core.notifications.telegram_notifier.get_telegram_notifier",
        lambda: _notifier(sent),
    )
    payload = {"n_p": 4, "skill_wr": 0.4, "pass_now": False}
    assert notify_phase_status(
        tmp_path,
        "playground",
        kind="progress",
        message="Crawling · n_P 4/150",
        learned=payload,
        missing=["n_P=4 < 150"],
    )
    assert notify_phase_status(
        tmp_path,
        "playground",
        kind="progress",
        message="Crawling · n_P 9/150",
        learned={"n_p": 9, "skill_wr": 0.401, "pass_now": False},
        missing=["n_P=9 < 150"],
    ) is False
    assert len(sent) == 1
    assert "skill_wr: 0.4" in sent[0]
    assert "LUMINA STATUS —" in sent[0]


@pytest.mark.unit
def test_failed_terminal_retries_when_undelivered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    telegram = MagicMock()
    telegram.send_message.side_effect = [False, True]
    monkeypatch.setattr(
        "lumina_core.notifications.telegram_notifier.get_telegram_notifier",
        lambda: telegram,
    )
    kwargs = {
        "kind": "failed",
        "error": "missing:n_B=1 < 500",
        "missing": ["n_B=1 < 500"],
        "learned": {"n_b": 1, "pass_now": False},
    }
    assert notify_phase_status(tmp_path, "awakening", **kwargs) is False
    assert notify_phase_status(tmp_path, "awakening", **kwargs) is True
    assert telegram.send_message.call_count == 2


@pytest.mark.unit
def test_birth_phase_status_is_not_this_channel(tmp_path: Path) -> None:
    assert notify_phase_status(tmp_path, "birth", kind="passed", learned={"n_b": 1}) is False


@pytest.mark.unit
def test_handoff_includes_birth_measurements_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[str] = []
    monkeypatch.setattr(
        "lumina_core.notifications.telegram_notifier.get_telegram_notifier",
        lambda: _notifier(sent),
    )
    assert notify_phase_handoff(
        tmp_path,
        completed="birth",
        nxt="awakening",
        learned={"cumulative_trades": 1200, "oos_winrate": 0.37},
    )
    assert len(sent) == 1
    text = sent[0]
    assert "Volgende fase: awakening" in text
    assert "cumulative_trades: 1200" in text
    assert "oos_winrate: 0.37" in text
    assert "sharpe" not in text
    assert "REAL start niet vanzelf" not in text


@pytest.mark.unit
def test_forget_allows_the_same_status_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[str] = []
    monkeypatch.setattr(
        "lumina_core.notifications.telegram_notifier.get_telegram_notifier",
        lambda: _notifier(sent),
    )
    assert notify_phase_status(tmp_path, "awakening", kind="started")
    assert notify_phase_status(tmp_path, "awakening", kind="started") is False
    forget_phase_status(tmp_path, ["awakening"])
    assert notify_phase_status(tmp_path, "awakening", kind="started")
    assert len(sent) == 2
    assert "Doel (fase-specificatie):" in sent[0]
