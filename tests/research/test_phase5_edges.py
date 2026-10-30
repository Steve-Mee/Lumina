"""Edge coverage for Phase 5 ports, proof CLI, weekly metrics, and data loaders."""

from __future__ import annotations

import argparse
import json
import math
import random
import runpy
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas_research import (
    FILL_AGENT_ID,
    SAFETY_AGENT_ID,
    SHADOW_AGENT_ID,
    EconomicRationale,
    ExecutionMode,
    ResearchFillEvent,
)
from lumina_core.engine.agent_blackboard import AgentBlackboard
from lumina_research.agents.generators import GeneratorError
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.cycles import catalog as catalog_mod
from lumina_research.cycles import cost_bands as cost_bands_mod
from lumina_research.cycles import geometry as geometry_mod
from lumina_research.cycles import strategies as strategies_mod
from lumina_research.cycles.catalog import EconomicCatalogGenerator, catalog
from lumina_research.cycles.cost_bands import band_for
from lumina_research.cycles.data import (
    DataRefused,
    DataStatus,
    LoadedTape,
    ResearchBar,
    _as_float,
    _bar_from_mapping,
    _search_roots,
    _timestamp_ns,
    discover_data,
    tape_for,
)
from lumina_research.cycles.fills import FillRefused, fill_probability, trade_through_fill
from lumina_research.cycles.geometry import GeometryRefused, floors_for, require_geometry
from lumina_research.cycles.report import CycleReport, CycleRow, death_reason, mapping_metric, write_cycle_reports
from lumina_research.cycles.strategies import StrategyRefused, simulate
from lumina_research.monitoring import horizons as horizons_mod
from lumina_research.monitoring import mutation_report as mutation_mod
from lumina_research.monitoring import vol_regime as vol_mod
from lumina_research.monitoring.acceptance import CAMPAIGN_MIN_SIGNALS, DETECTION_RATE_MIN, FAR_HEALTHY_MAX
from lumina_research.monitoring import cli as monitoring_cli_mod
from lumina_research.monitoring.cli import main as monitoring_main
from lumina_research.monitoring.config import load_default_config
from lumina_research.monitoring.horizons import combined_assessment
from lumina_research.monitoring.loop import ContinuityRuntime
from lumina_research.monitoring.material import _max_drawdown, _ratio, assess_material
from lumina_research.monitoring.mutation_report import (
    MutationFloorResult,
    evaluate_mutation_floor,
    resolve_mutation_report,
)
from lumina_research.monitoring.report import (
    DetectionPath,
    DetectionReport,
    GuardianReport,
    KindMetrics,
    MultiSeedDetectionReport,
    SeedDetectionRow,
)
from lumina_research.monitoring.types import ContinuityRefused, DecayAssessment
from lumina_research.monitoring.vol_regime import classify_vol_regime, realized_vol, trailing_percentile
from lumina_research.monitoring.weekly import build_weekly_metrics, load_hypothesis_rows
from lumina_research.ports.fills import FillSink, PortRefused
from lumina_research.ports.seal import _stable, accept_mac, canonical_signal
from lumina_research.ports.shadow import ShadowBook
from lumina_research.ports.sim_safety import SimSafetyConfig, SimSafetyGate, SimSafetyRefused
from lumina_research.proof import cli as cli_mod
from lumina_research.proof import runner as runner_mod
from lumina_research.proof.cli import build_parser, main as proof_main
from lumina_research.proof.continuity_suite import (
    ContinuitySuiteReport,
    _medium_holds,
    _short_holds,
    run_independent_continuity,
)
from lumina_research.proof.gate_suite import GateCase, GateSuiteReport
from lumina_research.proof.independent import INDEPENDENT_SEEDS, assert_independent_seeds, decaying_kind, path_for
from lumina_research.proof.log import log_proof_event
from lumina_research.proof.runner import _failures, run_empirical_verification
from tests.research.null_only_stub import write_passing_null_only_json
from tests.research.phase4_harness import admit_signal, make_runtime
from tests.research.test_phase5_cycles import _bars, _write_csv
from tests.research.test_phase5_proof import _kind, _report


def _empty_kind(*, kind: str, n: int = 0) -> KindMetrics:
    return KindMetrics(
        kind=kind,
        n=n,
        n_detected=0,
        n_false_alarms=0,
        detection_rate=0.0,
        false_alarm_rate=0.0,
        median_time_to_detect=None,
        p90_time_to_detect=None,
        max_time_to_detect=None,
    )


@pytest.mark.unit
def test_tiny_independent_continuity_covers_campaign(tmp_path: Path) -> None:
    with pytest.raises(ContinuityRefused, match="align"):
        run_independent_continuity(
            audit_dir=tmp_path / "bad",
            experiment_log_dir=tmp_path / "bad-e",
            n_per_kind=1,
            n_days=5,
            decay_start=2,
            seeds=INDEPENDENT_SEEDS[:2],
            instruments=("MES",),
            floor_kinds=("healthy_laplace",),
            slow_kinds=("slow_gradual_45",),
        )
    report = run_independent_continuity(
        audit_dir=tmp_path / "a",
        experiment_log_dir=tmp_path / "e",
        n_per_kind=1,
        n_days=8,
        decay_start=3,
        seeds=INDEPENDENT_SEEDS[:1],
        instruments=("MES",),
        floor_kinds=("healthy_laplace",),
        slow_kinds=("slow_gradual_45",),
    )
    assert report.floor.n_signals == 1
    assert report.slow.n_signals == 1
    assert report.slow_notes.startswith("Two horizons")


@pytest.mark.unit
def test_floor_size_and_kind_rejects() -> None:
    small = _report((_kind("healthy_laplace", far=0.0),), n_signals=10, n_seeds=1)
    assert _short_holds(small, n_signals_floor=CAMPAIGN_MIN_SIGNALS) is False
    assert _medium_holds(small, n_signals_floor=CAMPAIGN_MIN_SIGNALS) is False
    undersized = _report((_kind("healthy_laplace", far=0.0),), n_signals=10, n_seeds=10)
    assert _short_holds(undersized, n_signals_floor=CAMPAIGN_MIN_SIGNALS) is False
    healthy_far = _report((_kind("healthy_laplace", far=FAR_HEALTHY_MAX + 0.01, detection=0.0),))
    assert _short_holds(healthy_far, n_signals_floor=60) is False
    weak_detect = _report((_kind("abrupt_student", detection=DETECTION_RATE_MIN - 0.2, ttd=8.0),))
    assert _short_holds(weak_detect, n_signals_floor=60) is False
    missing_ttd = _report(
        (
            KindMetrics(
                kind="abrupt_student",
                n=10,
                n_detected=9,
                n_false_alarms=0,
                detection_rate=0.9,
                false_alarm_rate=0.0,
                median_time_to_detect=8.0,
                p90_time_to_detect=8.0,
                max_time_to_detect=None,
            ),
        )
    )
    assert _short_holds(missing_ttd, n_signals_floor=60) is False
    mixed = _report((_kind("healthy_laplace", far=0.0), _kind("slow_gradual_45", detection=0.5, ttd=10.0)))
    assert _medium_holds(mixed, n_signals_floor=30) is False
    with pytest.raises(ContinuityRefused, match="unique"):
        assert_independent_seeds((314159, 314159))
    rng = random.Random(1)
    with pytest.raises(ContinuityRefused, match="unknown independent"):
        path_for("not_a_kind", rng, oos_mean=0.7, oos_stdev=0.05, n=5, decay_start=1)
    assert decaying_kind("slow_gradual_30") is True


@pytest.mark.unit
def test_proof_cli_verify_weekly_and_unknown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class _Ok:
        passed = True

    monkeypatch.setattr(cli_mod, "run_empirical_verification", lambda **_kwargs: _Ok())
    assert proof_main(["verify", "--n-per-kind", "1", "--n-days", "8", "--decay-start", "3"]) == 0

    class _Fail:
        passed = False

    monkeypatch.setattr(cli_mod, "run_empirical_verification", lambda **_kwargs: _Fail())
    assert proof_main(["verify"]) == 2

    class _Data:
        usable = True

    class _Cycle:
        data = _Data()
        kill_rate_flag = "flag_all_dead_check_known_good_synthetics"

    monkeypatch.setattr(cli_mod, "run_research_cycles", lambda **_kwargs: _Cycle())
    monkeypatch.setattr(cli_mod, "assert_ledger_allows_run", lambda **_kwargs: None)
    write_passing_null_only_json(tmp_path)
    assert proof_main(["research", "--report-dir", str(tmp_path)]) == 0

    class _Quiet:
        data = _Data()
        kill_rate_flag = "within_expectation"

    monkeypatch.setattr(cli_mod, "run_research_cycles", lambda **_kwargs: _Quiet())
    assert proof_main(["research", "--report-dir", str(tmp_path)]) == 0

    captured: list[list[str]] = []

    def _scan(argv: list[str]) -> int:
        captured.append(list(argv))
        return 0

    monkeypatch.setattr(cli_mod, "run_guardian_scan", _scan)
    assert (
        proof_main(
            [
                "weekly",
                "--state-dir",
                str(tmp_path / "s"),
                "--report-dir",
                str(tmp_path / "r"),
                "--evolution-log-dir",
                str(tmp_path / "e"),
                "--mutation-report",
                str(tmp_path / "m.json"),
            ]
        )
        == 0
    )
    assert "--evolution-log-dir" in captured[0]
    assert "--mutation-report" in captured[0]

    parser = build_parser()
    monkeypatch.setattr(parser, "parse_args", lambda _argv=None: argparse.Namespace(command="nope"))
    monkeypatch.setattr(cli_mod, "build_parser", lambda: parser)
    with pytest.raises(AssertionError, match="unknown command"):
        proof_main(["verify"])


@pytest.mark.unit
def test_proof_module_entrypoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_mod, "main", lambda argv=None: 0)
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("lumina_research.proof", run_name="__main__")
    assert exc.value.code == 0


@pytest.mark.unit
def test_empirical_failures_and_log_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gate = GateSuiteReport(
        cases=(
            GateCase(
                name="noise_ar1",
                seed=1,
                expected_pass=False,
                passed=True,
                reject_reasons=(),
                pbo=0.1,
                dsr=0.9,
                wfe=0.8,
                n_oos_windows=6,
                purge_applied=True,
                embargo_applied=True,
                n_trials=2,
                median_oos=0.2,
            ),
        ),
        passed=False,
    )
    floor = _report((_kind("healthy_laplace", far=0.0),))
    continuity = ContinuitySuiteReport(
        floor=floor,
        slow=floor,
        floor_passed=False,
        short_passed=False,
        medium_passed=False,
        slow_notes="fail",
    )
    mutation = MutationFloorResult(
        passed=False,
        kill_rate=0.1,
        n_mutants=10,
        n_non_equivalent=10,
        n_excluded=0,
        n_killed=1,
        observed="low",
        required="kill_rate>=0.80",
        path="x",
    )
    assert _failures(gate, continuity, mutation) == (
        "gate_suite",
        "independent_continuity",
        "short_horizon",
        "medium_horizon",
        "mutation_kill_rate",
    )
    mixed_gate = GateSuiteReport(cases=gate.cases, passed=True)
    mixed_cont = ContinuitySuiteReport(
        floor=floor,
        slow=floor,
        floor_passed=True,
        short_passed=True,
        medium_passed=False,
        slow_notes="medium only",
    )
    mixed_mut = MutationFloorResult(
        passed=True,
        kill_rate=0.85,
        n_mutants=320,
        n_non_equivalent=320,
        n_excluded=0,
        n_killed=272,
        observed="ok",
        required="kill_rate>=0.80",
        path="x",
    )
    assert _failures(mixed_gate, mixed_cont, mixed_mut) == ("medium_horizon",)
    monkeypatch.setattr(runner_mod, "run_gate_suite", lambda **_kwargs: gate)
    monkeypatch.setattr(runner_mod, "run_independent_continuity", lambda **_kwargs: continuity)
    monkeypatch.setattr(runner_mod, "evaluate_mutation_floor", lambda _path: mutation)
    monkeypatch.setattr(runner_mod, "resolve_mutation_report", lambda _path: tmp_path / "mutation.json")
    result = run_empirical_verification(
        work_dir=tmp_path / "work",
        report_dir=tmp_path / "reports",
        evolution_log_dir=tmp_path / "evo",
        n_per_kind=1,
        n_days=8,
        decay_start=3,
        seeds=INDEPENDENT_SEEDS[:1],
        instruments=("MES",),
    )
    assert result.passed is False
    log_proof_event(path=tmp_path / "e.jsonl", event="none", metrics={"ok": True}, evolution_log_dir=None)
    log_proof_event(
        path=tmp_path / "e.jsonl",
        event="again",
        metrics={"ok": True},
        evolution_log_dir=tmp_path / "evo",
    )
    log_proof_event(
        path=tmp_path / "e.jsonl",
        event="third",
        metrics={"ok": True},
        evolution_log_dir=tmp_path / "evo",
    )


@pytest.mark.unit
def test_sim_safety_whitelist_sim_then_shadow_only() -> None:
    with pytest.raises(SimSafetyRefused, match="ADR cannot be attached"):
        SimSafetyConfig(live_adr_path="docs/adr/9999-live.md")
    with pytest.raises(SimSafetyRefused, match="sequence"):
        SimSafetyConfig.from_mapping({"sim_whitelist": 1})
    cfg = SimSafetyConfig()
    object.__setattr__(cfg, "sim_whitelist", frozenset({"SIM1"}))
    gate = SimSafetyGate(cfg)
    with pytest.raises(SimSafetyRefused, match="shadow only"):
        gate.admit(mode="sim", account_id="SIM1")
    with pytest.raises(SimSafetyRefused, match="not allowed"):
        gate.admit(mode=cast(ExecutionMode, "paper"), account_id="SHADOW")
    allowed = SimSafetyConfig()
    object.__setattr__(allowed, "sim_whitelist", frozenset({"SIM1"}))
    object.__setattr__(allowed, "allowed_modes", frozenset({"shadow", "sim"}))
    SimSafetyGate(allowed).admit(mode="sim", account_id="SIM1")


@pytest.mark.unit
def test_shadow_mapped_not_shadow_and_guards(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    book = ShadowBook(
        bus=EventBus(),
        authority=ProvenanceAuthority(),
        experiment_log_path=tmp_path / "exp.jsonl",
        blackboard=AgentBlackboard(persistence_path=tmp_path / "bb.jsonl"),
    )
    monkeypatch.setattr(SimSafetyGate, "admit", lambda self, **_kwargs: None)
    with pytest.raises(PortRefused, match="shadow mode only"):
        book.observe_signal(
            strategy_id="hyp-sim",
            direction="buy",
            size=1.0,
            expected_horizon="intraday",
            instrument="MES",
            limit_price=5000.0,
            mode="sim",
        )
    signal, _fill, _decision = book.observe_signal(
        strategy_id="hyp-ok",
        direction="buy",
        size=1.0,
        expected_horizon="intraday",
        instrument="MES",
        limit_price=5000.0,
    )
    assert book._guard_signal("rogue", {}) is False
    assert book._guard_signal(SHADOW_AGENT_ID, {}) is False
    live_signal = dict(signal.model_dump(mode="json"))
    live_signal["mode"] = "live"
    assert book._check_signal(SHADOW_AGENT_ID, live_signal, consume=False) is False
    assert book._guard_order("rogue", {}) is False
    assert book._guard_order(SHADOW_AGENT_ID, {}) is False
    live_order = dict(book.orders()[0].model_dump(mode="json"))
    live_order["mode"] = "live"
    assert book._check_order(SHADOW_AGENT_ID, live_order, consume=False) is False
    assert book._guard_fill("rogue", {}) is False
    assert book._guard_fill(SHADOW_AGENT_ID, {}) is False
    fabric = dict(book.fills()[0].model_dump(mode="json"))
    fabric["source"] = "fabric"
    assert book._check_fill(FILL_AGENT_ID, fabric, consume=False) is False
    assert book._guard_alert("rogue", {}) is False
    assert book._guard_alert(SAFETY_AGENT_ID, {}) is False
    assert book._guard_fill_bb(SHADOW_AGENT_ID, {}) is False
    assert book._guard_alert_bb(SAFETY_AGENT_ID, {}) is False


@pytest.mark.unit
def test_fill_sink_unknown_source_and_seal_list() -> None:
    sink = FillSink()
    bogus = ResearchFillEvent.model_construct(
        schema_version="research.fill.observed.v1",
        strategy_id="s",
        fill_price=1.0,
        qty=1.0,
        slippage=0.0,
        commission=0.0,
        timestamp="t",
        fill_id="f",
        instrument="MES",
        client_order_id="c",
        source="other",
        provenance_mac="a" * 64,
    )
    with pytest.raises(AssertionError):
        sink.ingest(bogus)
    authority = ProvenanceAuthority()
    assert accept_mac(authority, b"hello", "a" * 64, None) is False
    assert _stable([{"b": 1}, 2]) == [{"b": 1}, 2]
    fields = {
        "schema_version": "research.signal.intent.v1",
        "strategy_id": "s",
        "direction": "buy",
        "size": 1.0,
        "timestamp": "t",
        "expected_horizon": "intraday",
        "instrument": "MES",
        "account_id": "SHADOW",
        "mode": "shadow",
        "client_order_id": "c",
    }
    assert isinstance(canonical_signal(fields), bytes)


@pytest.mark.unit
def test_weekly_killed_detection_and_horizons(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = tmp_path / "experiments.jsonl"
    log.write_text(
        "\n"
        + json.dumps([1, 2])
        + "\n"
        + json.dumps(
            {
                "event": "hypothesis",
                "metrics": {"metrics": {"passed": True}},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    rows = load_hypothesis_rows(log)
    assert len(rows) == 1
    assert rows[0]["inner_metrics"] == {"passed": True}
    runtime = make_runtime(tmp_path)
    signal = admit_signal(runtime, "hyp-w", trial_id=1)
    paths = (
        DetectionPath(
            signal_id="s",
            decaying=True,
            detected=True,
            false_alarm=False,
            time_to_detect=6,
            final_stage="deweighted",
            kind="abrupt_student",
        ),
    )
    detection = DetectionReport(
        seed=1,
        n_healthy=0,
        n_decaying=1,
        n_detected=1,
        n_false_alarms=0,
        detection_rate=1.0,
        false_alarm_rate=0.0,
        median_time_to_detect=6.0,
        mean_time_to_detect=6.0,
        paths=paths,
        p90_time_to_detect=6.0,
    )
    empty_paths = DetectionReport(
        seed=1,
        n_healthy=1,
        n_decaying=0,
        n_detected=0,
        n_false_alarms=0,
        detection_rate=0.0,
        false_alarm_rate=0.0,
        median_time_to_detect=None,
        mean_time_to_detect=None,
        paths=(),
        p90_time_to_detect=None,
    )
    multi = MultiSeedDetectionReport(
        seeds=(
            SeedDetectionRow(
                seed=1,
                instrument="MES",
                n_signals=3,
                detection_rate=0.9,
                false_alarm_rate=0.0,
                median_time_to_detect=8.0,
                mean_time_to_detect=8.0,
            ),
        ),
        n_signals=3,
        n_seeds=1,
        n_healthy=1,
        n_decaying=2,
        n_detected=2,
        n_false_alarms=0,
        detection_rate=0.9,
        false_alarm_rate=0.0,
        median_time_to_detect=8.0,
        mean_time_to_detect=8.0,
        p10_time_to_detect=4.0,
        p90_time_to_detect=12.0,
        max_time_to_detect=12.0,
        time_to_detect=(8,),
        by_kind=(
            KindMetrics(
                kind="high_vol_mixture",
                n=10,
                n_detected=0,
                n_false_alarms=1,
                detection_rate=0.0,
                false_alarm_rate=0.1,
                median_time_to_detect=None,
                p90_time_to_detect=None,
                max_time_to_detect=None,
            ),
            KindMetrics(
                kind="abrupt_student",
                n=10,
                n_detected=9,
                n_false_alarms=0,
                detection_rate=0.9,
                false_alarm_rate=0.0,
                median_time_to_detect=8.0,
                p90_time_to_detect=10.0,
                max_time_to_detect=12.0,
            ),
            _empty_kind(kind="gradual_smooth", n=0),
        ),
        paths=(),
    )
    weekly = build_weekly_metrics(
        hypotheses=(
            {"event": "validation", "passed": False},
            {"event": "validation", "killed": True},
            {"event": "validation", "metrics": {"passed": False}},
            {"event": "validation", "metrics": {"metrics": {"passed": False}}},
            {"event": "validation", "metrics": {"reject_reason": "pbo"}},
            {"event": "validation", "metrics": {"failed_checks": ["pbo"]}},
            {"killed": True},
        ),
        signals=(signal,),
        live_means={signal.signal_id: 0.55},
        guardian=GuardianReport(
            cadence="weekly",
            n_signals=1,
            n_checks=1,
            n_ok=1,
            n_warn=0,
            n_violations=0,
            suspend_proposals=(),
            finding_ids=(),
            passed=True,
        ),
        detection=multi,
        slow_decay=(_empty_kind(kind="slow_gradual_45", n=0),),
    )
    assert weekly.n_killed >= 1
    assert weekly.realized_vs_expected[0].delta is not None
    missing_live = build_weekly_metrics(signals=(signal,), detection=detection)
    assert missing_live.realized_vs_expected[0].realized is None
    quiet = build_weekly_metrics(detection=empty_paths)
    assert quiet.false_alarm_rate == 0.0
    state = tmp_path / "weekly-state"
    live_runtime = ContinuityRuntime(
        audit_path=state / "audit.jsonl",
        experiment_log_path=state / "experiments.jsonl",
    )
    admit_signal(live_runtime, "hyp-cli", trial_id=9)
    admit_signal(live_runtime, "hyp-empty", trial_id=10)
    live_runtime.observe("hyp-cli", 0.71)
    monkeypatch.setattr(monitoring_cli_mod, "ContinuityRuntime", lambda **_kwargs: live_runtime)
    code = monitoring_main(["weekly", "--state-dir", str(state), "--report-dir", str(tmp_path / "weekly-out")])
    assert code in {0, 2}


@pytest.mark.unit
def test_material_horizons_vol_and_mutation_edges(tmp_path: Path) -> None:
    cfg = load_default_config()
    with pytest.raises(ContinuityRefused, match="empty"):
        assess_material((0.7, 0.7), (), cfg)
    with pytest.raises(ContinuityRefused, match="non-finite OOS"):
        assess_material((0.7,) * 30, (float("nan"), 0.7), cfg)
    negative = assess_material(tuple(-0.8 for _ in range(30)), tuple(-0.2 for _ in range(6)), cfg)
    assert negative.ready is True
    zero_oos = assess_material(tuple(-0.1 for _ in range(30)), tuple(0.0 for _ in range(6)), cfg)
    assert zero_oos.ready is True
    assert _ratio(-1.0, 0.0) == -math.inf
    with pytest.raises(ContinuityRefused, match="non-finite live"):
        _max_drawdown((1.0, float("nan")))
    short = DecayAssessment(
        method="cusum",
        severity=0,
        stage="active",
        statistic=0.0,
        threshold=0.0,
        live_mean=0.7,
        oos_mean=0.7,
        oos_stdev=0.05,
        percentile=None,
        cusum=None,
        sprt_llr=None,
        window=20,
        votes_deweight=0,
        votes_suspend=0,
        votes_retire=0,
        ready=True,
        horizon="short",
    )
    medium = DecayAssessment(
        method="cusum",
        severity=1,
        stage="deweighted",
        statistic=1.0,
        threshold=1.0,
        live_mean=0.2,
        oos_mean=0.7,
        oos_stdev=0.05,
        percentile=None,
        cusum=None,
        sprt_llr=None,
        window=40,
        votes_deweight=1,
        votes_suspend=0,
        votes_retire=0,
        ready=True,
        horizon="medium",
    )

    def _short(*_args: object, **_kwargs: object) -> DecayAssessment:
        return short

    def _medium(*_args: object, **_kwargs: object) -> DecayAssessment:
        return medium

    original_decay = horizons_mod.assess_decay
    original_material = horizons_mod.assess_material
    original_medium = horizons_mod._medium
    horizons_mod.assess_decay = _short  # type: ignore[method-assign]
    horizons_mod.assess_material = _short  # type: ignore[method-assign]
    horizons_mod._medium = _medium  # type: ignore[method-assign]
    try:
        combined = combined_assessment(tuple(0.7 for _ in range(45)), (0.7, 0.72, 0.74, 0.76), cfg)
        assert combined.horizon == "medium"
        assert combined.assessment.stage == "deweighted"
        material_wins = DecayAssessment(
            method="cusum",
            severity=1,
            stage="deweighted",
            statistic=1.0,
            threshold=1.0,
            live_mean=0.2,
            oos_mean=0.7,
            oos_stdev=0.05,
            percentile=None,
            cusum=None,
            sprt_llr=None,
            window=20,
            votes_deweight=1,
            votes_suspend=0,
            votes_retire=0,
            ready=True,
            horizon="short",
        )
        horizons_mod.assess_material = lambda *_a, **_k: material_wins  # type: ignore[method-assign]
        horizons_mod._medium = lambda *_a, **_k: short  # type: ignore[method-assign]
        material_combined = combined_assessment(tuple(0.7 for _ in range(45)), (0.7, 0.72, 0.74, 0.76), cfg)
        assert material_combined.assessment.stage == "deweighted"
        assert material_combined.horizon == "short"
    finally:
        horizons_mod.assess_decay = original_decay  # type: ignore[method-assign]
        horizons_mod.assess_material = original_material  # type: ignore[method-assign]
        horizons_mod._medium = original_medium  # type: ignore[method-assign]
    with pytest.raises(ContinuityRefused):
        realized_vol((1.0, 2.0), window=1)
    with pytest.raises(ContinuityRefused):
        realized_vol(tuple(float("nan") for _ in range(20)), window=20)
    with pytest.raises(ContinuityRefused):
        trailing_percentile((1.0, 2.0), pct=1.5)
    with pytest.raises(ContinuityRefused):
        classify_vol_regime(tuple(1.0 for _ in range(80)), trailing_window=1)
    original_vol = vol_mod.realized_vol
    original_pct = vol_mod.trailing_percentile

    def _fixed_vol(*_args: object, **_kwargs: object) -> float:
        return 2.0

    def _fixed_pct(_sample: object, *, pct: float) -> float:
        return 100.0 if pct > 0.6 else 1.0

    vol_mod.realized_vol = _fixed_vol  # type: ignore[method-assign]
    vol_mod.trailing_percentile = _fixed_pct  # type: ignore[method-assign]
    try:
        assert classify_vol_regime(tuple(1.0 for _ in range(80)), instrument="ES") == "high_vol"
    finally:
        vol_mod.realized_vol = original_vol  # type: ignore[method-assign]
        vol_mod.trailing_percentile = original_pct  # type: ignore[method-assign]
    missing = resolve_mutation_report(None, state_dir=Path("/tmp/does-not-exist-phase5"))
    assert missing is None or missing.is_file()
    original_reports = mutation_mod.DEFAULT_MUTATION_REPORTS
    mutation_mod.DEFAULT_MUTATION_REPORTS = ()
    try:
        assert resolve_mutation_report(None) is None
    finally:
        mutation_mod.DEFAULT_MUTATION_REPORTS = original_reports
    bad_rate = tmp_path / "phase5-mut-bad.json"
    bad_rate.write_text(
        json.dumps(
            {
                "kill_rate": 1.5,
                "n_mutants": 320,
                "n_killed": 10,
                "n_excluded": 0,
            }
        ),
        encoding="utf-8",
    )
    assert evaluate_mutation_floor(bad_rate).observed.startswith("invalid")
    bad_count = tmp_path / "phase5-mut-count.json"
    bad_count.write_text(
        json.dumps(
            {
                "kill_rate": 0.9,
                "n_mutants": -1,
                "n_killed": 1,
                "n_excluded": 0,
            }
        ),
        encoding="utf-8",
    )
    assert evaluate_mutation_floor(bad_count).observed.startswith("invalid")
    omitted = tmp_path / "phase5-mut-omit.json"
    omitted.write_text(
        json.dumps(
            {
                "kill_rate": 0.9,
                "n_mutants": 320,
                "n_killed": 288,
                "n_excluded": 0,
            }
        ),
        encoding="utf-8",
    )
    ok_omit = evaluate_mutation_floor(omitted)
    assert ok_omit.n_non_equivalent == 320
    not_number = tmp_path / "phase5-mut-str.json"
    not_number.write_text(
        json.dumps({"kill_rate": "high", "n_mutants": 320, "n_killed": 1, "n_excluded": 0}),
        encoding="utf-8",
    )
    assert evaluate_mutation_floor(not_number).observed.startswith("invalid")
    not_int = tmp_path / "phase5-mut-float.json"
    not_int.write_text(
        json.dumps({"kill_rate": 0.9, "n_mutants": 320.5, "n_killed": 1, "n_excluded": 0}),
        encoding="utf-8",
    )
    assert evaluate_mutation_floor(not_int).observed.startswith("invalid")


@pytest.mark.unit
def test_catalog_runtime_and_geometry_edges(monkeypatch: pytest.MonkeyPatch) -> None:
    generator = EconomicCatalogGenerator()
    assert generator.generator_id == "economic_catalog"
    with pytest.raises(GeneratorError, match="start at index 0"):
        generator.drafts(rng=random.Random(1), count=24, start_index=1)
    short = EconomicRationale.model_construct(
        mechanism="x",
        why_edge_exists="y",
        other_side="z",
        expected_regime="r",
        falsification_criterion="f",
        holding_period="h",
        survives_costs="c",
    )
    with pytest.raises(RuntimeError, match="incomplete"):
        catalog_mod._require_rationale(short)
    with pytest.raises(GeometryRefused, match="stop"):
        require_geometry(root="ES", target_ticks=8, stop_ticks=0)
    original_vx = catalog_mod._volatility_expansion
    monkeypatch.setattr(catalog_mod, "_volatility_expansion", lambda: ())
    with pytest.raises(RuntimeError, match="must contain"):
        catalog()
    monkeypatch.setattr(catalog_mod, "_volatility_expansion", original_vx)
    monkeypatch.setattr(catalog_mod, "REGISTERED_TEMPLATE_IDS", frozenset({"not_a_template"}))
    with pytest.raises(RuntimeError, match="12 registered"):
        catalog()
    fake = type("Spec", (), {"root": "CL"})()
    monkeypatch.setattr(cost_bands_mod, "spec_for", lambda _root: fake)
    with pytest.raises(ValueError, match="no cost band"):
        band_for("CL")
    monkeypatch.setattr(geometry_mod, "TICK_FLOORS", {})
    with pytest.raises(GeometryRefused, match="no tick floors"):
        floors_for("ES")


@pytest.mark.unit
def test_data_malformed_fallback_and_timestamps(tmp_path: Path) -> None:
    mes = tmp_path / "data" / "research" / "MES" / "1m"
    _write_csv(mes / "mes.csv", _bars(n=241))
    status = discover_data(repo_root=tmp_path)
    fallback = tape_for(status, "ES")
    assert fallback.instrument == "MES"
    assert tape_for(status, "MES").instrument == "MES"
    short_status = DataStatus(
        usable=False,
        tapes=(LoadedTape(instrument="ES", bar_size="1m", path=tmp_path / "x", bars=_bars(n=10)),),
        searched=(),
        missing=(),
        required={},
    )
    with pytest.raises(DataRefused):
        tape_for(short_status, "ES")
    duplicates = _search_roots(tmp_path, tmp_path / "data" / "research")
    assert len(duplicates) >= 1
    assert _timestamp_ns(True) is None
    assert _timestamp_ns(1_700_000_000) == 1_700_000_000 * 1_000_000_000
    assert _timestamp_ns(1_700_000_000.0) is not None
    assert _timestamp_ns("") is None
    assert _timestamp_ns("not-a-date") is None
    assert _timestamp_ns("2026-10-28T00:00:00") is None
    assert _timestamp_ns(object()) is None
    assert _as_float(True) is None
    assert _as_float("nope") is None
    assert _as_float(object()) is None
    assert _as_float("1.5") == 1.5
    assert _bar_from_mapping({"timestamp": 1, "open": 2, "high": 1, "low": 1, "close": 1, "volume": 1}) is None
    es_json = tmp_path / "data" / "research" / "ES" / "1m"
    es_json.mkdir(parents=True)
    (es_json / "notes.txt").write_text("skip", encoding="utf-8")
    (es_json / "short.csv").write_text("timestamp,open,high,low,close,volume\n", encoding="utf-8")
    (es_json / "bad.json").write_text("{not-json", encoding="utf-8")
    lines = ["", "not-json", json.dumps([1, 2]), json.dumps({"open": True, "high": 1, "low": 1, "close": 1})]
    (es_json / "mix.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (es_json / "arr.json").write_text(json.dumps([1, {"open": 1}]), encoding="utf-8")
    rows = []
    px = 5000.0
    for index in range(241):
        stamp = datetime.fromtimestamp(1_700_000_000 + index * 60, tz=timezone.utc).isoformat()
        rows.append(
            {
                "timestamp": stamp,
                "open": str(px),
                "high": px + 0.5,
                "low": px - 0.5,
                "close": px,
                "volume": "1000",
            }
        )
    rows[0] = {"timestamp": True, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}
    rows[1] = {"timestamp": 1_700_000_000, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}
    rows[2] = {"timestamp": 1_700_000_000.0, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}
    rows[3] = {"timestamp": "", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}
    rows[4] = {"timestamp": "not-a-date", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}
    rows[5] = {
        "timestamp": "2026-10-28T00:00:00",
        "open": 1,
        "high": 1,
        "low": 1,
        "close": 1,
        "volume": 1,
    }
    rows[6] = {"timestamp": "t", "open": None, "high": 1, "low": 1, "close": 1, "volume": 1}
    rows[7] = {"open": 2, "high": 1, "low": 1, "close": 1, "volume": 1, "timestamp": 1}
    rows[8] = {"timestamp": "1", "open": "nope", "high": 1, "low": 1, "close": 1, "volume": 1}
    five = tmp_path / "data" / "research" / "NQ" / "5m"
    five.mkdir(parents=True)
    _write_csv(five / "nq.csv", _bars(n=241, seed=2))
    record = struct.Struct("<q4iI")
    short_bin = tmp_path / "reports" / "playground_bar_archive" / "MNQ.bars"
    short_bin.parent.mkdir(parents=True, exist_ok=True)
    short_bin.write_bytes(record.pack(1, 1, 2, 0, 1, 10))
    loaded = discover_data(repo_root=tmp_path)
    roots = {item.instrument for item in loaded.tapes}
    assert "MES" in roots
    assert "NQ" in roots
    with pytest.raises(StrategyRefused):
        simulate(
            family="mean_reversion",
            bars=_bars(n=10),
            geometry=require_geometry(root="MES", target_ticks=16, stop_ticks=8),
            lookback=5,
            threshold=1.0,
            mode="fade",
        )
    with pytest.raises(StrategyRefused, match="align"):
        strategies_mod.mark_to_market_tape(_bars(n=241), (0.0,), "MES")
    bar = ResearchBar(ts_ns=1, open=10.0, high=10.5, low=9.5, close=10.0, volume=100.0)
    assert trade_through_fill(side=0.0, limit=9.6, bar=bar, average_volume=50.0) is False
    assert trade_through_fill(side=-1.0, limit=10.6, bar=bar, average_volume=50.0) is False
    assert trade_through_fill(side=-1.0, limit=10.4, bar=bar, average_volume=50.0) is True
    assert fill_probability(side=1.0, limit=9.0, bar=bar, average_volume=50.0) == 0.0
    with pytest.raises(FillRefused):
        fill_probability(side=1.0, limit=9.6, bar=bar, average_volume=0.0)
    assert death_reason(tested=False, passed=False, reasons=(), stopped=False) == "not_tested"
    assert death_reason(tested=True, passed=True, reasons=(), stopped=False) == "survived"
    assert death_reason(tested=True, passed=False, reasons=("pbo",), stopped=False) == "pbo"
    assert death_reason(tested=True, passed=False, reasons=(), stopped=False) == "rejected_without_reasons"
    assert mapping_metric({"x": True}, "x") is None
    assert mapping_metric({"x": 1.5}, "x") == 1.5
    geo = require_geometry(root="MES", target_ticks=16, stop_ticks=8)
    row = CycleRow(
        hypothesis_id="h",
        config_id="c",
        template_id="mean_reversion",
        family="mean_reversion",
        instrument="MES",
        pre_registered=True,
        tested=True,
        passed=True,
        reject_reasons=(),
        pbo=0.1,
        dsr=0.9,
        wfe=0.8,
        n_oos_windows=6,
        median_oos=0.2,
        geometry=geo,
        death_reason="survived",
    )
    report = CycleReport(
        n_hypotheses=1,
        n_tested=1,
        n_killed=0,
        n_survivors=1,
        kill_rate=0.0,
        kill_rate_flag="within_expectation",
        cost_bands=(),
        data=DataStatus(usable=True, tapes=(), searched=(), missing=(), required={}),
        rows=(row,),
        geometry_by_root=(geo,),
        stopped=False,
        stop_reason="",
    )
    _json_path, md_path = write_cycle_reports(report, tmp_path / "rep")
    assert "Survivors" in md_path.read_text(encoding="utf-8")


@pytest.mark.unit
def test_strategy_signed_branches() -> None:
    geo = require_geometry(root="MES", target_ticks=16, stop_ticks=8)
    down: list[ResearchBar] = []
    px = 5100.0
    for index in range(241):
        px -= 0.25
        down.append(
            ResearchBar(
                ts_ns=1_700_000_000_000_000_000 + index * 60_000_000_000,
                open=px + 0.4,
                high=px + 0.5,
                low=px - 0.5,
                close=px - 0.3,
                volume=1_000.0,
            )
        )
    simulate(family="volume_imbalance", bars=tuple(down), geometry=geo, lookback=10, threshold=0.1, mode="fade")
    simulate(family="regime_momentum", bars=tuple(down), geometry=geo, lookback=10, threshold=0.9, mode="follow")
    simulate(family="close_reversal", bars=tuple(down), geometry=geo, lookback=3, threshold=0.0, mode="fade")
    simulate(family="time_of_day", bars=tuple(down), geometry=geo, lookback=15, threshold=0.0, mode="fade")
    simulate(family="volatility_expansion", bars=tuple(down), geometry=geo, lookback=20, threshold=0.1, mode="breakout")
    compress: list[ResearchBar] = []
    px = 5000.0
    for index in range(241):
        width = 0.1 if 20 <= index < 40 else 2.0
        close = px + (0.5 if index % 2 == 0 else -0.5)
        compress.append(
            ResearchBar(
                ts_ns=1_700_000_000_000_000_000 + index * 60_000_000_000,
                open=px,
                high=px + width,
                low=px - width,
                close=close,
                volume=1_000.0,
            )
        )
    simulate(
        family="range_compression", bars=tuple(compress), geometry=geo, lookback=20, threshold=0.1, mode="breakout"
    )
