"""Rolling trial ledger after the book split: closed N=150, new book N=0."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from lumina_research.cycles.final_cycle import (
    DATA_ANSWERS_SHA256,
    FINALE_PREREG_SHA256,
    LH03_ANSWERS_SHA256,
    RV02_POWER_N_TRADES,
)
from lumina_research.cycles.nq_research import KIND_RELATIVE_VALUE
from lumina_research.cycles.null_model import NULL_BUILDER
from lumina_research.cycles.search_space import NEW_BOOK_HYPOTHESIS_CAP, NEW_BOOK_MAX_CYCLES
from lumina_research.cycles.stop_criterion import (
    CLOSED_BOOK_ID as STOP_CLOSED_BOOK_ID,
    NEW_BOOK_ID as STOP_NEW_BOOK_ID,
    STOP_CRITERION_TRIPPED,
    STOPTELLING_ANSWERS_PATH,
    STOPTELLING_ANSWERS_SHA256,
    n_full_cycles,
    n_prereg_hypotheses,
    n_survivors,
    stop_criterion_status,
)
from lumina_research.cycles.trial_ledger import (
    BOEKSPLIT_ANSWERS_PATH,
    BOEKSPLIT_ANSWERS_SHA256,
    CLOSED_BOOK_BLOCKS_REASON,
    CLOSED_BOOK_FINAL_N,
    CLOSED_BOOK_ID,
    DEFAULT_LEDGER_PATH,
    LEDGER_SCHEMA,
    LINE_STATE_CYCLE_COMPLETE,
    LINE_STATE_STOPPED,
    LINE_STOPPED_REASON,
    MARKETS,
    NEW_BOOK_BLOCKS_REASON,
    NEW_BOOK_ID,
    NEW_BOOK_STATUS,
    RULE_SPLIT_BOOKS,
    SECOND_CYCLE_REFUSED,
    LedgerBlocksRun,
    LedgerRefused,
    assert_ledger_allows_run,
    dsr_pbo_n_for_run,
    line_state_after_cycle,
    load_trial_ledger,
)
from lumina_research.proof.cli import main as proof_main
from lumina_research.validation.thresholds import FLOOR_DSR_PROBABILITY_MIN


def _zero_markets() -> dict[str, int]:
    return {"ES": 0, "MES": 0, "MNQ": 0, "NQ": 0}


def _closed_markets() -> dict[str, int]:
    return {"ES": 150, "MES": 0, "MNQ": 0, "NQ": 0}


def _payload(
    *,
    open_book: bool = False,
    prereg: dict[str, object] | None = None,
    status: str | None = None,
    n_cycles_completed: int = 0,
    n_hypotheses_stated: int | None = None,
    research_line_stopped: bool = False,
) -> dict[str, object]:
    stated = n_hypotheses_stated
    if stated is None and open_book and prereg is not None:
        raw_count = prereg.get("n_hypotheses")
        stated = raw_count if isinstance(raw_count, int) else 1
    active: dict[str, object] = {
        "id": NEW_BOOK_ID,
        "status": status if status is not None else ("open" if open_book else NEW_BOOK_STATUS),
        "open": open_book,
        "search_space_prereg": prereg,
        "n_cycles_allowed": NEW_BOOK_MAX_CYCLES,
        "n_cycles_completed": n_cycles_completed,
        "n_hypotheses_cap": NEW_BOOK_HYPOTHESIS_CAP,
        "n_hypotheses_stated": stated,
        "research_line_stopped": research_line_stopped,
        "n_by_market": _zero_markets(),
        "n_total": 0,
        "dsr_pbo_n": 0,
    }
    return {
        "schema": LEDGER_SCHEMA,
        "chosen_rule": RULE_SPLIT_BOOKS,
        "min_dsr_raised": False,
        "dsr_probability_min": FLOOR_DSR_PROBABILITY_MIN,
        "fundamental_change_approval": None,
        "closed_books": [
            {
                "id": CLOSED_BOOK_ID,
                "status": "closed",
                "n_by_market": _closed_markets(),
                "n_total": CLOSED_BOOK_FINAL_N,
                "dsr_pbo_n": CLOSED_BOOK_FINAL_N,
            }
        ],
        "active_book": active,
    }


def _write(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _open_prereg(path: Path) -> dict[str, object]:
    path.write_text("# fixture search-space prereg\n", encoding="utf-8")
    return {
        "lower_turnover": True,
        "longer_horizon": True,
        "relative_value_config_ids": ["p2rv-es-nq-guard-test"],
        "null_builder": NULL_BUILDER,
        "positive_control_included": True,
        "committed_path": str(path),
        "same_space_short_horizon": False,
        "n_hypotheses": 1,
        "nq_request": {
            "hypothesis_kind": KIND_RELATIVE_VALUE,
            "instruments": ["ES", "NQ"],
            "tape_window": "pre_holdout",
            "holdout_opened": False,
            "holdout_pin": "2026-01-28T23:00:00Z",
            "null_builder": NULL_BUILDER,
            "positive_control_included": True,
            "config_ids": ["p2rv-es-nq-guard-test"],
            "reuses_prereg_ids": [],
            "sim_requested": False,
            "promotion_requested": False,
        },
    }


@pytest.mark.unit
def test_boeksplit_answers_sha_is_frozen() -> None:
    digest = hashlib.sha256(BOEKSPLIT_ANSWERS_PATH.read_bytes()).hexdigest()
    assert digest == BOEKSPLIT_ANSWERS_SHA256
    assert digest.startswith("a970bf17")


@pytest.mark.unit
def test_stoptelling_answers_sha_is_frozen() -> None:
    digest = hashlib.sha256(STOPTELLING_ANSWERS_PATH.read_bytes()).hexdigest()
    assert digest == STOPTELLING_ANSWERS_SHA256
    assert digest.startswith("547f3047")


@pytest.mark.unit
def test_canonical_ledger_closes_old_book_and_holds_new_book_at_zero() -> None:
    ledger = load_trial_ledger()
    assert ledger.path == DEFAULT_LEDGER_PATH
    assert ledger.chosen_rule == RULE_SPLIT_BOOKS
    assert ledger.min_dsr_raised is False
    assert ledger.dsr_probability_min == FLOOR_DSR_PROBABILITY_MIN
    assert ledger.closed_book_id == CLOSED_BOOK_ID
    assert ledger.closed_n_for("ES") == 150
    assert ledger.closed_n_for("MES") == 0
    assert ledger.closed_n_for("MNQ") == 0
    assert ledger.closed_n_for("NQ") == 0
    assert ledger.closed_n_total == CLOSED_BOOK_FINAL_N
    assert ledger.active_book_id == NEW_BOOK_ID
    assert tuple(ledger.active_n_by_market) == MARKETS
    assert ledger.n_for("ES") == 0
    assert ledger.n_for("MES") == 0
    assert ledger.n_for("MNQ") == 0
    assert ledger.n_for("NQ") == 0
    assert ledger.active_n_total == 0
    assert ledger.dsr_pbo_n == 0
    assert dsr_pbo_n_for_run(ledger) == 0
    assert dsr_pbo_n_for_run(ledger) != ledger.closed_n_total
    assert ledger.closed_book_id == STOP_CLOSED_BOOK_ID
    assert ledger.active_book_id == STOP_NEW_BOOK_ID
    assert n_full_cycles() == 3
    assert n_prereg_hypotheses() == 19
    assert n_survivors() == 0
    assert ledger.active_open is True
    assert ledger.active_status == "open"
    assert ledger.n_cycles_allowed == 1
    assert ledger.n_cycles_completed == 0
    assert ledger.n_hypotheses_cap == 25
    assert ledger.n_hypotheses_stated == 6
    assert ledger.research_line_stopped is False
    assert ledger.blocks_run is False
    assert NEW_BOOK_MAX_CYCLES == 1
    assert NEW_BOOK_HYPOTHESIS_CAP == 25
    assert STOP_CRITERION_TRIPPED is True
    text = DEFAULT_LEDGER_PATH.read_text(encoding="utf-8")
    assert "TODO" not in text
    assert "decision_required" not in text
    payload = json.loads(text)
    stop_block = payload["stop_criterion"]
    live = stop_criterion_status()
    assert isinstance(stop_block, dict)
    assert stop_block["tripped"] is True
    assert stop_block["n_full_cycles"] == live.n_full_cycles == 3
    assert stop_block["n_prereg_hypotheses"] == live.n_prereg_hypotheses == 19
    assert stop_block["n_survivors"] == live.n_survivors == 0
    assert stop_block["counts_across_books"] is True
    assert stop_block["reset_by_split"] is False
    answers = payload["answers"]
    assert isinstance(answers, dict)
    assert answers["stoptelling_sha256"] == STOPTELLING_ANSWERS_SHA256
    assert answers["finale_cyclus_sha256"] == FINALE_PREREG_SHA256
    assert answers["data_sha256"] == DATA_ANSWERS_SHA256
    assert answers["lh03_sha256"] == LH03_ANSWERS_SHA256
    assert payload["active_book"]["dropped_config_ids"] == ["p2s-lh-02", "p2s-lh-04"]
    rv02 = payload["active_book"]["rv02_low_power"]
    assert isinstance(rv02, dict)
    assert rv02["n_trades"] == RV02_POWER_N_TRADES == 59
    assert rv02["low_power_risk_accepted"] is True
    lh03_atr = payload["active_book"]["lh03_atr"]
    assert isinstance(lh03_atr, dict)
    assert lh03_atr["clarification_not_hypothesis_change"] is True
    assert lh03_atr["source"] == "intraday_5m_atr14_strictly_before_event"
    assert payload["active_book"]["n_hypotheses_stated"] == 6
    pins = payload["active_book"]["data_pins"]
    assert isinstance(pins, dict)
    assert pins["vix_filter_rule"] == "previous_day_close"
    assert pins["nq_pre_holdout_sha256"].startswith("d60dd0c2")
    assert payload["fundamental_change_approval"] is None
    assert payload["active_book"]["n_cycles_allowed"] == 1
    assert payload["active_book"]["n_hypotheses_cap"] == 25
    with pytest.raises(LedgerBlocksRun, match="closed"):
        assert_ledger_allows_run(cycle="postkill-es")
    allowed = assert_ledger_allows_run()
    assert allowed.dsr_pbo_n == 0
    assert allowed.n_hypotheses_stated == 6


@pytest.mark.unit
def test_new_book_opens_only_with_search_space_prereg(tmp_path: Path) -> None:
    waiting = _write(tmp_path / "waiting.json", _payload())
    with pytest.raises(LedgerBlocksRun, match="search-space prereg"):
        assert_ledger_allows_run(waiting)
    opened = _write(
        tmp_path / "open.json",
        _payload(open_book=True, prereg=_open_prereg(tmp_path / "space.md")),
    )
    ledger = assert_ledger_allows_run(opened, cycle="future-rv")
    assert ledger.active_open is True
    assert ledger.dsr_pbo_n == 0
    with pytest.raises(LedgerBlocksRun, match="closed"):
        assert_ledger_allows_run(opened, cycle="limited-es")


@pytest.mark.unit
def test_loader_refuses_open_book_without_prereg(tmp_path: Path) -> None:
    with pytest.raises(LedgerRefused, match="search-space prereg"):
        load_trial_ledger(_write(tmp_path / "bad.json", _payload(open_book=True)))


@pytest.mark.unit
def test_loader_refuses_inconsistent_totals(tmp_path: Path) -> None:
    payload = _payload()
    book = payload["active_book"]
    assert isinstance(book, dict)
    book["n_total"] = 1
    with pytest.raises(LedgerRefused, match="n_total"):
        load_trial_ledger(_write(tmp_path / "bad.json", payload))


@pytest.mark.unit
def test_loader_refuses_missing_file(tmp_path: Path) -> None:
    with pytest.raises(LedgerRefused, match="missing"):
        load_trial_ledger(tmp_path / "nope.json")


@pytest.mark.unit
def test_canonical_module_has_no_todo() -> None:
    text = Path("lumina_research/cycles/trial_ledger.py").read_text(encoding="utf-8")
    assert "TODO" not in text
    assert "FIXME" not in text
    assert RULE_SPLIT_BOOKS in text


@pytest.mark.unit
def test_cli_closed_book_cycle_is_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lumina_research.proof.cli.assert_research_allowed", lambda _path: None)

    def _must_not_run(**_kwargs: object) -> None:
        raise AssertionError("closed-book cycle must not run after the split")

    monkeypatch.setattr("lumina_research.proof.cli.run_limited_es_cycle", _must_not_run)
    code = proof_main(
        [
            "research",
            "--cycle",
            "limited-es",
            "--es-csv",
            "x.csv",
            "--work-dir",
            str(tmp_path),
            "--report-dir",
            str(tmp_path),
        ]
    )
    assert code == 2
    assert CLOSED_BOOK_BLOCKS_REASON.startswith("trial ledger blocks")
    assert NEW_BOOK_BLOCKS_REASON.startswith("trial ledger blocks")
    assert SECOND_CYCLE_REFUSED.startswith("trial ledger blocks")
    assert LINE_STOPPED_REASON.startswith("trial ledger blocks")


@pytest.mark.unit
def test_line_state_after_cycle_zero_survivors_stops_the_line() -> None:
    assert line_state_after_cycle(n_survivors=0, n_cycles_completed_before=0) == LINE_STATE_STOPPED
    assert line_state_after_cycle(n_survivors=1, n_cycles_completed_before=0) == LINE_STATE_CYCLE_COMPLETE
    with pytest.raises(LedgerBlocksRun, match="2nd cycle"):
        line_state_after_cycle(n_survivors=0, n_cycles_completed_before=1)
    with pytest.raises(LedgerBlocksRun, match="2nd cycle"):
        line_state_after_cycle(n_survivors=3, n_cycles_completed_before=1)
    with pytest.raises(LedgerRefused, match="n_survivors"):
        line_state_after_cycle(n_survivors=-1, n_cycles_completed_before=0)


@pytest.mark.unit
def test_second_cycle_is_refused_even_with_leftover_hypothesis_budget(tmp_path: Path) -> None:
    complete = _write(
        tmp_path / "complete.json",
        _payload(
            status=LINE_STATE_CYCLE_COMPLETE,
            n_cycles_completed=1,
            n_hypotheses_stated=20,
        ),
    )
    ledger = load_trial_ledger(complete)
    assert ledger.active_open is False
    assert ledger.n_cycles_completed == 1
    assert ledger.n_hypotheses_stated == 20
    assert ledger.research_line_stopped is False
    assert ledger.blocks_run is True
    assert ledger.dsr_pbo_n == 0
    with pytest.raises(LedgerBlocksRun, match="2nd cycle"):
        assert_ledger_allows_run(complete)


@pytest.mark.unit
def test_research_line_stopped_refuses_further_runs(tmp_path: Path) -> None:
    stopped = _write(
        tmp_path / "stopped.json",
        _payload(
            status=LINE_STATE_STOPPED,
            n_cycles_completed=1,
            n_hypotheses_stated=1,
            research_line_stopped=True,
        ),
    )
    ledger = load_trial_ledger(stopped)
    assert ledger.active_status == LINE_STATE_STOPPED
    assert ledger.research_line_stopped is True
    assert ledger.blocks_run is True
    assert ledger.dsr_pbo_n == 0
    with pytest.raises(LedgerBlocksRun, match="research_line_stopped"):
        assert_ledger_allows_run(stopped)


@pytest.mark.unit
def test_loader_refuses_cap_and_reopen_violations(tmp_path: Path) -> None:
    two_cycles = _payload()
    book = two_cycles["active_book"]
    assert isinstance(book, dict)
    book["n_cycles_allowed"] = 2
    with pytest.raises(LedgerRefused, match="exactly 1 cycle"):
        load_trial_ledger(_write(tmp_path / "two.json", two_cycles))
    wide_cap = _payload()
    cap_book = wide_cap["active_book"]
    assert isinstance(cap_book, dict)
    cap_book["n_hypotheses_cap"] = 80
    with pytest.raises(LedgerRefused, match="cap must be 25"):
        load_trial_ledger(_write(tmp_path / "cap.json", wide_cap))
    approval = _payload()
    approval["fundamental_change_approval"] = "new-data-sources"
    with pytest.raises(LedgerRefused, match="cannot be reopened"):
        load_trial_ledger(_write(tmp_path / "reopen.json", approval))
    completed_twice = _payload(status=LINE_STATE_CYCLE_COMPLETE, n_cycles_completed=2)
    with pytest.raises(LedgerRefused, match="more than 1 cycle"):
        load_trial_ledger(_write(tmp_path / "twice.json", completed_twice))


@pytest.mark.unit
def test_loader_refuses_untripped_stop_block(tmp_path: Path) -> None:
    payload = _payload()
    payload["stop_criterion"] = {
        "tripped": False,
        "n_full_cycles": 3,
        "n_prereg_hypotheses": 19,
        "n_survivors": 0,
        "counts_across_books": True,
        "reset_by_split": False,
    }
    with pytest.raises(LedgerRefused, match="tripped"):
        load_trial_ledger(_write(tmp_path / "untripped.json", payload))


@pytest.mark.unit
def test_open_book_stated_count_must_match_prereg(tmp_path: Path) -> None:
    prereg = _open_prereg(tmp_path / "space.md")
    mismatch = _write(
        tmp_path / "mismatch.json",
        _payload(open_book=True, prereg=prereg, n_hypotheses_stated=2),
    )
    with pytest.raises(LedgerRefused, match="n_hypotheses_stated"):
        load_trial_ledger(mismatch)
