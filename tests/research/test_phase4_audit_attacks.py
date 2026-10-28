"""Independent audit attacks: bypass, replay, exposure, capacity, guardian, thresholds."""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lumina_core.agent_orchestration.schemas_research import MONITOR_AGENT_ID, RESEARCH_DECAY_TOPIC
from lumina_research.monitoring.cli import main
from lumina_research.monitoring.config import ContinuityConfigError, config_from_mapping, load_default_config
from lumina_research.monitoring.synthetic import DEFAULT_OOS
from lumina_research.monitoring.types import MIN_LIVE_OOS_VALUES, ContinuityRefused
from lumina_research.risk_core.types import DecisionKind
from lumina_research.validation.thresholds import FLOOR_MIN_OOS_WINDOWS
from tests.research.phase4_harness import admit_signal, make_runtime


@pytest.mark.unit
def test_short_oos_values_cannot_enter_live_book(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    with pytest.raises(ContinuityRefused, match="charter floor"):
        admit_signal(runtime, "hyp-short", trial_id=1, oos=(0.80, 0.82), n_oos_windows=6)
    assert runtime.registry.signals() == ()
    assert FLOOR_MIN_OOS_WINDOWS == 6


@pytest.mark.unit
def test_sizer_refuses_quantity_or_notional_above_promoted_base(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    admit_signal(runtime, "hyp-qty", trial_id=1, quantity=2.0, notional=10_000.0)
    now = datetime.now(timezone.utc)
    with pytest.raises(ContinuityRefused, match="cannot increase"):
        runtime.sizer.propose("hyp-qty", quantity=10.0, price=100.0, at=now)
    with pytest.raises(ContinuityRefused, match="cannot increase"):
        runtime.sizer.propose("hyp-qty", quantity=2.0, price=10_000.0, at=now)
    ok = runtime.sizer.propose("hyp-qty", quantity=2.0, price=5_000.0, at=now)
    assert ok.kind in {DecisionKind.APPROVED, DecisionKind.SCALED, DecisionKind.REJECTED}
    if ok.kind is not DecisionKind.REJECTED:
        assert ok.quantity <= 2.0 + 1e-9


@pytest.mark.unit
def test_weak_continuity_config_without_adr_is_refused() -> None:
    raw = asdict(load_default_config())
    raw["z_deweight"] = -100.0
    raw["z_suspend"] = -100.0
    raw["z_retire"] = -100.0
    with pytest.raises(ContinuityConfigError, match="z_deweight"):
        config_from_mapping(raw)
    raw = asdict(load_default_config())
    raw["max_signal_notional_pct"] = 1.0
    with pytest.raises(ContinuityConfigError, match="max_signal"):
        config_from_mapping(raw)
    raw = asdict(load_default_config())
    raw["window"] = 250
    raw["min_observations"] = 20
    with pytest.raises(ContinuityConfigError, match="window"):
        config_from_mapping(raw)
    raw = asdict(load_default_config())
    raw["sprt_alpha"] = 0.20
    with pytest.raises(ContinuityConfigError, match="ADR"):
        config_from_mapping(raw)
    raw = asdict(load_default_config())
    raw["equity"] = 1_000_000_000.0
    with pytest.raises(ContinuityConfigError, match="equity"):
        config_from_mapping(raw)


@pytest.mark.unit
def test_retired_signal_cannot_unretire_or_repromote(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    admit_signal(runtime, "hyp-r", trial_id=1, quantity=2.0, notional=10_000.0)
    runtime.registry.apply_stage("hyp-r", "retired")
    with pytest.raises(ContinuityRefused, match="already_live"):
        admit_signal(runtime, "hyp-r", trial_id=2)
    with pytest.raises(ContinuityRefused, match="restore"):
        runtime.registry.restore("hyp-r")
    retired = runtime.registry.require("hyp-r")
    zombie = replace(retired, stage="active", weight=1.0)
    runtime.registry._signals["hyp-r"] = zombie
    assert runtime.registry.verify(zombie) is False
    with pytest.raises(ContinuityRefused, match="tampered"):
        runtime.observe("hyp-r", 0.8)
    with pytest.raises(ContinuityRefused, match="tampered"):
        runtime.sizer.propose("hyp-r", quantity=2.0, price=5_000.0, at=datetime.now(timezone.utc))


@pytest.mark.unit
def test_event_replay_cannot_change_live_book(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    admit_signal(runtime, "hyp-e", trial_id=1)
    mean = sum(DEFAULT_OOS) / len(DEFAULT_OOS)
    for _ in range(30):
        runtime.observe("hyp-e", mean - 0.7)
    before = runtime.registry.require("hyp-e")
    events = runtime.bus.history(RESEARCH_DECAY_TOPIC, limit=20)
    if not events:
        pytest.skip("decay event not emitted on this path")
    payload = dict(events[-1].payload)
    with pytest.raises(PermissionError, match="issuer guard"):
        runtime.bus.publish(topic=RESEARCH_DECAY_TOPIC, producer=MONITOR_AGENT_ID, payload=payload)
    after = runtime.registry.require("hyp-e")
    assert after.stage == before.stage
    assert after.weight == before.weight
    assert after.capacity_scale == before.capacity_scale


@pytest.mark.unit
def test_nan_inf_empty_and_short_windows_do_not_increase_exposure(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    admit_signal(runtime, "hyp-n", trial_id=1, quantity=2.0, notional=10_000.0)
    for value in (float("nan"), float("inf"), float("-inf"), True):
        with pytest.raises(ContinuityRefused, match="non-finite"):
            runtime.observe("hyp-n", value)
    short = runtime.observe("hyp-n", 0.8)
    assert short.stage == "active"
    assert short.weight == 1.0
    now = datetime.now(timezone.utc)
    decision = runtime.sizer.propose("hyp-n", quantity=2.0, price=5_000.0, at=now)
    if decision.kind is not DecisionKind.REJECTED:
        assert decision.quantity <= 2.0 + 1e-9


@pytest.mark.unit
def test_same_cluster_split_cannot_evade_cluster_cap(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    admit_signal(runtime, "hyp-es", trial_id=1, instrument="ES", quantity=2.0, notional=12_000.0)
    admit_signal(runtime, "hyp-mes", trial_id=2, instrument="MES", quantity=2.0, notional=12_000.0)
    assert runtime.registry.require("hyp-es").cluster_id == runtime.registry.require("hyp-mes").cluster_id
    runtime.rebalance()
    total = sum(item.effective_notional() for item in runtime.registry.signals())
    cap = runtime.config.max_cluster_notional_pct * runtime.config.equity
    assert total <= cap + 1e-6
    with pytest.raises(ContinuityRefused, match="cannot increase"):
        runtime.capacity.scale_up("hyp-es", 1.0)


@pytest.mark.unit
def test_observe_and_size_fail_closed_after_risk_core_drift(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    admit_signal(runtime, "hyp-d", trial_id=1)
    object.__setattr__(runtime, "_snapshot", replace(runtime._snapshot, live_risk_hash="deadbeef"))
    with pytest.raises(Exception, match="drifted"):
        runtime.observe("hyp-d", 0.8)
    with pytest.raises(Exception, match="drifted"):
        runtime.rebalance()
    with pytest.raises(Exception, match="drifted"):
        runtime.propose_order("hyp-d", quantity=2.0, price=5_000.0)


@pytest.mark.unit
def test_guardian_risk_core_drift_proposes_suspend(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    admit_signal(runtime, "hyp-g", trial_id=1)
    runtime.trials.record(config_id="hyp-g", agent_id="hypothesis_agent", metrics={"phase": "test"})
    bad = replace(runtime._snapshot, live_risk_hash="0" * 64)
    report = runtime.guardian.scan(
        cadence="daily",
        baseline=runtime._snapshot,
        trials=runtime.trials.records(),
        live=bad,
    )
    assert report.passed is False
    assert "hyp-g" in report.suspend_proposals
    runtime.monitor.apply_guardian_suspend("hyp-g", "guardian:daily")
    assert runtime.registry.require("hyp-g").stage in {"suspended", "retired"}
    blocked = runtime.sizer.propose("hyp-g", quantity=2.0, price=5_000.0, at=datetime.now(timezone.utc))
    assert blocked.kind is DecisionKind.REJECTED


@pytest.mark.unit
def test_guardian_scan_errors_are_not_swallowed(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    admit_signal(runtime, "hyp-x", trial_id=1)

    def boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("bus down")

    runtime.guardian._bus.publish = boom  # type: ignore[method-assign]
    with pytest.raises(ContinuityRefused, match="failed closed"):
        runtime.guardian.scan(
            cadence="daily",
            baseline=runtime._snapshot,
            trials=runtime.trials.records(),
        )


@pytest.mark.unit
def test_runtime_equity_override_cannot_inflate_capacity(tmp_path: Path) -> None:
    with pytest.raises(ContinuityRefused, match="equity"):
        make_runtime(tmp_path, equity=1_000_000_000.0)


@pytest.mark.unit
def test_threshold_and_risk_core_writes_require_adr(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    with pytest.raises(ContinuityRefused, match="ADR"):
        runtime.mutate_thresholds()
    with pytest.raises(ContinuityRefused, match="cannot write"):
        runtime.write_risk_core(tmp_path / "limits.toml")
    with pytest.raises(ContinuityRefused, match="Risk Core"):
        runtime.set_risk_limits()


@pytest.mark.unit
def test_replenishment_does_not_admit_failed_gate_hypotheses(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    admitted = runtime.request_replenishment(seed=3)
    live = runtime.registry.signals()
    assert {item.signal_id for item in admitted} <= {item.signal_id for item in live}
    for signal in live:
        assert runtime.registry.verify(signal) is True
        assert signal.n_oos_windows >= 6
        assert len(signal.oos_values) >= MIN_LIVE_OOS_VALUES
        assert signal.weight <= 1.0


@pytest.mark.unit
def test_decisions_are_logged_with_timestamp_agent_and_metrics(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    admit_signal(runtime, "hyp-l", trial_id=1)
    runtime.monitor.apply_guardian_suspend("hyp-l", "probe")
    lines = runtime.log_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines
    payload = json.loads(lines[-1])
    assert payload["timestamp"]
    assert payload["agent_id"]
    assert "metrics" in payload["metrics"] or payload["event"] in {"suspend", "guardian", "deweight"}
    events = [json.loads(line)["event"] for line in lines]
    assert "admit" in events
    admit = json.loads(next(line for line in lines if json.loads(line)["event"] == "admit"))
    assert admit["agent_id"]
    assert admit["timestamp"]
    assert admit["metrics"]["metrics"]["state_mac"]


@pytest.mark.unit
def test_cli_rejects_weak_overlay_config(tmp_path: Path) -> None:
    weak = tmp_path / "weak.toml"
    packaged = (Path("lumina_research") / "monitoring" / "limits.toml").read_text(encoding="utf-8")
    weak.write_text(
        packaged.replace("z_deweight = -1.65", "z_deweight = -4.0")
        .replace("z_suspend = -2.33", "z_suspend = -4.5")
        .replace("z_retire = -2.88", "z_retire = -5.0"),
        encoding="utf-8",
    )
    code = main(
        [
            "daily",
            "--state-dir",
            str(tmp_path / "state"),
            "--report-dir",
            str(tmp_path / "reports"),
            "--config",
            str(weak),
        ]
    )
    assert code == 1
