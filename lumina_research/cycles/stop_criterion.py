"""Pre-registered hard stop for the current P2 search space.

Research-team FABRIEK answers 2026-10-30 08:12 (forwarded by Steve; not Steve).
This module locks the stop text and which cycles already count. The 08:33
book split resets only the DSR/PBO ledger. Stop counts stay across books.
The 08:50 STOPTELLING answers confirm the three earlier cycles count and
that the stop criterion is already tripped. It does not pre-register a new
hypothesis and does not run a trial.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

FABRIEK_ANSWERS_NAME = "ONDERZOEKERS-ANTWOORDEN-FABRIEK-20261030T0812.md"
FABRIEK_ANSWERS_SHA256 = "de73d38ccc30912a439b226f4248d5581f46d3253995dbbd6760fe1943c592f6"
STOP_CRITERION_PREREG_NAME = "phase5_p2_stop_criterion_preregister_2026-10-30.md"
STOPTELLING_ANSWERS_NAME = "ONDERZOEKERS-ANTWOORDEN-STOPTELLING-20261030T0850.md"
STOPTELLING_ANSWERS_SHA256 = "547f30476afe10f4cdc6a4918a48b0e2719964e9251d6f8c1ac7e40dc6787f11"
CLOSED_BOOK_ID = "p2-es-limited-postkill"
NEW_BOOK_ID = "p2-next-search-space"
COUNTS_ACROSS_BOOKS = True
STOP_CRITERION_TRIPPED = True

HARD_STOP_VERBATIM_NL = (
    "na 3 volledige cycli of 60-80 prereg hypotheses met 0 survivors, of 2 cycli "
    "met hoge positive-control power maar alles faalt na kosten -> zoekruimte "
    "fundamenteel wijzigen of stoppen/herallocatie."
)
HARD_STOP_VERBATIM_EN = (
    "after 3 full cycles OR 60-80 prereg hypotheses with 0 survivors, OR after "
    "2 cycles where positive-control power is high but every real hypothesis "
    "fails after costs, the search space is declared insufficient, and then "
    "either it is changed fundamentally or research stops."
)

_REPO = Path(__file__).resolve().parents[2]
STOP_CRITERION_PREREG_PATH = _REPO / "experiments" / "reports" / STOP_CRITERION_PREREG_NAME
FABRIEK_ANSWERS_PATH = _REPO / "docs" / "research" / FABRIEK_ANSWERS_NAME
STOPTELLING_ANSWERS_PATH = _REPO / "docs" / "research" / STOPTELLING_ANSWERS_NAME


@dataclass(frozen=True, slots=True)
class CountedCycle:
    cycle_id: str
    n_prereg_hypotheses: int
    n_killed: int
    n_survivors: int
    high_positive_control_power: bool
    all_real_hypotheses_fail_after_costs: bool
    counts_as_full_cycle: bool
    report: str
    book_id: str


COUNTED_CYCLES: tuple[CountedCycle, ...] = (
    CountedCycle(
        cycle_id="atr-es",
        n_prereg_hypotheses=10,
        n_killed=10,
        n_survivors=0,
        high_positive_control_power=False,
        all_real_hypotheses_fail_after_costs=True,
        counts_as_full_cycle=True,
        report="phase5_p2_atr_es.json",
        book_id=CLOSED_BOOK_ID,
    ),
    CountedCycle(
        cycle_id="limited-es",
        n_prereg_hypotheses=6,
        n_killed=6,
        n_survivors=0,
        high_positive_control_power=True,
        all_real_hypotheses_fail_after_costs=True,
        counts_as_full_cycle=True,
        report="phase5_p2_limited_es_end.json",
        book_id=CLOSED_BOOK_ID,
    ),
    CountedCycle(
        cycle_id="postkill-es",
        n_prereg_hypotheses=3,
        n_killed=3,
        n_survivors=0,
        high_positive_control_power=True,
        all_real_hypotheses_fail_after_costs=True,
        counts_as_full_cycle=True,
        report="phase5_p2_postkill_end.json",
        book_id=CLOSED_BOOK_ID,
    ),
)

NOT_COUNTED_CYCLE_IDS: tuple[str, ...] = (
    "first",
    "four-instrument",
    "null-audit",
    "null-only",
    "midpoint-d13",
    "midpoint-power",
    "midpoint-power-floor",
)


@dataclass(frozen=True, slots=True)
class StopCriterionStatus:
    n_full_cycles: int
    n_prereg_hypotheses: int
    n_survivors: int
    n_high_power_fail_after_costs_cycles: int
    three_full_cycles_zero_survivors: bool
    sixty_to_eighty_prereg_zero_survivors: bool
    two_high_power_all_fail_after_costs: bool
    search_space_insufficient: bool
    counts_across_books: bool
    n_books: int


def n_full_cycles(cycles: tuple[CountedCycle, ...] = COUNTED_CYCLES) -> int:
    return sum(1 for item in cycles if item.counts_as_full_cycle)


def n_prereg_hypotheses(cycles: tuple[CountedCycle, ...] = COUNTED_CYCLES) -> int:
    return sum(item.n_prereg_hypotheses for item in cycles)


def n_survivors(cycles: tuple[CountedCycle, ...] = COUNTED_CYCLES) -> int:
    return sum(item.n_survivors for item in cycles)


def n_high_power_fail_after_costs_cycles(
    cycles: tuple[CountedCycle, ...] = COUNTED_CYCLES,
) -> int:
    return sum(
        1
        for item in cycles
        if item.high_positive_control_power and item.all_real_hypotheses_fail_after_costs and item.n_survivors == 0
    )


def stop_criterion_status(
    cycles: tuple[CountedCycle, ...] = COUNTED_CYCLES,
) -> StopCriterionStatus:
    full = n_full_cycles(cycles)
    prereg = n_prereg_hypotheses(cycles)
    survivors = n_survivors(cycles)
    high_fail = n_high_power_fail_after_costs_cycles(cycles)
    three = full >= 3 and survivors == 0
    sixty = prereg >= 60 and survivors == 0
    two_power = high_fail >= 2
    return StopCriterionStatus(
        n_full_cycles=full,
        n_prereg_hypotheses=prereg,
        n_survivors=survivors,
        n_high_power_fail_after_costs_cycles=high_fail,
        three_full_cycles_zero_survivors=three,
        sixty_to_eighty_prereg_zero_survivors=sixty,
        two_high_power_all_fail_after_costs=two_power,
        search_space_insufficient=three or sixty or two_power,
        counts_across_books=COUNTS_ACROSS_BOOKS,
        n_books=len({item.book_id for item in cycles}),
    )
