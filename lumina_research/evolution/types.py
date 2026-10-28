"""Phase 3 mutation kinds and genome bounds. Fitness stays the Phase 1 composite."""

from __future__ import annotations

from typing import Literal

from lumina_core.agent_orchestration.schemas_research import (
    EconomicRationale,
    MutationKind,
    ParameterGenome,
)

ALLOWED_KINDS: frozenset[MutationKind] = frozenset({"parameter_tune", "open_window", "noise"})
PROTECTED_KINDS: frozenset[MutationKind] = frozenset({"threshold_change", "risk_core_change"})
FORBIDDEN_KINDS: frozenset[MutationKind] = frozenset({"strategy_switch", "skip_gate", "direct_promotion"})

MIN_N_OBS = 241
MAX_N_OBS = 720
MIN_IS_SIZE = 20
MAX_IS_SIZE = 120
MIN_OOS_SIZE = 10
MAX_OOS_SIZE = 60
MIN_OOS_WINDOWS = 6
MAX_QUANTITY = 10.0
MIN_SIGMA = 1e-6
MAX_SIGMA = 0.05
GENOME_TARGET = "genome"
THRESHOLD_TARGET = "lumina_research/validation/gate_thresholds.toml"
RISK_CORE_TARGET = "lumina_research/risk_core/limits.toml"
LIVE_RISK_TARGET = "lumina_core/risk"

Instrument = Literal["ES", "NQ", "MES", "MNQ"]


class MutationRefused(ValueError):
    """A mutation that is malformed or tries to skip the gate."""


def default_parent(*, instrument: Instrument = "MES") -> ParameterGenome:
    """Planted-edge parent used by the birth phase. Must still pass the full gate."""
    return ParameterGenome(
        instrument=instrument,
        n_obs=360,
        mu=0.0045,
        sigma=0.008,
        quantity=1.0,
        price=5_000.0,
        is_size=60,
        oos_size=30,
        planted=True,
        kind="planted_edge",
    )


def min_observations(is_size: int, oos_size: int) -> int:
    return max(MIN_N_OBS, int(is_size) + MIN_OOS_WINDOWS * int(oos_size))


def require_feasible(genome: ParameterGenome) -> ParameterGenome:
    if genome.n_obs < MIN_N_OBS or genome.n_obs > MAX_N_OBS:
        raise MutationRefused("n_obs is outside the birth window bounds")
    if genome.is_size < MIN_IS_SIZE or genome.is_size > MAX_IS_SIZE:
        raise MutationRefused("is_size is outside the birth window bounds")
    if genome.oos_size < MIN_OOS_SIZE or genome.oos_size > MAX_OOS_SIZE:
        raise MutationRefused("oos_size is outside the birth window bounds")
    if genome.n_obs < min_observations(genome.is_size, genome.oos_size):
        raise MutationRefused("walk-forward windows do not fit n_obs")
    if genome.sigma < MIN_SIGMA or genome.sigma > MAX_SIGMA:
        raise MutationRefused("sigma is outside the birth bounds")
    if genome.quantity <= 0.0 or genome.quantity > MAX_QUANTITY:
        raise MutationRefused("quantity is outside the birth bounds")
    return genome


def evolution_rationale(mechanism: str) -> EconomicRationale:
    return EconomicRationale(
        mechanism=mechanism,
        why_edge_exists="Impatient demand pays spread and impact to transfer inventory residual",
        other_side="Noise traders demanding immediacy on the futures tape",
        expected_regime="trend-up with moderate volatility, used only for sizing",
        falsification_criterion="median OOS after costs <= 0 or PBO > 0.50 or DSR < 0.95 or WFE < 0.5",
    )
