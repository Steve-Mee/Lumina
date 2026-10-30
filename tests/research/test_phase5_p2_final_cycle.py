"""09:13 final-cycle search-space lock. No Validation Gate trials."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from lumina_core.market.globex_hours import ET
from lumina_research.cycles.data import ResearchBar
from lumina_research.cycles.final_cycle import (
    DEFAULT_POWER_JSON,
    FINALE_PREREG_PATH,
    FINALE_PREREG_SHA256,
    KILL_DSR_MIN,
    KILL_OOS_POSITIVE_MIN,
    KILL_OOS_WINDOWS,
    LH01_TARGET_RANGE_MULT,
    LOCKED_HYPOTHESES,
    N_HYPOTHESES,
    RV02_SIZING,
    SEARCH_SPACE_PREREG_PATH,
    STATUS_BLOCKED,
    DataAvailability,
    all_config_ids,
    check_data_availability,
    count_nr7_breakouts,
    count_weekend_mr,
    kill_rule,
    missing_data_for,
    power_rows,
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


@pytest.mark.unit
def test_finale_prereg_sha_is_frozen() -> None:
    digest = hashlib.sha256(FINALE_PREREG_PATH.read_bytes()).hexdigest()
    assert digest == FINALE_PREREG_SHA256
    assert digest.startswith("106af5b2")
    text = FINALE_PREREG_PATH.read_text(encoding="utf-8")
    assert "RV-01" in text
    assert "LH-04" in text
    assert "DSR>=0.95" in text
    assert "TODO" not in text
    payload = json.loads(DEFAULT_POWER_JSON.read_text(encoding="utf-8"))
    assert payload["trials_run"] is False
    assert payload["dsr_pbo_n"] == 0
    assert payload["n_hypotheses"] == 6


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
    assert LH01_TARGET_RANGE_MULT == 1.5
    assert RV02_SIZING == "dollar_neutral"
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
def test_missing_data_blocks_rv_macro_and_cash() -> None:
    avail = DataAvailability(
        es_pre_holdout=True,
        nq_pre_holdout=False,
        vix=False,
        macro_calendar=False,
        cash_index=False,
        es_path="/tmp/es.csv",
        nq_path=None,
        vix_path=None,
        macro_path=None,
        cash_path=None,
        es_sha256=None,
    )
    by_id = {item.research_id: item for item in LOCKED_HYPOTHESES}
    assert missing_data_for(by_id["RV-01"], avail) == ("nq_pre_holdout", "vix")
    assert "nq_pre_holdout" in missing_data_for(by_id["RV-01"], avail)
    assert "vix" in missing_data_for(by_id["RV-01"], avail)
    assert missing_data_for(by_id["RV-02"], avail) == ("nq_pre_holdout",)
    assert missing_data_for(by_id["LH-01"], avail) == ()
    assert missing_data_for(by_id["LH-03"], avail) == ("macro_calendar",)
    assert missing_data_for(by_id["LH-04"], avail) == ("cash_index",)


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
def test_power_rows_mark_blocked_without_counting() -> None:
    avail = DataAvailability(
        es_pre_holdout=False,
        nq_pre_holdout=False,
        vix=False,
        macro_calendar=False,
        cash_index=False,
        es_path=None,
        nq_path=None,
        vix_path=None,
        macro_path=None,
        cash_path=None,
        es_sha256=None,
    )
    rows = power_rows(avail, es_bars=None)
    assert all(row.status == STATUS_BLOCKED for row in rows)
    assert all(row.n_trades is None for row in rows)


@pytest.mark.unit
def test_live_availability_does_not_invent_missing_tapes() -> None:
    avail = check_data_availability()
    assert avail.nq_pre_holdout is False
    assert avail.vix is False
    assert avail.macro_calendar is False
    assert avail.cash_index is False
    if avail.es_pre_holdout:
        assert avail.es_path is not None
    by_id = {item.research_id: item for item in LOCKED_HYPOTHESES}
    assert "nq_pre_holdout" in missing_data_for(by_id["RV-01"], avail)
    assert missing_data_for(by_id["LH-03"], avail)
    assert missing_data_for(by_id["LH-04"], avail)
