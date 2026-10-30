"""Locked 09:13 final-cycle search space for book p2-next-search-space.

Six pre-registered hypotheses. LH-02 and LH-04 are dropped but still count
in n_hypotheses=6. VIX<25 uses the previous day's close (no lookahead).

LH-03 1.2× ATR14 is the pre-registered parameter. The 10:00 answers clarify
that ATR(14) is the SMA of the last 14 true ranges on 5-minute bars whose
close is strictly before the release (no lookahead) — not daily ATR14.
That is a clarification, not a hypothesis change.

RV-02 power is 59 trades. The research team accepts the low-power risk and
still runs the trial.
"""

from __future__ import annotations

import bisect
import csv
import hashlib
import json
import math
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from lumina_core.market.globex_hours import ET, globex_session_date
from lumina_research.cycles.data import ResearchBar, read_csv_bars
from lumina_research.cycles.holdout import P2_HOLDOUT_START_NS, assert_no_holdout_timestamps
from lumina_research.cycles.nq_research import HOLDOUT_PIN_Z, KIND_RELATIVE_VALUE
from lumina_research.cycles.null_model import NULL_BUILDER
from lumina_research.cycles.search_space import NEW_BOOK_HYPOTHESIS_CAP
from lumina_research.cycles.sessions import annotate
from lumina_research.validation.thresholds import FLOOR_DSR_PROBABILITY_MIN

FINALE_PREREG_NAME = "ONDERZOEKERS-PREREG-FINALE-CYCLUS-20261030T0913.md"
FINALE_PREREG_SHA256 = "971bd2ef3ca798fdd0df976349420efd9915bf6f74734d5c1f6b50de51db743e"
DATA_ANSWERS_NAME = "ONDERZOEKERS-ANTWOORDEN-DATA-20261030T0936.md"
DATA_ANSWERS_SHA256 = "e37cd59ead7db0779c2c8a61be0f59bce4a1e6b37281433480e9d6652741c8fb"
LH03_ANSWERS_NAME = "ONDERZOEKERS-ANTWOORDEN-LH03-20261030T1000.md"
LH03_ANSWERS_SHA256 = "0c549ee1a1ba901f1bc6620b2ace5b0c0b5e6736d869b863a33e10a931320c4f"
SEARCH_SPACE_PREREG_NAME = "phase5_p2_search_space_preregister_2026-10-30.md"
N_HYPOTHESES = 6
LH01_TARGET_RANGE_MULT = 1.5
RV02_SIZING = "dollar_neutral"
RV02_ES_MULTIPLIER = 50.0
RV02_NQ_MULTIPLIER = 20.0
RV01_Z_ENTRY = 2.5
RV01_Z_EXIT = 0.5
RV01_Z_STOP = 4.0
RV01_LOOKBACK_SESSIONS = 20
RV01_MAX_HOLD_NS = 6 * 3600 * 1_000_000_000
RV02_REL_GAP_PCT = 0.4
RV02_POWER_N_TRADES = 59
RV02_LOW_POWER_ACCEPTED = True
RV02_LOW_POWER_NOTE = (
    "RV-02 power is 59 trades. The research team accepts the low-power risk "
    "and still runs the trial. This is not a parameter change."
)
LH03_ATR_MULT = 1.2
LH03_ATR_LEN = 14
LH03_LAG_NS = 5 * 60 * 1_000_000_000
LH03_FIVE_MIN_NS = 5 * 60 * 1_000_000_000
LH03_ATR_SOURCE = "intraday_5m_atr14_strictly_before_event"
LH03_ATR_CLARIFICATION = True
LH03_ATR_NOTE = (
    "The 1.2× ATR14 threshold uses INTRADAY ATR(14) on 5-minute bars "
    "(SMA of the last 14 true ranges from bars whose close is strictly "
    "before the release, no lookahead), NOT daily ATR14. Clarification of "
    "the pre-registered parameter, not a change to the hypothesis."
)
VIX_FILTER_MAX = 25.0
VIX_FILTER_RULE = "previous_day_close"
KILL_DSR_MIN = FLOOR_DSR_PROBABILITY_MIN
KILL_OOS_POSITIVE_MIN = 7
KILL_OOS_WINDOWS = 8
STATUS_READY = "ready"
STATUS_BLOCKED = "blocked_missing_data"
STATUS_DROPPED = "dropped"
DATA_ES = "es_pre_holdout"
DATA_NQ = "nq_pre_holdout"
DATA_VIX = "vix"
DATA_MACRO = "macro_calendar"
DATA_CASH = "cash_index"
PIN_ES_SHA256 = "6100588d2f3e519bd815b8f952dc15f01d434cc2a2b70e6453d0c3a7477bbca6"
PIN_NQ_SHA256 = "d60dd0c203ef31382def4278f4524a671bc7b4a050ab1334948ba693e269eed8"
PIN_NQ_GZ_SHA256 = "4f5f7d4ef94e5dbecf3afea5021ad6d693eb7050ade439dd74d076d114e5c855"
PIN_VIX_SHA256 = "481dc031c6d2b51b9150718c21c01b7f3706c99678ebf12b0edba19d0c8d2d1d"
PIN_MACRO_SHA256 = "104018d21552544a6c60ef52de0bbb6c82447c6afcb685e3059a14edd1c19aa7"
MACRO_EVENT_NAMES: frozenset[str] = frozenset({"CPI", "NFP", "FOMC_STATEMENT"})

_REPO = Path(__file__).resolve().parents[2]
FINALE_PREREG_PATH = _REPO / "docs" / "research" / FINALE_PREREG_NAME
DATA_ANSWERS_PATH = _REPO / "docs" / "research" / DATA_ANSWERS_NAME
LH03_ANSWERS_PATH = _REPO / "docs" / "research" / LH03_ANSWERS_NAME
SEARCH_SPACE_PREREG_PATH = _REPO / "experiments" / "reports" / SEARCH_SPACE_PREREG_NAME
DEFAULT_POWER_JSON = _REPO / "experiments" / "reports" / "phase5_p2_final_cycle_data_power.json"
DEFAULT_POWER_MD = _REPO / "experiments" / "reports" / "phase5_p2_final_cycle_data_power.md"

ES_TAPE_SEARCHED: tuple[str, ...] = (
    "/tmp/lumina-es/ES_pre_holdout.csv",
    "$LUMINA_RESEARCH_DATA_DIR/ES/1m/*.csv",
    "data/research/ES/1m/*.csv",
)
NQ_TAPE_SEARCHED: tuple[str, ...] = (
    "/tmp/lumina-nq/NQ_pre_holdout.csv",
    "$LUMINA_RESEARCH_DATA_DIR/NQ/1m/*.csv",
    "data/research/NQ/1m/*.csv",
)
VIX_SEARCHED: tuple[str, ...] = (
    "/tmp/lumina-vix/VIX_daily_pre_holdout.csv",
    "/tmp/lumina-vix/vix.csv",
    "$LUMINA_RESEARCH_DATA_DIR/VIX/1d/vix.csv",
    "data/research/VIX/1d/vix.csv",
)
MACRO_SEARCHED: tuple[str, ...] = (
    "/tmp/lumina-macro/macro_events_pre_holdout.csv",
    "/tmp/lumina-macro/releases.csv",
    "$LUMINA_RESEARCH_DATA_DIR/macro/releases.csv",
    "data/research/macro/releases.csv",
)
CASH_SEARCHED: tuple[str, ...] = (
    "$LUMINA_RESEARCH_DATA_DIR/SPX/1d/spx.csv",
    "data/research/SPX/1d/spx.csv",
    "/tmp/lumina-cash/spx.csv",
)


class DataPinRefused(RuntimeError):
    """A pre-holdout file exists but does not match the locked sha256 pin."""


@dataclass(frozen=True, slots=True)
class FinalHypothesis:
    research_id: str
    config_id: str
    kind: str
    instruments: tuple[str, ...]
    required_data: tuple[str, ...]
    entry: str
    exit_stop: str
    dropped: bool = False
    dropped_reason: str = ""


@dataclass(frozen=True, slots=True)
class DataAvailability:
    es_pre_holdout: bool
    nq_pre_holdout: bool
    vix: bool
    macro_calendar: bool
    cash_index: bool
    es_path: str | None
    nq_path: str | None
    vix_path: str | None
    macro_path: str | None
    cash_path: str | None
    es_sha256: str | None
    nq_sha256: str | None = None
    vix_sha256: str | None = None
    macro_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class PowerRow:
    research_id: str
    config_id: str
    status: str
    n_trades: int | None
    missing: tuple[str, ...]
    dropped_reason: str = ""


@dataclass(frozen=True, slots=True)
class MacroEvent:
    event: str
    event_ns: int
    session: date


@dataclass(frozen=True, slots=True)
class MacroFadePower:
    n_events: int
    n_with_post_bar: int
    n_short_atr: int
    n_trades: int


LOCKED_HYPOTHESES: tuple[FinalHypothesis, ...] = (
    FinalHypothesis(
        research_id="RV-01",
        config_id="p2s-rv-01",
        kind=KIND_RELATIVE_VALUE,
        instruments=("ES", "NQ"),
        required_data=(DATA_ES, DATA_NQ, DATA_VIX),
        entry="RTH ES/NQ close-ratio |z|>2.5 lookback 20 sessions; previous-day VIX<25",
        exit_stop="exit |z|<0.5 or 6h; stop |z|>=4.0",
    ),
    FinalHypothesis(
        research_id="RV-02",
        config_id="p2s-rv-02",
        kind=KIND_RELATIVE_VALUE,
        instruments=("ES", "NQ"),
        required_data=(DATA_ES, DATA_NQ),
        entry="RTH open |ES%−NQ% overnight gap|>0.4%; dollar-neutral fade",
        exit_stop="exit 50% fill or 90min; stop 1.5x relative gap",
    ),
    FinalHypothesis(
        research_id="LH-01",
        config_id="p2s-lh-01",
        kind="longer_horizon",
        instruments=("ES",),
        required_data=(DATA_ES,),
        entry="RTH break of prior NR7 day high/low",
        exit_stop="target 1.5x NR7 range; stop opposite NR7 side; EOD flatten",
    ),
    FinalHypothesis(
        research_id="LH-02",
        config_id="p2s-lh-02",
        kind="longer_horizon",
        instruments=("ES",),
        required_data=(DATA_ES,),
        entry="Monday RTH open fade if Friday |OC|>1.5x ATR14",
        exit_stop="exit 40% retrace or 2h; stop 1.0x Friday RTH range",
        dropped=True,
        dropped_reason="power n_trades=5",
    ),
    FinalHypothesis(
        research_id="LH-03",
        config_id="p2s-lh-03",
        kind="longer_horizon",
        instruments=("ES",),
        required_data=(DATA_ES, DATA_MACRO),
        entry="+5min after CPI/NFP/FOMC if |move|>1.2x ATR14; fade spike",
        exit_stop="exit 50% retrace or 90min; stop 1.5x spike",
    ),
    FinalHypothesis(
        research_id="LH-04",
        config_id="p2s-lh-04",
        kind="longer_horizon",
        instruments=("ES",),
        required_data=(DATA_ES, DATA_CASH),
        entry="cash-futures basis z>2.0 fade to mean",
        exit_stop="exit z->0; stop |z|>=3.5",
        dropped=True,
        dropped_reason="no free 1-minute SPX cash data",
    ),
)


def relative_value_config_ids() -> tuple[str, ...]:
    return tuple(item.config_id for item in LOCKED_HYPOTHESES if item.kind == KIND_RELATIVE_VALUE)


def all_config_ids() -> tuple[str, ...]:
    return tuple(item.config_id for item in LOCKED_HYPOTHESES)


def dropped_config_ids() -> tuple[str, ...]:
    return tuple(item.config_id for item in LOCKED_HYPOTHESES if item.dropped)


def runnable_config_ids() -> tuple[str, ...]:
    return tuple(item.config_id for item in LOCKED_HYPOTHESES if not item.dropped)


def rv02_low_power() -> Mapping[str, object]:
    return {
        "config_id": "p2s-rv-02",
        "n_trades": RV02_POWER_N_TRADES,
        "low_power_risk_accepted": RV02_LOW_POWER_ACCEPTED,
        "note": RV02_LOW_POWER_NOTE,
    }


def lh03_atr_lock() -> Mapping[str, object]:
    return {
        "source": LH03_ATR_SOURCE,
        "length": LH03_ATR_LEN,
        "multiple": LH03_ATR_MULT,
        "clarification_not_hypothesis_change": LH03_ATR_CLARIFICATION,
        "note": LH03_ATR_NOTE,
    }


def kill_rule() -> Mapping[str, object]:
    return {
        "dsr_min": KILL_DSR_MIN,
        "oos_positive_min": KILL_OOS_POSITIVE_MIN,
        "oos_windows": KILL_OOS_WINDOWS,
        "net_positive": True,
        "text": "DSR>=0.95 AND >=7/8 OOS+ AND net>0",
    }


def data_pins() -> Mapping[str, object]:
    return {
        "holdout_pin": HOLDOUT_PIN_Z,
        "es_pre_holdout_sha256": PIN_ES_SHA256,
        "nq_pre_holdout_sha256": PIN_NQ_SHA256,
        "nq_gz_sha256": PIN_NQ_GZ_SHA256,
        "vix_sha256": PIN_VIX_SHA256,
        "macro_sha256": PIN_MACRO_SHA256,
        "vix_filter_rule": VIX_FILTER_RULE,
        "cash_index": None,
        "lh03_atr_source": LH03_ATR_SOURCE,
        "lh03_atr_clarification_not_hypothesis_change": LH03_ATR_CLARIFICATION,
    }


def _expand(path: str) -> Path:
    env = os.environ.get("LUMINA_RESEARCH_DATA_DIR", "").rstrip("/")
    if path.startswith("$LUMINA_RESEARCH_DATA_DIR"):
        if not env:
            return Path("/__unset__") / path
        return Path(path.replace("$LUMINA_RESEARCH_DATA_DIR", env, 1))
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return _REPO / candidate


def _first_existing(patterns: Sequence[str]) -> Path | None:
    for raw in patterns:
        expanded = _expand(raw)
        if "*" in expanded.name:
            parent = expanded.parent
            if parent.is_dir():
                matches = sorted(parent.glob(expanded.name))
                if matches:
                    return matches[0]
            continue
        if expanded.is_file():
            return expanded
    return None


def _pinned(path: Path | None, expected: str, label: str) -> tuple[str | None, str | None]:
    if path is None:
        return None, None
    digest = _sha256(path)
    if digest != expected:
        raise DataPinRefused(f"{label} pin mismatch: got {digest}, expected {expected}")
    return str(path), digest


def check_data_availability() -> DataAvailability:
    es_path, es_sha = _pinned(_first_existing(ES_TAPE_SEARCHED), PIN_ES_SHA256, "ES")
    nq_path, nq_sha = _pinned(_first_existing(NQ_TAPE_SEARCHED), PIN_NQ_SHA256, "NQ")
    vix_path, vix_sha = _pinned(_first_existing(VIX_SEARCHED), PIN_VIX_SHA256, "VIX")
    macro_path, macro_sha = _pinned(_first_existing(MACRO_SEARCHED), PIN_MACRO_SHA256, "macro")
    cash_path = _first_existing(CASH_SEARCHED)
    return DataAvailability(
        es_pre_holdout=es_path is not None,
        nq_pre_holdout=nq_path is not None,
        vix=vix_path is not None,
        macro_calendar=macro_path is not None,
        cash_index=cash_path is not None,
        es_path=es_path,
        nq_path=nq_path,
        vix_path=vix_path,
        macro_path=macro_path,
        cash_path=None if cash_path is None else str(cash_path),
        es_sha256=es_sha,
        nq_sha256=nq_sha,
        vix_sha256=vix_sha,
        macro_sha256=macro_sha,
    )


def missing_data_for(hyp: FinalHypothesis, avail: DataAvailability) -> tuple[str, ...]:
    flags = {
        DATA_ES: avail.es_pre_holdout,
        DATA_NQ: avail.nq_pre_holdout,
        DATA_VIX: avail.vix,
        DATA_MACRO: avail.macro_calendar,
        DATA_CASH: avail.cash_index,
    }
    return tuple(item for item in hyp.required_data if not flags[item])


def count_nr7_breakouts(bars: Sequence[ResearchBar]) -> int:
    sessions = _rth_sessions(bars)
    if len(sessions) < 8:
        return 0
    n_trades = 0
    for index in range(7, len(sessions)):
        prior = sessions[index - 7 : index]
        nr7 = prior[-1]
        nr7_range = nr7.high - nr7.low
        if nr7_range > min(item.high - item.low for item in prior) + 1e-12:
            continue
        day = sessions[index]
        if day.high > nr7.high or day.low < nr7.low:
            n_trades += 1
    return n_trades


def count_weekend_mr(bars: Sequence[ResearchBar]) -> int:
    sessions = _rth_sessions(bars)
    if len(sessions) < 16:
        return 0
    ranges = [item.high - item.low for item in sessions]
    n_trades = 0
    for index, day in enumerate(sessions):
        if day.session.weekday() != 0 or index < 1:
            continue
        friday = sessions[index - 1]
        if friday.session.weekday() != 4:
            continue
        prior = ranges[max(0, index - 14) : index]
        atr = (sum(prior) / float(len(prior))) if prior else 0.0
        friday_move = abs(friday.close - friday.open)
        if atr > 0.0 and friday_move > 1.5 * atr:
            n_trades += 1
    return n_trades


def count_ratio_mr(
    es_bars: Sequence[ResearchBar],
    nq_bars: Sequence[ResearchBar],
    vix: Sequence[tuple[date, float]],
) -> int:
    """RV-01 entries: |z|>2.5 vs 20 prior session-close ratios, previous-day VIX<25.

    Both tails. One position at a time. Same-bar re-entry is refused.
    """
    nq_close = {item.ts_ns: item.close for item in nq_bars}
    es_sessions = _rth_sessions(es_bars)
    nq_sessions = _rth_sessions(nq_bars)
    es_close = {item.session: item.close for item in es_sessions}
    nq_sess_close = {item.session: item.close for item in nq_sessions}
    common = sorted(set(es_close) & set(nq_sess_close))
    ratios = [es_close[day] / nq_sess_close[day] for day in common]
    stats_by_day: dict[date, tuple[float, float]] = {}
    for index, day in enumerate(common):
        if index < RV01_LOOKBACK_SESSIONS:
            continue
        fitted = _mean_std(ratios[index - RV01_LOOKBACK_SESSIONS : index])
        if fitted is not None:
            stats_by_day[day] = fitted
    labels = annotate(es_bars)
    in_trade = False
    exit_ns = 0
    n_trades = 0
    for bar, session, is_rth in zip(es_bars, labels.session_dates, labels.rth, strict=True):
        if not is_rth:
            continue
        nq_px = nq_close.get(bar.ts_ns)
        if nq_px is None or nq_px == 0.0:
            continue
        fitted = stats_by_day.get(session)
        if fitted is None:
            continue
        mean, std = fitted
        z_score = (bar.close / nq_px - mean) / std
        abs_z = abs(z_score)
        if in_trade:
            if bar.ts_ns >= exit_ns or abs_z < RV01_Z_EXIT or abs_z >= RV01_Z_STOP:
                in_trade = False
            continue
        vix_prev = previous_vix_close(vix, session)
        if vix_prev is None or vix_prev >= VIX_FILTER_MAX:
            continue
        if abs_z > RV01_Z_ENTRY:
            n_trades += 1
            in_trade = True
            exit_ns = bar.ts_ns + RV01_MAX_HOLD_NS
    return n_trades


def count_relative_gap_fade(
    es_bars: Sequence[ResearchBar],
    nq_bars: Sequence[ResearchBar],
) -> int:
    """RV-02 entries: |ES overnight % − NQ overnight %| > 0.4 at RTH open."""
    es_sessions = _rth_sessions(es_bars)
    nq_sessions = {item.session: item for item in _rth_sessions(nq_bars)}
    n_trades = 0
    previous: _RthSession | None = None
    for day in es_sessions:
        nq_day = nq_sessions.get(day.session)
        if nq_day is None:
            continue
        if previous is not None:
            nq_prev = nq_sessions[previous.session]
            if previous.close > 0.0 and nq_prev.close > 0.0:
                es_gap = (day.open / previous.close - 1.0) * 100.0
                nq_gap = (nq_day.open / nq_prev.close - 1.0) * 100.0
                if abs(es_gap - nq_gap) > RV02_REL_GAP_PCT:
                    n_trades += 1
        previous = day
    return n_trades


def resample_five_minute(bars: Sequence[ResearchBar]) -> tuple[ResearchBar, ...]:
    """Clock-aligned 5-minute OHLC. Close timestamp is the last 1m bar in the bucket."""
    if not bars:
        return ()
    grouped: list[ResearchBar] = []
    bucket = bars[0].ts_ns // LH03_FIVE_MIN_NS
    open_px = bars[0].open
    high_px = bars[0].high
    low_px = bars[0].low
    close_px = bars[0].close
    volume = bars[0].volume
    last_ts = bars[0].ts_ns
    for bar in bars[1:]:
        current = bar.ts_ns // LH03_FIVE_MIN_NS
        if current != bucket:
            grouped.append(
                ResearchBar(
                    ts_ns=last_ts,
                    open=open_px,
                    high=high_px,
                    low=low_px,
                    close=close_px,
                    volume=volume,
                )
            )
            bucket = current
            open_px = bar.open
            high_px = bar.high
            low_px = bar.low
            close_px = bar.close
            volume = bar.volume
        else:
            high_px = max(high_px, bar.high)
            low_px = min(low_px, bar.low)
            close_px = bar.close
            volume += bar.volume
        last_ts = bar.ts_ns
    grouped.append(
        ResearchBar(
            ts_ns=last_ts,
            open=open_px,
            high=high_px,
            low=low_px,
            close=close_px,
            volume=volume,
        )
    )
    return tuple(grouped)


def five_minute_atr14_before(five_min: Sequence[ResearchBar], event_ns: int) -> float | None:
    """SMA of the last 14 true ranges on 5m bars with close strictly before event_ns."""
    if not five_min:
        return None
    stamps = [item.ts_ns for item in five_min]
    end = bisect.bisect_left(stamps, event_ns)
    start = end - (LH03_ATR_LEN + 1)
    if start < 0:
        return None
    window = five_min[start:end]
    if len(window) < LH03_ATR_LEN + 1:
        return None
    total = 0.0
    for index in range(1, len(window)):
        prev_close = window[index - 1].close
        bar = window[index]
        true_range = max(bar.high - bar.low, abs(bar.high - prev_close), abs(bar.low - prev_close))
        total += true_range
    atr = total / float(LH03_ATR_LEN)
    if atr <= 0.0:
        return None
    return atr


def macro_fade_power(es_bars: Sequence[ResearchBar], events: Sequence[MacroEvent]) -> MacroFadePower:
    """LH-03 entries vs 5-minute ATR(14) strictly before the release."""
    five_min = resample_five_minute(es_bars)
    ts_list = [item.ts_ns for item in es_bars]
    by_ts = {item.ts_ns: item for item in es_bars}
    n_with_post = 0
    n_short_atr = 0
    n_trades = 0
    for event in events:
        post = by_ts.get(event.event_ns + LH03_LAG_NS)
        if post is None:
            continue
        n_with_post += 1
        pre_index = bisect.bisect_left(ts_list, event.event_ns) - 1
        if pre_index < 0:
            continue
        pre = es_bars[pre_index]
        atr = five_minute_atr14_before(five_min, event.event_ns)
        if atr is None:
            n_short_atr += 1
            continue
        if abs(post.close - pre.close) > LH03_ATR_MULT * atr:
            n_trades += 1
    return MacroFadePower(
        n_events=len(events),
        n_with_post_bar=n_with_post,
        n_short_atr=n_short_atr,
        n_trades=n_trades,
    )


def count_macro_fade(es_bars: Sequence[ResearchBar], events: Sequence[MacroEvent]) -> int:
    """LH-03 entries: |close(+5min) − last close before event| > 1.2 × 5m ATR14."""
    return macro_fade_power(es_bars, events).n_trades


def previous_vix_close(vix: Sequence[tuple[date, float]], session: date) -> float | None:
    """Last VIX daily close with date strictly before the RTH session date."""
    if not vix:
        return None
    dates = [item[0] for item in vix]
    index = bisect.bisect_left(dates, session) - 1
    if index < 0:
        return None
    return vix[index][1]


def load_vix(path: Path) -> tuple[tuple[date, float], ...]:
    rows: list[tuple[date, float]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            raw_date = row.get("date")
            raw_close = row.get("close")
            if not raw_date or raw_close is None:
                continue
            day = date.fromisoformat(raw_date)
            close = float(raw_close)
            rows.append((day, close))
    rows.sort(key=lambda item: item[0])
    last = rows[-1][0] if rows else None
    if last is not None and last >= date(2026, 1, 29):
        raise DataPinRefused("VIX series reaches the holdout")
    return tuple(rows)


def load_macro_events(path: Path) -> tuple[MacroEvent, ...]:
    events: list[MacroEvent] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            name = str(row.get("event", "")).strip()
            if name not in MACRO_EVENT_NAMES:
                continue
            raw_date = str(row.get("date", "")).strip()
            raw_time = str(row.get("time_et", "")).strip()
            hour_s, minute_s = raw_time.split(":", 1)
            local = datetime(
                int(raw_date[0:4]),
                int(raw_date[5:7]),
                int(raw_date[8:10]),
                int(hour_s),
                int(minute_s),
                tzinfo=ET,
            )
            event_ns = int(local.astimezone(timezone.utc).timestamp() * 1_000_000_000)
            if event_ns >= P2_HOLDOUT_START_NS:
                raise DataPinRefused("macro event on or after the holdout pin")
            events.append(
                MacroEvent(
                    event=name,
                    event_ns=event_ns,
                    session=globex_session_date(local),
                )
            )
    return tuple(events)


def power_rows(
    avail: DataAvailability,
    *,
    es_bars: Sequence[ResearchBar] | None,
    nq_bars: Sequence[ResearchBar] | None = None,
    vix: Sequence[tuple[date, float]] | None = None,
    events: Sequence[MacroEvent] | None = None,
) -> tuple[PowerRow, ...]:
    rows: list[PowerRow] = []
    for hyp in LOCKED_HYPOTHESES:
        if hyp.dropped:
            n_trades: int | None = None
            if hyp.research_id == "LH-02" and es_bars is not None:
                n_trades = count_weekend_mr(es_bars)
            rows.append(
                PowerRow(
                    research_id=hyp.research_id,
                    config_id=hyp.config_id,
                    status=STATUS_DROPPED,
                    n_trades=n_trades,
                    missing=(),
                    dropped_reason=hyp.dropped_reason,
                )
            )
            continue
        missing = missing_data_for(hyp, avail)
        if missing:
            rows.append(
                PowerRow(
                    research_id=hyp.research_id,
                    config_id=hyp.config_id,
                    status=STATUS_BLOCKED,
                    n_trades=None,
                    missing=missing,
                )
            )
            continue
        counted = _count_ready(hyp.research_id, es_bars, nq_bars, vix, events)
        rows.append(
            PowerRow(
                research_id=hyp.research_id,
                config_id=hyp.config_id,
                status=STATUS_READY,
                n_trades=counted,
                missing=(),
            )
        )
    return tuple(rows)


def _count_ready(
    research_id: str,
    es_bars: Sequence[ResearchBar] | None,
    nq_bars: Sequence[ResearchBar] | None,
    vix: Sequence[tuple[date, float]] | None,
    events: Sequence[MacroEvent] | None,
) -> int:
    if research_id == "LH-01":
        if es_bars is None:
            raise ValueError("LH-01 power requires ES bars")
        return count_nr7_breakouts(es_bars)
    if research_id == "RV-01":
        if es_bars is None or nq_bars is None or vix is None:
            raise ValueError("RV-01 power requires ES, NQ, and VIX")
        return count_ratio_mr(es_bars, nq_bars, vix)
    if research_id == "RV-02":
        if es_bars is None or nq_bars is None:
            raise ValueError("RV-02 power requires ES and NQ")
        return count_relative_gap_fade(es_bars, nq_bars)
    if research_id == "LH-03":
        if es_bars is None or events is None:
            raise ValueError("LH-03 power requires ES and macro events")
        return count_macro_fade(es_bars, events)
    raise ValueError(f"{research_id} is ready but has no power counter")


def load_pre_holdout_es(path: Path) -> tuple[ResearchBar, ...]:
    return load_pre_holdout_bars(path)


def load_pre_holdout_bars(path: Path) -> tuple[ResearchBar, ...]:
    bars = read_csv_bars(path)
    assert_no_holdout_timestamps(bars, pin_ns=P2_HOLDOUT_START_NS)
    return bars


def build_power_report(
    *,
    avail: DataAvailability | None = None,
    es_bars: Sequence[ResearchBar] | None = None,
    nq_bars: Sequence[ResearchBar] | None = None,
    vix: Sequence[tuple[date, float]] | None = None,
    events: Sequence[MacroEvent] | None = None,
) -> dict[str, object]:
    found = check_data_availability() if avail is None else avail
    bars = es_bars
    nq = nq_bars
    vix_rows = vix
    macro_rows = events
    if bars is None and found.es_path is not None:
        bars = load_pre_holdout_bars(Path(found.es_path))
    if nq is None and found.nq_path is not None:
        nq = load_pre_holdout_bars(Path(found.nq_path))
    if vix_rows is None and found.vix_path is not None:
        vix_rows = load_vix(Path(found.vix_path))
    if macro_rows is None and found.macro_path is not None:
        macro_rows = load_macro_events(Path(found.macro_path))
    rows = power_rows(found, es_bars=bars, nq_bars=nq, vix=vix_rows, events=macro_rows)
    lh03_diag: dict[str, object] | None = None
    if bars is not None and macro_rows is not None:
        fade = macro_fade_power(bars, macro_rows)
        lh03_diag = {
            "n_events": fade.n_events,
            "n_with_post_bar": fade.n_with_post_bar,
            "n_short_atr": fade.n_short_atr,
            "n_trades": fade.n_trades,
            "atr_source": LH03_ATR_SOURCE,
            "clarification_not_hypothesis_change": LH03_ATR_CLARIFICATION,
        }
    return {
        "schema": "lumina.research.final_cycle_power.v3",
        "finale_prereg": FINALE_PREREG_NAME,
        "finale_prereg_sha256": FINALE_PREREG_SHA256,
        "data_answers": DATA_ANSWERS_NAME,
        "data_answers_sha256": DATA_ANSWERS_SHA256,
        "lh03_answers": LH03_ANSWERS_NAME,
        "lh03_answers_sha256": LH03_ANSWERS_SHA256,
        "n_hypotheses": N_HYPOTHESES,
        "n_hypotheses_cap": NEW_BOOK_HYPOTHESIS_CAP,
        "dropped_config_ids": list(dropped_config_ids()),
        "runnable_config_ids": list(runnable_config_ids()),
        "lh01_target_range_mult": LH01_TARGET_RANGE_MULT,
        "rv02_sizing": RV02_SIZING,
        "rv02_low_power": dict(rv02_low_power()),
        "lh03_atr": dict(lh03_atr_lock()),
        "vix_filter_rule": VIX_FILTER_RULE,
        "kill": dict(kill_rule()),
        "holdout_pin": HOLDOUT_PIN_Z,
        "trials_run": False,
        "dsr_pbo_n": 0,
        "lh03_power": lh03_diag,
        "data_pins": dict(data_pins()),
        "data": {
            "es_pre_holdout": found.es_pre_holdout,
            "nq_pre_holdout": found.nq_pre_holdout,
            "vix": found.vix,
            "macro_calendar": found.macro_calendar,
            "cash_index": found.cash_index,
            "es_path": found.es_path,
            "nq_path": found.nq_path,
            "vix_path": found.vix_path,
            "macro_path": found.macro_path,
            "cash_path": found.cash_path,
            "es_sha256": found.es_sha256,
            "nq_sha256": found.nq_sha256,
            "vix_sha256": found.vix_sha256,
            "macro_sha256": found.macro_sha256,
        },
        "hypotheses": [
            {
                "research_id": row.research_id,
                "config_id": row.config_id,
                "status": row.status,
                "n_trades": row.n_trades,
                "missing": list(row.missing),
                "dropped_reason": row.dropped_reason,
            }
            for row in rows
        ],
    }


def search_space_mapping() -> dict[str, object]:
    rv_ids = list(relative_value_config_ids())
    return {
        "lower_turnover": True,
        "longer_horizon": True,
        "relative_value_config_ids": rv_ids,
        "n_hypotheses": N_HYPOTHESES,
        "null_builder": NULL_BUILDER,
        "positive_control_included": True,
        "committed_path": f"experiments/reports/{SEARCH_SPACE_PREREG_NAME}",
        "same_space_short_horizon": False,
        "nq_request": {
            "hypothesis_kind": KIND_RELATIVE_VALUE,
            "instruments": ["ES", "NQ"],
            "tape_window": "pre_holdout",
            "holdout_opened": False,
            "holdout_pin": HOLDOUT_PIN_Z,
            "null_builder": NULL_BUILDER,
            "positive_control_included": True,
            "config_ids": rv_ids,
            "reuses_prereg_ids": [],
            "sim_requested": False,
            "promotion_requested": False,
        },
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mean_std(values: Sequence[float]) -> tuple[float, float] | None:
    count = len(values)
    if count < 2:
        return None
    mean = sum(values) / float(count)
    var = sum((item - mean) ** 2 for item in values) / float(count - 1)
    if var <= 0.0:
        return None
    return mean, math.sqrt(var)


@dataclass(frozen=True, slots=True)
class _RthSession:
    session: date
    open: float
    high: float
    low: float
    close: float


def rth_sessions(bars: Sequence[ResearchBar]) -> tuple[_RthSession, ...]:
    return _rth_sessions(bars)


def _rth_sessions(bars: Sequence[ResearchBar]) -> tuple[_RthSession, ...]:
    labels = annotate(bars)
    first_open: dict[date, float] = {}
    high: dict[date, float] = {}
    low: dict[date, float] = {}
    close: dict[date, float] = {}
    order: list[date] = []
    for bar, session, is_rth in zip(bars, labels.session_dates, labels.rth, strict=True):
        if not is_rth:
            continue
        if session not in first_open:
            first_open[session] = bar.open
            high[session] = bar.high
            low[session] = bar.low
            order.append(session)
        else:
            high[session] = max(high[session], bar.high)
            low[session] = min(low[session], bar.low)
        close[session] = bar.close
    return tuple(
        _RthSession(
            session=day,
            open=first_open[day],
            high=high[day],
            low=low[day],
            close=close[day],
        )
        for day in order
    )


def _assert_lock_invariants() -> None:
    if len(LOCKED_HYPOTHESES) != N_HYPOTHESES:
        raise RuntimeError("final cycle must lock exactly 6 hypotheses")
    if N_HYPOTHESES > NEW_BOOK_HYPOTHESIS_CAP:
        raise RuntimeError("final cycle exceeds the 25-hypothesis cap")
    if LH01_TARGET_RANGE_MULT != 1.5:
        raise RuntimeError("LH-01 target must be the single locked 1.5x")
    if RV02_SIZING != "dollar_neutral":
        raise RuntimeError("RV-02 sizing must be dollar_neutral")
    if VIX_FILTER_RULE != "previous_day_close":
        raise RuntimeError("RV-01 VIX filter must use previous_day_close")
    if dropped_config_ids() != ("p2s-lh-02", "p2s-lh-04"):
        raise RuntimeError("LH-02 and LH-04 must stay dropped inside n=6")
    if runnable_config_ids() != ("p2s-rv-01", "p2s-rv-02", "p2s-lh-01", "p2s-lh-03"):
        raise RuntimeError("runnable final-cycle ids must be RV-01, RV-02, LH-01, LH-03")
    if LH03_ATR_SOURCE != "intraday_5m_atr14_strictly_before_event":
        raise RuntimeError("LH-03 ATR must stay the 5-minute pre-event clarification")
    if RV02_LOW_POWER_ACCEPTED is not True or RV02_POWER_N_TRADES != 59:
        raise RuntimeError("RV-02 59-trade low-power risk must stay accepted")
    ids = [item.config_id for item in LOCKED_HYPOTHESES]
    if len(set(ids)) != len(ids):
        raise RuntimeError("final-cycle config ids must be unique")


def render_power_markdown(payload: Mapping[str, object]) -> str:
    hyps = payload.get("hypotheses")
    rows = hyps if isinstance(hyps, list) else []
    lines = [
        "# P2 final-cycle data availability + power (2026-10-30 10:00)",
        "",
        "Binding: `docs/research/ONDERZOEKERS-PREREG-FINALE-CYCLUS-20261030T0913.md`",
        f"content sha256 `{FINALE_PREREG_SHA256}`.",
        "",
        "Data answers: `docs/research/ONDERZOEKERS-ANTWOORDEN-DATA-20261030T0936.md`",
        f"content sha256 `{DATA_ANSWERS_SHA256}`.",
        "",
        f"LH-03 answers: `docs/research/{LH03_ANSWERS_NAME}`",
        f"content sha256 `{LH03_ANSWERS_SHA256}` (prefix `0c549ee1`).",
        "",
        "Holdout pin `2026-01-28T23:00:00Z` unopened. No SIM/promotion. Risk Core untouched.",
        "n_hypotheses stays **6**. Dropped LH-02 and LH-04 stay in N.",
        "",
        "## Addendum (research team, NOT Steve)",
        "",
        f"- {LH03_ATR_NOTE}",
        f"- {RV02_LOW_POWER_NOTE}",
        "",
        "## Locked single values (no grid)",
        "",
        "- LH-01 NR7 target = **1.5×** NR7 range",
        "- RV-02 sizing = **dollar-neutral**",
        "- RV-01 z = **|z| > 2.5** both tails; exit |z| < 0.5; stop |z| ≥ 4.0",
        "- RV-02 gap = **|ES% − NQ%| > 0.4** at RTH open",
        "- RV-01 VIX<25 = **previous day's close**",
        "- LH-03 ATR = **5-minute ATR(14) strictly before release** (clarification)",
        "",
        "## Trade counts (pre-holdout power, entries only)",
        "",
        "| research | config_id | status | n_trades |",
        "|---|---|---|---|",
    ]
    for row in rows:
        if not isinstance(row, dict):
            continue
        rid = str(row.get("research_id", ""))
        cid = str(row.get("config_id", ""))
        status = str(row.get("status", ""))
        n_trades = row.get("n_trades")
        extra = ""
        if rid == "RV-02":
            extra = " (low-power risk accepted)"
        if rid == "LH-02":
            extra = " (reason)"
        if rid == "LH-04":
            extra = " (no free 1m SPX)"
        shown = "—" if n_trades is None else f"**{n_trades}**"
        lines.append(f"| {rid} | `{cid}` | {status} | {shown}{extra} |")
    lh03 = payload.get("lh03_power")
    lines.extend(["", "LH-03 diagnostic (5-minute ATR14, no lookahead):"])
    if isinstance(lh03, dict):
        lines.append(
            f"{lh03.get('n_events')} events; {lh03.get('n_with_post_bar')} have a +5min bar; "
            f"{lh03.get('n_short_atr')} lack 14 five-minute true ranges before the release; "
            f"**{lh03.get('n_trades')}** exceed 1.2× 5-minute ATR14."
        )
    lines.extend(
        [
            "",
            "Kill still: DSR ≥ 0.95 AND ≥7/8 OOS+ AND net > 0.",
            "",
            "JSON: `phase5_p2_final_cycle_data_power.json`.",
            "",
        ]
    )
    return "\n".join(lines)


def write_power_artifacts(
    payload: Mapping[str, object],
    *,
    json_path: Path | None = None,
    md_path: Path | None = None,
) -> tuple[Path, Path]:
    target_json = json_path if json_path is not None else DEFAULT_POWER_JSON
    target_md = md_path if md_path is not None else DEFAULT_POWER_MD
    target_json.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    target_md.write_text(render_power_markdown(payload), encoding="utf-8")
    return target_json, target_md


_assert_lock_invariants()
