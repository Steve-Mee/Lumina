"""Deterministic synthetic tapes for research hypotheses. No network."""

from __future__ import annotations

import random
from typing import Literal, assert_never

from lumina_core.agent_orchestration.schemas_research import HypothesisProposed
from lumina_research.validation.cost_model import MarketSnapshot


class MaterializeRefused(ValueError):
    """Economic hypotheses cannot be turned into a synthetic tape."""


def gauss(rng: random.Random) -> float:
    """Standard normal draw from a seeded ``random.Random`` (no numpy)."""
    return rng.gauss(0.0, 1.0)


def materialize(
    hypothesis: HypothesisProposed,
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[MarketSnapshot, ...]]:
    """Map a sealed hypothesis to gross returns, positions and markets."""
    if hypothesis.kind == "economic":
        raise MaterializeRefused("economic hypotheses require a real-data materializer")
    rng = random.Random(hypothesis.seed)
    n = hypothesis.n_obs
    if hypothesis.overfit_in_sample:
        gross = _overfit_is_gross(n, int(hypothesis.is_size), hypothesis.sigma, rng)
        positions = tuple(1.0 for _ in range(n))
    elif hypothesis.kind == "planted_edge":
        gross = _planted_gross(n, hypothesis.mu, hypothesis.sigma, rng)
        positions = _positions("planted_edge", n, hypothesis.seed)
    elif hypothesis.kind == "noise":
        gross = tuple(hypothesis.mu + hypothesis.sigma * gauss(rng) for _ in range(n))
        positions = _positions("noise", n, hypothesis.seed)
    else:
        assert_never(hypothesis.kind)
    snap = MarketSnapshot(volume=10_000.0, average_volume=10_000.0, volatility_price=2.0)
    markets = tuple(snap for _ in range(n))
    return gross, positions, markets


def _planted_gross(n: int, mu: float, sigma: float, rng: random.Random) -> tuple[float, ...]:
    """Positive-drift tape with explicit vol and trend blocks so regimes are computable.

    Six blocks: four positive-drift and two milder negative-drift, alternating
    high/low volatility. Net expected drift stays positive after four-leg costs.
    """
    drifts = (mu * 1.6, mu * 1.6, -mu * 0.35, mu * 1.6, mu * 1.6, -mu * 0.35)
    sigmas = (sigma * 1.8, sigma * 0.55, sigma * 1.8, sigma * 0.55, sigma * 1.8, sigma * 0.55)
    block = n // 6
    out: list[float] = []
    for index, (drift, noise) in enumerate(zip(drifts, sigmas, strict=True)):
        length = block if index < 5 else n - 5 * block
        for _ in range(length):
            out.append(drift + noise * gauss(rng))
    return tuple(out)


def _overfit_is_gross(n: int, is_size: int, sigma: float, rng: random.Random) -> tuple[float, ...]:
    """Peak-fitted in-sample drift that dies out-of-sample. Not a planted edge."""
    peak = max(2, min(int(is_size), n))
    out: list[float] = []
    noise = max(float(sigma), 1e-6)
    for index in range(n):
        drift = 0.02 if index < peak else -0.003
        out.append(drift + noise * gauss(rng))
    return tuple(out)


def _positions(kind: Literal["noise", "planted_edge"], n: int, seed: int) -> tuple[float, ...]:
    if kind == "planted_edge":
        return tuple(1.0 for _ in range(n))
    rng = random.Random(seed + 17)
    return tuple(float(rng.choice((-1.0, 1.0))) for _ in range(n))
