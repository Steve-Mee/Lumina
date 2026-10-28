"""D6: HypothesisAgent refuses drafts without an explicit expected_horizon."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas_research import EconomicRationale, RESEARCH_HYPOTHESIS_TOPIC
from lumina_research.agents.generators import (
    GENERATOR_EXPLICIT_HORIZON_BARS,
    HypothesisDraft,
    HypothesisGenerator,
    NoiseGenerator,
)
from lumina_research.agents.hypothesis import HypothesisAgent, HypothesisRefused
from lumina_research.validation.trial_registry import TrialRegistry


def _rationale() -> EconomicRationale:
    return EconomicRationale(
        mechanism="Inventory-holding premium after four-leg costs xx",
        why_edge_exists="Impatient demand pays spread and impact to move inventory",
        other_side="Noise traders demanding immediacy on the tape",
        expected_regime="trend-up moderate volatility",
        falsification_criterion="median OOS after costs <= 0 or PBO > 0.50",
    )


class _NoHorizonGenerator(HypothesisGenerator):
    @property
    def generator_id(self) -> str:
        return "no_horizon"

    def drafts(self, *, rng: object, count: int, start_index: int) -> tuple[HypothesisDraft, ...]:
        del rng, start_index
        draft = HypothesisDraft(
            config_id="no-horizon-0",
            generator_id=self.generator_id,
            kind="noise",
            instrument="MES",
            seed=1,
            n_obs=360,
            mu=0.0,
            sigma=0.01,
            planted=False,
            proposed_quantity=1.0,
            proposed_price=5000.0,
            proposed_notional=5000.0,
            rationale=_rationale(),
            oos_size=30,
            expected_horizon_bars=None,
        )
        return (draft,) * int(count)


@pytest.mark.unit
def test_missing_horizon_is_hypothesis_refused(tmp_path: Path) -> None:
    bus = EventBus()
    agent = HypothesisAgent(
        bus=bus,
        registry=TrialRegistry(tmp_path / "audit.jsonl"),
        generators=(_NoHorizonGenerator(),),
        experiment_log_path=tmp_path / "exp.jsonl",
    )
    with pytest.raises(HypothesisRefused, match="expected_horizon"):
        agent.generate(seed=1, counts=(1,))
    assert bus.history(RESEARCH_HYPOTHESIS_TOPIC, limit=10) == []
    log = (tmp_path / "exp.jsonl").read_text(encoding="utf-8") if (tmp_path / "exp.jsonl").exists() else ""
    assert "hypothetical_fill" not in log


@pytest.mark.unit
def test_explicit_generator_horizon_is_logged(tmp_path: Path) -> None:
    assert GENERATOR_EXPLICIT_HORIZON_BARS == 8
    bus = EventBus()
    agent = HypothesisAgent(
        bus=bus,
        registry=TrialRegistry(tmp_path / "audit.jsonl"),
        generators=(NoiseGenerator(n_obs=360, instrument="MES"),),
        experiment_log_path=tmp_path / "exp.jsonl",
    )
    published = agent.generate(seed=3, counts=(1,))
    assert published[0].expected_horizon_bars == GENERATOR_EXPLICIT_HORIZON_BARS
    log = (tmp_path / "exp.jsonl").read_text(encoding="utf-8")
    assert '"expected_horizon_bars": 8' in log
