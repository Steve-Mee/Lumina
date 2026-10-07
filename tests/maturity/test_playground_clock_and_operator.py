"""Playground clock windows, tape breakeven, seal numbers, Telegram verbs."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lumina_core.birth.birth_exit_policy_export import file_sha256
from lumina_core.maturity.continuum import mark_phase_running
from lumina_core.maturity.playground.crawl import observation_for_row
from lumina_core.maturity.playground.envelope import assess_envelope, envelope_sealed_for_pass
from lumina_core.maturity.playground.law import evaluate_playground_exit
from lumina_core.maturity.playground.progress import load_playground_progress
from lumina_core.maturity.playground.recovery import (
    ConclusiveState,
    StallState,
    active_fault,
    step_conclusive,
    step_stall,
)
from lumina_core.maturity.playground.select import load_policy_identities
from lumina_core.maturity.playground.tape import tape_breakeven_wr
from lumina_core.maturity.playground.telegram_commands import apply_playground_command
from lumina_core.notifications.phase_status_notify import notify_phase_status


def test_short_fault_does_not_open_a_window() -> None:
    state = StallState()
    state = step_stall(state, now=0, active="nt_down", unfilled_edge=False, frozen=False, window_sec=1800).state
    stepped = step_stall(state, now=10, active=None, unfilled_edge=False, frozen=False, window_sec=1800)
    assert stepped.state.windows == 0
    assert stepped.stop is False


def test_three_windows_then_a_healthy_window_clears() -> None:
    state = StallState()
    now = 0.0
    for _ in range(4):
        now += 1800
        step = step_stall(state, now=now, active="nt_down", unfilled_edge=False, frozen=False, window_sec=1800)
        state = step.state
    assert state.windows == 3
    assert step.stop is True
    cleared = step_stall(
        StallState(windows=1, healthy_since=None),
        now=0,
        active=None,
        unfilled_edge=False,
        frozen=False,
        window_sec=1800,
    ).state
    done = step_stall(cleared, now=1800, active=None, unfilled_edge=False, frozen=False, window_sec=1800)
    assert done.state.windows == 0
    assert done.event == "reset"


def test_occupancy_fault_waits_for_a_real_sample() -> None:
    assert active_fault(nt_health="up", occupancy=0.10, total_bars=10) is None
    assert active_fault(nt_health="unknown", occupancy=0.40, total_bars=5000) is None
    assert active_fault(nt_health="unknown", occupancy=0.10, total_bars=10) is None
    assert active_fault(nt_health="up", occupancy=0.10, total_bars=500) == "occupancy_crash"
    assert active_fault(nt_health="down", occupancy=0.40, total_bars=1) == "nt_down"


def test_hold_skips_one_window() -> None:
    state = StallState(fault="nt_down", fault_since=0, hold_fault="nt_down")
    step = step_stall(state, now=1800, active="nt_down", unfilled_edge=False, frozen=False, window_sec=1800)
    assert step.state.windows == 0
    assert step.state.hold_fault == ""
    again = step_stall(step.state, now=3600, active="nt_down", unfilled_edge=False, frozen=False, window_sec=1800)
    assert again.state.windows == 1


def test_conclusive_ask_then_expire_then_continue_is_not_a_pass() -> None:
    state, event = step_conclusive(
        ConclusiveState(),
        now=0,
        n_p=150,
        blockers=["mean_r=-0.1900 < 0"],
        window_sec=1800,
    )
    assert event == "ask"
    held, quiet = step_conclusive(state, now=10, n_p=160, blockers=["mean_r=-0.1900 < 0"], window_sec=1800)
    assert quiet == ""
    _expired, event = step_conclusive(held, now=1800, n_p=160, blockers=["mean_r=-0.1900 < 0"], window_sec=1800)
    assert event == "expire"
    extended = ConclusiveState(bracket=150, asked_at=0, continued_through=150)
    again, event = step_conclusive(
        extended, now=10, n_p=160, blockers=["mean_r=-0.1900 < 0"], window_sec=1800
    )
    assert event == ""
    assert again.continued_through == 150
    _next, event = step_conclusive(
        extended, now=20, n_p=300, blockers=["skill_wr=0.3700 < BE=0.4600"], window_sec=1800
    )
    assert event == "ask"


def test_child_sha_must_match_the_awakening_sidecar(tmp_path: Path) -> None:
    art = tmp_path / "reports" / "birth_cloud_run" / "artifacts"
    art.mkdir(parents=True)
    child = art / "awakening_live_pi_star.zip"
    birth = art / "birth_exit_pi_star.zip"
    child.write_bytes(b"awakening-child")
    birth.write_bytes(b"birth-plant")
    pinned = file_sha256(child)
    (art / "awakening_live_pi_star.json").write_text(
        json.dumps({"sha256": pinned}),
        encoding="utf-8",
    )
    ids = load_policy_identities(tmp_path)
    assert ids["child_sha"] == pinned
    assert ids["awakening_child_sha"] == pinned
    assert ids["child_sha"] != ids["birth_sha"]
    child.write_bytes(b"swapped")
    swapped = load_policy_identities(tmp_path)
    assert swapped["child_sha"] != swapped["awakening_child_sha"]
    assert swapped["child_missing"] is True


def test_breakeven_comes_from_the_tape_geometry(tmp_path: Path) -> None:
    from lumina_core.maturity.playground.fills import record_policy_close

    empty, source = tape_breakeven_wr(tmp_path)
    assert empty is None
    assert source == "no_closes"
    record_policy_close(
        tmp_path,
        order_id="SIM-1",
        entry_px=5000.0,
        exit_px=5100.0,
        stop_px=4900.0,
        target_px=5300.0,
        side=1,
        qty=1,
        instrument="MES",
        mode="sim",
        source="orderpath",
    )
    be, source = tape_breakeven_wr(tmp_path)
    assert source == "tape"
    assert be is not None
    assert 0.0 < be < 0.5


def test_seal_without_numbers_is_not_a_pass(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    (state / "lumina_sim_envelope_sealed.json").write_text(
        json.dumps({"sealed": True}),
        encoding="utf-8",
    )
    assert envelope_sealed_for_pass(tmp_path) is False


def test_stale_telemetry_blocks_while_bars_flow(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    (state / "lumina_sim_envelope_sealed.json").write_text(
        json.dumps({"sealed": True, "daily_loss_cap": -150.0, "max_total_open_risk": 3000.0}),
        encoding="utf-8",
    )
    old = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    (state / "lumina_playground_risk_telemetry.json").write_text(
        json.dumps({"daily_pnl": 0.0, "open_risk": 0.0, "ts": old}),
        encoding="utf-8",
    )
    fresh = datetime.now(timezone.utc).isoformat()
    (state / "lumina_playground_bars.jsonl").write_text(
        json.dumps({"price": 5000.0, "ts": fresh}) + "\n",
        encoding="utf-8",
    )
    assessed = assess_envelope(tmp_path, n_p=0, bars_flowing=True)
    assert assessed["telemetry"] == "stale"
    breached = assess_envelope(tmp_path, n_p=1, bars_flowing=False)
    assert breached["breached"] is False
    (state / "lumina_playground_risk_telemetry.json").write_text(
        json.dumps(
            {
                "daily_pnl": -200.0,
                "open_risk": 10.0,
                "ts": fresh,
            }
        ),
        encoding="utf-8",
    )
    hit = assess_envelope(tmp_path, n_p=1, bars_flowing=False)
    assert hit["breached"] is False
    assert hit["loss_floor_hit"] is True


def test_price_only_row_is_not_an_observation() -> None:
    vector, reason = observation_for_row(
        {"close": 5000.0, "last": 5000.0},
        engine=object(),
        data=[],
        idx=0,
        position=0,
        qty=0,
        entry_price=0.0,
    )
    assert vector is None
    assert reason == "trend_window_short"


def test_telegram_status_names_a_locked_bar_book(tmp_path: Path) -> None:
    mark_phase_running(tmp_path, "playground", learned={"status": "starting"}, telegram=False)
    (tmp_path / "config.yaml").write_text(
        "mode: sim\nsim:\n  daily_loss_cap: null\n  max_total_open_risk: 3000.0\n",
        encoding="utf-8",
    )
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "lumina_bar_integrity.json").write_text(
        json.dumps(
            {
                "complete": False,
                "lock_new_entries": True,
                "reason": "nt_unreachable",
                "missing_count": 2,
                "message": "NT unreachable",
            }
        ),
        encoding="utf-8",
    )
    status = apply_playground_command(tmp_path, "STATUS")
    assert status is not None
    reply = str(status["reply"])
    assert "Barboek onvolledig" in reply
    assert "nieuwe entries staan dicht" in reply


def test_telegram_verbs_do_not_pass_the_gate(tmp_path: Path) -> None:
    mark_phase_running(tmp_path, "playground", learned={"status": "starting"}, telegram=False)
    (tmp_path / "config.yaml").write_text(
        "mode: sim\nsim:\n  daily_loss_cap: null\n  max_total_open_risk: 3000.0\n",
        encoding="utf-8",
    )
    assert apply_playground_command(tmp_path, "HELLO") is None
    deck = apply_playground_command(tmp_path, "DECK")
    assert deck is not None
    assert load_playground_progress(tmp_path).get("deck_live") is True
    assert load_playground_progress(tmp_path).get("deck_live_source") == "telegram"
    cap = apply_playground_command(tmp_path, "CAP -150")
    assert cap is not None
    assert "daily_loss_cap: -150" in (tmp_path / "config.yaml").read_text(encoding="utf-8")
    refused = apply_playground_command(tmp_path, "SEAL nope")
    assert refused is not None
    assert "geweigerd" in str(refused["reply"])
    status = apply_playground_command(tmp_path, "STATUS")
    assert status is not None
    token = str(load_playground_progress(tmp_path).get("seal_token") or "")
    assert token
    sealed = apply_playground_command(tmp_path, f"SEAL {token}")
    assert sealed is not None
    assert envelope_sealed_for_pass(tmp_path) is True
    ok, _missing, learned = evaluate_playground_exit(tmp_path)
    assert ok is False
    assert learned.get("pass_now") is False


def test_progress_retries_when_the_send_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import MagicMock

    telegram = MagicMock()
    telegram.send_message.side_effect = [False, True]
    monkeypatch.setattr(
        "lumina_core.notifications.telegram_notifier.get_telegram_notifier",
        lambda: telegram,
    )
    kwargs = {
        "kind": "progress",
        "message": "Crawling",
        "learned": {"n_p": 4, "pass_now": False},
        "missing": ["n_P=4 < 150"],
    }
    assert notify_phase_status(tmp_path, "playground", **kwargs) is False
    assert notify_phase_status(tmp_path, "playground", **kwargs) is True
    assert telegram.send_message.call_count == 2


def test_autopilot_polls_faster_only_while_playground_runs(tmp_path: Path) -> None:
    from lumina_core.maturity.autopilot import autopilot_interval_sec

    assert autopilot_interval_sec(tmp_path) == 300.0
    mark_phase_running(tmp_path, "playground", learned={"status": "starting"}, telegram=False)
    assert autopilot_interval_sec(tmp_path) == 20.0


def test_liveness_buckets_do_not_collapse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import MagicMock

    telegram = MagicMock()
    telegram.send_message.return_value = True
    monkeypatch.setattr(
        "lumina_core.notifications.telegram_notifier.get_telegram_notifier",
        lambda: telegram,
    )
    first = {"n_p": 4, "pass_now": False, "liveness_bucket": "2026-09-25T10:00"}
    second = {"n_p": 4, "pass_now": False, "liveness_bucket": "2026-09-25T10:30"}
    assert notify_phase_status(tmp_path, "playground", kind="liveness", learned=first, message="leeft")
    assert notify_phase_status(tmp_path, "playground", kind="liveness", learned=second, message="leeft")
    assert telegram.send_message.call_count == 2
