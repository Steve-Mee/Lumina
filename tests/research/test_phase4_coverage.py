"""Branch coverage for Phase 4 config, seals, CLI, guardian, and refuse paths."""

from __future__ import annotations

import json
import runpy
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from lumina_core.agent_orchestration.schemas_research import (
    CAPACITY_AGENT_ID,
    GUARDIAN_AGENT_ID,
    MONITOR_AGENT_ID,
    REPLENISH_AGENT_ID,
    PromotionCandidate,
    SignalDeweighted,
)
from lumina_core.engine.agent_blackboard import AgentBlackboard
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.evolution.integrity import capture_integrity
from lumina_research.evolution.regime import RegimeAction
from lumina_research.monitoring.capacity import CapacityController
from lumina_research.monitoring.cli import build_parser, load_decisions, main
from lumina_research.monitoring.config import ContinuityConfig, ContinuityConfigError, config_from_mapping, load_default_config
from lumina_research.monitoring.guardian import GuardianAgent, _integrity
from lumina_research.monitoring.loop import ContinuityRuntime, run_phase4_detection
from lumina_research.monitoring.monitor import LivePerformanceMonitor
from lumina_research.monitoring.monitor import _intermediate
from lumina_research.monitoring.registry import (
    LiveSignalRegistry,
    _count,
    _instrument,
    _number,
    _oos_values,
    _replace,
    _required_float,
    _text,
)
from lumina_research.monitoring.replenish import ReplenishAgent
from lumina_research.monitoring.report import DetectionPath, build_detection_report, log_decision
from lumina_research.monitoring.seal import _require_sequence, canonical_capacity, canonical_decay, canonical_guardian, mac_ok
from lumina_research.monitoring.sizing import ContinuitySizer
from lumina_research.monitoring.statistics import (
    _display,
    _select,
    assess_decay,
    cusum_down,
    empirical_percentile,
    rolling_mean,
    sprt_llr,
    sprt_threshold,
    z_score,
)
from lumina_research.monitoring.synthetic import DEFAULT_OOS, seal_promotion_pair
from lumina_research.monitoring.types import (
    ContinuityRefused,
    LiveSignal,
    family_for,
    finite_series,
    require_cluster,
    stage_rank,
    stage_weight,
    tighter_stage,
)
from lumina_research.risk_core.types import Decision, DecisionKind, OrderProposal
from tests.research.phase4_harness import admit_signal, make_runtime


@pytest.mark.unit
def test_config_rejects_unknown_keys_and_weak_floors(tmp_path: Path) -> None:
    cfg = load_default_config()
    raw = asdict(cfg)
    with pytest.raises(ContinuityConfigError, match="extra"):
        config_from_mapping({**raw, "nope": 1})
    weak = dict(raw)
    weak["pbo_promote_max"] = 0.4
    with pytest.raises(ContinuityConfigError, match="0.25"):
        config_from_mapping(weak)
    weak = dict(raw)
    weak["min_oos_windows"] = 3
    with pytest.raises(ContinuityConfigError, match="floor"):
        config_from_mapping(weak)
    weak = dict(raw)
    weak["method"] = "nope"
    with pytest.raises(ContinuityConfigError, match="method"):
        config_from_mapping(weak)
    path = tmp_path / "limits.toml"
    path.write_text("window = 20\n", encoding="utf-8")
    with pytest.raises(ContinuityConfigError):
        load_default_config(path)


@pytest.mark.unit
def test_types_and_rolling_mean_refuse() -> None:
    assert family_for("mes") == "es_index"
    with pytest.raises(ContinuityRefused):
        family_for("XYZ")
    assert finite_series((1.0, 2.0)) == (1.0, 2.0)
    with pytest.raises(ContinuityRefused):
        finite_series((float("nan"),))
    assert stage_rank("retired") == 3
    with pytest.raises(ContinuityRefused):
        rolling_mean((1.0,), 5)
    assert sprt_threshold(alpha=0.05, beta=0.10) > 0.0


@pytest.mark.unit
def test_events_forbid_extras_and_require_weight_drop() -> None:
    with pytest.raises(ValidationError):
        SignalDeweighted.model_validate(
            {
                "signal_id": "s",
                "hypothesis_id": "s",
                "config_id": "s",
                "trial_id": 1,
                "agent_id": "live_monitor_agent",
                "previous_weight": 0.5,
                "new_weight": 1.0,
                "reason": "nope",
                "provenance_mac": "a" * 64,
                "extra": True,
            }
        )


@pytest.mark.unit
def test_unknown_signal_and_replay_and_duplicate(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    admit_signal(runtime, "hyp-dup", trial_id=1)
    with pytest.raises(ContinuityRefused, match="already_live"):
        admit_signal(runtime, "hyp-dup", trial_id=2)
    with pytest.raises(ContinuityRefused, match="trial_replay"):
        admit_signal(runtime, "hyp-other", trial_id=1)
    with pytest.raises(ContinuityRefused, match="unknown signal"):
        runtime.observe("missing", 0.1)
    with pytest.raises(ContinuityRefused, match="non-finite"):
        runtime.observe("hyp-dup", float("nan"))


@pytest.mark.unit
def test_insufficient_window_does_not_stage(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    admit_signal(runtime, "hyp-short", trial_id=1)
    updated = runtime.observe("hyp-short", 0.8)
    assert updated.stage == "active"
    assert runtime.monitor.series("hyp-short") == (0.8,)


@pytest.mark.unit
def test_log_decision_and_detection_report_helpers(tmp_path: Path) -> None:
    log_decision(
        path=tmp_path / "exp.jsonl",
        agent_id="live_monitor_agent",
        event="decay",
        signal_id="s",
        metrics={"k": 1},
        evolution_log_dir=tmp_path / "brain",
    )
    assert (tmp_path / "brain" / "phase4-continuity.jsonl").is_file()
    report = build_detection_report(
        seed=1,
        paths=(
            DetectionPath("h", False, False, False, None, "active"),
            DetectionPath("d", True, True, False, 12, "retired"),
        ),
    )
    assert report.detection_rate == 1.0
    assert report.false_alarm_rate == 0.0


@pytest.mark.unit
def test_cli_parser_and_bad_cadence(tmp_path: Path) -> None:
    parser = build_parser()
    args = parser.parse_args(["daily", "--state-dir", str(tmp_path), "--report-dir", str(tmp_path / "r")])
    assert args.cadence == "daily"
    runtime = make_runtime(tmp_path)
    with pytest.raises(ContinuityRefused, match="cadence"):
        runtime.guardian_scan("hourly")


@pytest.mark.unit
def test_blackboard_and_replenish_noop_when_above_floor(tmp_path: Path) -> None:
    board = AgentBlackboard(persistence_path=tmp_path / "bb.jsonl")
    runtime = ContinuityRuntime(
        audit_path=tmp_path / "audit.jsonl",
        experiment_log_path=tmp_path / "exp.jsonl",
        blackboard=board,
    )
    admit_signal(runtime, "hyp-1", trial_id=1)
    admit_signal(runtime, "hyp-2", trial_id=2)
    assert runtime.registry.n_active() >= 2
    assert runtime.request_replenishment(seed=1) == ()
    assert runtime.replenish.requests() == ()


@pytest.mark.unit
def test_seal_helpers_round_trip() -> None:
    assert canonical_decay(
        {
            "schema_version": "research.decay.detected.v1",
            "signal_id": "s",
            "hypothesis_id": "s",
            "config_id": "s",
            "trial_id": 1,
            "agent_id": "live_monitor_agent",
            "method": "combined",
            "statistic": 1.0,
            "threshold": 3.0,
            "window": 20,
            "live_mean": 0.1,
            "oos_mean": 0.8,
            "oos_stdev": 0.1,
            "percentile": 0.0,
            "cusum": 1.0,
            "sprt_llr": 0.2,
            "stage": "deweighted",
        }
    )
    assert canonical_guardian(
        {
            "schema_version": "research.guardian.finding.v1",
            "finding_id": "g-1",
            "cadence": "daily",
            "check_id": "costs",
            "signal_id": "s",
            "agent_id": "guardian_agent",
            "passed": True,
            "severity": "ok",
            "suspend_proposed": False,
            "evidence": {"metric": "costs", "observed": "ok", "required": "ok"},
        }
    )


@pytest.mark.unit
def test_load_decisions_rejects_non_objects(tmp_path: Path) -> None:
    (tmp_path / "decisions.json").write_text(json.dumps([1, 2]), encoding="utf-8")
    with pytest.raises(ContinuityRefused):
        load_decisions(tmp_path)


@pytest.mark.unit
def test_config_threshold_ordering() -> None:
    raw = asdict(load_default_config())
    raw["z_retire"] = 0.0
    raw["z_deweight"] = -3.0
    with pytest.raises(ContinuityConfigError, match="z thresholds"):
        config_from_mapping(raw)


@pytest.mark.unit
def test_assess_decay_not_ready_until_window() -> None:
    cfg = load_default_config()
    assessment = assess_decay((0.8, 0.8), DEFAULT_OOS, cfg)
    assert assessment.ready is False
    assert assessment.severity == 0


@pytest.mark.unit
def test_config_validator_matrix() -> None:
    raw = asdict(load_default_config())
    with pytest.raises(TypeError):
        class Child(ContinuityConfig):  # type: ignore[misc]
            pass

    short = dict(raw)
    short["window"] = 5
    short["min_observations"] = 20
    with pytest.raises(ContinuityConfigError, match="window"):
        config_from_mapping(short)
    pct = dict(raw)
    pct["percentile_retire"] = 0.2
    pct["percentile_suspend"] = 0.05
    with pytest.raises(ContinuityConfigError, match="percentile"):
        config_from_mapping(pct)
    cusum = dict(raw)
    cusum["cusum_h_deweight"] = 9.0
    cusum["cusum_h_suspend"] = 5.0
    with pytest.raises(ContinuityConfigError, match="CUSUM"):
        config_from_mapping(cusum)
    weak_reject = dict(raw)
    weak_reject["pbo_reject_min"] = 0.4
    with pytest.raises(ContinuityConfigError, match="0.50"):
        config_from_mapping(weak_reject)
    cases: tuple[tuple[str, object], ...] = (
        ("z_deweight", float("inf")),
        ("cusum_k", 0.0),
        ("min_capacity_weight", -1.0),
        ("percentile_deweight", 1.5),
        ("max_signal_notional_pct", 0.0),
        ("sprt_alpha", 1.0),
        ("window", 0),
        ("min_active_signals", -1),
        ("equity", "x"),
        ("method", 1),
    )
    for key, value in cases:
        broken = dict(raw)
        broken[key] = value
        with pytest.raises(ContinuityConfigError):
            config_from_mapping(broken)


@pytest.mark.unit
def test_statistics_refuse_and_combined_votes() -> None:
    with pytest.raises(ContinuityRefused):
        rolling_mean((1.0, 2.0), 0)
    with pytest.raises(ContinuityRefused):
        rolling_mean((float("nan"),) * 20, 20)
    with pytest.raises(ContinuityRefused):
        z_score(live_mean=0.0, oos_mean=0.0, oos_stdev=0.1, n=0)
    with pytest.raises(ContinuityRefused):
        z_score(live_mean=0.0, oos_mean=0.0, oos_stdev=-0.1, n=5)
    assert z_score(live_mean=1.0, oos_mean=1.0, oos_stdev=0.0, n=5) == 0.0
    with pytest.raises(ContinuityRefused):
        empirical_percentile(0.1, ())
    with pytest.raises(ContinuityRefused):
        empirical_percentile(float("nan"), (0.1, 0.2))
    with pytest.raises(ContinuityRefused):
        cusum_down((0.1,), mu0=0.0, k=-1.0)
    with pytest.raises(ContinuityRefused):
        cusum_down((float("nan"),), mu0=0.0, k=0.1)
    with pytest.raises(ContinuityRefused):
        sprt_llr((0.1,), mu0=float("nan"), mu1=0.0, sigma=1.0)
    assert sprt_llr((0.5, 0.5), mu0=0.5, mu1=0.1, sigma=0.0) == 0.0
    assert sprt_llr((0.0,), mu0=0.5, mu1=0.1, sigma=0.0) == float("inf")
    assert sprt_llr((0.0,), mu0=0.5, mu1=0.9, sigma=0.0) == float("-inf")
    with pytest.raises(ContinuityRefused):
        sprt_llr((float("nan"),), mu0=0.0, mu1=-1.0, sigma=1.0)
    with pytest.raises(ContinuityRefused):
        sprt_threshold(alpha=0.0, beta=0.1)
    with pytest.raises(ContinuityRefused):
        assess_decay((0.1,) * 30, (), load_default_config())
    with pytest.raises(ContinuityRefused):
        assess_decay((0.1,) * 30, (float("nan"),) * 6, load_default_config())
    assert _select("combined", z_sev=3, pct_sev=3, cusum_sev=0, sprt_sev=0) == 3
    assert _select("combined", z_sev=2, pct_sev=2, cusum_sev=0, sprt_sev=0) == 2
    assert _select("combined", z_sev=1, pct_sev=0, cusum_sev=3, sprt_sev=0) == 2
    assert _select("combined", z_sev=0, pct_sev=0, cusum_sev=2, sprt_sev=0) == 2
    assert _select("combined", z_sev=1, pct_sev=1, cusum_sev=0, sprt_sev=0) == 1
    assert _select("combined", z_sev=0, pct_sev=0, cusum_sev=0, sprt_sev=1) == 0
    cfg = load_default_config()
    assert _display("sprt", 0.0, 0.0, 0.0, 1.5, cfg, 2.0) == (1.5, 2.0)
    assert _display("combined", 0.0, 0.0, 4.0, 0.0, cfg, 2.0)[0] == 4.0


@pytest.mark.unit
def test_types_stage_helpers_and_cluster() -> None:
    with pytest.raises(TypeError):
        class Child(LiveSignal):  # type: ignore[misc]
            pass
    assert stage_weight("active", deweight_multiplier=0.5) == 1.0
    assert stage_weight("deweighted", deweight_multiplier=0.5) == 0.5
    assert stage_weight("suspended", deweight_multiplier=0.5) == 0.0
    assert stage_weight("retired", deweight_multiplier=0.5) == 0.0
    assert tighter_stage("retired", "active") == "retired"
    with pytest.raises(ContinuityRefused):
        require_cluster("XYZ")


@pytest.mark.unit
def test_cli_main_error_and_module_entrypoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state = tmp_path / "state"
    state.mkdir()
    (state / "decisions.json").write_text('{"not": "a list"}', encoding="utf-8")
    assert main(["daily", "--state-dir", str(state), "--report-dir", str(tmp_path / "r")]) == 1
    monkeypatch.setattr("sys.argv", ["prog", "weekly", "--state-dir", str(tmp_path / "s"), "--report-dir", str(tmp_path / "out")])
    with pytest.raises(SystemExit) as caught:
        runpy.run_module("lumina_research.monitoring", run_name="__main__")
    assert caught.value.code in {0, 2}


@pytest.mark.unit
def test_capacity_noop_and_issuer_guards(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    admit_signal(runtime, "hyp-small", trial_id=1, quantity=2.0, notional=1_000.0)
    assert runtime.rebalance() == ()
    assert runtime.capacity._guard("rogue", {}) is False
    assert runtime.capacity._guard(CAPACITY_AGENT_ID, {"signal_id": "x"}) is False
    payload = {
        "signal_id": "hyp-small",
        "instrument": "MES",
        "family_id": "es_index",
        "cluster_id": "es",
        "agent_id": CAPACITY_AGENT_ID,
        "previous_scale": 1.0,
        "new_scale": 0.5,
        "reasons": ["signal"],
        "provenance_mac": "0" * 64,
    }
    assert runtime.capacity._guard(CAPACITY_AGENT_ID, {**payload, "new_scale": 0.9, "previous_scale": 0.4}) is False
    assert runtime.capacity._guard(CAPACITY_AGENT_ID, payload) is False
    with pytest.raises(ContinuityRefused, match="cannot increase"):
        runtime.capacity._emit(runtime.registry.require("hyp-small"), previous_scale=0.1, reasons=("signal",))
    with pytest.raises(TypeError):
        class Child(CapacityController):  # type: ignore[misc]
            pass


@pytest.mark.unit
def test_guardian_live_snapshot_and_gated_decision(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    admit_signal(runtime, "hyp-a", trial_id=1)
    runtime.trials.record(config_id="hyp-a", agent_id="hypothesis_agent", metrics={"phase": "test"})
    with pytest.raises(TypeError):
        class Child(GuardianAgent):  # type: ignore[misc]
            pass
    intact = capture_integrity()
    ok = runtime.guardian.scan(cadence="daily", baseline=runtime._snapshot, trials=runtime.trials.records(), live=intact)
    assert ok.n_violations == 0
    bad = replace(intact, live_risk_hash="0" * 64)
    report = runtime.guardian.scan(
        cadence="daily",
        baseline=runtime._snapshot,
        trials=runtime.trials.records(),
        live=bad,
        decisions=({"hypothesis_id": "hyp-a", "gated": True},),
    )
    assert report.n_violations >= 1
    assert runtime.guardian._guard("rogue", {}) is False
    assert runtime.guardian._guard(GUARDIAN_AGENT_ID, {"finding_id": "x"}) is False
    drifted = replace(intact, floors=(0.0, 0.0, 0.0, 0.0, 0.0))
    broken = runtime.guardian.scan(cadence="daily", baseline=drifted, trials=runtime.trials.records(), live=drifted)
    assert broken.n_violations >= 1
    ok_flag, _detail = _integrity(intact)
    assert ok_flag is True
    bad_flag, _why = _integrity(drifted)
    assert bad_flag is False


@pytest.mark.unit
def test_registry_mismatch_tamper_and_helpers(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    candidate, validation = seal_promotion_pair(
        runtime.authority,
        hypothesis_id="hyp-a",
        config_id="hyp-a",
        trial_id=1,
        instrument="MES",
        quantity=2.0,
        notional=10_000.0,
    )
    issue = dict(candidate.model_dump(mode="json"))
    issue["hypothesis_id"] = "hyp-b"
    issue["issue_mac"] = runtime.authority.seal_issue(issue)
    mixed = PromotionCandidate.model_validate(issue)
    with pytest.raises(ContinuityRefused, match="hypothesis mismatch"):
        runtime.admit(mixed, validation)
    candidate_c, validation_c = seal_promotion_pair(
        runtime.authority,
        hypothesis_id="hyp-c",
        config_id="hyp-c",
        trial_id=2,
        instrument="MES",
        quantity=2.0,
        notional=10_000.0,
    )
    issue_c = dict(candidate_c.model_dump(mode="json"))
    issue_c["config_id"] = "other"
    issue_c["issue_mac"] = runtime.authority.seal_issue(issue_c)
    with pytest.raises(ContinuityRefused, match="config mismatch"):
        runtime.admit(PromotionCandidate.model_validate(issue_c), validation_c)
    raw = asdict(load_default_config())
    raw["min_oos_windows"] = 7
    tight = make_runtime(tmp_path / "tight", config=config_from_mapping(raw))
    with pytest.raises(ContinuityRefused, match="charter floor"):
        admit_signal(tight, "hyp-short-oos", trial_id=1, n_oos_windows=6)
    signal = admit_signal(runtime, "hyp-live", trial_id=3)
    assert runtime.registry.apply_stage("hyp-live", "active") is signal
    with pytest.raises(ContinuityRefused, match="illegal capacity"):
        runtime.registry.apply_capacity_scale("hyp-live", 1.5)
    scaled = runtime.registry.apply_capacity_scale("hyp-live", 0.4)
    with pytest.raises(ContinuityRefused, match="cannot increase"):
        runtime.registry.apply_capacity_scale("hyp-live", 0.9)
    lowered = runtime.registry.apply_stage("hyp-live", "deweighted")
    with pytest.raises(ContinuityRefused, match="stage cannot recede"):
        _replace(lowered, stage="active")
    with pytest.raises(ContinuityRefused, match="cannot increase"):
        _replace(scaled, weight=1.1)
    tampered = replace(runtime.registry.require("hyp-live"), admission_mac="0" * 64)
    runtime.registry._signals["hyp-live"] = tampered
    with pytest.raises(ContinuityRefused, match="tampered"):
        runtime.registry.apply_stage("hyp-live", "deweighted")
    with pytest.raises(ContinuityRefused, match="tampered"):
        runtime.registry.apply_capacity_scale("hyp-live", 0.1)
    with pytest.raises(ContinuityRefused):
        _oos_values({})
    with pytest.raises(ContinuityRefused):
        _oos_values({"oos_distribution": {}})
    with pytest.raises(ContinuityRefused):
        _oos_values({"oos_distribution": {"values": [float("nan")]}})
    with pytest.raises(ContinuityRefused):
        _required_float(None, "pbo")
    with pytest.raises(ContinuityRefused):
        _number(float("inf"), "x")
    with pytest.raises(ContinuityRefused):
        _count(True, "n")
    with pytest.raises(ContinuityRefused):
        _text("", "name")
    with pytest.raises(ContinuityRefused):
        _instrument(1)
    with pytest.raises(ContinuityRefused):
        _instrument("FOO")
    _, validation_bad = seal_promotion_pair(
        ProvenanceAuthority(),
        hypothesis_id="hyp-foreign-val",
        config_id="hyp-foreign-val",
        trial_id=8,
        instrument="MES",
        quantity=2.0,
        notional=10_000.0,
    )
    local_c, _local_v = seal_promotion_pair(
        runtime.authority,
        hypothesis_id="hyp-local-c",
        config_id="hyp-local-c",
        trial_id=8,
        instrument="MES",
        quantity=2.0,
        notional=10_000.0,
    )
    with pytest.raises(ContinuityRefused, match="validation provenance"):
        runtime.admit(local_c, validation_bad)
    issue_t = dict(local_c.model_dump(mode="json"))
    issue_t["trial_id"] = 99
    issue_t["issue_mac"] = runtime.authority.seal_issue(issue_t)
    with pytest.raises(ContinuityRefused, match="trial mismatch"):
        runtime.admit(PromotionCandidate.model_validate(issue_t), _local_v)
    with pytest.raises(TypeError):
        class Child(LiveSignalRegistry):  # type: ignore[misc]
            pass


@pytest.mark.unit
def test_monitor_accessors_guards_and_emit(tmp_path: Path) -> None:
    board = AgentBlackboard(persistence_path=tmp_path / "bb.jsonl")
    runtime = ContinuityRuntime(
        audit_path=tmp_path / "audit.jsonl",
        experiment_log_path=tmp_path / "exp.jsonl",
        blackboard=board,
        evolution_log_dir=tmp_path / "evo",
    )
    admit_signal(runtime, "hyp-m", trial_id=1, quantity=2.0, notional=12_000.0)
    admit_signal(runtime, "hyp-m2", trial_id=2, quantity=2.0, notional=12_000.0)
    runtime.rebalance()
    runtime.trials.record(config_id="hyp-m", agent_id="hypothesis_agent", metrics={"phase": "test"})
    runtime.trials.record(config_id="hyp-m2", agent_id="hypothesis_agent", metrics={"phase": "test"})
    runtime.guardian_scan("daily")
    assert runtime.monitor.decay_events() == ()
    assert runtime.monitor.suspend_events() == ()
    assert runtime.monitor.retire_events() == ()
    with pytest.raises(ContinuityRefused, match="non-finite"):
        runtime.observe("hyp-m", "bad")
    with pytest.raises(TypeError):
        class Child(LivePerformanceMonitor):  # type: ignore[misc]
            pass
    signal = runtime.registry.require("hyp-m")
    with pytest.raises(ContinuityRefused, match="active-stage"):
        runtime.monitor._emit_stage(signal, previous_weight=1.0, stage="active", reason="noop")
    with pytest.raises(ContinuityRefused, match="cannot increase"):
        runtime.monitor._emit_stage(signal, previous_weight=0.1, stage="deweighted", reason="up")
    assert runtime.monitor._guard_decay("rogue", {}) is False
    assert runtime.monitor._guard_decay(MONITOR_AGENT_ID, {"signal_id": "x"}) is False
    assert runtime.monitor._guard_deweight("rogue", {}) is False
    assert runtime.monitor._guard_deweight(MONITOR_AGENT_ID, {"signal_id": "x"}) is False
    assert runtime.monitor._guard_suspend("rogue", {}) is False
    assert runtime.monitor._guard_suspend(MONITOR_AGENT_ID, {"signal_id": "x"}) is False
    assert runtime.monitor._guard_retire("rogue", {}) is False
    assert runtime.monitor._guard_retire(MONITOR_AGENT_ID, {"signal_id": "x"}) is False
    weight_payload = {
        "signal_id": "hyp-m",
        "hypothesis_id": "hyp-m",
        "config_id": "hyp-m",
        "trial_id": 1,
        "agent_id": MONITOR_AGENT_ID,
        "previous_weight": 0.4,
        "new_weight": 0.5,
        "reason": "up",
        "provenance_mac": "0" * 64,
    }
    assert runtime.monitor._guard_deweight(MONITOR_AGENT_ID, weight_payload) is False
    suspend_payload = {
        **weight_payload,
        "previous_weight": 0.5,
        "new_weight": 0.2,
        "reason": "not-zero",
    }
    assert runtime.monitor._guard_suspend(MONITOR_AGENT_ID, suspend_payload) is False
    retire_payload = {**suspend_payload, "new_weight": 0.1, "reason": "not-zero-retire"}
    assert runtime.monitor._guard_retire(MONITOR_AGENT_ID, retire_payload) is False
    assert _intermediate("retired", "active") == ()
    mean = sum(DEFAULT_OOS) / len(DEFAULT_OOS)
    for _ in range(30):
        runtime.observe("hyp-m", mean - 0.5)


@pytest.mark.unit
def test_replenish_capacity_reason_and_guards(tmp_path: Path) -> None:
    raw = asdict(load_default_config())
    raw["min_active_signals"] = 0
    raw["min_capacity_weight"] = 50.0
    board = AgentBlackboard(persistence_path=tmp_path / "bb.jsonl")
    runtime = ContinuityRuntime(
        audit_path=tmp_path / "audit.jsonl",
        experiment_log_path=tmp_path / "exp.jsonl",
        config=config_from_mapping(raw),
        blackboard=board,
        evolution_log_dir=tmp_path / "evo",
    )
    admit_signal(runtime, "hyp-1", trial_id=1)
    result = runtime.replenish.maybe_request(seed=1, counts=(1, 1))
    assert result is not None
    assert result[0].reason == "capacity"
    with pytest.raises(ContinuityRefused, match="generator counts"):
        runtime.replenish.maybe_request(seed=1)
    assert runtime.replenish._guard("rogue", {}) is False
    assert runtime.replenish._guard(REPLENISH_AGENT_ID, {"request_id": "x"}) is False
    lonely = ReplenishAgent(
        bus=runtime.bus,
        registry=runtime.registry,
        authority=runtime.authority,
        config=runtime.config,
        experiment_log_path=tmp_path / "exp2.jsonl",
    )
    none_path = lonely.maybe_request(seed=2)
    assert none_path is not None
    with pytest.raises(TypeError):
        class ChildReplenish(ReplenishAgent):  # type: ignore[misc]
            pass


@pytest.mark.unit
def test_sizing_refuses_and_loop_paths(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    admit_signal(runtime, "hyp-sz", trial_id=1, quantity=2.0, notional=10_000.0)
    now = datetime.now(timezone.utc)
    decision = runtime.propose_order("hyp-sz", quantity=2.0, price=5_000.0)
    assert decision.kind in {DecisionKind.APPROVED, DecisionKind.SCALED, DecisionKind.REJECTED}
    with pytest.raises(ContinuityRefused):
        runtime.sizer.propose("hyp-sz", quantity=float("nan"), price=5_000.0, at=now)
    with pytest.raises(ContinuityRefused):
        runtime.sizer.propose(
            "hyp-sz",
            quantity=2.0,
            price=5_000.0,
            at=now,
            regime=RegimeAction(size_multiplier=1.5, throttle=False, vol="low", trend="up"),
        )
    with pytest.raises(TypeError):
        class ChildSizer(ContinuitySizer):  # type: ignore[misc]
            pass
    with pytest.raises(TypeError):
        class ChildRuntime(ContinuityRuntime):  # type: ignore[misc]
            pass
    runtime.registry.apply_capacity_scale("hyp-sz", 0.0)
    blocked = runtime.sizer.propose("hyp-sz", quantity=2.0, price=5_000.0, at=now)
    assert blocked.reason == "monitoring_zero_weight"
    admit_signal(runtime, "hyp-bump", trial_id=2, quantity=2.0, notional=10_000.0)
    tampered = replace(runtime.registry.require("hyp-bump"), admission_mac="0" * 64)
    runtime.registry._signals["hyp-bump"] = tampered
    with pytest.raises(ContinuityRefused, match="tampered"):
        runtime.sizer.propose("hyp-bump", quantity=2.0, price=5_000.0, at=now)
    admit_signal(runtime, "hyp-core", trial_id=3, quantity=2.0, notional=10_000.0)

    class _Bump:
        def heartbeat(self, at: datetime) -> None:
            del at

        def propose_order(self, proposal: OrderProposal) -> Decision:
            return Decision(
                kind=DecisionKind.APPROVED,
                reason="approved",
                quantity=proposal.quantity + 1.0,
                notional=proposal.notional + 1.0,
                agent_id=proposal.agent_id,
            )

    runtime.sizer._core = _Bump()  # type: ignore[assignment]
    with pytest.raises(ContinuityRefused, match="increased"):
        runtime.sizer.propose("hyp-core", quantity=2.0, price=5_000.0, at=now)

    class _BumpScaled:
        def heartbeat(self, at: datetime) -> None:
            del at

        def propose_order(self, proposal: OrderProposal) -> Decision:
            return Decision(
                kind=DecisionKind.SCALED,
                reason="scaled",
                quantity=proposal.quantity + 1.0,
                notional=proposal.notional + 1.0,
                agent_id=proposal.agent_id,
            )

    runtime.sizer._core = _BumpScaled()  # type: ignore[assignment]
    with pytest.raises(ContinuityRefused, match="increased"):
        runtime.sizer.propose("hyp-core", quantity=2.0, price=5_000.0, at=now)

    live_candidate, _live_val = seal_promotion_pair(
        runtime.authority,
        hypothesis_id="hyp-sz",
        config_id="hyp-sz",
        trial_id=50,
        instrument="MES",
        quantity=2.0,
        notional=10_000.0,
    )
    runtime.promotion._issued.append(live_candidate)
    skipped = runtime.ingest_promotions()
    assert skipped == ()

    with pytest.raises(ContinuityRefused, match="unknown instrument"):
        run_phase4_detection(
            audit_path=tmp_path / "a.jsonl",
            experiment_log_path=tmp_path / "e.jsonl",
            n_healthy=0,
            n_decaying=0,
            instrument="FOO",
        )
    report = run_phase4_detection(
        audit_path=tmp_path / "a2.jsonl",
        experiment_log_path=tmp_path / "e2.jsonl",
        n_healthy=1,
        n_decaying=1,
        n_days=20,
        decay_start=10,
        seed=1,
    )
    assert report.n_healthy == 1
    candidate, validation = seal_promotion_pair(
        runtime.authority,
        hypothesis_id="ghost",
        config_id="ghost",
        trial_id=9,
        instrument="MES",
        quantity=2.0,
        notional=10_000.0,
    )
    runtime.promotion._issued.append(candidate)
    with pytest.raises(ContinuityRefused, match="promotion without ValidationResult"):
        runtime.ingest_promotions()
    object.__setattr__(runtime, "_snapshot", replace(runtime._snapshot, live_risk_hash="deadbeef"))
    with pytest.raises(Exception, match="drifted"):
        runtime.assert_intact()


@pytest.mark.unit
def test_seal_mac_and_reasons() -> None:
    authority = ProvenanceAuthority()
    assert mac_ok(authority, b"abc", 1) is False
    assert mac_ok(authority, b"abc", "0" * 64) is False
    with pytest.raises(KeyError):
        _require_sequence(1)
    assert canonical_capacity(
        {
            "signal_id": "s",
            "instrument": "MES",
            "family_id": "es_index",
            "cluster_id": "es",
            "agent_id": CAPACITY_AGENT_ID,
            "previous_scale": 1.0,
            "new_scale": 0.5,
            "reasons": ["signal"],
        }
    )


@pytest.mark.unit
def test_cli_replenish_flag_on_empty_book(tmp_path: Path) -> None:
    code = main(
        [
            "daily",
            "--state-dir",
            str(tmp_path / "state"),
            "--report-dir",
            str(tmp_path / "reports"),
            "--replenish",
            "--seed",
            "3",
        ]
    )
    assert code in {0, 2}
