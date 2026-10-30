"""Rolling trial ledger after the book split: closed N=150, new book N=0."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from lumina_research.cycles.nq_research import KIND_RELATIVE_VALUE
from lumina_research.cycles.null_model import NULL_BUILDER
from lumina_research.cycles.stop_criterion import (
    CLOSED_BOOK_ID as STOP_CLOSED_BOOK_ID,
)
from lumina_research.cycles.stop_criterion import (
    NEW_BOOK_ID as STOP_NEW_BOOK_ID,
)
from lumina_research.cycles.stop_criterion import n_full_cycles, n_prereg_hypotheses, n_survivors
from lumina_research.cycles.trial_ledger import (
    BOEKSPLIT_ANSWERS_PATH,
    BOEKSPLIT_ANSWERS_SHA256,
    CLOSED_BOOK_BLOCKS_REASON,
    CLOSED_BOOK_FINAL_N,
    CLOSED_BOOK_ID,
    DEFAULT_LEDGER_PATH,
    MARKETS,
    NEW_BOOK_BLOCKS_REASON,
    NEW_BOOK_ID,
    NEW_BOOK_STATUS,
    RULE_SPLIT_BOOKS,
    LedgerBlocksRun,
    LedgerRefused,
    assert_ledger_allows_run,
    dsr_pbo_n_for_run,
    load_trial_ledger,
)
from lumina_research.proof.cli import main as proof_main
from lumina_research.validation.thresholds import FLOOR_DSR_PROBABILITY_MIN


def _zero_markets() -> dict[str, int]:
    return {"ES": 0, "MES": 0, "MNQ": 0, "NQ": 0}


def _closed_markets() -> dict[str, int]:
    return {"ES": 150, "MES": 0, "MNQ": 0, "NQ": 0}


def _payload(*, open_book: bool = False, prereg: dict[str, object] | None = None) -> dict[str, object]:
    active: dict[str, object] = {
        "id": NEW_BOOK_ID,
        "status": "open" if open_book else NEW_BOOK_STATUS,
        "open": open_book,
        "search_space_prereg": prereg,
        "n_by_market": _zero_markets(),
        "n_total": 0,
        "dsr_pbo_n": 0,
    }
    return {
        "schema": "lumina.research.trial_ledger.v2",
        "chosen_rule": RULE_SPLIT_BOOKS,
        "min_dsr_raised": False,
        "dsr_probability_min": FLOOR_DSR_PROBABILITY_MIN,
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
    assert ledger.active_open is False
    assert ledger.active_status == NEW_BOOK_STATUS
    assert ledger.blocks_run is True
    text = DEFAULT_LEDGER_PATH.read_text(encoding="utf-8")
    assert "TODO" not in text
    assert "decision_required" not in text
    with pytest.raises(LedgerBlocksRun, match="closed"):
        assert_ledger_allows_run(cycle="postkill-es")
    with pytest.raises(LedgerBlocksRun, match="search-space prereg"):
        assert_ledger_allows_run()


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
