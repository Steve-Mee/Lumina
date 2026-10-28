"""Hypothesis / Validation / Promotion agents: rationale, trials, full pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.agent_orchestration.schemas_research import (
    RESEARCH_HYPOTHESIS_TOPIC,
    RESEARCH_VALIDATION_TOPIC,
    EconomicRationale,
)
from lumina_research.agents.generators import HypothesisDraft, HypothesisGenerator, NoiseGenerator
from lumina_research.agents.hypothesis import HypothesisAgent, HypothesisRefused
from lumina_research.agents.provenance import ProvenanceAuthority, ProvenanceError
from lumina_research.validation.pipeline import evaluate_candidate
from lumina_research.validation.trial_registry import TrialRegistry
from tests.research.phase2_harness import make_agents


class _BlankGenerator(HypothesisGenerator):
    @property
    def generator_id(self) -> str:
        return "blank"

    def drafts(self, *, rng: object, count: int, start_index: int) -> tuple[HypothesisDraft, ...]:
        good = EconomicRationale(
            mechanism="Placeholder mechanism text that is long enough",
            why_edge_exists="Placeholder why-edge text that is long enough",
            other_side="Placeholder other-side text that is long enough",
            expected_regime="trend-up moderate volatility",
            falsification_criterion="median OOS after costs <= 0 or PBO > 0.50",
        )
        draft = HypothesisDraft(
            config_id="blank-0",
            generator_id="blank",
            kind="noise",
            instrument="MES",
            seed=1,
            n_obs=240,
            mu=0.0,
            sigma=0.01,
            planted=False,
            proposed_quantity=1.0,
            proposed_price=5000.0,
            proposed_notional=5000.0,
            rationale=good,
        )
        object.__setattr__(draft, "rationale", None)
        return (draft,)


@pytest.mark.unit
def test_hypothesis_without_rationale_is_refused(tmp_path: Path) -> None:
    from lumina_core.agent_orchestration.event_bus import EventBus

    bus = EventBus()
    registry = TrialRegistry(tmp_path / "audit.jsonl")
    agent = HypothesisAgent(
        bus=bus,
        registry=registry,
        generators=(_BlankGenerator(),),
        experiment_log_path=tmp_path / "exp.jsonl",
    )
    with pytest.raises(HypothesisRefused):
        agent.generate(seed=1, counts=(1,))
    assert bus.history(RESEARCH_HYPOTHESIS_TOPIC) == [] or len(bus.history(RESEARCH_HYPOTHESIS_TOPIC, limit=10)) == 0


@pytest.mark.unit
def test_every_generated_variant_increments_trial_registry(tmp_path: Path) -> None:
    bus, registry, _auth, hypothesis, validation, _promo = make_agents(tmp_path)
    generated = hypothesis.generate(seed=11, counts=(3, 1))
    assert len(generated) == 4
    assert registry.n_trials == 4
    validation.flush()
    assert registry.n_trials == 8
    results = bus.history(RESEARCH_VALIDATION_TOPIC, limit=20)
    assert len(results) == 4
    for event in results:
        payload = event.payload
        assert "oos_distribution" in payload
        assert "dsr" in payload
        assert "pbo" in payload
        assert "wfe" in payload
        assert "reject_reasons" in payload
        assert payload["oos_distribution"]["values"] is not None


@pytest.mark.unit
def test_validation_agent_binds_evaluate_candidate_not_a_shortcut(tmp_path: Path) -> None:
    _bus, _registry, _auth, _h, validation, _p = make_agents(tmp_path)
    bound = object.__getattribute__(validation, "_evaluate")
    assert bound is evaluate_candidate


@pytest.mark.unit
def test_validation_agent_cannot_replace_pipeline(tmp_path: Path) -> None:
    _bus, _registry, _auth, _h, validation, _p = make_agents(tmp_path)
    with pytest.raises(AttributeError):
        validation._evaluate = lambda **_k: None  # type: ignore[method-assign]


@pytest.mark.unit
def test_experiment_log_is_append_only_jsonl_with_required_fields(tmp_path: Path) -> None:
    _bus, _registry, _auth, hypothesis, validation, _p = make_agents(tmp_path)
    hypothesis.generate(seed=3, counts=(2, 1))
    validation.flush()
    log_path = tmp_path / "experiments.jsonl"
    lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) >= 6
    import json

    events = [json.loads(line) for line in lines]
    assert all("timestamp" in row and "T" in row["timestamp"] for row in events)
    hyp_rows = [row for row in events if row["event"] == "hypothesis"]
    val_rows = [row for row in events if row["event"] == "validation"]
    assert hyp_rows
    assert val_rows
    sample = val_rows[0]["metrics"]
    assert sample["hypothesis_id"]
    assert sample["rationale"]["mechanism"]
    assert "oos_distribution" in sample["metrics"]
    assert "failed_checks" in sample
    assert "gate_check_failed" in sample


@pytest.mark.unit
def test_provenance_authority_rejects_short_key() -> None:
    with pytest.raises(ProvenanceError):
        ProvenanceAuthority(key=b"short")


@pytest.mark.unit
def test_noise_generator_is_deterministic() -> None:
    import random

    a = NoiseGenerator().drafts(rng=random.Random(42), count=2, start_index=0)
    b = NoiseGenerator().drafts(rng=random.Random(42), count=2, start_index=0)
    assert [d.config_id for d in a] == [d.config_id for d in b]
    assert a[0].rationale.mechanism
