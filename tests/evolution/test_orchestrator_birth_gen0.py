from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from lumina_core.evolution.dna_registry import PolicyDNA
from lumina_core.evolution.evolution_orchestrator import EvolutionOrchestrator


class _ABFrameworkStub:
    def __init__(self, **_kwargs):
        pass

    def run_auto_forks(self, *, candidate_pool, **_kwargs):
        variants = [dict(item) for item in list(candidate_pool or [])]
        return SimpleNamespace(
            selected_variant={
                "dna_hash": str(candidate_pool[0]["dna_hash"]),
                "score": float(candidate_pool[0].get("score", 42.0) or 42.0),
            },
            experiment_id="ab-birth-gen0-test",
            variants=variants,
        )


class _RegistryWithBirthGen0:
    def __init__(self) -> None:
        self._active = PolicyDNA.create(
            prompt_id="birth_v2_certificate",
            version="active",
            content={"candidate_name": "birth_v2_certificate", "birth_certificate_version": "2.0"},
            fitness_score=0.42,
            generation=0,
            lineage_hash="birthgen0",
        )
        self._ranked: list[PolicyDNA] = []

    def get_ranked_dna(self, limit: int = 3) -> list[PolicyDNA]:
        return list(self._ranked[: max(0, int(limit))])

    def get_latest_dna(self, version: str = "active") -> PolicyDNA | None:
        if version == "active":
            return self._active
        return None

    def register_dna(self, dna: PolicyDNA) -> PolicyDNA:
        if dna.version == "active":
            self._active = dna
        self._ranked = [dna, *[item for item in self._ranked if item.hash != dna.hash]]
        return dna

    def mutate(
        self,
        *,
        parent: PolicyDNA,
        mutation_rate: float,
        content: str | None = None,
        fitness_score: float,
        version: str,
        lineage_hash: str,
        crossover: PolicyDNA | None = None,
    ) -> PolicyDNA:
        del crossover
        return PolicyDNA.create(
            prompt_id=parent.prompt_id,
            version=version,
            content=content if content is not None else parent.content,
            fitness_score=fitness_score,
            generation=parent.generation + 1,
            parent_ids=[parent.hash],
            mutation_rate=mutation_rate,
            lineage_hash=lineage_hash,
        )


class _SimRunnerStub:
    def evaluate_variants(self, variants: list[PolicyDNA], **_kwargs: Any):
        from lumina_core.evolution.multi_day_sim_runner import SimResult

        return [
            SimResult(
                dna_hash=variant.hash,
                day_count=1,
                avg_pnl=25.0,
                max_drawdown_ratio=0.01,
                regime_fit_bonus=0.1,
                fitness=42.0,
                shadow_mode=False,
                hypothetical_fills=None,
            )
            for variant in variants
        ]


@pytest.mark.unit
def test_orchestrator_skips_bootstrap_when_birth_gen0_exists(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import lumina_core.evolution.evolution_orchestrator as eo

    monkeypatch.setattr(eo.EvolutionOrchestrator, "_instance", None)
    monkeypatch.setattr(eo, "ABExperimentFramework", _ABFrameworkStub)

    bootstrap_calls: list[dict[str, Any]] = []

    def _spy_bootstrap(self, *, base_metrics: dict[str, Any]) -> PolicyDNA:
        bootstrap_calls.append(dict(base_metrics))
        return PolicyDNA.create(
            prompt_id="bootstrap_seed",
            version="active",
            content={"name": "bootstrap"},
            fitness_score=0.0,
            generation=0,
            lineage_hash="bootstrap",
        )

    monkeypatch.setattr(eo.EvolutionOrchestrator, "_bootstrap_active_dna", _spy_bootstrap)

    orchestrator = EvolutionOrchestrator()
    orchestrator._shadow_state_path = tmp_path / "shadow_birth_gen0.json"
    orchestrator._registry = cast(Any, _RegistryWithBirthGen0())
    orchestrator._sim_runner = cast(Any, _SimRunnerStub())
    seen_active: list[PolicyDNA | None] = []

    def _generate_candidates(**kwargs: Any) -> list[PolicyDNA]:
        seen_active.append(kwargs.get("active_dna"))
        return [
            PolicyDNA.create(
                prompt_id="candidate",
                version="candidate",
                content={"name": "candidate"},
                fitness_score=40.0,
                generation=1,
                lineage_hash="c1",
            )
        ]

    orchestrator._generate_candidates = cast(Any, _generate_candidates)

    result = orchestrator._run_single_generation(
        generation_offset=0,
        mode="sim",
        explicit_human_approval=False,
        require_human_approval=False,
        real_promotion_approvals=None,
        base_metrics={"net_pnl": 10.0, "max_drawdown": 20.0, "account_equity": 50_000.0},
        sim_days=1,
    )

    assert bootstrap_calls == []
    assert seen_active
    assert seen_active[0] is not None
    assert seen_active[0].prompt_id == "birth_v2_certificate"
    assert result.generation == 0
