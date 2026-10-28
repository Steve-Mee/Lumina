"""Pluggable hypothesis generators. Deterministic and seeded. No network, no LLM."""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass

from lumina_core.agent_orchestration.schemas_research import EconomicRationale


class GeneratorError(ValueError):
    """Generator refused to emit a variant."""


@dataclass(frozen=True, slots=True)
class HypothesisDraft:
    config_id: str
    generator_id: str
    kind: str
    instrument: str
    seed: int
    n_obs: int
    mu: float
    sigma: float
    planted: bool
    proposed_quantity: float
    proposed_price: float
    proposed_notional: float
    rationale: EconomicRationale
    is_size: int = 60
    oos_size: int = 30
    parent_config_id: str = ""


class HypothesisGenerator(ABC):
    """Every variant must carry a complete economic rationale."""

    @property
    @abstractmethod
    def generator_id(self) -> str:
        """Stable id recorded on every trial this generator emits."""

    @abstractmethod
    def drafts(self, *, rng: random.Random, count: int, start_index: int) -> tuple[HypothesisDraft, ...]:
        """Return exactly ``count`` drafts. Dropping a variant is a refuse."""


class NoiseGenerator(HypothesisGenerator):
    """Noise / false-story variants. They still need a rationale so DSR N counts them."""

    def __init__(
        self,
        *,
        n_obs: int = 360,
        sigma: float = 0.012,
        instrument: str = "MES",
        quantity: float = 1.0,
        price: float = 5_000.0,
    ) -> None:
        self._n_obs = n_obs
        self._sigma = sigma
        self._instrument = instrument
        self._quantity = quantity
        self._price = price

    @property
    def generator_id(self) -> str:
        return "noise"

    def drafts(self, *, rng: random.Random, count: int, start_index: int) -> tuple[HypothesisDraft, ...]:
        if count < 0:
            raise GeneratorError("count must be >= 0")
        items: list[HypothesisDraft] = []
        for offset in range(count):
            index = start_index + offset
            seed = rng.randint(1, 2_147_483_647)
            config_id = f"noise-{index:04d}-s{seed}"
            rationale = EconomicRationale(
                mechanism=(
                    f"Claimed calendar-numerology overlay #{index} on a zero-drift futures tape"
                ),
                why_edge_exists=(
                    "The story asserts a seasonal premium without a risk-bearing counterparty "
                    "or inventory constraint that would survive costs"
                ),
                other_side="Unspecified residual; no impatient flow is identified",
                expected_regime="all-regimes equally, which is itself a falsifiable claim",
                falsification_criterion=(
                    "median OOS after costs <= 0 or PBO > 0.50 or DSR < 0.95 or WFE < 0.5"
                ),
            )
            items.append(
                HypothesisDraft(
                    config_id=config_id,
                    generator_id=self.generator_id,
                    kind="noise",
                    instrument=self._instrument,
                    seed=seed,
                    n_obs=self._n_obs,
                    mu=0.0,
                    sigma=self._sigma,
                    planted=False,
                    proposed_quantity=self._quantity,
                    proposed_price=self._price,
                    proposed_notional=self._quantity * self._price,
                    rationale=rationale,
                )
            )
        return tuple(items)


class PlantedEdgeGenerator(HypothesisGenerator):
    """Genuine synthetic edge after four-leg costs. Still must pass the full gate."""

    def __init__(
        self,
        *,
        n_obs: int = 360,
        mu: float = 0.0045,
        sigma: float = 0.008,
        instrument: str = "MES",
        quantity: float = 1.0,
        price: float = 5_000.0,
    ) -> None:
        self._n_obs = n_obs
        self._mu = mu
        self._sigma = sigma
        self._instrument = instrument
        self._quantity = quantity
        self._price = price

    @property
    def generator_id(self) -> str:
        return "planted_edge"

    def drafts(self, *, rng: random.Random, count: int, start_index: int) -> tuple[HypothesisDraft, ...]:
        if count < 0:
            raise GeneratorError("count must be >= 0")
        items: list[HypothesisDraft] = []
        for offset in range(count):
            index = start_index + offset
            seed = rng.randint(1, 2_147_483_647)
            strength = 1.0 if offset == 0 else max(0.85, 1.0 - 0.08 * offset)
            config_id = f"planted-{index:04d}-s{seed}"
            rationale = EconomicRationale(
                mechanism=(
                    "Inventory-holding premium on a positive-drift synthetic futures tape "
                    "after commission, half-spread, slippage and sqrt market impact"
                ),
                why_edge_exists=(
                    "Impatient demand pays spread and impact to transfer inventory; "
                    "a patient long earns the residual drift net of the four-leg cost model"
                ),
                other_side="Noise traders demanding immediacy / liquidity consumers",
                expected_regime="trend-up with moderate volatility",
                falsification_criterion=(
                    "median OOS after costs <= 0 or PBO > 0.50 or DSR < 0.95 or WFE < 0.5 "
                    "or a missing OOS distribution"
                ),
            )
            items.append(
                HypothesisDraft(
                    config_id=config_id,
                    generator_id=self.generator_id,
                    kind="planted_edge",
                    instrument=self._instrument,
                    seed=seed,
                    n_obs=self._n_obs,
                    mu=self._mu * strength,
                    sigma=self._sigma,
                    planted=True,
                    proposed_quantity=self._quantity,
                    proposed_price=self._price,
                    proposed_notional=self._quantity * self._price,
                    rationale=rationale,
                )
            )
        return tuple(items)
