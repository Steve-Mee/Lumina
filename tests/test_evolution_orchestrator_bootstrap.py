from __future__ import annotations

from pathlib import Path
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
    def evaluate_variants(
        self,
        variants: list[PolicyDNA],
        *,
        days: int,
        nightly_report: dict | None = None,
        shadow_mode: bool = False,
        real_market_data: bool = False,
    ):
        del days, real_market_data  # Not used in stub
        base_pnl = float((nightly_report or {}).get("net_pnl", 25.0) or 25.0)
        return [
            SimResult(
                dna_hash=variant.hash,
                day_count=1,
                avg_pnl=base_pnl,
                max_drawdown_ratio=0.01,
                regime_fit_bonus=0.1,
                fitness=42.0,
                shadow_mode=shadow_mode,
                hypothetical_fills=[] if shadow_mode else None,
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

    def evaluate_shadow_promotion(
        self, *, dna: PolicyDNA, shadow_total_pnl: float, veto_blocked: bool
    ) -> dict[str, object]:
        base = self.evaluate_dna_promotion(dna)
        return {
            **base,
            "recommendation": bool(base["recommendation"] and shadow_total_pnl > 0.0 and not veto_blocked),
            "shadow_total_pnl": float(shadow_total_pnl),
            "veto_blocked": bool(veto_blocked),
        }


def test_evolution_orchestrator_bootstraps_seed_for_empty_registry(monkeypatch, tmp_path: Path) -> None:
    import lumina_core.evolution.evolution_orchestrator as eo

    monkeypatch.setattr(eo.EvolutionOrchestrator, "_instance", None)
    monkeypatch.setattr(eo, "ABExperimentFramework", _ABFrameworkStub)

    orchestrator = EvolutionOrchestrator()
    orchestrator._shadow_state_path = tmp_path / "shadow_bootstrap.json"
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


def test_evolution_orchestrator_real_path_starts_shadow_before_promotion(monkeypatch, tmp_path: Path) -> None:
    import lumina_core.evolution.evolution_orchestrator as eo

    monkeypatch.setattr(eo.EvolutionOrchestrator, "_instance", None)
    monkeypatch.setattr(eo, "ABExperimentFramework", _ABFrameworkStub)

    orchestrator = EvolutionOrchestrator()
    orchestrator._shadow_state_path = tmp_path / "shadow_pending.json"
    registry = _RegistryStub()
    orchestrator._registry = cast(Any, registry)
    orchestrator._sim_runner = cast(Any, _SimRunnerStub())
    orchestrator._approval_twin = cast(Any, _TwinStub(recommendation=True))

    summary = orchestrator.run_nightly_evolution_cycle(
        generations=1,
        sim_duration_hours=24,
        nightly_report={"net_pnl": 100.0, "max_drawdown": 50.0, "sharpe": 1.2},
        mode="real",
        explicit_human_approval=False,
    )

    assert summary["status"] == "complete"
    assert int(summary["promotions"]) == 0
    active = registry.get_latest_dna("active")
    assert active is not None
    assert int(active.generation) == 0


def test_evolution_orchestrator_real_path_promotes_after_shadow_pass(monkeypatch, tmp_path: Path) -> None:
    import lumina_core.evolution.evolution_orchestrator as eo

    monkeypatch.setattr(eo.EvolutionOrchestrator, "_instance", None)
    monkeypatch.setattr(eo, "ABExperimentFramework", _ABFrameworkStub)

    orchestrator = EvolutionOrchestrator()
    orchestrator._shadow_state_path = tmp_path / "shadow_pass.json"
    registry = _RegistryStub()
    twin = _TwinStub(recommendation=True)
    fixed_candidate = PolicyDNA.create(
        prompt_id="shadow-fixed",
        version="candidate",
        content={"name": "fixed"},
        fitness_score=42.0,
        generation=1,
        lineage_hash="L1",
    )

    def _fixed_candidates(*, top_dna, active_dna, generation_offset):
        del top_dna, active_dna, generation_offset
        return [fixed_candidate]

    monkeypatch.setattr(
        eo.EvolutionGuard,
        "resolve_shadow_days",
        lambda self, minimum_days=3, maximum_days=7: 1,
    )

    orchestrator._registry = cast(Any, registry)
    orchestrator._sim_runner = cast(Any, _SimRunnerStub())
    orchestrator._approval_twin = cast(Any, twin)
    orchestrator._generate_candidates = cast(Any, _fixed_candidates)

    summary = orchestrator.run_nightly_evolution_cycle(
        generations=2,
        sim_duration_hours=24,
        nightly_report={"net_pnl": 120.0, "max_drawdown": 40.0, "sharpe": 1.4},
        mode="real",
        explicit_human_approval=False,
    )

    assert summary["status"] == "complete"
    assert int(summary["promotions"]) >= 1
    assert twin.calls >= 2
    active = registry.get_latest_dna("active")
    assert active is not None
    assert int(active.generation) >= 1
