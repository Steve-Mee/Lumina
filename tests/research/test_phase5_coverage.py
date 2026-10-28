"""Branch coverage for Phase 5 ports, proof, weekly, and data edges."""

from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.engine.agent_blackboard import AgentBlackboard
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.cycles.data import DataRefused, ResearchBar, discover_data, tape_for
from lumina_research.cycles.fills import FillRefused, fill_probability, trade_through_fill
from lumina_research.monitoring.weekly import load_hypothesis_rows
from lumina_research.ports.fail_closed import decide_failure
from lumina_research.ports.fills import FillSink
from lumina_research.ports.seal import accept_mac, canonical_signal
from lumina_research.ports.shadow import ShadowBook
from lumina_research.ports.sim_safety import SimSafetyConfig, SimSafetyGate, SimSafetyRefused
from lumina_research.proof.cli import build_parser
from lumina_research.proof.continuity_suite import _floor_holds
from lumina_research.proof.independent import student_t, slow_gradual
from lumina_research.proof.log import log_proof_event
from lumina_research.monitoring.types import ContinuityRefused


def _bar() -> ResearchBar:
    return ResearchBar(ts_ns=1, open=10.0, high=10.5, low=9.5, close=10.0, volume=100.0)


@pytest.mark.unit
def test_fill_model_refuses_negative_volume_multiple() -> None:
    with pytest.raises(FillRefused):
        trade_through_fill(side=1.0, limit=9.6, bar=_bar(), average_volume=50.0, volume_multiple=-0.1)
    assert fill_probability(side=1.0, limit=9.6, bar=_bar(), average_volume=50.0) == 1.0


@pytest.mark.unit
def test_data_json_array_and_naive_timestamp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = tmp_path / "data" / "research" / "ES" / "1m"
    folder.mkdir(parents=True)
    rows = []
    px = 5000.0
    for index in range(241):
        stamp = datetime.fromtimestamp(1_700_000_000 + index * 60, tz=timezone.utc).isoformat()
        rows.append(
            {
                "timestamp": stamp,
                "open": px,
                "high": px + 0.5,
                "low": px - 0.5,
                "close": px,
                "volume": 1000,
            }
        )
    (folder / "es.json").write_text(json.dumps(rows), encoding="utf-8")
    status = discover_data(repo_root=tmp_path)
    assert status.usable is True
    monkeypatch.setenv("LUMINA_RESEARCH_DATA_DIR", str(tmp_path / "data" / "research"))
    again = discover_data(repo_root=tmp_path / "unused")
    assert again.usable is True
    del os.environ["LUMINA_RESEARCH_DATA_DIR"]
    missing = discover_data(repo_root=tmp_path / "missing-root")
    assert missing.usable is False
    with pytest.raises(DataRefused):
        tape_for(missing, "ES")


@pytest.mark.unit
def test_independent_refuses_and_proof_log(tmp_path: Path) -> None:
    rng = random.Random(1)
    with pytest.raises(ContinuityRefused):
        student_t(rng, df=1)
    with pytest.raises(ContinuityRefused):
        slow_gradual(rng, oos_mean=0.7, oos_stdev=0.05, n=40, decay_start=5, ramp_days=10)
    log_proof_event(
        path=tmp_path / "e.jsonl",
        event="unit",
        metrics={"ok": True},
        evolution_log_dir=tmp_path / "evo",
    )
    assert (tmp_path / "evo" / "phase5-empirical.jsonl").is_file()
    assert (tmp_path / "evo" / "phase5-empirical.md").is_file()


@pytest.mark.unit
def test_subclass_and_healthy_fail_closed_and_mac_replay() -> None:
    with pytest.raises(TypeError):
        class _Gate(SimSafetyGate):
            pass

    with pytest.raises(TypeError):
        class _Cfg(SimSafetyConfig):
            pass

    with pytest.raises(TypeError):
        class _Sink(FillSink):
            pass

    with pytest.raises(TypeError):
        class _Book(ShadowBook):
            pass

    healthy = decide_failure(
        stale_data=False,
        lost_connection=False,
        monitor_alarm=False,
        open_position=False,
        risk_core_limit=False,
    )
    assert healthy.allow_new_orders is True
    quiet_alarm = decide_failure(
        stale_data=False,
        lost_connection=False,
        monitor_alarm=True,
        open_position=False,
        risk_core_limit=False,
    )
    assert quiet_alarm.allow_new_orders is False
    authority = ProvenanceAuthority()
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
    digest = authority.mac(canonical_signal(fields))
    seen: set[str] = set()
    assert accept_mac(authority, canonical_signal(fields), digest, seen) is True
    assert accept_mac(authority, canonical_signal(fields), digest, seen) is False
    assert accept_mac(authority, canonical_signal(fields), 1, None) is False


@pytest.mark.unit
def test_shadow_blackboard_and_weekly_missing_log(tmp_path: Path) -> None:
    board = AgentBlackboard(persistence_path=tmp_path / "bb.jsonl")
    book = ShadowBook(
        bus=EventBus(),
        authority=ProvenanceAuthority(),
        experiment_log_path=tmp_path / "exp.jsonl",
        blackboard=board,
    )
    book.observe_signal(
        strategy_id="hyp-bb",
        direction="sell",
        size=2.0,
        expected_horizon="session",
        instrument="MNQ",
        limit_price=18000.0,
    )
    assert book.fills()
    assert load_hypothesis_rows(tmp_path / "missing.jsonl") == ()
    parser = build_parser()
    assert parser.parse_args(["verify", "--n-per-kind", "1"]).command == "verify"
    from lumina_research.monitoring.report import KindMetrics, MultiSeedDetectionReport, SeedDetectionRow

    empty = MultiSeedDetectionReport(
        seeds=(),
        n_signals=0,
        n_seeds=0,
        n_healthy=0,
        n_decaying=0,
        n_detected=0,
        n_false_alarms=0,
        detection_rate=0.0,
        false_alarm_rate=0.0,
        median_time_to_detect=None,
        mean_time_to_detect=None,
        p10_time_to_detect=None,
        p90_time_to_detect=None,
        max_time_to_detect=None,
        time_to_detect=(),
        by_kind=(),
        paths=(),
    )
    assert _floor_holds(empty, n_signals_floor=10) is True
    del KindMetrics, SeedDetectionRow


@pytest.mark.unit
def test_sim_safety_mapping_modes_and_intent(tmp_path: Path) -> None:
    del tmp_path
    with pytest.raises(SimSafetyRefused, match="allowed_modes"):
        SimSafetyConfig.from_mapping({"allowed_modes": "shadow"})
    gate = SimSafetyGate()
    from lumina_core.agent_orchestration.schemas_research import SignalIntent

    intent = SignalIntent(
        strategy_id="s",
        direction="buy",
        size=1.0,
        timestamp="t",
        expected_horizon="intraday",
        instrument="MES",
        account_id="SHADOW",
        mode="shadow",
        client_order_id="c",
        provenance_mac="c" * 64,
    )
    gate.admit_intent(intent)
    lost = decide_failure(
        stale_data=False,
        lost_connection=True,
        monitor_alarm=False,
        open_position=True,
        risk_core_limit=False,
    )
    assert lost.kind == "lost_connection"
    stale = decide_failure(
        stale_data=True,
        lost_connection=False,
        monitor_alarm=False,
        open_position=False,
        risk_core_limit=False,
    )
    assert stale.kind == "stale_data"
