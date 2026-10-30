"""Rolling trial ledger after the 08:33 book split and the 08:50 cap.

The limited-es/postkill book is closed at its final N. A new book starts at
N=0. DSR/PBO use that book's N only. Min-DSR is not raised. The hard stop
still counts cycles and hypotheses across books and is already tripped. The
new book allows exactly 1 cycle or at most 25 hypotheses, whichever comes
first. A 2nd cycle is refused. 0 survivors after that cycle sets
research_line_stopped. The new book does not open until an explicit
search-space pre-register exists.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from lumina_research.cycles.final_cycle import DATA_ANSWERS_SHA256, FINALE_PREREG_SHA256
from lumina_research.cycles.search_space import (
    NEW_BOOK_HYPOTHESIS_CAP,
    NEW_BOOK_MAX_CYCLES,
    SearchSpaceRefused,
    assert_search_space_prereg_opens_book,
    search_space_prereg_from_mapping,
)
from lumina_research.cycles.stop_criterion import (
    STOP_CRITERION_TRIPPED,
    STOPTELLING_ANSWERS_SHA256,
    stop_criterion_status,
)
from lumina_research.validation.thresholds import FLOOR_DSR_PROBABILITY_MIN

LEDGER_SCHEMA = "lumina.research.trial_ledger.v3"
LEDGER_NAME = "phase5_p2_trial_ledger.json"
MARKETS: tuple[str, ...] = ("ES", "MES", "MNQ", "NQ")
CLOSED_BOOK_ID = "p2-es-limited-postkill"
CLOSED_BOOK_FINAL_N = 150
NEW_BOOK_ID = "p2-next-search-space"
NEW_BOOK_STATUS = "awaiting_search_space_prereg"
LINE_STATE_STOPPED = "research_line_stopped"
LINE_STATE_CYCLE_COMPLETE = "cycle_complete"
RULE_SPLIT_BOOKS = "split_books"
RULE_RAISE_MIN_DSR = "raise_min_dsr"
CLOSED_BOOK_CYCLES: frozenset[str] = frozenset({"first", "four-instrument", "atr-es", "limited-es", "postkill-es"})
BOEKSPLIT_ANSWERS_NAME = "ONDERZOEKERS-ANTWOORDEN-BOEKSPLIT-20261030T0833.md"
BOEKSPLIT_ANSWERS_SHA256 = "a970bf171b9e38a0bdc69b919c7cc0484c711e99068bfcd765e9f6d5d6c21474"

_REPO = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER_PATH = _REPO / "experiments" / "reports" / LEDGER_NAME
BOEKSPLIT_ANSWERS_PATH = _REPO / "docs" / "research" / BOEKSPLIT_ANSWERS_NAME

CLOSED_BOOK_BLOCKS_REASON = "trial ledger blocks this run: book p2-es-limited-postkill is closed at N=150"
NEW_BOOK_BLOCKS_REASON = (
    "trial ledger blocks this run: new book is not open; requires an explicit "
    "search-space prereg (lower turnover, longer horizon, at least 1 relative-value idea)"
)
SECOND_CYCLE_REFUSED = (
    "trial ledger blocks this run: p2-next-search-space allows exactly 1 cycle; a 2nd cycle is refused"
)
LINE_STOPPED_REASON = (
    "trial ledger blocks this run: research_line_stopped; 0 survivors on this "
    "line; further runs need a more fundamental change (e.g. new data sources) "
    "with explicit approval"
)


class LedgerRefused(RuntimeError):
    """Ledger file missing, unreadable, or internally inconsistent."""


class LedgerBlocksRun(RuntimeError):
    """Closed book, or new book still awaiting a search-space pre-register."""


@dataclass(frozen=True, slots=True)
class TrialLedger:
    path: Path
    schema: str
    chosen_rule: str
    min_dsr_raised: bool
    dsr_probability_min: float
    closed_book_id: str
    closed_n_by_market: Mapping[str, int]
    closed_n_total: int
    active_book_id: str
    active_n_by_market: Mapping[str, int]
    active_n_total: int
    dsr_pbo_n: int
    active_open: bool
    active_status: str
    n_cycles_allowed: int
    n_cycles_completed: int
    n_hypotheses_cap: int
    n_hypotheses_stated: int | None
    research_line_stopped: bool

    def n_for(self, market: str) -> int:
        if market not in self.active_n_by_market:
            raise LedgerRefused(f"unknown market {market}")
        return int(self.active_n_by_market[market])

    def closed_n_for(self, market: str) -> int:
        if market not in self.closed_n_by_market:
            raise LedgerRefused(f"unknown market {market}")
        return int(self.closed_n_by_market[market])

    @property
    def blocks_run(self) -> bool:
        if self.research_line_stopped:
            return True
        if self.n_cycles_completed >= NEW_BOOK_MAX_CYCLES:
            return True
        return self.active_open is not True


def dsr_pbo_n_for_run(ledger: TrialLedger) -> int:
    """DSR/PBO N is the active book's count only. Closed-book N is not reused."""
    if ledger.active_book_id == CLOSED_BOOK_ID:
        raise LedgerRefused("closed book does not accept new DSR/PBO trials")
    if ledger.min_dsr_raised:
        raise LedgerRefused("min-DSR must not be raised")
    if ledger.dsr_probability_min != FLOOR_DSR_PROBABILITY_MIN:
        raise LedgerRefused("min-DSR must stay 0.95")
    return int(ledger.dsr_pbo_n)


def line_state_after_cycle(*, n_survivors: int, n_cycles_completed_before: int) -> str:
    """Terminal line state after the one allowed cycle in p2-next-search-space."""
    if (
        isinstance(n_cycles_completed_before, bool)
        or not isinstance(n_cycles_completed_before, int)
        or n_cycles_completed_before < 0
    ):
        raise LedgerRefused("n_cycles_completed_before must be a non-negative integer")
    if n_cycles_completed_before >= NEW_BOOK_MAX_CYCLES:
        raise LedgerBlocksRun(SECOND_CYCLE_REFUSED)
    if isinstance(n_survivors, bool) or not isinstance(n_survivors, int) or n_survivors < 0:
        raise LedgerRefused("n_survivors must be a non-negative integer")
    if n_survivors == 0:
        return LINE_STATE_STOPPED
    return LINE_STATE_CYCLE_COMPLETE


def load_trial_ledger(path: Path | None = None) -> TrialLedger:
    ledger_path = path if path is not None else DEFAULT_LEDGER_PATH
    if not ledger_path.is_file():
        raise LedgerRefused(f"trial ledger missing: {ledger_path}")
    try:
        payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LedgerRefused("trial ledger is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise LedgerRefused("trial ledger root must be an object")
    if payload.get("schema") != LEDGER_SCHEMA:
        raise LedgerRefused("trial ledger schema mismatch")
    _validate_optional_stop_lock(payload)
    if payload.get("chosen_rule") != RULE_SPLIT_BOOKS:
        raise LedgerRefused("ledger chosen_rule must be split_books")
    if payload.get("min_dsr_raised") is not False:
        raise LedgerRefused("min-DSR must not be raised")
    dsr_min = _as_dsr_min(payload.get("dsr_probability_min"))
    closed = _closed_limited_postkill(payload.get("closed_books"))
    active = _as_object(payload.get("active_book"), field="active_book")
    active_id = active.get("id")
    if active_id != NEW_BOOK_ID:
        raise LedgerRefused(f"active_book.id must be {NEW_BOOK_ID}")
    active_n = _n_by_market(_as_object(active.get("n_by_market"), field="active_book.n_by_market"))
    active_total = _as_nonneg_int(active.get("n_total"), field="active_book.n_total")
    if active_total != sum(active_n.values()):
        raise LedgerRefused("active_book.n_total must equal the sum of n_by_market")
    dsr_pbo_n = _as_nonneg_int(active.get("dsr_pbo_n"), field="active_book.dsr_pbo_n")
    if dsr_pbo_n != active_total:
        raise LedgerRefused("DSR/PBO N must equal the active book's N only")
    if payload.get("fundamental_change_approval") is not None:
        raise LedgerRefused(
            "this line cannot be reopened; a more fundamental change needs a new book and explicit approval"
        )
    n_cycles_allowed = _as_nonneg_int(active.get("n_cycles_allowed"), field="n_cycles_allowed")
    if n_cycles_allowed != NEW_BOOK_MAX_CYCLES:
        raise LedgerRefused("p2-next-search-space allows exactly 1 cycle")
    n_cycles_completed = _as_nonneg_int(
        active.get("n_cycles_completed"),
        field="n_cycles_completed",
    )
    if n_cycles_completed > NEW_BOOK_MAX_CYCLES:
        raise LedgerRefused("p2-next-search-space cannot complete more than 1 cycle")
    n_hypotheses_cap = _as_nonneg_int(active.get("n_hypotheses_cap"), field="n_hypotheses_cap")
    if n_hypotheses_cap != NEW_BOOK_HYPOTHESIS_CAP:
        raise LedgerRefused("p2-next-search-space hypothesis cap must be 25")
    n_hypotheses_stated = _optional_hypothesis_count(active.get("n_hypotheses_stated"))
    stopped_flag = active.get("research_line_stopped")
    if not isinstance(stopped_flag, bool):
        raise LedgerRefused("research_line_stopped must be a boolean")
    status = active.get("status")
    if not isinstance(status, str) or not status.strip():
        raise LedgerRefused("active_book.status must be a non-empty string")
    prereg = active.get("search_space_prereg")
    opened = active.get("open")
    if opened is not True and opened is not False:
        raise LedgerRefused("active_book.open must be boolean")
    if status == LINE_STATE_STOPPED:
        if opened is not False:
            raise LedgerRefused("research_line_stopped book cannot be open")
        if stopped_flag is not True:
            raise LedgerRefused("status research_line_stopped requires research_line_stopped=true")
        if n_cycles_completed != NEW_BOOK_MAX_CYCLES:
            raise LedgerRefused("research_line_stopped requires the one allowed cycle to have run")
    elif opened is True:
        if not isinstance(prereg, dict):
            raise LedgerRefused("open book requires a search-space prereg")
        try:
            parsed = search_space_prereg_from_mapping(
                _as_object(prereg, field="search_space_prereg"),
                repo_root=_REPO,
            )
            assert_search_space_prereg_opens_book(parsed)
        except SearchSpaceRefused as exc:
            raise LedgerRefused(str(exc)) from exc
        if status != "open":
            raise LedgerRefused("open book status must be open")
        if stopped_flag is not False:
            raise LedgerRefused("open book cannot be research_line_stopped")
        if n_cycles_completed != 0:
            raise LedgerRefused("open book has not completed its one cycle yet")
        if n_hypotheses_stated != parsed.n_hypotheses:
            raise LedgerRefused("n_hypotheses_stated must match the search-space prereg")
    elif opened is False and status == LINE_STATE_CYCLE_COMPLETE:
        if stopped_flag is not False:
            raise LedgerRefused("cycle_complete is not research_line_stopped")
        if n_cycles_completed != NEW_BOOK_MAX_CYCLES:
            raise LedgerRefused("cycle_complete requires the one allowed cycle to have run")
    elif opened is False:
        if prereg is not None:
            raise LedgerRefused("unopened book must not claim a search-space prereg")
        if status != NEW_BOOK_STATUS:
            raise LedgerRefused(f"active_book.status must be {NEW_BOOK_STATUS}")
        if stopped_flag is not False:
            raise LedgerRefused("awaiting book cannot be research_line_stopped")
        if active_total != 0:
            raise LedgerRefused("new book starts at N=0 until a search-space cycle runs")
        if n_cycles_completed != 0:
            raise LedgerRefused("awaiting book has completed 0 cycles")
        if n_hypotheses_stated is not None:
            raise LedgerRefused("awaiting book has no stated hypothesis count")
    return TrialLedger(
        path=ledger_path,
        schema=LEDGER_SCHEMA,
        chosen_rule=RULE_SPLIT_BOOKS,
        min_dsr_raised=False,
        dsr_probability_min=dsr_min,
        closed_book_id=CLOSED_BOOK_ID,
        closed_n_by_market=closed[0],
        closed_n_total=closed[1],
        active_book_id=NEW_BOOK_ID,
        active_n_by_market=active_n,
        active_n_total=active_total,
        dsr_pbo_n=dsr_pbo_n,
        active_open=bool(opened),
        active_status=status,
        n_cycles_allowed=NEW_BOOK_MAX_CYCLES,
        n_cycles_completed=n_cycles_completed,
        n_hypotheses_cap=NEW_BOOK_HYPOTHESIS_CAP,
        n_hypotheses_stated=n_hypotheses_stated,
        research_line_stopped=stopped_flag,
    )


def assert_ledger_allows_run(
    path: Path | None = None,
    *,
    cycle: str | None = None,
) -> TrialLedger:
    ledger = load_trial_ledger(path)
    if cycle in CLOSED_BOOK_CYCLES:
        raise LedgerBlocksRun(CLOSED_BOOK_BLOCKS_REASON)
    if ledger.chosen_rule == RULE_RAISE_MIN_DSR or ledger.min_dsr_raised:
        raise LedgerRefused("min-DSR must not be raised")
    if ledger.research_line_stopped:
        raise LedgerBlocksRun(LINE_STOPPED_REASON)
    if ledger.n_cycles_completed >= NEW_BOOK_MAX_CYCLES:
        raise LedgerBlocksRun(SECOND_CYCLE_REFUSED)
    if ledger.blocks_run:
        raise LedgerBlocksRun(NEW_BOOK_BLOCKS_REASON)
    return ledger


def _validate_optional_stop_lock(payload: Mapping[str, object]) -> None:
    answers = payload.get("answers")
    if answers is not None:
        block = _as_object(answers, field="answers")
        if block.get("stoptelling_sha256") != STOPTELLING_ANSWERS_SHA256:
            raise LedgerRefused("stoptelling answers sha mismatch")
        if block.get("finale_cyclus_sha256") != FINALE_PREREG_SHA256:
            raise LedgerRefused("finale cyclus sha mismatch")
        if block.get("data_sha256") != DATA_ANSWERS_SHA256:
            raise LedgerRefused("data answers sha mismatch")
    raw = payload.get("stop_criterion")
    if raw is None:
        return
    block = _as_object(raw, field="stop_criterion")
    status = stop_criterion_status()
    if block.get("tripped") is not STOP_CRITERION_TRIPPED:
        raise LedgerRefused("stop criterion tripped flag mismatch")
    if block.get("counts_across_books") is not True:
        raise LedgerRefused("stop counter counts across books")
    if block.get("reset_by_split") is not False:
        raise LedgerRefused("stop counter is not reset by the book split")
    if block.get("n_full_cycles") != status.n_full_cycles:
        raise LedgerRefused("stop criterion n_full_cycles mismatch")
    if block.get("n_prereg_hypotheses") != status.n_prereg_hypotheses:
        raise LedgerRefused("stop criterion n_prereg_hypotheses mismatch")
    if block.get("n_survivors") != status.n_survivors:
        raise LedgerRefused("stop criterion n_survivors mismatch")


def _as_dsr_min(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LedgerRefused("dsr_probability_min must be a number")
    loaded = float(value)
    if loaded != float(FLOOR_DSR_PROBABILITY_MIN):
        raise LedgerRefused("min-DSR must stay 0.95; do not raise")
    return float(FLOOR_DSR_PROBABILITY_MIN)


def _closed_limited_postkill(value: object) -> tuple[dict[str, int], int]:
    if not isinstance(value, list) or not value:
        raise LedgerRefused("closed_books must be a non-empty list")
    found: dict[str, int] | None = None
    total = -1
    for item in value:
        block = _as_object(item, field="closed_books[]")
        if block.get("id") != CLOSED_BOOK_ID:
            continue
        if block.get("status") != "closed":
            raise LedgerRefused("limited-postkill book must be closed")
        n_by_market = _n_by_market(_as_object(block.get("n_by_market"), field="closed_books.n_by_market"))
        n_total = _as_nonneg_int(block.get("n_total"), field="closed_books.n_total")
        if n_total != sum(n_by_market.values()):
            raise LedgerRefused("closed book n_total must equal the sum of n_by_market")
        if n_total != CLOSED_BOOK_FINAL_N:
            raise LedgerRefused(f"closed book final N must be {CLOSED_BOOK_FINAL_N}")
        dsr_n = _as_nonneg_int(block.get("dsr_pbo_n"), field="closed_books.dsr_pbo_n")
        if dsr_n != n_total:
            raise LedgerRefused("closed book dsr_pbo_n is historical and frozen")
        found = n_by_market
        total = n_total
    if found is None:
        raise LedgerRefused("closed_books must include p2-es-limited-postkill")
    return found, total


def _as_object(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise LedgerRefused(f"{field} must be an object")
    typed: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise LedgerRefused(f"{field} keys must be strings")
        typed[key] = item
    return typed


def _optional_hypothesis_count(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise LedgerRefused("n_hypotheses_stated must be null or an integer")
    if value < 1 or value > NEW_BOOK_HYPOTHESIS_CAP:
        raise LedgerRefused("n_hypotheses_stated must be in 1..25")
    return value


def _as_nonneg_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise LedgerRefused(f"{field} must be an integer")
    if value < 0:
        raise LedgerRefused(f"{field} must be >= 0")
    return value


def _n_by_market(raw: Mapping[str, object]) -> dict[str, int]:
    out: dict[str, int] = {}
    for market in MARKETS:
        if market not in raw:
            raise LedgerRefused(f"n_by_market missing {market}")
        out[market] = _as_nonneg_int(raw[market], field=f"n_by_market.{market}")
    extra = set(raw) - set(MARKETS)
    if extra:
        raise LedgerRefused("n_by_market has unknown markets")
    return out
