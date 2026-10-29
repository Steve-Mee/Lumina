"""23:07 limited ES strategy-run: locked six p2l-* configs, GO sha, CLI."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_research.cycles.data import DataStatus
from lumina_research.cycles.limited_es import (
    GO_ANSWERS_NAME,
    GO_ANSWERS_SHA256,
    LOCKED_IDS,
    PRE_HOLDOUT_CSV_SHA256,
    limited_es_specs,
    overall_verdict,
)
from lumina_research.cycles.positive_control import BREAKOUT_MIDPOINT_ATR, FADE_MIDPOINT_ATR
from lumina_research.cycles.report import CycleReport
from lumina_research.proof.cli import build_parser, main as proof_main


@pytest.mark.unit
def test_limited_es_specs_are_exactly_the_six_preregistered_ids() -> None:
    specs = limited_es_specs()
    assert tuple(item.config_id for item in specs) == LOCKED_IDS
    assert len(specs) == 6
    assert {item.instrument for item in specs} == {"ES"}
    assert all(item.session_filter == "rth" for item in specs)
    assert all(item.session_end_flatten for item in specs)
    assert all(item.time_stop_bars == 2000 for item in specs)
    assert all(item.has_fit_step is False for item in specs)
    fade_t, fade_s = FADE_MIDPOINT_ATR
    bo_t, bo_s = BREAKOUT_MIDPOINT_ATR
    fade = {item.config_id for item in specs if item.target_atr == fade_t and item.stop_atr == fade_s}
    breakout = {item.config_id for item in specs if item.target_atr == bo_t and item.stop_atr == bo_s}
    assert fade == {"p2l-mr-es", "p2l-or-fade-es", "p2l-vwap-es", "p2l-tod-es"}
    assert breakout == {"p2l-rc-es", "p2l-vx-es"}
    tod = next(item for item in specs if item.config_id == "p2l-tod-es")
    assert tod.template_id == "time_of_day_inventory"
    assert tod.lookback == 30
    assert "p2a-or-bo-es" not in {item.config_id for item in specs}


@pytest.mark.unit
def test_limited_es_go_answers_sha_is_frozen() -> None:
    path = Path("docs/research") / GO_ANSWERS_NAME
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == GO_ANSWERS_SHA256
    assert digest.startswith("33200329")
    assert PRE_HOLDOUT_CSV_SHA256.startswith("6100588d")


@pytest.mark.unit
def test_limited_es_preregister_records_go_and_keeps_six() -> None:
    text = Path("experiments/reports/phase5_p2_limited_es_preregister_2026-10-29.md").read_text(encoding="utf-8")
    assert "p2l-mr-es" in text
    assert "p2l-vx-es" in text
    assert "p2l-tod-es" in text
    assert "TOD decision: keep" in text
    assert "n configs stays 6" in text
    assert "NQ closed" in text
    assert "33200329" in text
    assert "GO" in text
    assert "no extra variants" in text.lower() or "No extra variants" in text


@pytest.mark.unit
def test_overall_verdict_never_promotes() -> None:
    empty = DataStatus(usable=True, tapes=(), searched=(), missing=(), required={})

    def _report(*, tested: int, killed: int, survivors: int, stopped: bool) -> CycleReport:
        return CycleReport(
            n_hypotheses=6,
            n_tested=tested,
            n_killed=killed,
            n_survivors=survivors,
            kill_rate=None if tested == 0 else killed / float(tested),
            kill_rate_flag="ok",
            cost_bands=(),
            data=empty,
            rows=(),
            geometry_by_root=(),
            stopped=stopped,
            stop_reason="positive_control_failed" if stopped else "",
        )

    assert overall_verdict(_report(tested=6, killed=6, survivors=0, stopped=False)) == ("all_kill_no_promotion")
    assert overall_verdict(_report(tested=6, killed=5, survivors=1, stopped=False)) == ("survivors_exist_no_promotion")
    assert overall_verdict(_report(tested=0, killed=0, survivors=0, stopped=True)) == ("stopped_control_failed")
    assert overall_verdict(_report(tested=0, killed=0, survivors=0, stopped=False)) == "not_tested"


@pytest.mark.unit
def test_committed_limited_es_pit_is_all_kill_no_promotion() -> None:
    payload = json.loads(Path("experiments/reports/phase5_p2_limited_es_end.json").read_text(encoding="utf-8"))
    assert payload["overall_verdict"] == "all_kill_no_promotion"
    assert payload["n_tested"] == 6
    assert payload["n_killed"] == 6
    assert payload["n_survivors"] == 0
    assert payload["holdout_opened"] is False
    assert payload["nq_closed"] is True
    assert payload["promotion"] is False
    assert payload["sim_real"] is False
    assert payload["extra_variants"] is False
    assert payload["planted_detected"] is True
    assert payload["null_detected"] is False
    assert payload["csv_sha256"].startswith("6100588d")
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
        assert row["dsr"] is not None and float(row["dsr"]) < 0.95
        assert "dsr_below_threshold" in row["reject_reasons"]


@pytest.mark.unit
def test_cli_limited_es_requires_es_csv(tmp_path: Path) -> None:
    assert (
        proof_main(
            [
                "research",
                "--cycle",
                "limited-es",
                "--work-dir",
                str(tmp_path),
                "--report-dir",
                str(tmp_path),
            ]
        )
        == 2
    )


@pytest.mark.unit
def test_cli_limited_es_is_a_strategy_cycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parser = build_parser()
    args = parser.parse_args(["research", "--cycle", "limited-es", "--es-csv", "local.csv"])
    assert args.cycle == "limited-es"
    assert args.es_csv == Path("local.csv")

    monkeypatch.setattr("lumina_research.proof.cli.assert_research_allowed", lambda _path: None)

    class _Stopped:
        report = SimpleNamespace(stop_reason="positive_control_failed", control_note="fail", stopped=True)

    monkeypatch.setattr("lumina_research.proof.cli.run_limited_es_cycle", lambda **_kwargs: _Stopped())
    assert (
        proof_main(
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
        == 2
    )

    class _Done:
        report = SimpleNamespace(stop_reason="", control_note="ok", stopped=False)

    monkeypatch.setattr("lumina_research.proof.cli.run_limited_es_cycle", lambda **_kwargs: _Done())
    assert (
        proof_main(
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
        == 0
    )
