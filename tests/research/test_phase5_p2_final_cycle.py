"""09:13 final-cycle search-space lock plus 09:36 data pins. No Validation Gate trials."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from lumina_core.market.globex_hours import ET
from lumina_research.cycles.data import ResearchBar
from lumina_research.cycles.final_cycle import (
    DATA_ANSWERS_PATH,
    DATA_ANSWERS_SHA256,
    DEFAULT_POWER_JSON,
    FINALE_PREREG_PATH,
    FINALE_PREREG_SHA256,
    KILL_DSR_MIN,
    KILL_OOS_POSITIVE_MIN,
    KILL_OOS_WINDOWS,
    LH01_TARGET_RANGE_MULT,
    LOCKED_HYPOTHESES,
    N_HYPOTHESES,
    PIN_MACRO_SHA256,
    PIN_NQ_SHA256,
    PIN_VIX_SHA256,
    RV02_SIZING,
    SEARCH_SPACE_PREREG_PATH,
    STATUS_BLOCKED,
    STATUS_DROPPED,
    STATUS_READY,
    VIX_FILTER_RULE,
    DataAvailability,
    MacroEvent,
    all_config_ids,
    check_data_availability,
    count_macro_fade,
    count_nr7_breakouts,
    count_ratio_mr,
    count_relative_gap_fade,
    count_weekend_mr,
    dropped_config_ids,
    kill_rule,
    missing_data_for,
    power_rows,
    previous_vix_close,
    relative_value_config_ids,
    search_space_mapping,
)
from lumina_research.cycles.nq_research import KIND_RELATIVE_VALUE
from lumina_research.cycles.search_space import (
    NEW_BOOK_HYPOTHESIS_CAP,
    assert_search_space_prereg_opens_book,
    search_space_prereg_from_mapping,
)
from lumina_research.cycles.trial_ledger import assert_ledger_allows_run, load_trial_ledger


def _bar(day: date, hour_et: int, minute_et: int, open_: float, high: float, low: float, close: float) -> ResearchBar:
    moment = datetime(day.year, day.month, day.day, hour_et, minute_et, tzinfo=ET)
    return ResearchBar(
        ts_ns=int(moment.timestamp() * 1_000_000_000),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=1.0,
    )


def _rth_day(day: date, *, open_: float, high: float, low: float, close: float) -> tuple[ResearchBar, ...]:
    return (
        _bar(day, 9, 31, open_, high, low, open_),
        _bar(day, 16, 0, close, high, low, close),
    )


def _weekdays(start: date, n: int) -> list[date]:
    out: list[date] = []
    cursor = start
    while len(out) < n:
        if cursor.weekday() < 5:
            out.append(cursor)
        cursor += timedelta(days=1)
    return out


def _empty_avail(**overrides: object) -> DataAvailability:
    payload: dict[str, object] = {
        "es_pre_holdout": False,
        "nq_pre_holdout": False,
        "vix": False,
        "macro_calendar": False,
        "cash_index": False,
        "es_path": None,
        "nq_path": None,
        "vix_path": None,
        "macro_path": None,
        "cash_path": None,
        "es_sha256": None,
    }
    payload.update(overrides)
    return DataAvailability(**payload)  # type: ignore[arg-type]


@pytest.mark.unit
def test_finale_prereg_and_data_answers_sha_are_frozen() -> None:
    digest = hashlib.sha256(FINALE_PREREG_PATH.read_bytes()).hexdigest()
    assert digest == FINALE_PREREG_SHA256
    assert digest.startswith("971bd2ef")
    text = FINALE_PREREG_PATH.read_text(encoding="utf-8")
    assert "RV-01" in text
    assert "LH-04" in text
    assert "DSR>=0.95" in text
    assert "TODO" not in text
    data_digest = hashlib.sha256(DATA_ANSWERS_PATH.read_bytes()).hexdigest()
    assert data_digest == DATA_ANSWERS_SHA256
    assert data_digest.startswith("e37cd59e")
    data_text = DATA_ANSWERS_PATH.read_text(encoding="utf-8")
    assert "LH-04" in data_text
    assert "LH-02" in data_text
    payload = json.loads(DEFAULT_POWER_JSON.read_text(encoding="utf-8"))
    assert payload["trials_run"] is False
    assert payload["dsr_pbo_n"] == 0
    assert payload["n_hypotheses"] == 6
    assert payload["vix_filter_rule"] == "previous_day_close"
    assert payload["dropped_config_ids"] == ["p2s-lh-02", "p2s-lh-04"]


@pytest.mark.unit
def test_six_hypotheses_one_cycle_cap_and_kill_rule() -> None:
    assert N_HYPOTHESES == 6
    assert len(LOCKED_HYPOTHESES) == 6
    assert N_HYPOTHESES <= NEW_BOOK_HYPOTHESIS_CAP
    assert relative_value_config_ids() == ("p2s-rv-01", "p2s-rv-02")
    assert all_config_ids() == (
        "p2s-rv-01",
        "p2s-rv-02",
        "p2s-lh-01",
        "p2s-lh-02",
        "p2s-lh-03",
        "p2s-lh-04",
    )
    assert dropped_config_ids() == ("p2s-lh-02", "p2s-lh-04")
    assert LH01_TARGET_RANGE_MULT == 1.5
    assert RV02_SIZING == "dollar_neutral"
    assert VIX_FILTER_RULE == "previous_day_close"
    rule = kill_rule()
    assert rule["dsr_min"] == KILL_DSR_MIN == 0.95
    assert rule["oos_positive_min"] == KILL_OOS_POSITIVE_MIN == 7
    assert rule["oos_windows"] == KILL_OOS_WINDOWS == 8
    assert rule["net_positive"] is True


@pytest.mark.unit
def test_search_space_mapping_opens_the_new_book() -> None:
    parsed = search_space_prereg_from_mapping(search_space_mapping(), repo_root=Path("."))
    assert_search_space_prereg_opens_book(parsed)
    assert parsed.n_hypotheses == 6
    assert parsed.committed_path.resolve() == SEARCH_SPACE_PREREG_PATH.resolve()
    assert parsed.nq_request.hypothesis_kind == KIND_RELATIVE_VALUE


@pytest.mark.unit
def test_canonical_ledger_is_open_at_n_zero_with_six_stated() -> None:
    ledger = load_trial_ledger()
    assert ledger.active_open is True
    assert ledger.n_hypotheses_stated == 6
    assert ledger.dsr_pbo_n == 0
    assert ledger.n_cycles_completed == 0
    allowed = assert_ledger_allows_run()
    assert allowed.active_book_id == "p2-next-search-space"


@pytest.mark.unit
def test_missing_data_blocks_rv_and_macro_not_dropped() -> None:
    avail = _empty_avail(es_pre_holdout=True, es_path="/tmp/es.csv")
    by_id = {item.research_id: item for item in LOCKED_HYPOTHESES}
    assert missing_data_for(by_id["RV-01"], avail) == ("nq_pre_holdout", "vix")
    assert missing_data_for(by_id["RV-02"], avail) == ("nq_pre_holdout",)
    assert missing_data_for(by_id["LH-01"], avail) == ()
    assert missing_data_for(by_id["LH-03"], avail) == ("macro_calendar",)
    assert missing_data_for(by_id["LH-04"], avail) == ("cash_index",)
    assert by_id["LH-02"].dropped is True
    assert by_id["LH-04"].dropped is True


@pytest.mark.unit
def test_nr7_and_weekend_power_counts_on_synthetic_rth() -> None:
    nr7_days = _weekdays(date(2024, 1, 2), 8)
    nr7_bars: list[ResearchBar] = []
    for index, day in enumerate(nr7_days):
        if index == 6:
            nr7_bars.extend(_rth_day(day, open_=100.0, high=101.0, low=100.0, close=100.5))
        elif index == 7:
            nr7_bars.extend(_rth_day(day, open_=101.0, high=103.0, low=100.5, close=102.0))
        else:
            nr7_bars.extend(_rth_day(day, open_=100.0, high=110.0, low=100.0, close=105.0))
    assert count_nr7_breakouts(nr7_bars) == 1

    week_days = _weekdays(date(2023, 12, 4), 16)
    week_bars: list[ResearchBar] = []
    for index, day in enumerate(week_days):
        if index == 14:
            week_bars.extend(_rth_day(day, open_=100.0, high=140.0, low=100.0, close=140.0))
        else:
            week_bars.extend(_rth_day(day, open_=100.0, high=101.0, low=100.0, close=100.5))
    assert week_days[14].weekday() == 4
    assert week_days[15].weekday() == 0
    assert count_weekend_mr(week_bars) == 1


@pytest.mark.unit
def test_ratio_mr_uses_previous_day_vix_not_same_day() -> None:
    days = _weekdays(date(2024, 1, 2), 21)
    es_bars: list[ResearchBar] = []
    nq_bars: list[ResearchBar] = []
    for index, day in enumerate(days):
        es_close = 100.0 + (index % 2) * 0.5
        nq_close = 100.0
        if index == 20:
            es_close = 130.0
        es_bars.extend(_rth_day(day, open_=100.0, high=es_close, low=99.0, close=es_close))
        nq_bars.extend(_rth_day(day, open_=100.0, high=101.0, low=99.0, close=nq_close))
    last = days[20]
    vix = (
        (last - timedelta(days=1), 20.0),
        (last, 40.0),
    )
    assert previous_vix_close(vix, last) == 20.0
    assert count_ratio_mr(es_bars, nq_bars, vix) == 1
    blocked = ((last - timedelta(days=1), 30.0), (last, 10.0))
    assert count_ratio_mr(es_bars, nq_bars, blocked) == 0


@pytest.mark.unit
def test_relative_gap_fade_counts_abs_gap_over_threshold() -> None:
    days = _weekdays(date(2024, 1, 2), 2)
    es = [
        *_rth_day(days[0], open_=100.0, high=101.0, low=99.0, close=100.0),
        *_rth_day(days[1], open_=101.0, high=102.0, low=100.0, close=101.0),
    ]
    nq = [
        *_rth_day(days[0], open_=200.0, high=201.0, low=199.0, close=200.0),
        *_rth_day(days[1], open_=200.0, high=201.0, low=199.0, close=200.0),
    ]
    assert count_relative_gap_fade(es, nq) == 1
    nq_matched = [
        *_rth_day(days[0], open_=200.0, high=201.0, low=199.0, close=200.0),
        *_rth_day(days[1], open_=202.0, high=203.0, low=201.0, close=202.0),
    ]
    assert count_relative_gap_fade(es, nq_matched) == 0


@pytest.mark.unit
def test_macro_fade_counts_five_minute_spike_vs_atr() -> None:
    days = _weekdays(date(2024, 1, 2), 15)
    bars: list[ResearchBar] = []
    for day in days[:-1]:
        bars.extend(_rth_day(day, open_=100.0, high=101.0, low=100.0, close=100.5))
    event_day = days[-1]
    bars.append(_bar(event_day, 8, 29, 100.0, 100.2, 99.8, 100.0))
    bars.append(_bar(event_day, 8, 35, 102.0, 102.5, 101.5, 102.0))
    bars.extend(_rth_day(event_day, open_=102.0, high=103.0, low=101.0, close=102.0))
    event_ns = int(datetime(event_day.year, event_day.month, event_day.day, 8, 30, tzinfo=ET).timestamp() * 1_000_000_000)
    events = (MacroEvent(event="CPI", event_ns=event_ns, session=event_day),)
    assert count_macro_fade(bars, events) == 1
    tiny = (MacroEvent(event="CPI", event_ns=event_ns, session=event_day),)
    bars_tiny: list[ResearchBar] = []
    for day in days[:-1]:
        bars_tiny.extend(_rth_day(day, open_=100.0, high=101.0, low=100.0, close=100.5))
    bars_tiny.append(_bar(event_day, 8, 29, 100.0, 100.2, 99.8, 100.0))
    bars_tiny.append(_bar(event_day, 8, 35, 100.5, 100.6, 100.4, 100.5))
    bars_tiny.extend(_rth_day(event_day, open_=100.5, high=101.0, low=100.0, close=100.5))
    assert count_macro_fade(bars_tiny, tiny) == 0


@pytest.mark.unit
def test_power_rows_mark_dropped_even_without_tapes() -> None:
    avail = _empty_avail()
    rows = power_rows(avail, es_bars=None)
    by_id = {row.research_id: row for row in rows}
    assert by_id["LH-02"].status == STATUS_DROPPED
    assert by_id["LH-04"].status == STATUS_DROPPED
    assert by_id["LH-02"].n_trades is None
    assert by_id["RV-01"].status == STATUS_BLOCKED
    assert by_id["RV-02"].status == STATUS_BLOCKED
    assert by_id["LH-01"].status == STATUS_BLOCKED
    assert by_id["LH-03"].status == STATUS_BLOCKED
    assert all(row.n_trades is None for row in rows)


@pytest.mark.unit
def test_live_availability_pins_when_present() -> None:
    avail = check_data_availability()
    assert avail.cash_index is False
    if avail.nq_pre_holdout:
        assert avail.nq_sha256 == PIN_NQ_SHA256
    if avail.vix:
        assert avail.vix_sha256 == PIN_VIX_SHA256
    if avail.macro_calendar:
        assert avail.macro_sha256 == PIN_MACRO_SHA256
    by_id = {item.research_id: item for item in LOCKED_HYPOTHESES}
    if not avail.nq_pre_holdout:
        assert "nq_pre_holdout" in missing_data_for(by_id["RV-01"], avail)
    if not avail.macro_calendar:
        assert missing_data_for(by_id["LH-03"], avail)


@pytest.mark.unit
def test_committed_power_json_keeps_n_six_and_no_trials() -> None:
    payload = json.loads(DEFAULT_POWER_JSON.read_text(encoding="utf-8"))
    statuses = {row["research_id"]: row["status"] for row in payload["hypotheses"]}
    assert statuses["LH-02"] == STATUS_DROPPED
    assert statuses["LH-04"] == STATUS_DROPPED
    assert payload["trials_run"] is False
    assert len(payload["hypotheses"]) == 6
    if payload["data"]["nq_pre_holdout"] and payload["data"]["vix"] and payload["data"]["macro_calendar"]:
        assert statuses["RV-01"] == STATUS_READY
        assert statuses["RV-02"] == STATUS_READY
        assert statuses["LH-01"] == STATUS_READY
        assert statuses["LH-03"] == STATUS_READY
        assert isinstance(payload["hypotheses"][0]["n_trades"], int)
