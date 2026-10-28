"""Birth phase opens windows and tunes parameters through the reflector only."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_research.agents.generators import GeneratorError
from lumina_research.evolution.mutations import DraftGenerator, mutation_to_draft
from lumina_research.evolution.regime import RegimeObservation, RegimePolicy
from lumina_research.evolution.types import MAX_N_OBS, MutationRefused, default_parent, min_observations
from tests.research.phase3_harness import make_runtime


@pytest.mark.unit
def test_open_window_raises_n_obs_to_fit_walk_forward(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    parent = default_parent()
    opened = runtime.birth.open_window(parent, seed=4, index=0, oos_size=40)
    need = min_observations(parent.is_size, 40)
    assert opened.kind == "open_window"
    assert opened.genome.oos_size == 40
    assert opened.genome.n_obs >= need
    assert opened.genome.kind == parent.kind
    assert runtime.registry.n_trials >= 1


@pytest.mark.unit
def test_tune_and_noise_children_are_distinct_trials(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    parent = default_parent()
    tuned = runtime.birth.tune(parent, seed=5, index=1, scale_mu=0.95)
    noise = runtime.birth.noise_child(parent, seed=6, index=2)
    assert tuned.kind == "parameter_tune"
    assert tuned.genome.planted is True
    assert tuned.genome.mu == pytest.approx(parent.mu * 0.95)
    assert noise.kind == "noise"
    assert noise.genome.planted is False
    assert noise.genome.mu == 0.0
    assert tuned.trial_id != noise.trial_id
    assert runtime.registry.n_trials == 2


@pytest.mark.unit
def test_illegal_window_and_quantity_are_refused(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    parent = default_parent()
    with pytest.raises(MutationRefused, match="is_size"):
        runtime.birth.open_window(parent, seed=1, index=0, is_size=2)
    with pytest.raises(MutationRefused, match="oos_size"):
        runtime.birth.open_window(parent, seed=1, index=0, oos_size=200)
    with pytest.raises(MutationRefused, match="max n_obs"):
        runtime.birth.open_window(parent, seed=1, index=0, n_obs=MAX_N_OBS + 1, oos_size=60)
    with pytest.raises(MutationRefused, match="quantity"):
        runtime.birth.tune(parent, seed=1, index=0, scale_quantity=100.0)


@pytest.mark.unit
def test_draft_generator_and_forbidden_to_draft(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    parent = default_parent()
    mutation = runtime.birth.tune(parent, seed=7, index=0)
    action = RegimePolicy().act(RegimeObservation(vol="low", trend="up"))
    draft = mutation_to_draft(mutation, action=action)
    assert draft.parent_config_id
    assert draft.is_size == parent.is_size
    gen = DraftGenerator((draft,))
    assert gen.generator_id == "evolution"
    with pytest.raises(GeneratorError):
        gen.drafts(rng=None, count=0, start_index=0)  # type: ignore[arg-type]
    forbidden = runtime.reflector.propose(
        kind="strategy_switch",
        target="strategy",
        genome=parent,
        rationale=mutation.rationale,
        seed=8,
        parent_config_id="p",
        config_id="switch-1",
    )
    with pytest.raises(MutationRefused, match="forbidden"):
        mutation_to_draft(forbidden, action=action)
    protected = runtime.reflector.propose(
        kind="threshold_change",
        target="lumina_research/validation/gate_thresholds.toml",
        genome=parent,
        rationale=mutation.rationale,
        seed=9,
        parent_config_id="p",
        config_id="thr-1",
    )
    with pytest.raises(MutationRefused, match="protected"):
        mutation_to_draft(protected, action=action)


@pytest.mark.unit
def test_runtime_and_birth_cannot_be_subclassed(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    with pytest.raises(TypeError):

        class _B(type(runtime.birth)):  # type: ignore[misc]
            pass

    with pytest.raises(TypeError):

        class _E(type(runtime)):  # type: ignore[misc]
            pass

    with pytest.raises(AttributeError):
        runtime.reflector._bus = None  # type: ignore[misc]
