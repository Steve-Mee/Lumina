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
    LH03_ANSWERS_PATH,
    LH03_ANSWERS_SHA256,
    LH03_ATR_CLARIFICATION,
    LH03_ATR_SOURCE,
    LOCKED_HYPOTHESES,
    N_HYPOTHESES,
    PIN_MACRO_SHA256,
    PIN_NQ_SHA256,
    PIN_VIX_SHA256,
    RV02_LOW_POWER_ACCEPTED,
    RV02_POWER_N_TRADES,
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
    five_minute_atr14_before,
    kill_rule,
    missing_data_for,
    power_rows,
    previous_vix_close,
    relative_value_config_ids,
    resample_five_minute,
    runnable_config_ids,
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
    lh03_digest = hashlib.sha256(LH03_ANSWERS_PATH.read_bytes()).hexdigest()
    assert lh03_digest == LH03_ANSWERS_SHA256
    assert lh03_digest.startswith("0c549ee1")
    lh03_text = LH03_ANSWERS_PATH.read_text(encoding="utf-8")
    assert "5-minutenbars" in lh03_text
    assert "Hypothese blijft" in lh03_text
    payload = json.loads(DEFAULT_POWER_JSON.read_text(encoding="utf-8"))
    assert payload["trials_run"] is False
    assert payload["dsr_pbo_n"] == 0
    assert payload["n_hypotheses"] == 6
    assert payload["vix_filter_rule"] == "previous_day_close"
    assert payload["dropped_config_ids"] == ["p2s-lh-02", "p2s-lh-04"]
    assert payload["lh03_answers_sha256"] == LH03_ANSWERS_SHA256
    assert payload["lh03_atr"]["clarification_not_hypothesis_change"] is True
    assert payload["lh03_atr"]["source"] == LH03_ATR_SOURCE
    assert payload["rv02_low_power"]["n_trades"] == RV02_POWER_N_TRADES
    assert payload["rv02_low_power"]["low_power_risk_accepted"] is True


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
    assert runnable_config_ids() == ("p2s-rv-01", "p2s-rv-02", "p2s-lh-01", "p2s-lh-03")
    assert LH01_TARGET_RANGE_MULT == 1.5
    assert RV02_SIZING == "dollar_neutral"
    assert VIX_FILTER_RULE == "previous_day_close"
    assert LH03_ATR_CLARIFICATION is True
    assert LH03_ATR_SOURCE == "intraday_5m_atr14_strictly_before_event"
    assert RV02_LOW_POWER_ACCEPTED is True
    assert RV02_POWER_N_TRADES == 59
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


def _consecutive_minutes(
    day: date,
    hour: int,
    minute: int,
    n: int,
    *,
    open_: float,
    high: float,
    low: float,
    close: float,
) -> list[ResearchBar]:
    out: list[ResearchBar] = []
    cursor = datetime(day.year, day.month, day.day, hour, minute, tzinfo=ET)
    for _ in range(n):
        out.append(
            ResearchBar(
                ts_ns=int(cursor.timestamp() * 1_000_000_000),
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=1.0,
            )
        )
        cursor += timedelta(minutes=1)
    return out


@pytest.mark.unit
def test_macro_fade_uses_five_minute_atr_not_daily() -> None:
    event_day = date(2024, 1, 22)
    # 80 quiet 1m bars (7:10–8:29) → 16 five-minute TRs before 8:30.
    quiet = _consecutive_minutes(
        event_day, 7, 10, 80, open_=100.0, high=100.4, low=100.0, close=100.2
    )
    post = _bar(event_day, 8, 35, 102.0, 102.5, 101.5, 102.0)
    rth = _rth_day(event_day, open_=102.0, high=120.0, low=90.0, close=110.0)
    bars = [*quiet, post, *rth]
    event_ns = int(datetime(event_day.year, event_day.month, event_day.day, 8, 30, tzinfo=ET).timestamp() * 1_000_000_000)
    events = (MacroEvent(event="CPI", event_ns=event_ns, session=event_day),)
    five = resample_five_minute(quiet)
    atr = five_minute_atr14_before(five, event_ns)
    assert atr is not None
    assert atr < 1.0
    assert count_macro_fade(bars, events) == 1
    tiny_post = _bar(event_day, 8, 35, 100.3, 100.35, 100.25, 100.3)
    tiny_bars = [*quiet, tiny_post, *rth]
    assert count_macro_fade(tiny_bars, events) == 0


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
        by_row = {row["research_id"]: row for row in payload["hypotheses"]}
        assert by_row["RV-02"]["n_trades"] == RV02_POWER_N_TRADES == 59
        assert by_row["LH-03"]["n_trades"] == 62
        assert payload["lh03_atr"]["clarification_not_hypothesis_change"] is True
        assert payload["rv02_low_power"]["low_power_risk_accepted"] is True
        assert payload["lh03_power"]["n_trades"] == 62


@pytest.mark.unit
def test_final_cycle_specs_are_the_four_runnable_ids() -> None:
    from lumina_research.cycles.final_cycle_run import final_cycle_specs
    from lumina_research.proof.cli import build_parser

    specs = final_cycle_specs()
    assert tuple(item.config_id for item in specs) == runnable_config_ids()
    assert all(item.instrument == "ES" for item in specs)
    parser = build_parser()
    args = parser.parse_args(["research", "--cycle", "final-cycle"])
    assert args.cycle == "final-cycle"


@pytest.mark.unit
def test_team_kill_rejects_weak_oos_or_nonpositive_net() -> None:
    from lumina_research.cycles.data import DataStatus
    from lumina_research.cycles.final_cycle_run import apply_team_kill
    from lumina_research.cycles.geometry import require_geometry
    from lumina_research.cycles.report import CycleReport, CycleRow

    geometry = require_geometry(root="ES", target_ticks=1, stop_ticks=1)
    data = DataStatus(usable=True, tapes=(), searched=(), missing=(), required={})

    def _row(*, passed: bool, dsr: float, pct: float, net: float) -> CycleRow:
        return CycleRow(
            hypothesis_id="h1",
            config_id="p2s-rv-02",
            template_id="overnight_gap",
            family="es_nq_rel_gap",
            instrument="ES",
            pre_registered=True,
            tested=True,
            passed=passed,
            reject_reasons=(),
            pbo=0.1,
            dsr=dsr,
            wfe=0.5,
            n_oos_windows=8,
            median_oos=0.01,
            geometry=geometry,
            death_reason="survived",
            n_trades=59,
            net_pnl=net,
            pct_positive_oos=pct,
        )

    def _report(row: CycleRow) -> CycleReport:
        return CycleReport(
            n_hypotheses=1,
            n_tested=1,
            n_killed=0,
            n_survivors=1,
            kill_rate=0.0,
            kill_rate_flag="ok",
            cost_bands=(),
            data=data,
            rows=(row,),
            geometry_by_root=(geometry,),
            stopped=False,
            stop_reason="",
        )

    keep = apply_team_kill(_report(_row(passed=True, dsr=0.99, pct=0.875, net=0.01)))
    assert keep.n_survivors == 1
    weak_oos = apply_team_kill(_report(_row(passed=True, dsr=0.99, pct=0.625, net=0.01)))
    assert weak_oos.n_survivors == 0
    assert "team_kill_oos" in weak_oos.rows[0].reject_reasons
    weak_net = apply_team_kill(_report(_row(passed=True, dsr=0.99, pct=1.0, net=-0.01)))
    assert weak_net.n_survivors == 0
    assert "team_kill_net" in weak_net.rows[0].reject_reasons
    nan_oos = apply_team_kill(_report(_row(passed=True, dsr=0.99, pct=float("nan"), net=0.01)))
    assert nan_oos.n_survivors == 0
    assert "team_kill_oos" in nan_oos.rows[0].reject_reasons


@pytest.mark.unit
def test_lh01_signals_fire_on_nr7_break() -> None:
    from lumina_research.cycles.final_cycle_sim import _lh01_signals
    from lumina_research.cycles.prepare import prepare_tape

    nr7_days = _weekdays(date(2024, 1, 2), 8)
    bars: list[ResearchBar] = []
    for index, day in enumerate(nr7_days):
        if index == 6:
            bars.extend(_rth_day(day, open_=100.0, high=101.0, low=100.0, close=100.5))
        elif index == 7:
            bars.extend(_rth_day(day, open_=101.0, high=103.0, low=100.5, close=102.0))
        else:
            bars.extend(_rth_day(day, open_=100.0, high=110.0, low=100.0, close=105.0))
    prepared = prepare_tape("ES", bars)
    signals, atr = _lh01_signals(prepared)
    signal_i = next(index for index, item in enumerate(signals) if item != 0.0)
    assert sum(1 for item in signals if item != 0.0) == 1
    assert atr[signal_i] > 0.0
    if signal_i + 1 < len(atr):
        assert atr[signal_i + 1] > 0.0


@pytest.mark.unit
def test_lh03_signals_write_atr_onto_fill_bar() -> None:
    from lumina_research.cycles.final_cycle_sim import _lh03_signals
    from lumina_research.cycles.prepare import prepare_tape

    event_day = date(2024, 1, 22)
    quiet = _consecutive_minutes(
        event_day, 7, 10, 80, open_=100.0, high=100.4, low=100.0, close=100.2
    )
    post = _bar(event_day, 8, 35, 102.0, 102.5, 101.5, 102.0)
    fill = _bar(event_day, 8, 36, 102.0, 102.2, 101.8, 101.9)
    rth = _rth_day(event_day, open_=102.0, high=120.0, low=90.0, close=110.0)
    prepared = prepare_tape("ES", [*quiet, post, fill, *rth])
    event_ns = int(
        datetime(event_day.year, event_day.month, event_day.day, 8, 30, tzinfo=ET).timestamp()
        * 1_000_000_000
    )
    events = (MacroEvent(event="CPI", event_ns=event_ns, session=event_day),)
    signals, atr = _lh03_signals(prepared, events)
    signal_i = next(index for index, item in enumerate(signals) if item != 0.0)
    assert signals[signal_i] == -1.0
    assert atr[signal_i] > 0.0
    assert atr[signal_i + 1] > 0.0
