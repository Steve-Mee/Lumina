"""11:06 existence-test lock: two tests, separate non-DSR book, not run."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from lumina_research.cycles.existence import (
    AMBIGUITY_COST_OF_ONE_TRADE,
    AMBIGUITY_IDS,
    AMBIGUITY_RECONSTITUTION,
    AMBIGUITY_ROLL_WEEK,
    AMBIGUITY_T_TEST_VS_BOOTSTRAP,
    AMBIGUITY_TREND_20D_UNIT,
    AMBIGUITY_TREND_60_120,
    ANSWERS_PATH,
    ANSWERS_SHA256,
    BLOCKED_EVENT_KINDS,
    BOOK_ID,
    COUNTS_IN_DSR_N,
    EVENT_MONTH_END,
    EVENT_QUARTER_END,
    EVENT_RECONSTITUTION,
    EVENT_ROLL_WEEK,
    EXISTENCE_RUN_REFUSED,
    IMPLEMENTED_EVENT_KINDS,
    NOT_IN_THIS_LOCK,
    PIN_ES_SHA256,
    PREREG_PATH,
    SPEC_SHA256,
    TEST_CALENDAR,
    TEST_IDS,
    TEST_OVERNIGHT,
    TREND_IMPLEMENTED_LENGTHS,
    TREND_LOOKBACK_LENGTH,
    TREND_MECHANISM_LENGTHS,
    TRIALS_RUN,
    ExistenceRefused,
    assert_existence_lock,
    calendar_rebalance_events,
    canonical_spec,
    cost_of_one_trade_usd,
    excess_return_statistic,
    existence_book_payload,
    reconstitution_dates,
    require_implemented_event_kind,
    roll_week_sessions,
    run_existence_tests,
    spec_sha256,
    trend_lookback_length,
    trend_lookback_unit,
)
from lumina_research.cycles.final_cycle import PIN_ES_SHA256 as FINAL_ES_SHA256
from lumina_research.cycles.nq_research import HOLDOUT_PIN_Z
from lumina_research.cycles.trial_ledger import (
    DEFAULT_LEDGER_PATH,
    LINE_STOPPED_REASON,
    NEW_BOOK_ID,
    LedgerBlocksRun,
    LedgerRefused,
    assert_ledger_allows_run,
    dsr_pbo_n_for_run,
    load_trial_ledger,
)
from lumina_research.proof.cli import build_parser, main as proof_main


@pytest.mark.unit
def test_bestaanstoetsen_answers_sha_is_frozen() -> None:
    digest = hashlib.sha256(ANSWERS_PATH.read_bytes()).hexdigest()
    assert digest == ANSWERS_SHA256
    assert digest.startswith("6b9dc2a8")
    text = ANSWERS_PATH.read_text(encoding="utf-8")
    assert "NOT Steve" in text
    assert "Calendar rebalancing" in text
    assert "20/60/120" in text
    assert "do NOT count in DSR N" in text
    assert "TODO" not in text


@pytest.mark.unit
def test_existence_spec_hash_is_locked() -> None:
    assert spec_sha256() == SPEC_SHA256
    assert SPEC_SHA256.startswith("5a3a54f4")
    assert_existence_lock()
    spec = canonical_spec()
    assert spec["book_id"] == BOOK_ID
    assert spec["counts_in_dsr_n"] is False
    assert spec["trials_run"] is False
    assert spec["instrument"] == "ES"
    assert spec["nq_trading"] is False
    assert spec["holdout_pin"] == HOLDOUT_PIN_Z
    assert spec["holdout_opened"] is False
    assert spec["optimization"] is False
    assert spec["atr_es_retest"] is False
    assert spec["looser_threshold_accepted"] is False
    assert spec["test_ids"] == list(TEST_IDS)
    assert spec["not_in_this_lock"] == list(NOT_IN_THIS_LOCK)
    assert spec["pin_es_sha256"] == PIN_ES_SHA256 == FINAL_ES_SHA256
    tests = spec["tests"]
    assert isinstance(tests, dict)
    calendar = tests[TEST_CALENDAR]
    overnight = tests[TEST_OVERNIGHT]
    assert isinstance(calendar, dict)
    assert isinstance(overnight, dict)
    assert calendar["event_kinds_implemented"] == list(IMPLEMENTED_EVENT_KINDS)
    assert calendar["event_kinds_blocked"] == list(BLOCKED_EVENT_KINDS)
    assert overnight["trend_lookback_length"] == 20
    assert overnight["trend_lookback_unit"] == "unresolved"
    assert overnight["trend_60_120_implemented"] is False
    assert overnight["combined_overnight_and_20d_filter"] is True
    raw_ambiguities = spec["ambiguities"]
    assert isinstance(raw_ambiguities, list)
    ambiguity_ids = [item["id"] for item in raw_ambiguities if isinstance(item, dict)]
    assert tuple(ambiguity_ids) == AMBIGUITY_IDS
    assert "reconstitution_dates_source" in AMBIGUITY_IDS
    assert "roll_week_definition" in AMBIGUITY_IDS
    assert "cost_of_one_trade" in AMBIGUITY_IDS
    assert "t_test_vs_bootstrap" in AMBIGUITY_IDS
    assert "trend_60_120_not_in_rule" in AMBIGUITY_IDS
    assert TRIALS_RUN is False
    assert COUNTS_IN_DSR_N is False
    prereg = PREREG_PATH.read_text(encoding="utf-8")
    assert SPEC_SHA256 in prereg
    assert "Not run" in prereg or "not run" in prereg.lower()
    source = Path("lumina_research/cycles/existence.py").read_text(encoding="utf-8")
    assert "TODO" not in source
    assert "from lumina_research.cycles.rolls" not in source
    assert "NT8_ROLL_DATES" in source


@pytest.mark.unit
def test_existence_run_is_refused() -> None:
    with pytest.raises(ExistenceRefused, match="locked and not run"):
        run_existence_tests()
    with pytest.raises(ExistenceRefused, match="locked and not run"):
        run_existence_tests(es_csv=Path("/tmp/lumina-es/ES_pre_holdout.csv"))
    assert EXISTENCE_RUN_REFUSED.startswith("existence tests are locked")


@pytest.mark.unit
def test_cli_existence_refuses_without_dsr_ledger_or_runner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def _must_not_lock(_path: Path) -> None:
        raise AssertionError("existence must skip null lock")

    def _must_not_ledger(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("existence must skip DSR ledger")

    def _must_not_run(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("existence cycle must not start a research runner")

    monkeypatch.setattr("lumina_research.proof.cli.assert_research_allowed", _must_not_lock)
    monkeypatch.setattr("lumina_research.proof.cli.assert_ledger_allows_run", _must_not_ledger)
    monkeypatch.setattr("lumina_research.proof.cli.run_research_cycles", _must_not_run)
    monkeypatch.setattr("lumina_research.proof.cli.run_final_cycle", _must_not_run)
    parser = build_parser()
    args = parser.parse_args(["research", "--cycle", "existence"])
    assert args.cycle == "existence"
    code = proof_main(
        [
            "research",
            "--cycle",
            "existence",
            "--work-dir",
            str(tmp_path),
            "--report-dir",
            str(tmp_path),
        ]
    )
    assert code == 2
    captured = capsys.readouterr()
    assert EXISTENCE_RUN_REFUSED in captured.err
    assert "research_line_stopped" not in captured.err


@pytest.mark.unit
def test_month_end_and_quarter_end_from_session_dates() -> None:
    january = calendar_rebalance_events((date(2024, 1, 30), date(2024, 1, 31), date(2024, 2, 1)))
    march = calendar_rebalance_events((date(2024, 3, 28), date(2024, 3, 29), date(2024, 4, 1)))
    june = calendar_rebalance_events((date(2024, 6, 27), date(2024, 6, 28), date(2024, 7, 1)))
    december = calendar_rebalance_events((date(2024, 12, 30), date(2024, 12, 31)))
    assert {item.session: item.kinds for item in january} == {date(2024, 1, 31): (EVENT_MONTH_END,)}
    assert {item.session: item.kinds for item in march} == {date(2024, 3, 29): (EVENT_MONTH_END, EVENT_QUARTER_END)}
    assert {item.session: item.kinds for item in june} == {date(2024, 6, 28): (EVENT_MONTH_END, EVENT_QUARTER_END)}
    assert {item.session: item.kinds for item in december} == {date(2024, 12, 31): (EVENT_MONTH_END, EVENT_QUARTER_END)}
    truncated = calendar_rebalance_events((date(2024, 1, 29), date(2024, 1, 30)))
    assert truncated == ()
    lone_month_end = calendar_rebalance_events((date(2024, 1, 31),))
    assert lone_month_end[0].kinds == (EVENT_MONTH_END,)


@pytest.mark.unit
def test_reconstitution_roll_week_cost_and_statistic_are_unresolved() -> None:
    with pytest.raises(ExistenceRefused, match="reconstitution"):
        reconstitution_dates()
    with pytest.raises(ExistenceRefused, match="roll-week"):
        roll_week_sessions()
    with pytest.raises(ExistenceRefused, match="reconstitution"):
        require_implemented_event_kind(EVENT_RECONSTITUTION)
    with pytest.raises(ExistenceRefused, match="roll-week"):
        require_implemented_event_kind(EVENT_ROLL_WEEK)
    require_implemented_event_kind(EVENT_MONTH_END)
    require_implemented_event_kind(EVENT_QUARTER_END)
    with pytest.raises(ExistenceRefused, match="cost of one trade"):
        cost_of_one_trade_usd()
    with pytest.raises(ExistenceRefused, match="t-test or bootstrap"):
        excess_return_statistic()
    with pytest.raises(ExistenceRefused, match="unit"):
        trend_lookback_unit()
    assert trend_lookback_length() == TREND_LOOKBACK_LENGTH == 20
    assert TREND_MECHANISM_LENGTHS == (20, 60, 120)
    assert TREND_IMPLEMENTED_LENGTHS == (20,)
    assert 60 not in TREND_IMPLEMENTED_LENGTHS
    assert 120 not in TREND_IMPLEMENTED_LENGTHS
    assert AMBIGUITY_RECONSTITUTION
    assert "NT8_ROLL_DATES" in AMBIGUITY_ROLL_WEEK
    assert "5.74" in AMBIGUITY_COST_OF_ONE_TRADE
    assert "bootstrap" in AMBIGUITY_T_TEST_VS_BOOTSTRAP
    assert "unresolved" in AMBIGUITY_TREND_20D_UNIT
    assert "not in the locked rule" in AMBIGUITY_TREND_60_120


@pytest.mark.unit
def test_canonical_ledger_keeps_existence_book_out_of_dsr_n() -> None:
    ledger = load_trial_ledger()
    assert ledger.active_book_id == NEW_BOOK_ID
    assert ledger.research_line_stopped is True
    assert ledger.dsr_pbo_n == 74
    assert dsr_pbo_n_for_run(ledger) == 74
    assert ledger.existence_book is not None
    assert ledger.existence_book.book_id == BOOK_ID
    assert ledger.existence_book.book_id != NEW_BOOK_ID
    assert ledger.existence_book.counts_in_dsr_n is False
    assert ledger.existence_book.trials_run is False
    assert ledger.existence_book.spec_sha256 == SPEC_SHA256
    payload = json.loads(DEFAULT_LEDGER_PATH.read_text(encoding="utf-8"))
    answers = payload["answers"]
    assert isinstance(answers, dict)
    assert answers["bestaanstoetsen_sha256"] == ANSWERS_SHA256
    book = payload["existence_book"]
    assert book == existence_book_payload()
    assert book["counts_in_dsr_n"] is False
    assert book["trials_run"] is False
    assert payload["stop_criterion"]["n_full_cycles"] == 3
    assert payload["stop_criterion"]["n_prereg_hypotheses"] == 19
    assert payload["active_book"]["id"] == NEW_BOOK_ID
    with pytest.raises(LedgerBlocksRun, match="research_line_stopped"):
        assert_ledger_allows_run(cycle="existence")
    assert LINE_STOPPED_REASON.startswith("trial ledger blocks")


@pytest.mark.unit
def test_loader_refuses_existence_book_in_dsr_n_or_marked_run(tmp_path: Path) -> None:
    payload = json.loads(DEFAULT_LEDGER_PATH.read_text(encoding="utf-8"))
    book = payload["existence_book"]
    assert isinstance(book, dict)
    book["counts_in_dsr_n"] = True
    counted = tmp_path / "counted.json"
    counted.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(LedgerRefused, match="must not count in DSR N"):
        load_trial_ledger(counted)
    book["counts_in_dsr_n"] = False
    book["trials_run"] = True
    ran = tmp_path / "ran.json"
    ran.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(LedgerRefused, match="must not be marked run"):
        load_trial_ledger(ran)
    book["trials_run"] = False
    book["nq_trading"] = True
    nq = tmp_path / "nq.json"
    nq.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(LedgerRefused, match="must not trade NQ"):
        load_trial_ledger(nq)
