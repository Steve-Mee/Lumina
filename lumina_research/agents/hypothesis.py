"""HypothesisAgent: generate variants with a required rationale; each variant is a trial."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Literal, Sequence

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas_research import (
    HYPOTHESIS_AGENT_ID,
    RESEARCH_HYPOTHESIS_TOPIC,
    EconomicRationale,
    HypothesisProposed,
)
from lumina_core.engine.agent_blackboard import AgentBlackboard
from lumina_research.agents.economic_templates import TemplateRefused, require_economic_template
from lumina_research.agents.experiment_log import log_experiment
from lumina_research.agents.frozen import Frozen
from lumina_research.agents.generators import HypothesisDraft, HypothesisGenerator
from lumina_research.agents.payloads import dump_json
from lumina_research.validation.trial_registry import TrialRegistry

_INSTRUMENTS: dict[str, Literal["ES", "NQ", "MES", "MNQ"]] = {
    "ES": "ES",
    "NQ": "NQ",
    "MES": "MES",
    "MNQ": "MNQ",
}
_KINDS: dict[str, Literal["noise", "planted_edge", "economic"]] = {
    "noise": "noise",
    "planted_edge": "planted_edge",
    "economic": "economic",
}


class HypothesisRefused(ValueError):
    """A hypothesis without a complete rationale is refused and not published."""


class HypothesisAgent(Frozen):
    """Pluggable generators only. No network. Every generated variant increments TrialRegistry."""

    _bus: EventBus
    _registry: TrialRegistry
    _generators: tuple[HypothesisGenerator, ...]
    _log_path: Path
    _blackboard: AgentBlackboard | None

    def __init_subclass__(cls) -> None:
        raise TypeError("HypothesisAgent cannot be subclassed")

    def __init__(
        self,
        *,
        bus: EventBus,
        registry: TrialRegistry,
        generators: Sequence[HypothesisGenerator],
        experiment_log_path: Path,
        blackboard: AgentBlackboard | None = None,
    ) -> None:
        if not generators:
            raise HypothesisRefused("at least one generator is required")
        self._bus = bus
        self._registry = registry
        self._generators = tuple(generators)
        self._log_path = experiment_log_path
        self._blackboard = blackboard
        self._freeze()

    def generate(self, *, seed: int, counts: Sequence[int]) -> tuple[HypothesisProposed, ...]:
        """Publish exactly ``sum(counts)`` variants. A missing rationale is a refuse."""
        if len(counts) != len(self._generators):
            raise HypothesisRefused("counts must align with generators")
        rng = random.Random(seed)
        published: list[HypothesisProposed] = []
        start = 0
        for generator, count in zip(self._generators, counts, strict=True):
            drafts = generator.drafts(rng=rng, count=int(count), start_index=start)
            if len(drafts) != int(count):
                raise HypothesisRefused("generator dropped variants; every variant must be emitted")
            for draft in drafts:
                if draft.kind not in _KINDS:
                    raise HypothesisRefused(f"unknown hypothesis kind {draft.kind!r}")
                if draft.kind == "economic":
                    try:
                        require_economic_template(draft.generator_id)
                    except TemplateRefused as exc:
                        raise HypothesisRefused(str(exc)) from exc
                published.append(self._accept(draft))
            start += int(count)
        return tuple(published)

    def _accept(self, draft: HypothesisDraft) -> HypothesisProposed:
        rationale = _require_rationale(draft.rationale)
        trial_id = self._registry.record(
            config_id=draft.config_id,
            agent_id=HYPOTHESIS_AGENT_ID,
            metrics={"phase": "generate", "kind": draft.kind, "generator_id": draft.generator_id},
        )
        hypothesis_id = f"hyp-{draft.config_id}"
        kind = _KINDS[draft.kind]
        payload = HypothesisProposed(
            hypothesis_id=hypothesis_id,
            config_id=draft.config_id,
            trial_id=trial_id,
            agent_id=HYPOTHESIS_AGENT_ID,
            generator_id=draft.generator_id,
            kind=kind,
            instrument=_instrument(draft.instrument),
            seed=draft.seed,
            n_obs=draft.n_obs,
            mu=draft.mu,
            sigma=draft.sigma,
            planted=bool(draft.planted),
            proposed_quantity=draft.proposed_quantity,
            proposed_price=draft.proposed_price,
            proposed_notional=draft.proposed_notional,
            is_size=int(draft.is_size),
            oos_size=int(draft.oos_size),
            parent_config_id=str(draft.parent_config_id),
            overfit_in_sample=bool(draft.overfit_in_sample),
            rationale=rationale,
        )
        dumped = dump_json(payload)
        self._bus.publish(
            topic=RESEARCH_HYPOTHESIS_TOPIC,
            producer=HYPOTHESIS_AGENT_ID,
            payload=dict(dumped),
        )
        if self._blackboard is not None:
            self._blackboard.publish_sync(
                topic=RESEARCH_HYPOTHESIS_TOPIC,
                producer=HYPOTHESIS_AGENT_ID,
                payload=dict(dumped),
                confidence=1.0,
            )
        log_experiment(
            path=self._log_path,
            agent_id=HYPOTHESIS_AGENT_ID,
            event="hypothesis",
            hypothesis_id=hypothesis_id,
            rationale=dump_json(rationale),
            metrics={"trial_id": trial_id, "kind": draft.kind, "config_id": draft.config_id},
            reject_reason=None,
            failed_checks=(),
        )
        return payload


def _require_rationale(rationale: object) -> EconomicRationale:
    if rationale is None:
        raise HypothesisRefused("a hypothesis without a rationale is refused")
    if isinstance(rationale, EconomicRationale):
        return rationale
    if isinstance(rationale, dict):
        try:
            return EconomicRationale.model_validate(rationale)
        except Exception as exc:
            raise HypothesisRefused("a hypothesis without a rationale is refused") from exc
    raise HypothesisRefused("a hypothesis without a rationale is refused")


def _instrument(root: str) -> Literal["ES", "NQ", "MES", "MNQ"]:
    mapped = _INSTRUMENTS.get(root.strip().upper())
    if mapped is None:
        raise HypothesisRefused(f"unsupported instrument {root!r}")
    return mapped
