"""Rolling trial ledger after the 08:33 book split.

The limited-es/postkill book is closed at its final N. A new book starts at
N=0. DSR/PBO use that book's N only. Min-DSR is not raised. The hard stop
still counts cycles and hypotheses across books. The new book does not open
until an explicit search-space pre-register exists.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from lumina_research.cycles.search_space import (
    SearchSpaceRefused,
    assert_search_space_prereg_opens_book,
    search_space_prereg_from_mapping,
)
from lumina_research.validation.thresholds import FLOOR_DSR_PROBABILITY_MIN

LEDGER_SCHEMA = "lumina.research.trial_ledger.v2"
LEDGER_NAME = "phase5_p2_trial_ledger.json"
MARKETS: tuple[str, ...] = ("ES", "MES", "MNQ", "NQ")
CLOSED_BOOK_ID = "p2-es-limited-postkill"
CLOSED_BOOK_FINAL_N = 150
NEW_BOOK_ID = "p2-next-search-space"
NEW_BOOK_STATUS = "awaiting_search_space_prereg"
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
    status = active.get("status")
    if not isinstance(status, str) or not status.strip():
        raise LedgerRefused("active_book.status must be a non-empty string")
    prereg = active.get("search_space_prereg")
    opened = active.get("open")
    if opened is True:
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
        if status == NEW_BOOK_STATUS:
            raise LedgerRefused("open book status cannot be awaiting_search_space_prereg")
    elif opened is False:
        if prereg is not None:
            raise LedgerRefused("unopened book must not claim a search-space prereg")
        if status != NEW_BOOK_STATUS:
            raise LedgerRefused(f"active_book.status must be {NEW_BOOK_STATUS}")
        if active_total != 0:
            raise LedgerRefused("new book starts at N=0 until a search-space cycle runs")
    else:
        raise LedgerRefused("active_book.open must be boolean")
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
    if ledger.blocks_run:
        raise LedgerBlocksRun(NEW_BOOK_BLOCKS_REASON)
    return ledger


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
