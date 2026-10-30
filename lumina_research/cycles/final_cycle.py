"""Locked 09:13 final-cycle search space for book p2-next-search-space.

Six pre-registered hypotheses. No Validation Gate trial. DSR/PBO N stays 0.
Ambiguous bands are resolved to one value. Missing data blocks a hypothesis.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Mapping, Sequence

from lumina_research.cycles.data import ResearchBar, read_csv_bars
from lumina_research.cycles.holdout import P2_HOLDOUT_START_NS, assert_no_holdout_timestamps
from lumina_research.cycles.nq_research import HOLDOUT_PIN_Z, KIND_RELATIVE_VALUE
from lumina_research.cycles.null_model import NULL_BUILDER
from lumina_research.cycles.search_space import NEW_BOOK_HYPOTHESIS_CAP
from lumina_research.cycles.sessions import annotate
from lumina_research.validation.thresholds import FLOOR_DSR_PROBABILITY_MIN

FINALE_PREREG_NAME = "ONDERZOEKERS-PREREG-FINALE-CYCLUS-20261030T0913.md"
FINALE_PREREG_SHA256 = "106af5b23d2eeb24454a2174e8c59ae24fb69e78c9729bb6e2accf3452aedade"
SEARCH_SPACE_PREREG_NAME = "phase5_p2_search_space_preregister_2026-10-30.md"
N_HYPOTHESES = 6
LH01_TARGET_RANGE_MULT = 1.5
RV02_SIZING = "dollar_neutral"
RV02_ES_MULTIPLIER = 50.0
RV02_NQ_MULTIPLIER = 20.0
KILL_DSR_MIN = FLOOR_DSR_PROBABILITY_MIN
KILL_OOS_POSITIVE_MIN = 7
KILL_OOS_WINDOWS = 8
STATUS_READY = "ready"
STATUS_BLOCKED = "blocked_missing_data"
DATA_ES = "es_pre_holdout"
DATA_NQ = "nq_pre_holdout"
DATA_VIX = "vix"
DATA_MACRO = "macro_calendar"
DATA_CASH = "cash_index"

_REPO = Path(__file__).resolve().parents[2]
FINALE_PREREG_PATH = _REPO / "docs" / "research" / FINALE_PREREG_NAME
SEARCH_SPACE_PREREG_PATH = _REPO / "experiments" / "reports" / SEARCH_SPACE_PREREG_NAME
DEFAULT_POWER_JSON = _REPO / "experiments" / "reports" / "phase5_p2_final_cycle_data_power.json"

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
    "$LUMINA_RESEARCH_DATA_DIR/VIX/1d/vix.csv",
    "data/research/VIX/1d/vix.csv",
    "/tmp/lumina-vix/vix.csv",
)
MACRO_SEARCHED: tuple[str, ...] = (
    "$LUMINA_RESEARCH_DATA_DIR/macro/releases.csv",
    "data/research/macro/releases.csv",
    "/tmp/lumina-macro/releases.csv",
)
CASH_SEARCHED: tuple[str, ...] = (
    "$LUMINA_RESEARCH_DATA_DIR/SPX/1d/spx.csv",
    "data/research/SPX/1d/spx.csv",
    "/tmp/lumina-cash/spx.csv",
)


@dataclass(frozen=True, slots=True)
class FinalHypothesis:
    research_id: str
    config_id: str
    kind: str
    instruments: tuple[str, ...]
    required_data: tuple[str, ...]
    entry: str
    exit_stop: str


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


@dataclass(frozen=True, slots=True)
class PowerRow:
    research_id: str
    config_id: str
    status: str
    n_trades: int | None
    missing: tuple[str, ...]


LOCKED_HYPOTHESES: tuple[FinalHypothesis, ...] = (
    FinalHypothesis(
        research_id="RV-01",
        config_id="p2s-rv-01",
        kind=KIND_RELATIVE_VALUE,
        instruments=("ES", "NQ"),
        required_data=(DATA_ES, DATA_NQ, DATA_VIX),
        entry="RTH ES/NQ close-ratio z>2.5 lookback 20 sessions; VIX<25",
        exit_stop="exit z<0.5 or 6h; stop |z|>=4.0",
    ),
    FinalHypothesis(
        research_id="RV-02",
        config_id="p2s-rv-02",
        kind=KIND_RELATIVE_VALUE,
        instruments=("ES", "NQ"),
        required_data=(DATA_ES, DATA_NQ),
        entry="RTH open relative overnight gap (ES%-NQ%)>0.4%; dollar-neutral fade",
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
    ),
)


def relative_value_config_ids() -> tuple[str, ...]:
    return tuple(item.config_id for item in LOCKED_HYPOTHESES if item.kind == KIND_RELATIVE_VALUE)


def all_config_ids() -> tuple[str, ...]:
    return tuple(item.config_id for item in LOCKED_HYPOTHESES)


def kill_rule() -> Mapping[str, object]:
    return {
        "dsr_min": KILL_DSR_MIN,
        "oos_positive_min": KILL_OOS_POSITIVE_MIN,
        "oos_windows": KILL_OOS_WINDOWS,
        "net_positive": True,
        "text": "DSR>=0.95 AND >=7/8 OOS+ AND net>0",
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


def check_data_availability() -> DataAvailability:
    es_path = _first_existing(ES_TAPE_SEARCHED)
    nq_path = _first_existing(NQ_TAPE_SEARCHED)
    vix_path = _first_existing(VIX_SEARCHED)
    macro_path = _first_existing(MACRO_SEARCHED)
    cash_path = _first_existing(CASH_SEARCHED)
    es_sha: str | None = None
    if es_path is not None:
        es_sha = _sha256(es_path)
    return DataAvailability(
        es_pre_holdout=es_path is not None,
        nq_pre_holdout=nq_path is not None,
        vix=vix_path is not None,
        macro_calendar=macro_path is not None,
        cash_index=cash_path is not None,
        es_path=None if es_path is None else str(es_path),
        nq_path=None if nq_path is None else str(nq_path),
        vix_path=None if vix_path is None else str(vix_path),
        macro_path=None if macro_path is None else str(macro_path),
        cash_path=None if cash_path is None else str(cash_path),
        es_sha256=es_sha,
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


def power_rows(
    avail: DataAvailability,
    *,
    es_bars: Sequence[ResearchBar] | None,
) -> tuple[PowerRow, ...]:
    rows: list[PowerRow] = []
    for hyp in LOCKED_HYPOTHESES:
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
        n_trades: int
        if hyp.research_id == "LH-01":
            if es_bars is None:
                raise ValueError("LH-01 power requires ES bars")
            n_trades = count_nr7_breakouts(es_bars)
        elif hyp.research_id == "LH-02":
            if es_bars is None:
                raise ValueError("LH-02 power requires ES bars")
            n_trades = count_weekend_mr(es_bars)
        else:
            raise ValueError(f"{hyp.research_id} is ready but has no power counter")
        rows.append(
            PowerRow(
                research_id=hyp.research_id,
                config_id=hyp.config_id,
                status=STATUS_READY,
                n_trades=n_trades,
                missing=(),
            )
        )
    return tuple(rows)


def load_pre_holdout_es(path: Path) -> tuple[ResearchBar, ...]:
    bars = read_csv_bars(path)
    assert_no_holdout_timestamps(bars, pin_ns=P2_HOLDOUT_START_NS)
    return bars


def build_power_report(
    *,
    avail: DataAvailability | None = None,
    es_bars: Sequence[ResearchBar] | None = None,
) -> dict[str, object]:
    found = check_data_availability() if avail is None else avail
    bars = es_bars
    if bars is None and found.es_path is not None:
        bars = load_pre_holdout_es(Path(found.es_path))
    rows = power_rows(found, es_bars=bars)
    return {
        "schema": "lumina.research.final_cycle_power.v1",
        "finale_prereg": FINALE_PREREG_NAME,
        "finale_prereg_sha256": FINALE_PREREG_SHA256,
        "n_hypotheses": N_HYPOTHESES,
        "n_hypotheses_cap": NEW_BOOK_HYPOTHESIS_CAP,
        "lh01_target_range_mult": LH01_TARGET_RANGE_MULT,
        "rv02_sizing": RV02_SIZING,
        "kill": dict(kill_rule()),
        "holdout_pin": "2026-01-28T23:00:00Z",
        "trials_run": False,
        "dsr_pbo_n": 0,
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
        },
        "hypotheses": [
            {
                "research_id": row.research_id,
                "config_id": row.config_id,
                "status": row.status,
                "n_trades": row.n_trades,
                "missing": list(row.missing),
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


@dataclass(frozen=True, slots=True)
class _RthSession:
    session: date
    open: float
    high: float
    low: float
    close: float


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
    ids = [item.config_id for item in LOCKED_HYPOTHESES]
    if len(set(ids)) != len(ids):
        raise RuntimeError("final-cycle config ids must be unique")


_assert_lock_invariants()
