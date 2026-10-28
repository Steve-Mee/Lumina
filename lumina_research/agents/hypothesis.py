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
from lumina_research.agents.experiment_log import log_experiment
from lumina_research.agents.generators import HypothesisDraft, HypothesisGenerator
from lumina_research.validation.trial_registry import TrialRegistry


class HypothesisRefused(ValueError):
    """A hypothesis without a complete rationale is refused and not published."""


class HypothesisAgent:
    """Pluggable generators only. No network. Every generated variant increments TrialRegistry."""

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
        object.__setattr__(self, "_bus", bus)
        object.__setattr__(self, "_registry", registry)
        object.__setattr__(self, "_generators", tuple(generators))
        object.__setattr__(self, "_log_path", experiment_log_path)
        object.__setattr__(self, "_blackboard", blackboard)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("HypothesisAgent attributes are frozen")

    def generate(self, *, seed: int, counts: Sequence[int]) -> tuple[HypothesisProposed, ...]:
        generators: tuple[HypothesisGenerator, ...] = self._generators  # type: ignore[attr-defined]
        if len(counts) != len(generators):
            raise HypothesisRefused("counts must align with generators")
        rng = random.Random(seed)
        published: list[HypothesisProposed] = []
        start = 0
        for generator, count in zip(generators, counts, strict=True):
            drafts = generator.drafts(rng=rng, count=int(count), start_index=start)
            if len(drafts) != int(count):
                raise HypothesisRefused("generator dropped variants; every variant must be emitted")
            for draft in drafts:
                if draft.kind not in {"noise", "planted_edge"}:
                    raise HypothesisRefused(f"unknown hypothesis kind {draft.kind!r}")
                published.append(self._accept(draft))
            start += int(count)
        return tuple(published)

    def _accept(self, draft: HypothesisDraft) -> HypothesisProposed:
        rationale = _require_rationale(draft.rationale)
        registry: TrialRegistry = self._registry  # type: ignore[attr-defined]
        trial_id = registry.record(
            config_id=draft.config_id,
            agent_id=HYPOTHESIS_AGENT_ID,
            metrics={"phase": "generate", "kind": draft.kind, "generator_id": draft.generator_id},
        )
        hypothesis_id = f"hyp-{draft.config_id}"
        payload = HypothesisProposed(
            hypothesis_id=hypothesis_id,
            config_id=draft.config_id,
            trial_id=trial_id,
            agent_id=HYPOTHESIS_AGENT_ID,
            generator_id=draft.generator_id,
            kind="planted_edge" if draft.kind == "planted_edge" else "noise",
            instrument=_instrument(draft.instrument),
            seed=draft.seed,
            n_obs=draft.n_obs,
            mu=draft.mu,
            sigma=draft.sigma,
            planted=bool(draft.planted),
            proposed_quantity=draft.proposed_quantity,
            proposed_price=draft.proposed_price,
            proposed_notional=draft.proposed_notional,
            rationale=rationale,
        )
        dumped = payload.model_dump(mode="json", exclude_none=False)
        bus: EventBus = self._bus  # type: ignore[attr-defined]
        bus.publish(
            topic=RESEARCH_HYPOTHESIS_TOPIC,
            producer=HYPOTHESIS_AGENT_ID,
            payload=dumped,
        )
        board: AgentBlackboard | None = self._blackboard  # type: ignore[attr-defined]
        if board is not None:
            board.publish_sync(
                topic=RESEARCH_HYPOTHESIS_TOPIC,
                producer=HYPOTHESIS_AGENT_ID,
                payload=dumped,
                confidence=1.0,
            )
        log_experiment(
            path=self._log_path,  # type: ignore[attr-defined]
            agent_id=HYPOTHESIS_AGENT_ID,
            event="hypothesis",
            hypothesis_id=hypothesis_id,
            rationale=rationale.model_dump(mode="json"),
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
    key = root.strip().upper()
    if key == "ES":
        return "ES"
    if key == "NQ":
        return "NQ"
    if key == "MES":
        return "MES"
    if key == "MNQ":
        return "MNQ"
    raise HypothesisRefused(f"unsupported instrument {root!r}")
