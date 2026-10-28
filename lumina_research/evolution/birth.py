"""Birth phase: open new walk-forward windows and tune parameters. Propose-only."""

from __future__ import annotations

from lumina_core.agent_orchestration.schemas_research import MutationProposed, ParameterGenome
from lumina_research.agents.frozen import Frozen
from lumina_research.evolution.mutations import copy_genome
from lumina_research.evolution.reflector import ReflectorAgent
from lumina_research.evolution.types import (
    GENOME_TARGET,
    MAX_IS_SIZE,
    MAX_N_OBS,
    MAX_OOS_SIZE,
    MIN_IS_SIZE,
    MIN_OOS_SIZE,
    MutationRefused,
    evolution_rationale,
    min_observations,
    require_feasible,
)


class BirthRefused(ValueError):
    """Birth tried to apply, switch strategy, or open an illegal window."""


class BirthPhase(Frozen):
    """Opens research windows and parameter children through the reflector only."""

    _reflector: ReflectorAgent

    def __init_subclass__(cls) -> None:
        raise TypeError("BirthPhase cannot be subclassed")

    def __init__(self, reflector: ReflectorAgent) -> None:
        self._reflector = reflector
        self._freeze()

    def apply(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise BirthRefused("birth can only propose")

    def switch_strategy(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise BirthRefused("birth cannot hard-switch strategies from regime")

    def open_window(
        self,
        parent: ParameterGenome,
        *,
        seed: int,
        index: int,
        is_size: int | None = None,
        oos_size: int | None = None,
        n_obs: int | None = None,
    ) -> MutationProposed:
        next_is = parent.is_size if is_size is None else int(is_size)
        next_oos = parent.oos_size if oos_size is None else int(oos_size)
        if next_is < MIN_IS_SIZE or next_is > MAX_IS_SIZE:
            raise MutationRefused("is_size is outside the birth window bounds")
        if next_oos < MIN_OOS_SIZE or next_oos > MAX_OOS_SIZE:
            raise MutationRefused("oos_size is outside the birth window bounds")
        need = min_observations(next_is, next_oos)
        next_n = parent.n_obs if n_obs is None else int(n_obs)
        next_n = max(next_n, need)
        if next_n > MAX_N_OBS:
            raise MutationRefused("opened window exceeds max n_obs")
        child = copy_genome(parent, is_size=next_is, oos_size=next_oos, n_obs=next_n)
        require_feasible(child)
        config_id = f"birth-window-{index:04d}-s{seed}"
        return self._reflector.propose(
            kind="open_window",
            target=GENOME_TARGET,
            genome=child,
            rationale=evolution_rationale(
                f"Open a new walk-forward window is={next_is} oos={next_oos} n={next_n} on the parent tape"
            ),
            seed=seed,
            parent_config_id=_parent_id(parent, index),
            config_id=config_id,
        )

    def tune(
        self,
        parent: ParameterGenome,
        *,
        seed: int,
        index: int,
        scale_mu: float = 1.0,
        scale_sigma: float = 1.0,
        scale_quantity: float = 1.0,
    ) -> MutationProposed:
        child = copy_genome(
            parent,
            mu=float(parent.mu) * float(scale_mu),
            sigma=float(parent.sigma) * float(scale_sigma),
            quantity=float(parent.quantity) * float(scale_quantity),
        )
        config_id = f"birth-tune-{index:04d}-s{seed}"
        return self._reflector.propose(
            kind="parameter_tune",
            target=GENOME_TARGET,
            genome=child,
            rationale=evolution_rationale(
                f"Tune parent mu*{scale_mu:.3f} sigma*{scale_sigma:.3f} qty*{scale_quantity:.3f} through the gate"
            ),
            seed=seed,
            parent_config_id=_parent_id(parent, index),
            config_id=config_id,
        )

    def overfit_tune(
        self,
        parent: ParameterGenome,
        *,
        seed: int,
        index: int,
        scale_mu: float = 2.0,
    ) -> MutationProposed:
        """Parameter tune peak-fitted on in-sample windows. Counted, expected to die OOS."""
        child = copy_genome(
            parent,
            mu=float(parent.mu) * float(scale_mu),
            planted=False,
            kind="noise",
            overfit_in_sample=True,
        )
        config_id = f"birth-overfit-{index:04d}-s{seed}"
        return self._reflector.propose(
            kind="parameter_tune",
            target=GENOME_TARGET,
            genome=child,
            rationale=evolution_rationale(
                f"In-sample peak-fit mu*{scale_mu:.3f} that must die on the OOS walk-forward"
            ),
            seed=seed,
            parent_config_id=_parent_id(parent, index),
            config_id=config_id,
        )

    def noise_child(
        self,
        parent: ParameterGenome,
        *,
        seed: int,
        index: int,
    ) -> MutationProposed:
        child = copy_genome(
            parent,
            mu=0.0,
            planted=False,
            kind="noise",
        )
        config_id = f"birth-noise-{index:04d}-s{seed}"
        return self._reflector.propose(
            kind="noise",
            target=GENOME_TARGET,
            genome=child,
            rationale=evolution_rationale(
                f"Noise mutation #{index} of the parent window, counted in DSR N, expected to die"
            ),
            seed=seed,
            parent_config_id=_parent_id(parent, index),
            config_id=config_id,
        )


def _parent_id(parent: ParameterGenome, index: int) -> str:
    return f"parent-{parent.kind}-{parent.instrument}-{index}"
