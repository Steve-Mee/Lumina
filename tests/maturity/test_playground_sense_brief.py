"""The Eerste stappen brief must tell the operator what she is doing and waiting for."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lumina_core.maturity.playground.sense_brief import build_sense_brief


def _write_sense(root: Path, closes: list[dict[str, object]], **extra: object) -> None:
    state = root / "state"
    state.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "playground_sense_v1",
        "closes": closes,
        "open": [],
        "resolved": [],
        "decision_bars": 3,
        "flat_bars": 3,
        "last_action0": 0.15,
        "pass_now": False,
    }
    payload.update(extra)
    (state / "lumina_playground_sense.json").write_text(json.dumps(payload), encoding="utf-8")
    (state / "lumina_sim_envelope_sealed.json").write_text(
        json.dumps({"sealed": True, "daily_loss_cap": -1000.0, "max_total_open_risk": 500.0}),
        encoding="utf-8",
    )


def _brief(root: Path, *, running: bool = True, now: datetime | None = None) -> dict[str, object]:
    return build_sense_brief(
        root,
        running=running,
        now=now or datetime(2026, 10, 2, 16, 10, tzinfo=timezone.utc),
    )


@pytest.mark.unit
def test_brief_does_not_wait_to_start_on_a_240_minute_candle(tmp_path: Path) -> None:
    _write_sense(
        tmp_path,
        [
            {"ts": "2026-10-02T16:08:00+00:00", "px": 100.0},
            {"ts": "2026-10-02T16:09:00+00:00", "px": 101.0},
        ],
    )
    brief = _brief(tmp_path)
    text = " ".join(str(line) for line in brief["lines"])
    assert "niet nodig om te beginnen" in text or "Geen 240-minutenkaars nodig" in text
    assert "kiest plat" in text
    assert brief["pass_now"] is False
    assert "Helling pas om" not in text
    assert "schaduw H1" not in text.lower()
    assert "first-touch" not in text.lower()
    assert " UTC" not in text


@pytest.mark.unit
def test_brief_names_a_multi_minute_gap(tmp_path: Path) -> None:
    _write_sense(
        tmp_path,
        [
            {"ts": "2026-10-02T16:26:06+00:00", "px": 100.0},
            {"ts": "2026-10-02T16:33:09+00:00", "px": 101.0},
        ],
    )
    text = " ".join(str(line) for line in _brief(tmp_path)["lines"])
    assert "Gat van 7 minuten" in text
    assert "geen minuut binnen" in text
    assert "Chicago" in text


@pytest.mark.unit
def test_equal_closes_are_a_still_print_not_a_candle_wait(tmp_path: Path) -> None:
    closes = []
    for minute in range(12):
        hour_min = 16 * 60 + minute
        closes.append(
            {
                "ts": f"2026-10-02T{hour_min // 60:02d}:{hour_min % 60:02d}:00+00:00",
                "px": 100.0,
            }
        )
    _write_sense(tmp_path, closes)
    text = " ".join(str(line) for line in _brief(tmp_path)["lines"])
    assert "stil" in text
    assert "beweegt niet" in text
    assert "Helling pas om" not in text


@pytest.mark.unit
def test_open_shadow_is_not_described_as_an_order(tmp_path: Path) -> None:
    _write_sense(
        tmp_path,
        [{"ts": "2026-10-02T16:08:00+00:00", "px": 7775.0}],
        open=[
            {
                "name": "null_b",
                "leg": 1,
                "side": 1,
                "entry": 7775.0,
                "entry_i": 0,
                "stop_pct": 0.01,
                "target_pct": 0.02,
                "hold": 120,
            }
        ],
    )
    text = " ".join(str(line) for line in _brief(tmp_path)["lines"])
    assert "Stop of doel" not in text
    assert "staat open vanaf" not in text
    assert "Schaduw first-touch" not in text


@pytest.mark.unit
def test_stopped_clock_does_not_claim_a_stall(tmp_path: Path) -> None:
    _write_sense(
        tmp_path,
        [{"ts": "2026-10-02T15:00:00+00:00", "px": 7775.0}],
    )
    brief = _brief(
        tmp_path,
        running=False,
        now=datetime(2026, 10, 2, 16, 10, tzinfo=timezone.utc),
    )
    text = " ".join(str(line) for line in brief["lines"])
    assert "staat stil" in text
    assert "Drie zulke vensters" not in text
    assert brief["tone"] == "idle"


@pytest.mark.unit
def test_occupancy_outside_band_is_named_as_her_choice(tmp_path: Path) -> None:
    _write_sense(
        tmp_path,
        [{"ts": "2026-10-02T16:09:00+00:00", "px": 7775.0}],
        decision_bars=125,
        flat_bars=125,
    )
    state = tmp_path / "state"
    (state / "lumina_playground_progress.json").write_text(
        json.dumps({"n_p": 0, "occupancy": 1.0, "chart_listing": "MES DEC26", "last_px": 7775.0}),
        encoding="utf-8",
    )
    brief = _brief(tmp_path)
    text = " ".join(str(line) for line in brief["lines"])
    assert "Occupancy 100% plat" in text
    assert "niet de schoolpoort" in text
    assert "25–75%" not in text
    assert brief["market"].startswith("MES DEC26")
    assert brief["headline"].startswith("Zij kiest plat")


@pytest.mark.unit
def test_bar_book_lock_is_an_operator_alert(tmp_path: Path) -> None:
    _write_sense(tmp_path, [{"ts": "2026-10-02T16:09:00+00:00", "px": 7775.0}])
    (tmp_path / "state" / "lumina_bar_integrity.json").write_text(
        json.dumps(
            {
                "complete": False,
                "lock_new_entries": True,
                "reason": "unexplained",
                "missing_count": 4,
                "message": "NT 1m book incomplete",
            }
        ),
        encoding="utf-8",
    )
    brief = _brief(tmp_path)
    text = " ".join(str(line) for line in brief["lines"])
    assert "Barboek onvolledig" in text
    assert "nieuwe entries staan dicht" in text
    assert "4 ontbrekende NT 1m-bars" in text
    assert brief["tone"] == "alert"


@pytest.mark.unit
def test_the_screen_names_the_sentence_she_is_scoring(tmp_path: Path) -> None:
    from lumina_core.maturity.playground.learning_book import append_name, record_archive_fact

    record_archive_fact(
        tmp_path,
        tape_count=10,
        minute_count=354874,
        holdout_start_ns=1,
        tail_end_ns=2,
        symbol="MES",
    )
    for name in ("b1-return", "b1440-volatility"):
        append_name(
            tmp_path,
            {
                "name": name,
                "status": "lab",
                "sentence": {"bar_minutes": 1 if name.startswith("b1") else 1440},
            },
        )
    _write_sense(
        tmp_path,
        [],
        decision_bars=0,
        flat_bars=0,
        audit_verdict="blind",
    )
    (tmp_path / "state" / "lumina_playground_crawl.json").write_text(
        json.dumps({"position_side": 0, "pending_unfilled": False, "total_bars": 1945}),
        encoding="utf-8",
    )
    brief = _brief(tmp_path)
    text = " ".join(str(line) for line in brief["lines"])
    assert str(brief["headline"]).startswith("Onderzoek b1-return")
    assert "b1440" not in str(brief["headline"])
    assert "eerste gesloten minuut" not in text
    assert "Ogen: blind" not in text
    assert "plant-vector is leeg" in text
    assert "354874" in str(brief["paper"])
    assert "NinjaTrader: plat" in str(brief["venue"])
    assert "papieren uitslagen zijn geen orders" in str(brief["paper"]).lower()


@pytest.mark.unit
def test_unsealed_envelope_is_the_operator_wait(tmp_path: Path) -> None:
    _write_sense(tmp_path, [{"ts": "2026-10-02T16:09:00+00:00", "px": 7775.0}])
    (tmp_path / "state" / "lumina_sim_envelope_sealed.json").unlink()
    brief = _brief(tmp_path)
    assert "dagvloer en SEAL" in str(brief["waiting"])
    assert brief["tone"] == "wait"
