"""06:38 post-kill follow-up: diagnostics, three p2p-* locks, CLI, no tape run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_research.cycles.data import DataStatus
from lumina_research.cycles.geometry import family_break_even_win_rate
from lumina_research.cycles.postkill_es import (
    ANSWERS_NAME,
    ANSWERS_SHA256,
    BREAKOUT_STRETCH_ATR,
    LOCKED_IDS,
    PREREG_NAME,
    PRIOR_LIMITED_N_TRIALS,
    TOD_LOOKBACK,
    breakout_diagnostics_from_limited_pit,
    family_close_verdicts,
    overall_verdict,
    postkill_es_specs,
    seed_prior_dsr_n,
    tod_diagnostics_from_limited_pit,
    write_blocked_report,
)
from lumina_research.cycles.positive_control import BREAKOUT_MIDPOINT_ATR, FADE_MIDPOINT_ATR
from lumina_research.cycles.report import CycleReport
from lumina_research.proof.cli import build_parser, main as proof_main
from lumina_research.validation.thresholds import FLOOR_DSR_PROBABILITY_MIN
from lumina_research.validation.trial_registry import TrialRegistry


@pytest.mark.unit
def test_postkill_answers_sha_is_frozen() -> None:
    path = Path("docs/research") / ANSWERS_NAME
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == ANSWERS_SHA256
    assert digest.startswith("311ea60a")


@pytest.mark.unit
def test_postkill_preregister_locks_three_fresh_ids() -> None:
    text = Path("experiments/reports") / PREREG_NAME
    body = text.read_text(encoding="utf-8")
    assert "p2p-rc-es" in body
    assert "p2p-vx-es" in body
    assert "p2p-tod-es" in body
    assert "2.4" in body
    assert "**45**" in body
    assert "311ea60a" in body
    assert "no extra variants" in body.lower() or "No extra variants" in body
    assert "plants" in body.lower()
    assert "NQ closed" in body
    assert "p2l-rc-es" in body
    assert "Never promote on gross" in body


@pytest.mark.unit
def test_postkill_specs_match_preregister() -> None:
    specs = postkill_es_specs()
    assert tuple(item.config_id for item in specs) == LOCKED_IDS
    assert {item.instrument for item in specs} == {"ES"}
    assert all(item.session_filter == "rth" for item in specs)
    assert all(item.session_end_flatten for item in specs)
    assert all(item.time_stop_bars == 2000 for item in specs)
    assert all(item.has_fit_step is False for item in specs)
    fade_t, fade_s = FADE_MIDPOINT_ATR
    bo_mid_t, bo_mid_s = BREAKOUT_MIDPOINT_ATR
    assert bo_mid_t == 1.8
    assert bo_mid_s == 0.9
    rc = next(item for item in specs if item.config_id == "p2p-rc-es")
    vx = next(item for item in specs if item.config_id == "p2p-vx-es")
    tod = next(item for item in specs if item.config_id == "p2p-tod-es")
    assert rc.target_atr == BREAKOUT_STRETCH_ATR
    assert vx.target_atr == BREAKOUT_STRETCH_ATR
    assert rc.stop_atr == 0.9
    assert vx.stop_atr == 0.9
    assert tod.lookback == TOD_LOOKBACK
    assert tod.target_atr == fade_t
    assert tod.stop_atr == fade_s
    assert tod.template_id == "time_of_day_inventory"
    assert "p2l-rc-es" not in {item.config_id for item in specs}
    assert family_break_even_win_rate(target_atr=2.4, stop_atr=0.9) == pytest.approx(0.9 / 3.3)


@pytest.mark.unit
def test_breakout_diagnostics_match_limited_pit() -> None:
    rows = {row["config_id"]: row for row in breakout_diagnostics_from_limited_pit()}
    rc = rows["p2l-rc-es"]
    vx = rows["p2l-vx-es"]
    assert rc["n_trades"] == 682
    assert rc["exit_target"] == 12
    assert rc["exit_session_end"] == 589
    assert rc["exit_stop"] == 81
    assert rc["exit_time_stop"] == 0
    assert float(rc["mean_mfe_ticks"]) == pytest.approx(96.651, abs=0.01)
    assert float(rc["mean_mae_ticks"]) == pytest.approx(90.742, abs=0.01)
    assert float(rc["commission_per_trade"]) == pytest.approx(3960.60 / 682, abs=0.01)
    assert float(rc["net_pnl"]) < 0.0
    assert vx["n_trades"] == 732
    assert vx["exit_target"] == 17
    assert vx["exit_session_end"] == 591
    assert float(vx["slippage_per_trade"]) > float(vx["commission_per_trade"])
    assert float(vx["net_pnl"]) < 0.0
    tod = tod_diagnostics_from_limited_pit()
    assert tod["n_trades"] == 589
    assert float(tod["gross_pnl"]) > 0.0
    assert float(tod["net_pnl"]) < 0.0


@pytest.mark.unit
def test_overall_verdict_tape_missing_is_not_a_family_close() -> None:
    assert overall_verdict(None, tape_missing=True) == "tape_missing_no_new_trials"
    families = family_close_verdicts((), tape_missing=True)
    assert families["breakout"] == "pending_tape"
    assert families["tod"] == "pending_tape"
    empty = CycleReport(
        n_hypotheses=3,
        n_tested=0,
        n_killed=0,
        n_survivors=0,
        kill_rate=None,
        kill_rate_flag="not_tested",
        cost_bands=(),
        data=DataStatus(usable=False, tapes=(), searched=(), missing=("ES",), required={}),
        rows=(),
        geometry_by_root=(),
        stopped=False,
        stop_reason="",
    )
    assert overall_verdict(empty, tape_missing=False) == "not_tested"


@pytest.mark.unit
def test_dsr_floor_and_prior_n_unchanged() -> None:
    assert FLOOR_DSR_PROBABILITY_MIN == 0.95
    assert PRIOR_LIMITED_N_TRIALS == 78


@pytest.mark.unit
def test_seed_prior_dsr_n_counts_seventy_eight(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    seed_prior_dsr_n(audit, n=3)
    registry = TrialRegistry(audit)
    assert registry.n_trials == 3
    registry.record(config_id="p2p-rc-es", agent_id="test", metrics={})
    assert registry.n_trials == 4


@pytest.mark.unit
def test_cli_postkill_es_requires_es_csv(tmp_path: Path) -> None:
    assert (
        proof_main(
            [
                "research",
                "--cycle",
                "postkill-es",
                "--work-dir",
                str(tmp_path),
                "--report-dir",
                str(tmp_path),
            ]
        )
        == 2
    )


@pytest.mark.unit
def test_cli_postkill_es_is_a_strategy_cycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parser = build_parser()
    args = parser.parse_args(["research", "--cycle", "postkill-es", "--es-csv", "local.csv"])
    assert args.cycle == "postkill-es"
    assert args.es_csv == Path("local.csv")
    monkeypatch.setattr("lumina_research.proof.cli.assert_research_allowed", lambda _path: None)

    class _Stopped:
        report = SimpleNamespace(stop_reason="positive_control_failed", control_note="fail", stopped=True)

    monkeypatch.setattr("lumina_research.proof.cli.run_postkill_es_cycle", lambda **_kwargs: _Stopped())
    assert (
        proof_main(
            [
                "research",
                "--cycle",
                "postkill-es",
                "--es-csv",
                "x.csv",
                "--work-dir",
                str(tmp_path),
                "--report-dir",
                str(tmp_path),
            ]
        )
        == 2
    )

    class _Done:
        report = SimpleNamespace(stop_reason="", control_note="ok", stopped=False)

    monkeypatch.setattr("lumina_research.proof.cli.run_postkill_es_cycle", lambda **_kwargs: _Done())
    assert (
        proof_main(
            [
                "research",
                "--cycle",
                "postkill-es",
                "--es-csv",
                "x.csv",
                "--work-dir",
                str(tmp_path),
                "--report-dir",
                str(tmp_path),
            ]
        )
        == 0
    )


@pytest.mark.unit
def test_blocked_report_does_not_invent_trials(tmp_path: Path) -> None:
    path = write_blocked_report(report_dir=tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["overall_verdict"] == "tape_missing_no_new_trials"
    assert payload["tape_missing"] is True
    assert payload["n_tested"] == 0
    assert payload["n_survivors"] == 0
    assert payload["holdout_opened"] is False
    assert payload["nq_closed"] is True
    assert payload["promotion"] is False
    assert payload["plants_run"] is False
    assert payload["breakout_family"] == "pending_tape"
    assert payload["tod_family"] == "pending_tape"
    assert payload["config_ids"] == list(LOCKED_IDS)
    assert payload["prior_limited_n_trials"] == 78
    assert payload["answers_sha256"].startswith("311ea60a")
    assert len(payload["configs"]) == 0
    assert payload["breakout_diagnostics"][0]["config_id"] == "p2l-rc-es"


@pytest.mark.unit
def test_committed_postkill_pit_is_all_kill_families_closed() -> None:
    payload = json.loads(Path("experiments/reports/phase5_p2_postkill_end.json").read_text(encoding="utf-8"))
    assert payload["overall_verdict"] == "all_kill_no_promotion"
    assert payload["tape_missing"] is False
    assert payload["n_tested"] == 3
    assert payload["n_killed"] == 3
    assert payload["n_survivors"] == 0
    assert payload["holdout_opened"] is False
    assert payload["promotion"] is False
    assert payload["plants_run"] is False
    assert payload["nq_closed"] is True
    assert payload["sim_real"] is False
    assert payload["breakout_family"] == "closed_net_negative"
    assert payload["tod_family"] == "closed_failed_gates"
    assert payload["prereg_commit"] == "72078670"
    assert payload["prereg_sha256"].startswith("d259b84e")
    assert payload["prior_limited_n_trials"] == 78
    assert payload["answers_sha256"].startswith("311ea60a")
    assert str(payload["csv_sha256"]).startswith("6100588d")
    assert payload["n_bars_es"] == 818851
    assert payload["es_last_ts"] == "2026-01-28T22:00:00Z"
    assert payload["config_ids"] == list(LOCKED_IDS)
    by_id = {row["config_id"]: row for row in payload["configs"]}
    assert set(by_id) == set(LOCKED_IDS)
    for config_id in LOCKED_IDS:
        row = by_id[config_id]
        assert row["instrument"] == "ES"
        assert row["tested"] is True
        assert row["passed_gate"] is False
        assert row["n_oos_windows"] == 8
        assert float(row["dsr"]) < 0.95
        assert float(row["net_pnl"]) < 0.0
        assert int(row["n_trials"]) >= 78
        assert "dsr_below_threshold" in row["reject_reasons"]
    assert float(by_id["p2p-rc-es"]["net_pnl"]) < 0.0
    assert float(by_id["p2p-vx-es"]["net_pnl"]) < 0.0
    assert float(by_id["p2p-vx-es"]["gross_pnl"]) > 0.0
    assert float(by_id["p2p-tod-es"]["gross_pnl"]) > 0.0
