"""Phase 2 fail-closed branches: generators, freeze, provenance, reports."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.engine.agent_blackboard import AgentBlackboard
from lumina_research.agents.generators import GeneratorError, NoiseGenerator, PlantedEdgeGenerator
from lumina_research.agents.hypothesis import HypothesisAgent, HypothesisRefused
from lumina_research.agents.payloads import json_float
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.agents.report import _fmt, build_kill_rate_report
from lumina_research.validation.trial_registry import TrialRegistry
from tests.research.phase2_harness import make_agents


@pytest.mark.unit
def test_generator_rejects_negative_count() -> None:
    import random

    with pytest.raises(GeneratorError):
        NoiseGenerator().drafts(rng=random.Random(1), count=-1, start_index=0)
    with pytest.raises(GeneratorError):
        PlantedEdgeGenerator().drafts(rng=random.Random(1), count=-1, start_index=0)


@pytest.mark.unit
def test_hypothesis_agent_rejects_count_mismatch(tmp_path: Path) -> None:
    bus = EventBus()
    agent = HypothesisAgent(
        bus=bus,
        registry=TrialRegistry(tmp_path / "a.jsonl"),
        generators=(NoiseGenerator(), PlantedEdgeGenerator()),
        experiment_log_path=tmp_path / "e.jsonl",
    )
    with pytest.raises(HypothesisRefused, match="counts must align"):
        agent.generate(seed=1, counts=(1,))
    with pytest.raises(HypothesisRefused, match="at least one generator"):
        HypothesisAgent(
            bus=bus,
            registry=TrialRegistry(tmp_path / "b.jsonl"),
            generators=(),
            experiment_log_path=tmp_path / "e.jsonl",
        )


@pytest.mark.unit
def test_agents_are_frozen(tmp_path: Path) -> None:
    _bus, _r, auth, hyp, val, promo = make_agents(tmp_path)
    with pytest.raises(AttributeError):
        hyp._bus = EventBus()  # type: ignore[misc]
    with pytest.raises(AttributeError):
        val._evaluate = None  # type: ignore[misc]
    with pytest.raises(AttributeError):
        promo._core = None  # type: ignore[misc]
    with pytest.raises(AttributeError):
        auth._sign = None  # type: ignore[misc]


@pytest.mark.unit
def test_json_float_and_report_fmt() -> None:
    assert json_float(math.nan) is None
    assert json_float(math.inf) is None
    assert json_float(1.25) == pytest.approx(1.25)
    assert _fmt(None) == "n/a"
    assert _fmt(1.5) == "1.5000"


@pytest.mark.unit
def test_provenance_rejects_bad_mac() -> None:
    authority = ProvenanceAuthority()
    fields = {
        "schema_version": "research.validation.result.v1",
        "hypothesis_id": "h",
        "config_id": "c",
        "trial_id": 1,
        "agent_id": "validation_agent",
        "passed": False,
        "reject_reasons": ["doubt"],
        "oos_distribution": {"values": [], "median": None, "mean": None, "stdev": None, "worst": None, "best": None, "pct_positive": None},
        "dsr": {
            "probability": None,
            "observed_sr": None,
            "expected_max_sr": None,
            "sr_standard_error": None,
            "n_trials": 0,
            "n_observations": 0,
            "skew": None,
            "kurtosis": None,
            "formulation": "bailey_lopez_de_prado_2014",
        },
        "pbo": {
            "pbo": None,
            "n_slices": 0,
            "n_combinations": 0,
            "n_configs": 0,
            "n_below_median": 0,
            "formulation": "cscv_logit_bailey_2014",
            "logit_mean": None,
        },
        "wfe": {
            "wfe": None,
            "mean_is_sharpe": None,
            "mean_oos_sharpe": None,
            "n_windows": 0,
            "mode": "",
            "parameter_stability": None,
        },
        "regimes": {
            "vol_high_sharpe": None,
            "vol_low_sharpe": None,
            "trend_up_sharpe": None,
            "trend_down_sharpe": None,
            "robustness": None,
        },
        "n_oos_windows": 0,
        "median_oos_after_costs": None,
    }
    digest, mac = authority.seal_validation(fields)
    payload = {**fields, "report_sha256": digest, "provenance_mac": mac}
    assert authority.verify_validation(payload) is not None
    payload["provenance_mac"] = "0" * 64
    assert authority.verify_validation(payload) is None
    assert authority.verify_issue({"issue_mac": "nope"}) is False
    assert authority.guard_promotion("rogue", {}) is False


@pytest.mark.unit
def test_blackboard_guard_cannot_attach_to_existing_topic(tmp_path: Path) -> None:
    board = AgentBlackboard(persistence_path=tmp_path / "bb.jsonl")
    with pytest.raises(ValueError, match="existing Blackboard topics stay unguarded"):
        board.register_topic_guard("agent.rl.proposal", lambda _p, _d: True)


@pytest.mark.unit
def test_empty_kill_rate_report() -> None:
    report = build_kill_rate_report(
        seed=0,
        planted_ids=(),
        results=(),
        promotions=(),
        planted_flags={},
    )
    assert report.kill_rate == 0.0
    assert report.n_hypotheses == 0


@pytest.mark.unit
def test_validation_flush_empty(tmp_path: Path) -> None:
    _bus, _r, _a, _h, validation, _p = make_agents(tmp_path)
    assert validation.flush() == ()
    assert validation.pending() == ()
