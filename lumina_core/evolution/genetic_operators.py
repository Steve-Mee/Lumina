"""Live fitness helper. Birth-v1 mutation/crossover is archived (Validation Gate)."""

from __future__ import annotations

from .dna_registry import PolicyDNA


def mutate_prompt(prompt: str, rate: float) -> str:
    del rate
    return str(prompt or "")


def crossover(parent1: PolicyDNA, parent2: PolicyDNA) -> str:
    del parent2
    return str(getattr(parent1, "content", "") or "")


def calculate_fitness(
    pnl: float,
    max_dd: float,
    sharpe: float,
    *,
    capital_preservation_threshold: float = 25000.0,
    drawdown_weight: float = 0.0001,
    reality_gap_penalty: float = 0.0,
    pbo: float = 0.0,
    dsr: float | None = None,
    sharpe_positive_pct: float = 1.0,
) -> float:
    """Score a candidate. Does not generate signals."""
    pnl_value = float(pnl or 0.0)
    drawdown_value = float(max_dd or 0.0)
    sharpe_value = float(sharpe or 0.0)
    if drawdown_value > float(capital_preservation_threshold):
        return float("-inf")

    base = sharpe_value + (pnl_value / 10000.0) - (drawdown_value * float(drawdown_weight))
    base -= float(reality_gap_penalty or 0.0)
    pbo_value = max(0.0, min(1.0, float(pbo or 0.0)))
    base -= pbo_value * 2.0
    if dsr is not None and float(dsr) < 0.0:
        base = min(base, 0.0)
    consistency = float(sharpe_positive_pct or 1.0)
    if consistency < 0.5:
        base -= 0.5
    return base
