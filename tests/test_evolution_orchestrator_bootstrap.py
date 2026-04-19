from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from lumina_core.evolution.dna_registry import PolicyDNA
from lumina_core.evolution.evolution_orchestrator import EvolutionOrchestrator
from lumina_core.evolution.multi_day_sim_runner import SimResult


class _RegistryStub:
    def __init__(self) -> None:
        self._ranked: list[PolicyDNA] = []
        self._active: PolicyDNA | None = None

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
    def evaluate_variants(self, variants: list[PolicyDNA], *, days: int, nightly_report: dict | None = None):
        del days, nightly_report
        return [
            SimResult(
                dna_hash=variant.hash,
                day_count=1,
                avg_pnl=25.0,
                max_drawdown_ratio=0.01,
                regime_fit_bonus=0.1,
                fitness=42.0,
            )
            for variant in variants
        ]


class _ABFrameworkStub:
    def __init__(self, **_kwargs):
        pass

    def run_auto_forks(self, *, candidate_pool, **_kwargs):
        return SimpleNamespace(
            selected_variant={
                "dna_hash": str(candidate_pool[0]["dna_hash"]),
                "score": float(candidate_pool[0].get("score", 42.0) or 42.0),
            },
            experiment_id="ab-bootstrap-test",
        )


class _TwinStub:
    def __init__(self, recommendation: bool = True) -> None:
        self.recommendation = recommendation
        self.calls = 0

    def evaluate_dna_promotion(self, _dna: PolicyDNA) -> dict[str, object]:
        self.calls += 1
        return {
            "recommendation": bool(self.recommendation),
            "confidence": 0.95,
            "explanation": "stub",
            "risk_flags": [],
        }


def test_evolution_orchestrator_bootstraps_seed_for_empty_registry(monkeypatch) -> None:
    import lumina_core.evolution.evolution_orchestrator as eo

    monkeypatch.setattr(eo.EvolutionOrchestrator, "_instance", None)
    monkeypatch.setattr(eo, "ABExperimentFramework", _ABFrameworkStub)

    orchestrator = EvolutionOrchestrator()
    registry = _RegistryStub()
    orchestrator._registry = cast(Any, registry)
    orchestrator._sim_runner = cast(Any, _SimRunnerStub())

    summary = orchestrator.run_nightly_evolution_cycle(
        generations=1,
        sim_duration_hours=24,
        nightly_report={"net_pnl": -50.0, "max_drawdown": 100.0, "sharpe": -0.4},
        mode="sim",
    )

    assert summary["status"] == "complete"
    assert int(summary["generations_run"]) == 1
    assert int(summary["total_candidates_evaluated"]) >= 5
    assert registry.get_latest_dna("active") is not None


def test_evolution_orchestrator_blocks_real_without_explicit_human_approval(monkeypatch) -> None:
    import lumina_core.evolution.evolution_orchestrator as eo

    monkeypatch.setattr(eo.EvolutionOrchestrator, "_instance", None)
    monkeypatch.setattr(eo, "ABExperimentFramework", _ABFrameworkStub)

    orchestrator = EvolutionOrchestrator()
    orchestrator._registry = cast(Any, _RegistryStub())
    orchestrator._sim_runner = cast(Any, _SimRunnerStub())
    orchestrator._approval_twin = cast(Any, _TwinStub(recommendation=True))

    summary = orchestrator.run_nightly_evolution_cycle(
        generations=1,
        sim_duration_hours=24,
        nightly_report={"net_pnl": 100.0, "max_drawdown": 50.0, "sharpe": 1.2},
        mode="real",
        explicit_human_approval=False,
    )

    assert summary["status"] == "blocked"
    assert summary["reason"] == "real_promotion_requires_explicit_human_approval"


def test_evolution_orchestrator_real_path_uses_approval_twin(monkeypatch) -> None:
    import lumina_core.evolution.evolution_orchestrator as eo

    monkeypatch.setattr(eo.EvolutionOrchestrator, "_instance", None)
    monkeypatch.setattr(eo, "ABExperimentFramework", _ABFrameworkStub)

    orchestrator = EvolutionOrchestrator()
    registry = _RegistryStub()
    twin = _TwinStub(recommendation=True)
    orchestrator._registry = cast(Any, registry)
    orchestrator._sim_runner = cast(Any, _SimRunnerStub())
    orchestrator._approval_twin = cast(Any, twin)

    summary = orchestrator.run_nightly_evolution_cycle(
        generations=1,
        sim_duration_hours=24,
        nightly_report={"net_pnl": 120.0, "max_drawdown": 40.0, "sharpe": 1.4},
        mode="real",
        explicit_human_approval=True,
    )

    assert summary["status"] == "complete"
    assert twin.calls >= 1
    assert registry.get_latest_dna("active") is not None
