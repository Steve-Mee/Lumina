"""Pre-registered P2 existence tests (research team 11:06, NOT Steve).

Two tests, ES only, pre-holdout only, separate non-DSR book. This module
locks the spec and refuses the run. It does not count in DSR/PBO N, does
not reopen p2-next-search-space, and does not run a Validation Gate trial.
60/120-day trend is mechanism language only and is not implemented.
Index reconstitution and roll week are blocked until the team names a source.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Mapping, Sequence

from lumina_research.cycles.cost_bands import COMMISSION_USD_PER_SIDE, ES_ONE_WAY_USD
from lumina_research.cycles.nq_research import HOLDOUT_PIN_Z, PRE_HOLDOUT_WINDOW
from lumina_research.validation.cost_model import COST_MODEL_VERSION
from lumina_research.validation.thresholds import FLOOR_DSR_PROBABILITY_MIN

ANSWERS_NAME = "ONDERZOEKERS-ANTWOORDEN-BESTAANSTOETSEN-20261030T1106.md"
ANSWERS_SHA256 = "6b9dc2a894b1f10d37e6a96745377627682de7b758ee1a9cd2b70b127a5f8ab4"
BESTAANSTOETSEN_ANSWERS_SHA256 = ANSWERS_SHA256
PREREG_NAME = "phase5_p2_existence_preregister_2026-10-30.md"
BOOK_ID = "p2-existence-20261030"
BOOK_STATUS = "preregistered_not_run"
TEST_CALENDAR = "ex-01-calendar-rebalance"
TEST_OVERNIGHT = "ex-02-overnight-trend-20d"
TEST_IDS: tuple[str, ...] = (TEST_CALENDAR, TEST_OVERNIGHT)
NOT_IN_THIS_LOCK: tuple[str, ...] = ("ex-03-options-gamma",)
INSTRUMENT = "ES"
TRIALS_RUN = False
COUNTS_IN_DSR_N = False
ATR_ES_DEAD = True
LOOSER_THRESHOLD_ACCEPTED = False
NQ_TRADING = False
SIM_REQUESTED = False
PROMOTION_REQUESTED = False
OPTIMIZATION = False
HOLDOUT_OPENED = False
PIN_ES_SHA256 = "6100588d2f3e519bd815b8f952dc15f01d434cc2a2b70e6453d0c3a7477bbca6"
EVENT_MONTH_END = "month_end"
EVENT_QUARTER_END = "quarter_end"
EVENT_RECONSTITUTION = "index_reconstitution"
EVENT_ROLL_WEEK = "roll_week"
IMPLEMENTED_EVENT_KINDS: tuple[str, ...] = (EVENT_MONTH_END, EVENT_QUARTER_END)
BLOCKED_EVENT_KINDS: tuple[str, ...] = (EVENT_RECONSTITUTION, EVENT_ROLL_WEEK)
QUARTER_END_MONTHS: frozenset[int] = frozenset({3, 6, 9, 12})
TREND_LOOKBACK_LENGTH = 20
TREND_MECHANISM_LENGTHS: tuple[int, ...] = (20, 60, 120)
TREND_IMPLEMENTED_LENGTHS: tuple[int, ...] = (20,)
TEST2_COMBINED_OVERNIGHT_AND_20D = True
P_VALUE_THRESHOLD = 0.05
CHARTER_DSR_MIN = FLOOR_DSR_PROBABILITY_MIN
CHARTER_OOS_POSITIVE_MIN = 7
CHARTER_OOS_WINDOWS = 8
ES_COMMISSION_SIDE_USD = float(COMMISSION_USD_PER_SIDE["ES"])
ES_COMMISSION_ROUND_TRIP_USD = ES_COMMISSION_SIDE_USD * 2.0
ES_ONE_WAY_BAND_USD: tuple[float, float] = ES_ONE_WAY_USD
STATISTIC_CANDIDATES: tuple[str, ...] = ("two_sample_t_test", "bootstrap")
COST_CANDIDATES: tuple[str, ...] = (
    "es_commission_round_trip",
    "cost_model_1.2.0_four_leg",
    "es_one_way_band_usd",
)
AMBIGUITY_IDS: tuple[str, ...] = (
    "reconstitution_dates_source",
    "roll_week_definition",
    "cost_of_one_trade",
    "t_test_vs_bootstrap",
    "event_window_1_to_3_days_vs_close_to_close_rule",
    "event_after_close",
    "matched_control_definition",
    "test2_control_flat_vs_random",
    "trend_20d_unit",
    "trend_60_120_not_in_rule",
    "overnight_unfiltered_vs_trend_filtered",
    "p_value_one_vs_two_sided",
    "excess_return_units",
    "event_day_session_calendar_rth_vs_globex",
    "month_end_also_quarter_end_double_count",
)

EXISTENCE_RUN_REFUSED = (
    "existence tests are locked and not run; they are a separate book and "
    "do not count in DSR/PBO N; this CLI cycle refuses until the research "
    "team resolves the flagged ambiguities and explicitly GO-runs them"
)
AMBIGUITY_RECONSTITUTION = "index reconstitution dates source is unresolved; no calendar is locked"
AMBIGUITY_ROLL_WEEK = (
    "roll-week definition is unresolved; NT8_ROLL_DATES is the first Globex "
    "session of a new front month and is not a stand-in for roll week"
)
AMBIGUITY_COST_OF_ONE_TRADE = (
    "cost of one trade is unresolved; candidates are ES commission round-trip "
    f"${ES_COMMISSION_ROUND_TRIP_USD:.2f}, CostModel {COST_MODEL_VERSION} "
    "four-leg, and the ES one-way band "
    f"${ES_ONE_WAY_BAND_USD[0]:.2f}-${ES_ONE_WAY_BAND_USD[1]:.2f}"
)
AMBIGUITY_T_TEST_VS_BOOTSTRAP = "statistic is unresolved; the lock lists two-sample t-test or bootstrap"
AMBIGUITY_TREND_20D_UNIT = (
    "20-day lookback length is 20; the unit (RTH sessions vs calendar days vs Globex sessions) is unresolved"
)
AMBIGUITY_TREND_60_120 = "60/120-day trend is mechanism language only and is not in the locked rule"

_REPO = Path(__file__).resolve().parents[2]
ANSWERS_PATH = _REPO / "docs" / "research" / ANSWERS_NAME
PREREG_PATH = _REPO / "experiments" / "reports" / PREREG_NAME
SPEC_SHA256 = "5a3a54f429c768d2181a037ba99f029f47a6ffcc4d53cb79a7b16672deebec41"


class ExistenceRefused(RuntimeError):
    """Existence-test lock is missing, inconsistent, or the run is refused."""


@dataclass(frozen=True, slots=True)
class CalendarEvent:
    session: date
    kinds: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExistenceBookState:
    book_id: str
    status: str
    open: bool
    counts_in_dsr_n: bool
    trials_run: bool
    spec_sha256: str


def canonical_spec() -> dict[str, object]:
    """Frozen existence-test spec. JSON-serializable; hashed with sorted keys."""
    return {
        "answers_name": ANSWERS_NAME,
        "answers_sha256": ANSWERS_SHA256,
        "atr_es_retest": False,
        "book_id": BOOK_ID,
        "charter_kill": {
            "dsr_min": CHARTER_DSR_MIN,
            "net_positive": True,
            "oos_positive_min": CHARTER_OOS_POSITIVE_MIN,
            "oos_windows": CHARTER_OOS_WINDOWS,
        },
        "counts_in_dsr_n": False,
        "directions_evaluated": "separately_no_shared_book",
        "dropped": ["fx_commodities", "gp"],
        "holdout_opened": False,
        "holdout_pin": HOLDOUT_PIN_Z,
        "instrument": INSTRUMENT,
        "looser_threshold_accepted": False,
        "not_in_this_lock": list(NOT_IN_THIS_LOCK),
        "nq_promotion": False,
        "nq_trading": False,
        "optimization": False,
        "order_accepted": [
            "calendar_rebalancing",
            "multi_day_risk_premium",
            "options_dealer_gamma_after_data_costs",
        ],
        "passing_direction_opens": "new_dsr_book_n_0",
        "pin_es_sha256": PIN_ES_SHA256,
        "promotion_requested": False,
        "q2_stop_rule": "0_survivors_over_three_directions_full_charter",
        "sim_requested": False,
        "tape_window": PRE_HOLDOUT_WINDOW,
        "test_ids": list(TEST_IDS),
        "tests": {
            TEST_CALENDAR: {
                "controls": "matched_non_event_days_same_month",
                "data": PRE_HOLDOUT_WINDOW,
                "event_kinds_blocked": list(BLOCKED_EVENT_KINDS),
                "event_kinds_implemented": list(IMPLEMENTED_EVENT_KINDS),
                "id": TEST_CALENDAR,
                "instrument": INSTRUMENT,
                "kill": ("excess_not_positive_and_significant_p_lt_0.05_or_effect_size_lt_cost_of_one_trade"),
                "name": "calendar_rebalancing",
                "optimization": False,
                "p_value_threshold": P_VALUE_THRESHOLD,
                "rule": "long_close_before_event_to_close_event_or_next_if_after_close",
                "statistic": "two_sample_t_or_bootstrap_unresolved",
            },
            TEST_OVERNIGHT: {
                "combined_overnight_and_20d_filter": TEST2_COMBINED_OVERNIGHT_AND_20D,
                "controls": "flat_or_random_entry_unresolved",
                "data": PRE_HOLDOUT_WINDOW,
                "id": TEST_OVERNIGHT,
                "instrument": INSTRUMENT,
                "kill": "no_positive_excess_distinguishable_from_zero_after_costs",
                "name": "overnight_plus_20d_trend",
                "optimization": False,
                "p_value_threshold": P_VALUE_THRESHOLD,
                "rule_overnight": "long_rth_close_to_next_rth_open",
                "rule_trend": "long_if_previous_20_day_return_gt_0_hold_overnight",
                "statistic": "two_sample_t_or_bootstrap_unresolved",
                "trend_60_120_implemented": False,
                "trend_60_120_in_rule": False,
                "trend_lookback_length": TREND_LOOKBACK_LENGTH,
                "trend_lookback_unit": "unresolved",
                "trend_mechanism_lengths": list(TREND_MECHANISM_LENGTHS),
            },
        },
        "trials_run": False,
        "ambiguities": [_ambiguity_entry(item) for item in AMBIGUITY_IDS],
        "cost_of_one_trade": {
            "status": "unresolved",
            "candidates": [
                {
                    "id": "es_commission_round_trip",
                    "usd": ES_COMMISSION_ROUND_TRIP_USD,
                    "note": "ADR-0055 Free ES $2.87/side; not selected",
                },
                {
                    "id": "cost_model_1.2.0_four_leg",
                    "version": COST_MODEL_VERSION,
                    "note": "commission + half-spread + slippage + impact; not selected",
                },
                {
                    "id": "es_one_way_band_usd",
                    "max_usd": ES_ONE_WAY_BAND_USD[1],
                    "min_usd": ES_ONE_WAY_BAND_USD[0],
                    "note": "research band, not a single cost; not selected",
                },
            ],
        },
    }


def canonical_spec_bytes() -> bytes:
    return json.dumps(canonical_spec(), sort_keys=True, separators=(",", ":")).encode("utf-8")


def spec_sha256() -> str:
    return hashlib.sha256(canonical_spec_bytes()).hexdigest()


def existence_book_payload() -> dict[str, object]:
    return {
        "id": BOOK_ID,
        "status": BOOK_STATUS,
        "open": False,
        "counts_in_dsr_n": False,
        "trials_run": False,
        "instrument": INSTRUMENT,
        "tape_window": PRE_HOLDOUT_WINDOW,
        "holdout_opened": False,
        "holdout_pin": HOLDOUT_PIN_Z,
        "nq_trading": False,
        "sim_requested": False,
        "promotion_requested": False,
        "optimization": False,
        "atr_es_retest": False,
        "looser_threshold_accepted": False,
        "test_ids": list(TEST_IDS),
        "not_in_this_lock": list(NOT_IN_THIS_LOCK),
        "committed_path": f"experiments/reports/{PREREG_NAME}",
        "answers_name": ANSWERS_NAME,
        "answers_sha256": ANSWERS_SHA256,
        "spec_sha256": SPEC_SHA256,
        "ambiguity_ids": list(AMBIGUITY_IDS),
    }


def existence_book_from_mapping(raw: Mapping[str, object]) -> ExistenceBookState:
    book_id = _as_str(raw.get("id"), field="existence_book.id")
    if book_id != BOOK_ID:
        raise ExistenceRefused(f"existence_book.id must be {BOOK_ID}")
    if raw.get("status") != BOOK_STATUS:
        raise ExistenceRefused("existence_book.status must be preregistered_not_run")
    if raw.get("open") is not False:
        raise ExistenceRefused("existence_book must not be open")
    if raw.get("counts_in_dsr_n") is not False:
        raise ExistenceRefused("existence tests must not count in DSR N")
    if raw.get("trials_run") is not False:
        raise ExistenceRefused("existence tests must not be marked run")
    if raw.get("instrument") != INSTRUMENT:
        raise ExistenceRefused("existence tests are ES only")
    if raw.get("tape_window") != PRE_HOLDOUT_WINDOW:
        raise ExistenceRefused("existence tests are pre-holdout only")
    if raw.get("holdout_opened") is not False:
        raise ExistenceRefused("existence book must not open holdout")
    if raw.get("nq_trading") is not False:
        raise ExistenceRefused("existence tests must not trade NQ")
    if raw.get("sim_requested") is not False:
        raise ExistenceRefused("existence tests must not request SIM")
    if raw.get("promotion_requested") is not False:
        raise ExistenceRefused("existence tests must not request promotion")
    if raw.get("optimization") is not False:
        raise ExistenceRefused("existence tests must not optimize")
    if raw.get("atr_es_retest") is not False:
        raise ExistenceRefused("atr-es configs are dead and must not be retested")
    if raw.get("looser_threshold_accepted") is not False:
        raise ExistenceRefused("looser DSR/OOS threshold is not accepted")
    if raw.get("test_ids") != list(TEST_IDS):
        raise ExistenceRefused("existence_book.test_ids mismatch")
    if raw.get("not_in_this_lock") != list(NOT_IN_THIS_LOCK):
        raise ExistenceRefused("existence_book.not_in_this_lock mismatch")
    if raw.get("answers_sha256") != ANSWERS_SHA256:
        raise ExistenceRefused("existence_book answers sha mismatch")
    if raw.get("spec_sha256") != SPEC_SHA256:
        raise ExistenceRefused("existence_book spec sha mismatch")
    path_value = _as_str(raw.get("committed_path"), field="existence_book.committed_path")
    committed = Path(path_value)
    if not committed.is_absolute():
        committed = _REPO / committed
    if not committed.is_file():
        raise ExistenceRefused("existence prereg file is missing")
    return ExistenceBookState(
        book_id=BOOK_ID,
        status=BOOK_STATUS,
        open=False,
        counts_in_dsr_n=False,
        trials_run=False,
        spec_sha256=SPEC_SHA256,
    )


def assert_existence_lock() -> None:
    if not ANSWERS_PATH.is_file():
        raise ExistenceRefused(f"existence answers missing: {ANSWERS_PATH}")
    digest = hashlib.sha256(ANSWERS_PATH.read_bytes()).hexdigest()
    if digest != ANSWERS_SHA256:
        raise ExistenceRefused(f"existence answers sha mismatch: {digest}")
    if spec_sha256() != SPEC_SHA256:
        raise ExistenceRefused(f"existence spec sha mismatch: {spec_sha256()}")
    if TRIALS_RUN is not False or COUNTS_IN_DSR_N is not False:
        raise ExistenceRefused("existence lock must stay unrun and out of DSR N")
    if TREND_IMPLEMENTED_LENGTHS != (TREND_LOOKBACK_LENGTH,):
        raise ExistenceRefused("only the 20-day lookback length is in the locked rule")
    if 60 in TREND_IMPLEMENTED_LENGTHS or 120 in TREND_IMPLEMENTED_LENGTHS:
        raise ExistenceRefused(AMBIGUITY_TREND_60_120)
    if not PREREG_PATH.is_file():
        raise ExistenceRefused(f"existence prereg missing: {PREREG_PATH}")


def run_existence_tests(**_kwargs: object) -> None:
    """Refuse. The 11:06 lock does not authorize a run."""
    raise ExistenceRefused(EXISTENCE_RUN_REFUSED)


def calendar_rebalance_events(sessions: Sequence[date]) -> tuple[CalendarEvent, ...]:
    """Month-end and quarter-end only. Reconstitution and roll week stay blocked.

    The sequence must be the complete session calendar used for the test. A hole
    that skips the rest of a month would look like month-end; that is a data
    defect, not a chosen holiday calendar.
    """
    if not sessions:
        return ()
    ordered = tuple(sessions)
    previous: date | None = None
    for session in ordered:
        if previous is not None and session <= previous:
            raise ExistenceRefused("session dates must be strictly increasing")
        previous = session
    events: list[CalendarEvent] = []
    for index, session in enumerate(ordered):
        nxt = ordered[index + 1] if index + 1 < len(ordered) else None
        if not _is_calendar_month_end(session, nxt):
            continue
        kinds: list[str] = [EVENT_MONTH_END]
        if session.month in QUARTER_END_MONTHS:
            kinds.append(EVENT_QUARTER_END)
        events.append(CalendarEvent(session=session, kinds=tuple(kinds)))
    return tuple(events)


def require_implemented_event_kind(kind: str) -> None:
    if kind in BLOCKED_EVENT_KINDS:
        if kind == EVENT_RECONSTITUTION:
            raise ExistenceRefused(AMBIGUITY_RECONSTITUTION)
        raise ExistenceRefused(AMBIGUITY_ROLL_WEEK)
    if kind not in IMPLEMENTED_EVENT_KINDS:
        raise ExistenceRefused(f"unknown calendar event kind {kind}")


def reconstitution_dates() -> tuple[date, ...]:
    raise ExistenceRefused(AMBIGUITY_RECONSTITUTION)


def roll_week_sessions() -> tuple[date, ...]:
    raise ExistenceRefused(AMBIGUITY_ROLL_WEEK)


def cost_of_one_trade_usd() -> float:
    raise ExistenceRefused(AMBIGUITY_COST_OF_ONE_TRADE)


def excess_return_statistic() -> str:
    raise ExistenceRefused(AMBIGUITY_T_TEST_VS_BOOTSTRAP)


def trend_lookback_unit() -> str:
    raise ExistenceRefused(AMBIGUITY_TREND_20D_UNIT)


def trend_lookback_length() -> int:
    return TREND_LOOKBACK_LENGTH


def _is_calendar_month_end(session: date, next_session: date | None) -> bool:
    if next_session is not None:
        return (next_session.year, next_session.month) != (session.year, session.month)
    return (session + timedelta(days=1)).month != session.month


def _ambiguity_entry(item: str) -> dict[str, str]:
    notes = {
        "reconstitution_dates_source": AMBIGUITY_RECONSTITUTION,
        "roll_week_definition": AMBIGUITY_ROLL_WEEK,
        "cost_of_one_trade": AMBIGUITY_COST_OF_ONE_TRADE,
        "t_test_vs_bootstrap": AMBIGUITY_T_TEST_VS_BOOTSTRAP,
        "event_window_1_to_3_days_vs_close_to_close_rule": (
            "expected language is 1-3 trading days around the event; the locked "
            "rule is close of day before to close of event day (or next day if "
            "event after close). This lock implements the rule, not a 1-3 day window"
        ),
        "event_after_close": (
            "when an event is 'after close' is unresolved; month-end/quarter-end "
            "are calendar session dates and use previous-close to event-close"
        ),
        "matched_control_definition": (
            "matched non-event days in the same month is unspecified (which days, how many, with/without replacement)"
        ),
        "test2_control_flat_vs_random": ("Test 2 controls are listed as flat or random-entry; neither is chosen"),
        "trend_20d_unit": AMBIGUITY_TREND_20D_UNIT,
        "trend_60_120_not_in_rule": AMBIGUITY_TREND_60_120,
        "overnight_unfiltered_vs_trend_filtered": (
            "the expected sentence lists overnight return and 20/60/120d trend as "
            "two effects; this lock implements overnight plus the 20-day filter "
            "as one combined rule and does not run an unfiltered overnight book"
        ),
        "p_value_one_vs_two_sided": "p<0.05 is locked; one-sided vs two-sided is not",
        "excess_return_units": ("excess return units (points, percent, net after which cost) are unresolved"),
        "event_day_session_calendar_rth_vs_globex": (
            "Test 1 says close of day; whether that day is an RTH session or a "
            "Globex session is unresolved. Month-end identification takes a "
            "session-date sequence and does not choose the calendar"
        ),
        "month_end_also_quarter_end_double_count": (
            "a quarter-end session is also a month-end; whether that day is one "
            "event or two is unresolved. Identification tags both kinds on one day"
        ),
    }
    return {"id": item, "status": "unresolved", "note": notes[item]}


def _as_str(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExistenceRefused(f"{field} must be a non-empty string")
    return value
