"""Branch coverage for Phase 4 config, seals, CLI, guardian, and refuse paths."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest
from pydantic import ValidationError

from lumina_core.agent_orchestration.schemas_research import SignalDeweighted
from lumina_core.engine.agent_blackboard import AgentBlackboard
from lumina_research.monitoring.cli import build_parser, load_decisions
from lumina_research.monitoring.config import ContinuityConfigError, config_from_mapping, load_default_config
from lumina_research.monitoring.loop import ContinuityRuntime
from lumina_research.monitoring.report import DetectionPath, build_detection_report, log_decision
from lumina_research.monitoring.seal import canonical_decay, canonical_guardian
from lumina_research.monitoring.statistics import assess_decay, rolling_mean, sprt_threshold
from lumina_research.monitoring.synthetic import DEFAULT_OOS
from lumina_research.monitoring.types import ContinuityRefused, family_for, finite_series, stage_rank
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
