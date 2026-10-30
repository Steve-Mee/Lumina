"""FABRIEK answers freeze and the hard-stop criterion lock. No new trials."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from lumina_research.cycles.stop_criterion import (
    CLOSED_BOOK_ID,
    COUNTED_CYCLES,
    COUNTS_ACROSS_BOOKS,
    CountedCycle,
    FABRIEK_ANSWERS_NAME,
    FABRIEK_ANSWERS_PATH,
    FABRIEK_ANSWERS_SHA256,
    HARD_STOP_VERBATIM_EN,
    HARD_STOP_VERBATIM_NL,
    NEW_BOOK_ID,
    NOT_COUNTED_CYCLE_IDS,
    STOP_CRITERION_PREREG_PATH,
    STOP_CRITERION_TRIPPED,
    STOPTELLING_ANSWERS_NAME,
    STOPTELLING_ANSWERS_PATH,
    STOPTELLING_ANSWERS_SHA256,
    n_full_cycles,
    n_high_power_fail_after_costs_cycles,
    n_prereg_hypotheses,
    n_survivors,
    stop_criterion_status,
)


@pytest.mark.unit
def test_fabriek_answers_sha_is_frozen() -> None:
    digest = hashlib.sha256(FABRIEK_ANSWERS_PATH.read_bytes()).hexdigest()
    assert digest == FABRIEK_ANSWERS_SHA256
    assert digest.startswith("de73d38c")
    assert FABRIEK_ANSWERS_NAME in str(FABRIEK_ANSWERS_PATH)


@pytest.mark.unit
def test_stoptelling_answers_sha_is_frozen() -> None:
    digest = hashlib.sha256(STOPTELLING_ANSWERS_PATH.read_bytes()).hexdigest()
    assert digest == STOPTELLING_ANSWERS_SHA256
    assert digest.startswith("547f3047")
    assert STOPTELLING_ANSWERS_NAME in str(STOPTELLING_ANSWERS_PATH)
    assert STOP_CRITERION_TRIPPED is True


@pytest.mark.unit
def test_stop_prereg_contains_verbatim_criterion() -> None:
    text = STOP_CRITERION_PREREG_PATH.read_text(encoding="utf-8")
    assert HARD_STOP_VERBATIM_NL in text
    assert HARD_STOP_VERBATIM_EN in text
    assert "de73d38c" in text
    assert "atr-es" in text
    assert "limited-es" in text
    assert "postkill-es" in text
    assert "Not counted" in text
    assert "search space is declared insufficient" in text.lower()
    assert "split_books" in text
    assert "across books" in text
    assert "a970bf17" in text
    assert "547f3047" in text
    assert "research_line_stopped" in text
    assert "exactly 1 cycle" in text
    assert STOP_CRITERION_TRIPPED is True
    assert "TODO" not in text


@pytest.mark.unit
def test_counted_cycles_are_three_full_zero_survivors() -> None:
    assert tuple(item.cycle_id for item in COUNTED_CYCLES) == (
        "atr-es",
        "limited-es",
        "postkill-es",
    )
    assert n_full_cycles() == 3
    assert n_prereg_hypotheses() == 19
    assert n_survivors() == 0
    assert n_high_power_fail_after_costs_cycles() == 2
    assert "first" in NOT_COUNTED_CYCLE_IDS
    assert "four-instrument" in NOT_COUNTED_CYCLE_IDS
    assert "null-only" in NOT_COUNTED_CYCLE_IDS
    status = stop_criterion_status()
    assert status.three_full_cycles_zero_survivors is True
    assert status.sixty_to_eighty_prereg_zero_survivors is False
    assert status.two_high_power_all_fail_after_costs is True
    assert status.search_space_insufficient is True
    assert status.counts_across_books is True
    assert COUNTS_ACROSS_BOOKS is True
    assert STOP_CRITERION_TRIPPED is True
    assert status.search_space_insufficient is STOP_CRITERION_TRIPPED
    assert status.n_books == 1
    assert {item.book_id for item in COUNTED_CYCLES} == {CLOSED_BOOK_ID}
    reports = Path("experiments/reports")
    for item in COUNTED_CYCLES:
        payload_path = reports / item.report
        assert payload_path.is_file()
        text = payload_path.read_text(encoding="utf-8")
        assert '"n_survivors": 0' in text


@pytest.mark.unit
def test_stop_counter_does_not_reset_when_the_ledger_splits() -> None:
    extra = CountedCycle(
        cycle_id="future-rv",
        n_prereg_hypotheses=1,
        n_killed=1,
        n_survivors=0,
        high_positive_control_power=True,
        all_real_hypotheses_fail_after_costs=True,
        counts_as_full_cycle=True,
        report="phase5_p2_postkill_end.json",
        book_id=NEW_BOOK_ID,
    )
    status = stop_criterion_status(COUNTED_CYCLES + (extra,))
    assert status.n_full_cycles == 4
    assert status.n_prereg_hypotheses == 20
    assert status.n_survivors == 0
    assert status.n_books == 2
    assert status.counts_across_books is True
    assert extra.book_id == NEW_BOOK_ID
