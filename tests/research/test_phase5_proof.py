"""Independent P1 verification suite, reports, and proof CLI."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from lumina_research.monitoring.acceptance import (
    DETECTION_RATE_MIN,
    FAR_HEALTHY_MAX,
    FAR_HIGH_VOL_MAX,
    TTD_MAX_TRADING_DAYS,
    TTD_MEDIUM_MAX_TRADING_DAYS,
)
from lumina_research.monitoring.mutation_report import evaluate_mutation_floor, resolve_mutation_report
from lumina_research.monitoring.report import KindMetrics, MultiSeedDetectionReport, SeedDetectionRow
from lumina_research.proof.cli import build_parser, main
from lumina_research.proof.continuity_suite import _medium_holds, _short_holds, kind_rows
from lumina_research.proof.gate_suite import run_gate_suite
from lumina_research.proof.independent import (
    INDEPENDENT_SEEDS,
    FLOOR_KINDS,
    SLOW_KINDS,
    decaying_kind,
    healthy_kind,
    map_instrument,
    path_for,
)
from lumina_research.proof.report import write_empirical_reports
from lumina_research.proof.runner import run_empirical_verification


def _kind(
    kind: str,
    *,
    n: int = 10,
    detection: float = 0.9,
    far: float = 0.0,
    ttd: float = 8.0,
) -> KindMetrics:
    decaying = decaying_kind(kind) if kind not in {"healthy_laplace", "high_vol_mixture"} else False
    if kind in SLOW_KINDS:
        decaying = True
    return KindMetrics(
        kind=kind,
        n=n,
        n_detected=int(round(detection * n)) if decaying else 0,
        n_false_alarms=int(round(far * n)),
        detection_rate=detection if decaying else 0.0,
        false_alarm_rate=far,
        median_time_to_detect=ttd if decaying else None,
        p90_time_to_detect=ttd if decaying else None,
        max_time_to_detect=ttd if decaying else None,
    )


def _report(kinds: tuple[KindMetrics, ...], *, n_signals: int = 60, n_seeds: int = 10) -> MultiSeedDetectionReport:
    return MultiSeedDetectionReport(
        seeds=(
            SeedDetectionRow(
                seed=1,
                instrument="MES",
                n_signals=n_signals,
                detection_rate=0.9,
                false_alarm_rate=0.0,
                median_time_to_detect=8.0,
                mean_time_to_detect=8.0,
            ),
        ),
        n_signals=n_signals,
        n_seeds=n_seeds,
        n_healthy=10,
        n_decaying=50,
        n_detected=45,
        n_false_alarms=0,
        detection_rate=0.9,
        false_alarm_rate=0.0,
        median_time_to_detect=8.0,
        mean_time_to_detect=8.0,
        p10_time_to_detect=4.0,
        p90_time_to_detect=12.0,
        max_time_to_detect=12.0,
        time_to_detect=(8,),
        by_kind=kinds,
        paths=(),
    )


@pytest.mark.unit
def test_independent_generators_and_instrument_map() -> None:
    rng = random.Random(INDEPENDENT_SEEDS[0])
    oos_mean, oos_stdev, n, start = 0.75, 0.05, 40, 10
    for kind in (*FLOOR_KINDS, *SLOW_KINDS):
        series = path_for(kind, rng, oos_mean=oos_mean, oos_stdev=oos_stdev, n=n, decay_start=start)
        assert len(series) == n
        assert all(isinstance(item, float) for item in series)
    assert map_instrument("mes") == "MES"
    with pytest.raises(Exception):
        map_instrument("BTC")
    assert healthy_kind("healthy_laplace") == "healthy"
    assert healthy_kind("high_vol_mixture") == "high_vol"
    assert decaying_kind("slow_gradual_45") is True


@pytest.mark.unit
def test_short_holds_rejects_twelve_percent_high_vol_far() -> None:
    passing = _report(
        (
            _kind("healthy_laplace", far=FAR_HEALTHY_MAX, detection=0.0),
            _kind("high_vol_mixture", far=FAR_HIGH_VOL_MAX, detection=0.0),
            _kind("abrupt_student", detection=DETECTION_RATE_MIN, ttd=float(TTD_MAX_TRADING_DAYS)),
            _kind("gradual_smooth", detection=0.9, ttd=10.0),
            _kind("regime_laplace", detection=0.9, ttd=10.0),
            _kind("material_break", detection=0.9, ttd=10.0),
        )
    )
    assert _short_holds(passing, n_signals_floor=60) is True
    too_far = _report((_kind("high_vol_mixture", far=0.12, detection=0.0),))
    assert _short_holds(too_far, n_signals_floor=60) is False
    slow_ok = _report((_kind("slow_gradual_45", detection=0.9, ttd=40.0),))
    assert _medium_holds(slow_ok, n_signals_floor=30) is True
    slow_late = _report(
        (_kind("slow_gradual_45", detection=0.9, ttd=float(TTD_MEDIUM_MAX_TRADING_DAYS) + 1),)
    )
    assert _medium_holds(slow_late, n_signals_floor=30) is False
    assert kind_rows(passing)[0].kind == "healthy_laplace"


@pytest.mark.unit
def test_gate_suite_kills_overfit_and_noise(tmp_path: Path) -> None:
    report = run_gate_suite(audit_dir=tmp_path)
    names = {item.name: item for item in report.cases}
    assert names["overfit_ar1_random_search"].expected_pass is False
    assert names["overfit_ar1_random_search"].passed is False
    assert names["noise_ar1"].passed is False
    assert names["healthy_student_t_drift"].expected_pass is True
    assert names["pipeline_evaluate_candidate"].expected_pass is True
    assert report.passed is True


@pytest.mark.unit
def test_mutation_report_missing_and_invalid(tmp_path: Path) -> None:
    missing = evaluate_mutation_floor(None)
    assert missing.passed is False
    assert missing.observed == "missing"
    bogus = tmp_path / "nope.json"
    assert evaluate_mutation_floor(bogus).passed is False
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    assert evaluate_mutation_floor(bad).observed.startswith("invalid")
    not_obj = tmp_path / "list.json"
    not_obj.write_text("[]", encoding="utf-8")
    assert evaluate_mutation_floor(not_obj).observed == "invalid:not_object"
    good = tmp_path / "ok.json"
    good.write_text(
        json.dumps(
            {
                "kill_rate": 0.85,
                "n_mutants": 320,
                "n_killed": 272,
                "n_excluded": 0,
                "n_non_equivalent": 320,
            }
        ),
        encoding="utf-8",
    )
    result = evaluate_mutation_floor(good)
    assert result.passed is True
    local = tmp_path / "state"
    local.mkdir()
    (local / "mutation.json").write_text(good.read_text(encoding="utf-8"), encoding="utf-8")
    resolved = resolve_mutation_report(None, state_dir=local)
    assert resolved == local / "mutation.json"


@pytest.mark.unit
def test_empirical_report_writer(tmp_path: Path) -> None:
    from lumina_research.monitoring.mutation_report import MutationFloorResult
    from lumina_research.proof.continuity_suite import ContinuitySuiteReport
    from lumina_research.proof.gate_suite import GateCase, GateSuiteReport

    gate = GateSuiteReport(
        cases=(
            GateCase(
                name="noise_ar1",
                seed=1,
                expected_pass=False,
                passed=False,
                reject_reasons=("pbo",),
                pbo=0.6,
                dsr=0.4,
                wfe=0.2,
                n_oos_windows=6,
                purge_applied=True,
                embargo_applied=True,
                n_trials=2,
                median_oos=0.01,
            ),
        ),
        passed=True,
    )
    floor = _report((_kind("healthy_laplace", far=0.0),))
    continuity = ContinuitySuiteReport(
        floor=floor,
        slow=floor,
        floor_passed=True,
        short_passed=True,
        medium_passed=True,
        slow_notes="two horizons",
    )
    mutation = MutationFloorResult(
        passed=True,
        kill_rate=0.825,
        n_mutants=320,
        n_non_equivalent=320,
        n_excluded=0,
        n_killed=264,
        observed="ok",
        required="kill_rate>=0.80",
        path="x",
    )
    json_path, md_path = write_empirical_reports(
        directory=tmp_path, gate=gate, continuity=continuity, mutation=mutation
    )
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["short_horizon_passed"] is True
    assert payload["medium_horizon_passed"] is True
    text = md_path.read_text(encoding="utf-8")
    assert "TTD <= 15" in text
    assert "TTD <= 45" in text


@pytest.mark.unit
def test_proof_cli_research_stops_without_data(tmp_path: Path) -> None:
    parser = build_parser()
    args = parser.parse_args(["research", "--work-dir", str(tmp_path / "w"), "--report-dir", str(tmp_path / "r")])
    assert args.command == "research"
    code = main(
        [
            "research",
            "--work-dir",
            str(tmp_path / "work"),
            "--report-dir",
            str(tmp_path / "reports"),
            "--evolution-log-dir",
            str(tmp_path / "evo"),
            "--data-dir",
            str(tmp_path / "empty"),
        ]
    )
    assert code == 3
    assert (tmp_path / "reports" / "phase5_research_cycles.json").is_file()
    assert (tmp_path / "reports" / "phase5_sim_plan.md").is_file()


@pytest.mark.unit
def test_empirical_runner_wires_reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from lumina_research.monitoring.mutation_report import MutationFloorResult
    from lumina_research.proof import runner as runner_mod
    from lumina_research.proof.continuity_suite import ContinuitySuiteReport
    from lumina_research.proof.gate_suite import GateCase, GateSuiteReport

    gate = GateSuiteReport(
        cases=(
            GateCase(
                name="noise_ar1",
                seed=1,
                expected_pass=False,
                passed=False,
                reject_reasons=("pbo",),
                pbo=0.6,
                dsr=0.4,
                wfe=0.2,
                n_oos_windows=6,
                purge_applied=True,
                embargo_applied=True,
                n_trials=2,
                median_oos=0.01,
            ),
        ),
        passed=True,
    )
    floor = _report((_kind("healthy_laplace", far=0.0),))
    continuity = ContinuitySuiteReport(
        floor=floor,
        slow=floor,
        floor_passed=True,
        short_passed=True,
        medium_passed=True,
        slow_notes="two horizons",
    )
    mutation = MutationFloorResult(
        passed=True,
        kill_rate=0.825,
        n_mutants=320,
        n_non_equivalent=320,
        n_excluded=0,
        n_killed=264,
        observed="ok",
        required="kill_rate>=0.80",
        path="x",
    )
    monkeypatch.setattr(runner_mod, "run_gate_suite", lambda **_kwargs: gate)
    monkeypatch.setattr(runner_mod, "run_independent_continuity", lambda **_kwargs: continuity)
    monkeypatch.setattr(runner_mod, "evaluate_mutation_floor", lambda _path: mutation)
    monkeypatch.setattr(runner_mod, "resolve_mutation_report", lambda _path: tmp_path / "mutation.json")
    result = run_empirical_verification(
        work_dir=tmp_path / "work",
        report_dir=tmp_path / "reports",
        evolution_log_dir=tmp_path / "evo",
        n_per_kind=1,
        n_days=25,
        decay_start=8,
        seeds=INDEPENDENT_SEEDS[:2],
        instruments=("MES", "ES"),
    )
    assert result.passed is True
    assert result.json_path.is_file()
    payload = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert payload["short_horizon_passed"] is True
    assert payload["medium_horizon_passed"] is True


@pytest.mark.slow
def test_tiny_independent_continuity_smoke(tmp_path: Path) -> None:
    result = run_empirical_verification(
        work_dir=tmp_path / "work",
        report_dir=tmp_path / "reports",
        evolution_log_dir=tmp_path / "evo",
        mutation_report=Path("experiments/reports/phase4_mutation.json"),
        n_per_kind=1,
        n_days=25,
        decay_start=8,
        seeds=INDEPENDENT_SEEDS[:2],
        instruments=("MES", "ES"),
    )
    assert result.gate.passed is True
    assert result.json_path.is_file()
    assert result.md_path.is_file()
    payload = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert "short_horizon_passed" in payload
    assert "medium_horizon_passed" in payload
