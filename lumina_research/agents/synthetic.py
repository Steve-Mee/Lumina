"""Deterministic synthetic tapes for research hypotheses. No network."""

from __future__ import annotations

import random
from typing import Literal

from lumina_core.agent_orchestration.schemas_research import HypothesisProposed
from lumina_research.validation.cost_model import MarketSnapshot


def gauss(rng: random.Random) -> float:
    return rng.gauss(0.0, 1.0)


def materialize(
    hypothesis: HypothesisProposed,
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[MarketSnapshot, ...]]:
    """Map a sealed hypothesis to gross returns, positions and markets."""
    rng = random.Random(hypothesis.seed)
    n = hypothesis.n_obs
    gross = tuple(hypothesis.mu + hypothesis.sigma * gauss(rng) for _ in range(n))
    positions = _positions(hypothesis.kind, n, hypothesis.seed)
    snap = MarketSnapshot(volume=10_000.0, average_volume=10_000.0, volatility_price=2.0)
    markets = tuple(snap for _ in range(n))
    return gross, positions, markets


def _positions(kind: Literal["noise", "planted_edge"], n: int, seed: int) -> tuple[float, ...]:
    if kind == "planted_edge":
        return tuple(1.0 for _ in range(n))
    rng = random.Random(seed + 17)
    return tuple(float(rng.choice((-1.0, 1.0))) for _ in range(n))
