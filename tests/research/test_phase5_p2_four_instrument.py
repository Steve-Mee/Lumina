"""Four-instrument cycle: cost-fix report names, ES/NQ translations, fail-closed data."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_research.cycles.catalog import catalog
from lumina_research.cycles.data import DataStatus, LoadedTape
from lumina_research.cycles.first_cycle import first_cycle_specs
from lumina_research.cycles.four_instrument import (
    COMPARISON_NAME,
    ES_NQ_CYCLES_STEM,
    ES_NQ_NEEDED,
    ES_NQ_RESULTS_NAME,
    MES_MNQ_CYCLES_STEM,
    MES_MNQ_RESULTS_NAME,
    es_nq_specs,
    run_four_instrument_cycle,
)
from lumina_research.cycles.geometry import require_geometry
from lumina_research.cycles.holdout import HoldoutLocked
from lumina_research.cycles.positive_control import run_controls_per_instrument
from lumina_research.cycles.report import CycleReport, write_cycle_reports
from lumina_research.cycles.runner import run_research_cycles
from lumina_research.cycles.seal import (
    CSV_SHA256,
    ES_NQ_SEAL_NAME,
    LIVE_SEAL_SHA256,
    SEAL_NAME,
    seal_holdout,
)
from lumina_research.proof.cli import build_parser, main as proof_main
from lumina_research.validation.trial_registry import TrialRegistry
from tests.research.test_phase5_p2 import _span_bars
from tests.research.test_phase5_p2_fixes import _control_tape


def _empty_report() -> CycleReport:
    geo = require_geometry(root="MES", target_ticks=16, stop_ticks=8)
    return CycleReport(
        n_hypotheses=0,
        n_tested=0,
        n_killed=0,
        n_survivors=0,
        kill_rate=None,
        kill_rate_flag="not_tested",
        cost_bands=(),
        data=DataStatus(usable=False, tapes=(), searched=(), missing=(), required={}),
        rows=(),
        geometry_by_root=(geo,),
        stopped=True,
        stop_reason="no_usable_real_market_data",
    )


@pytest.mark.unit
def test_es_nq_specs_copy_first_cycle_not_catalog_duplicates() -> None:
    source = first_cycle_specs()
    translated = es_nq_specs(source)
    assert len(translated) == 12
    assert {item.instrument for item in translated} == {"ES", "NQ"}
    assert all(item.config_id.startswith("p2c-") for item in translated)
    catalog_ids = {item.config_id for item in catalog()}
    assert "mr-es-20-1.5" in catalog_ids
    assert "p2c-mr-es-10-1.5" not in catalog_ids
    by_src = {item.config_id: item for item in source}
    by_dst = {item.config_id: item for item in translated}
    mes = by_src["mr-mes-10-1.5"]
    es = by_dst["p2c-mr-es-10-1.5"]
    assert es.instrument == "ES"
    assert es.lookback == mes.lookback == 10
    assert es.threshold == mes.threshold == 1.5
    assert es.mode == mes.mode
    assert es.target_ticks == mes.target_ticks == 16
    assert es.stop_ticks == mes.stop_ticks == 8
    catalog_es = next(item for item in catalog() if item.config_id == "mr-es-20-1.5")
    assert catalog_es.lookback == 20
    assert catalog_es.target_ticks == 8
    mnq = by_src["vi-mnq-10-0.55"]
    nq = by_dst["p2c-vi-nq-10-0.55"]
    assert nq.instrument == "NQ"
    assert nq.lookback == mnq.lookback
    assert nq.target_ticks == 16
    assert nq.stop_ticks == 8


@pytest.mark.unit
def test_write_cycle_reports_refuses_repo_baseline() -> None:
    reports = Path("experiments/reports")
    with pytest.raises(RuntimeError, match="phase5_p2_results"):
        write_cycle_reports(_empty_report(), reports)


@pytest.mark.unit
def test_runner_custom_stems_skip_sidecars_and_baseline(tmp_path: Path) -> None:
    result = run_research_cycles(
        work_dir=tmp_path / "work",
        report_dir=tmp_path / "reports",
        evolution_log_dir=None,
        repo_root=tmp_path,
        write_sidecars=False,
        cycles_stem=MES_MNQ_CYCLES_STEM,
        results_name=MES_MNQ_RESULTS_NAME,
    )
    assert result.report.stopped is True
    reports = tmp_path / "reports"
    assert (reports / MES_MNQ_RESULTS_NAME).is_file()
    assert (reports / f"{MES_MNQ_CYCLES_STEM}.json").is_file()
    assert not (reports / "phase5_p2_results.md").is_file()
    assert not (reports / "phase5_research_cycles.json").is_file()
    assert not (reports / "phase5_sim_plan.md").is_file()
    assert not (reports / "phase5_first_cycle_preregister.md").is_file()


@pytest.mark.unit
def test_four_instrument_missing_es_nq_is_fail_closed(tmp_path: Path) -> None:
    result = run_four_instrument_cycle(
        work_dir=tmp_path / "work",
        report_dir=tmp_path / "reports",
        repo_root=tmp_path,
        data_dir=tmp_path / "missing-research-data",
    )
    assert result.mes_mnq.report.stopped is True
    assert result.es_nq.report.stopped is True
    assert result.es_nq.report.stop_reason == "no_usable_real_market_data"
    reports = tmp_path / "reports"
    assert (reports / MES_MNQ_RESULTS_NAME).is_file()
    assert (reports / ES_NQ_RESULTS_NAME).is_file()
    assert (reports / COMPARISON_NAME).is_file()
    assert not (reports / "phase5_p2_results.md").is_file()
    es_json = json.loads((reports / f"{ES_NQ_CYCLES_STEM}.json").read_text(encoding="utf-8"))
    ids = {row["config_id"] for row in es_json["hypotheses"]}
    assert "p2c-mr-es-10-1.5" in ids
    assert "mr-es-20-1.5" not in ids
    comparison = (reports / COMPARISON_NAME).read_text(encoding="utf-8")
    assert "MES/MNQ cost-fix effect" in comparison
    assert "### MES cost-fix effect" in comparison
    assert "### MNQ cost-fix effect" in comparison
    assert "Same-family ES vs MES and NQ vs MNQ" in comparison
    assert "ES/NQ tape gaps (not filled)" in comparison
    assert "comm/trade" in comparison
    assert ES_NQ_NEEDED.split("(")[0].strip() in comparison or "PIT NT8 1m" in comparison


@pytest.mark.unit
def test_csv_sha256_pins_es_nq_continuous() -> None:
    assert CSV_SHA256["ES"].startswith("6b23a4dd")
    assert CSV_SHA256["NQ"].startswith("9d41f220")
    assert len(CSV_SHA256["ES"]) == 64
    assert len(CSV_SHA256["NQ"]) == 64


@pytest.mark.unit
def test_reuse_mes_mnq_requires_existing_reports(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="reuse_mes_mnq missing"):
        run_four_instrument_cycle(
            work_dir=tmp_path / "work",
            report_dir=tmp_path / "reports",
            repo_root=tmp_path,
            reuse_mes_mnq=True,
        )


@pytest.mark.unit
def test_reuse_mes_mnq_keeps_costfix_files(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    payload = {
        "n_hypotheses": 12,
        "n_tested": 12,
        "n_killed": 12,
        "n_survivors": 0,
        "kill_rate": 1.0,
        "kill_rate_flag": "ok",
        "hypotheses": [],
        "planted_detected": True,
        "null_detected": False,
        "holdout_seal_sha256": "85e4588fde77159315a72bdaa722d6487f93bbad9bf24999311f893950489d40",
    }
    (reports / f"{MES_MNQ_CYCLES_STEM}.json").write_text(json.dumps(payload), encoding="utf-8")
    (reports / f"{MES_MNQ_CYCLES_STEM}.md").write_text("costfix\n", encoding="utf-8")
    (reports / MES_MNQ_RESULTS_NAME).write_text("results\n", encoding="utf-8")
    before = (reports / MES_MNQ_RESULTS_NAME).read_text(encoding="utf-8")
    result = run_four_instrument_cycle(
        work_dir=tmp_path / "work",
        report_dir=reports,
        repo_root=tmp_path,
        data_dir=tmp_path / "missing-research-data",
        reuse_mes_mnq=True,
    )
    assert result.mes_mnq.report.n_tested == 12
    assert result.mes_mnq.report.control_note.startswith("reused MES/MNQ")
    assert result.es_nq.report.stopped is True
    assert (reports / MES_MNQ_RESULTS_NAME).read_text(encoding="utf-8") == before
    comparison = (reports / COMPARISON_NAME).read_text(encoding="utf-8")
    assert "p2c-mr-es-10-1.5" in comparison


@pytest.mark.unit
def test_seal_refuses_overwrite_live_mes_mnq_identity(tmp_path: Path) -> None:
    live = Path("experiments/reports") / SEAL_NAME
    payload = live.read_text(encoding="utf-8")
    (tmp_path / SEAL_NAME).write_text(payload, encoding="utf-8")
    bars = _span_bars()
    csv = tmp_path / "MES" / "1m" / "mes.csv"
    csv.parent.mkdir(parents=True)
    csv.write_text("timestamp,open,high,low,close,volume\n", encoding="utf-8")
    tape = LoadedTape(instrument="MES", bar_size="1m", path=csv, bars=bars)
    with pytest.raises(HoldoutLocked, match="refusing to overwrite live"):
        seal_holdout((tape,), report_dir=tmp_path, require_known_files=False)
    committed = json.loads((tmp_path / SEAL_NAME).read_text(encoding="utf-8"))
    assert committed["seal_sha256"] == LIVE_SEAL_SHA256
    alt = seal_holdout(
        (tape,),
        report_dir=tmp_path,
        require_known_files=False,
        filename=ES_NQ_SEAL_NAME,
    )
    assert alt["seal_sha256"] != LIVE_SEAL_SHA256
    assert (tmp_path / ES_NQ_SEAL_NAME).is_file()
    still = json.loads((tmp_path / SEAL_NAME).read_text(encoding="utf-8"))
    assert still["seal_sha256"] == LIVE_SEAL_SHA256


@pytest.mark.unit
def test_run_controls_per_instrument_accepts_mes_tape(tmp_path: Path) -> None:
    prepared = _control_tape()
    accepted, failed = run_controls_per_instrument(
        prepared={"MES": prepared},
        registry=TrialRegistry(tmp_path / "control.jsonl"),
        audit_path=tmp_path / "control.jsonl",
        is_size=6,
        oos_size=2,
    )
    assert "MES" in accepted
    assert failed == {}
    assert accepted["MES"].positive.detected is True
    assert accepted["MES"].null.detected is False


@pytest.mark.unit
def test_cli_four_instrument_cycle_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parser = build_parser()
    args = parser.parse_args(["research", "--cycle", "four-instrument"])
    assert args.cycle == "four-instrument"

    class _Report:
        stopped = True
        stop_reason = "no_usable_real_market_data"

    class _Data:
        usable = True

    class _Cycle:
        data = _Data()
        kill_rate_flag = "not_tested"
        report = _Report()

    class _Four:
        mes_mnq = _Cycle()
        es_nq = _Cycle()
        comparison_path = tmp_path / "cmp.md"

    captured: list[dict[str, object]] = []

    def _run(**kwargs: object) -> _Four:
        captured.append(dict(kwargs))
        return _Four()

    monkeypatch.setattr(
        "lumina_research.proof.cli.run_four_instrument_cycle",
        _run,
    )
    assert proof_main(["research", "--cycle", "four-instrument", "--work-dir", str(tmp_path)]) == 0
    assert captured and captured[0]["work_dir"] == tmp_path
    assert captured[0]["reuse_mes_mnq"] is False
    captured.clear()
    assert (
        proof_main(
            [
                "research",
                "--cycle",
                "four-instrument",
                "--reuse-mes-mnq",
                "--work-dir",
                str(tmp_path),
            ]
        )
        == 0
    )
    assert captured and captured[0]["reuse_mes_mnq"] is True
