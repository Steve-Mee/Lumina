"""Attack tests: no ungated registry insert, event forgery, replenish shortcut, weight increase."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.agent_orchestration.schemas_research import (
    MONITOR_AGENT_ID,
    RESEARCH_DECAY_TOPIC,
    RESEARCH_PROMOTION_TOPIC,
    PromotionCandidate,
)
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.monitoring.synthetic import seal_promotion_pair
from lumina_research.monitoring.types import ContinuityRefused
from tests.research.phase4_harness import admit_signal, make_runtime


@pytest.mark.unit
def test_direct_registry_insertion_is_forbidden(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    signal = admit_signal(runtime, "hyp-ok", trial_id=1)
    with pytest.raises(ContinuityRefused, match="direct registry insertion"):
        runtime.insert_direct(signal)
    with pytest.raises(ContinuityRefused, match="direct registry insertion"):
        runtime.registry.insert(signal)


@pytest.mark.unit
def test_unsigned_validation_cannot_be_admitted(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    foreign = ProvenanceAuthority()
    candidate, validation = seal_promotion_pair(
        foreign,
        hypothesis_id="hyp-forged",
        config_id="hyp-forged",
        trial_id=1,
        instrument="MES",
        quantity=2.0,
        notional=10_000.0,
    )
    with pytest.raises(ContinuityRefused, match="provenance"):
        runtime.admit(candidate, validation)


@pytest.mark.unit
def test_failed_gate_result_cannot_be_admitted(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    with pytest.raises(ContinuityRefused, match="gate failed"):
        admit_signal(runtime, "hyp-fail", trial_id=1, passed=False, reject_reasons=("pbo_hard_reject",), pbo=0.9)


@pytest.mark.unit
def test_event_forgery_on_decay_topic_is_rejected(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    admit_signal(runtime, "hyp-ok", trial_id=1)
    with pytest.raises(PermissionError):
        runtime.bus.publish(
            topic=RESEARCH_DECAY_TOPIC,
            producer="rogue_agent",
            payload={
                "signal_id": "hyp-ok",
                "hypothesis_id": "hyp-ok",
                "config_id": "hyp-ok",
                "trial_id": 1,
                "agent_id": MONITOR_AGENT_ID,
                "method": "cusum",
                "statistic": 9.0,
                "threshold": 3.0,
                "window": 20,
                "live_mean": 0.0,
                "oos_mean": 0.8,
                "oos_stdev": 0.1,
                "percentile": 0.0,
                "cusum": 9.0,
                "sprt_llr": 9.0,
                "stage": "retired",
                "provenance_mac": "0" * 64,
            },
        )
    with pytest.raises(PermissionError, match="issuer guard"):
        runtime.bus.publish(
            topic=RESEARCH_DECAY_TOPIC,
            producer=MONITOR_AGENT_ID,
            payload={
                "signal_id": "hyp-ok",
                "hypothesis_id": "hyp-ok",
                "config_id": "hyp-ok",
                "trial_id": 1,
                "agent_id": MONITOR_AGENT_ID,
                "method": "cusum",
                "statistic": 9.0,
                "threshold": 3.0,
                "window": 20,
                "live_mean": 0.0,
                "oos_mean": 0.8,
                "oos_stdev": 0.1,
                "percentile": 0.0,
                "cusum": 9.0,
                "sprt_llr": 9.0,
                "stage": "retired",
                "provenance_mac": "0" * 64,
            },
        )


@pytest.mark.unit
def test_replenishment_shortcut_cannot_insert(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    with pytest.raises(ContinuityRefused, match="Validation Gate"):
        runtime.replenish_shortcut("hyp-skip")
    admitted = runtime.request_replenishment(seed=7)
    live_ids = {item.signal_id for item in runtime.registry.signals()}
    for signal in admitted:
        assert signal.signal_id in live_ids
    for candidate in runtime.promotion.issued():
        assert candidate.hypothesis_id in live_ids or any(
            item.hypothesis_id == candidate.hypothesis_id for item in admitted
        )


@pytest.mark.unit
def test_weight_increase_and_restore_are_forbidden(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    admit_signal(runtime, "hyp-w", trial_id=1)
    with pytest.raises(ContinuityRefused, match="cannot increase"):
        runtime.increase_weight("hyp-w", 2.0)
    with pytest.raises(ContinuityRefused, match="cannot increase"):
        runtime.capacity.scale_up("hyp-w", 1.0)
    with pytest.raises(ContinuityRefused, match="cannot increase"):
        runtime.sizer.increase_quantity("hyp-w", 10.0)
    with pytest.raises(ContinuityRefused, match="restore"):
        runtime.registry.restore("hyp-w")
    with pytest.raises(ContinuityRefused, match="Risk Core"):
        runtime.set_risk_limits()


@pytest.mark.unit
def test_forged_promotion_candidate_cannot_publish(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    with pytest.raises(PermissionError):
        runtime.bus.publish(
            topic=RESEARCH_PROMOTION_TOPIC,
            producer="rogue_agent",
            payload=PromotionCandidate.model_validate(
                {
                    "hypothesis_id": "x",
                    "config_id": "x",
                    "trial_id": 1,
                    "agent_id": "promotion_agent",
                    "instrument": "MES",
                    "decision_kind": "approved",
                    "scaled": False,
                    "quantity": 1.0,
                    "notional": 1.0,
                    "risk_reason": "approved",
                    "validation_report_sha256": "a" * 64,
                    "validation_mac": "b" * 64,
                    "issue_mac": "c" * 64,
                }
            ).model_dump(mode="json"),
        )
