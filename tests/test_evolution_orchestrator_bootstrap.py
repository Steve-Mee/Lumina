from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
import hashlib
import json
import os

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from lumina_core.evolution.dna_registry import PolicyDNA
from lumina_core.evolution.evolution_orchestrator import EvolutionOrchestrator
from lumina_core.evolution.multi_day_sim_runner import SimResult
from lumina_core.governance import ApprovalChain, ApprovalPolicy


def _public_hex(private_key: Ed25519PrivateKey) -> str:
    return (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        .hex()
    )


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
        true_backtest_mode: bool = False,
        **_: Any,
    ):
        del days, real_market_data, true_backtest_mode  # Not used in stub
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


class _SimRunnerParallelCapture(_SimRunnerStub):
    """Legt ``parallel_realities`` vast (integratietest met :func:`resolve_parallel_realities`)."""

    def __init__(self) -> None:
        self.last_parallel: int | None = None

    def evaluate_variants(
        self,
        variants: list[PolicyDNA],
        *,
        days: int,
        nightly_report: dict | None = None,
        shadow_mode: bool = False,
        real_market_data: bool = False,
        true_backtest_mode: bool = False,
        parallel_realities: int = 1,
        **kwargs: Any,
    ) -> list[SimResult]:
        self.last_parallel = int(parallel_realities)
        return super().evaluate_variants(
            variants,
            days=days,
            nightly_report=nightly_report,
            shadow_mode=shadow_mode,
            real_market_data=real_market_data,
            true_backtest_mode=true_backtest_mode,
        )


class _SimRunnerWithGeneratedStub(_SimRunnerStub):
    def _test_generated_strategy(self, _code_snippet: str) -> float:
        return 120.0


class _SimRunnerWithGeneratedShadowFailStub(_SimRunnerWithGeneratedStub):
    def evaluate_variants(
        self,
        variants: list[PolicyDNA],
        *,
        days: int,
        nightly_report: dict | None = None,
        shadow_mode: bool = False,
        real_market_data: bool = False,
        true_backtest_mode: bool = False,
        **_: Any,
    ):
        del days, real_market_data, true_backtest_mode
        if shadow_mode:
            return [
                SimResult(
                    dna_hash=variant.hash,
                    day_count=1,
                    avg_pnl=0.0,
                    max_drawdown_ratio=0.01,
                    regime_fit_bonus=0.0,
                    fitness=0.0,
                    shadow_mode=True,
                    hypothetical_fills=[],
                )
                for variant in variants
            ]
        base_pnl = float((nightly_report or {}).get("net_pnl", 25.0) or 25.0)
        return [
            SimResult(
                dna_hash=variant.hash,
                day_count=1,
                avg_pnl=base_pnl,
                max_drawdown_ratio=0.01,
                regime_fit_bonus=0.1,
                fitness=42.0,
                shadow_mode=False,
                hypothetical_fills=None,
            )
            for variant in variants
        ]


class _StrategyGeneratorStub:
    def __init__(self) -> None:
        self._index = 0

    def generate_new_strategy(self, hypothesis: str) -> str:
        del hypothesis
        self._index += 1
        return (
            "def generated_strategy(context: dict) -> dict:\n"
            '    """Generated deterministic strategy."""\n'
            "    close = list(context.get('close', []) or [])\n"
            "    if len(close) < 2:\n"
            f"        return {{'name': 'g{self._index}', 'regime_focus': 'neutral', 'signal_bias': 'neutral', 'confidence': 0.0, 'rules': ['insufficient_history']}}\n"
            f"    return {{'name': 'g{self._index}', 'regime_focus': 'trending', 'signal_bias': 'buy', 'confidence': 0.95, 'rules': ['momentum']}}\n"
        )

    def compile_and_validate(self, code_snippet: str):
        return SimpleNamespace(
            code=str(code_snippet),
            function_name="generated_strategy",
            metadata={
                "name": "generated_stub",
                "regime_focus": "trending",
                "signal_bias": "buy",
                "confidence": 0.95,
            },
        )


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
            experiment_id="ab-bootstrap-test",
            variants=variants,
        )


class _PromotionGatePassStub:
    def evaluate(self, dna_hash: str, *, evidence: Any) -> Any:
        del dna_hash, evidence
        return SimpleNamespace(
            promoted=True,
            fail_reasons=(),
            model_dump=lambda mode="json": {"promoted": True, "fail_reasons": []},
        )


class _ApprovalChainStub:
    def __init__(self, approved: bool) -> None:
        self.approved = bool(approved)

    def verify(self, *, payload: Any, signatures: Any) -> tuple[bool, str]:
        del payload, signatures
        return self.approved, "approved" if self.approved else "threshold_not_met"


class _PolicyWeightsStub:
    def __init__(self) -> None:
        import torch

        self._state = {
            "layer.weight": torch.ones((2, 2), dtype=torch.float32),
            "layer.bias": torch.zeros((2,), dtype=torch.float32),
        }

    def state_dict(self):
        return {k: v.clone() for k, v in self._state.items()}

    def load_state_dict(self, state, strict=True):
        del strict
        self._state = {k: v.clone() for k, v in dict(state).items()}


class _ModelWeightsStub:
    def __init__(self) -> None:
        self.policy = _PolicyWeightsStub()

    def save(self, path: str) -> None:
        Path(path).write_text("weights-stub", encoding="utf-8")


class _PPOTrainerStub:
    def __init__(self) -> None:
        self.engine = SimpleNamespace(rl_policy_model=_ModelWeightsStub())

    def save_weights(self, policy_path) -> str:
        target = Path(policy_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self.engine.rl_policy_model.save(str(target))
        return str(target)

    def load_weights(self, _policy_path):
        # Keep active model stable in tests; emulate successful load.
        return self.engine.rl_policy_model

    def evaluate_policy_zip_rollouts(self, policy_path, simulator_data, **kwargs):
        del simulator_data, kwargs
        name = Path(policy_path).name
        if name.startswith("baseline_gen"):
            return {
                "ok": True,
                "shadow_equity_delta": 30.0,
                "shadow_total_reward": 1.0,
                "backtest_fitness": 100.0,
                "backtest_equity_delta": 0.0,
            }
        h = int(hashlib.sha256(name.encode()).hexdigest()[:8], 16)
        return {
            "ok": True,
            "shadow_equity_delta": 25.0,
            "shadow_total_reward": 1.0,
            "backtest_fitness": 100.2 + (h % 100) / 500.0,
            "backtest_equity_delta": 0.0,
        }


class _TwinStub:
    def __init__(self, recommendation: bool = True) -> None:
        self.recommendation = recommendation
        self.calls = 0

    def evaluate_dna_promotion(self, _dna: PolicyDNA) -> dict[str, object]:
        self.calls += 1
        return {
            "recommendation": bool(self.recommendation),
            "confidence": 0.97,
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

    def _fixed_candidates(*, top_dna, active_dna, generation_offset, dream_report=None, evolution_mode="sim", **kw):
        del top_dna, active_dna, generation_offset, dream_report, evolution_mode, kw
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
    orchestrator._promotion_gate = cast(Any, _PromotionGatePassStub())
    orchestrator._approval_chain = cast(Any, _ApprovalChainStub(approved=True))

    summary = orchestrator.run_nightly_evolution_cycle(
        generations=2,
        sim_duration_hours=24,
        nightly_report={"net_pnl": 120.0, "max_drawdown": 40.0, "sharpe": 1.4},
        mode="real",
        explicit_human_approval=True,
    )

    assert summary["status"] == "complete"
    assert int(summary["promotions"]) >= 1
    assert twin.calls >= 2
    active = registry.get_latest_dna("active")
    assert active is not None
    assert int(active.generation) >= 1


def test_evolution_orchestrator_registers_generated_strategy_winners(monkeypatch, tmp_path: Path) -> None:
    import lumina_core.evolution.evolution_orchestrator as eo

    monkeypatch.setattr(eo.EvolutionOrchestrator, "_instance", None)
    monkeypatch.setattr(eo, "ABExperimentFramework", _ABFrameworkStub)

    orchestrator = EvolutionOrchestrator()
    orchestrator._shadow_state_path = tmp_path / "shadow_generated.json"
    orchestrator._lumina_bible.path = tmp_path / "generated_bible.jsonl"
    orchestrator._generated_bible_path = orchestrator._lumina_bible.path
    registry = _RegistryStub()
    orchestrator._registry = cast(Any, registry)
    orchestrator._sim_runner = cast(Any, _SimRunnerWithGeneratedStub())
    orchestrator._strategy_generator = cast(Any, _StrategyGeneratorStub())

    summary = orchestrator.run_nightly_evolution_cycle(
        generations=1,
        sim_duration_hours=24,
        nightly_report={"net_pnl": 100.0, "max_drawdown": 50.0, "sharpe": 1.2},
        mode="sim",
    )

    ranked = registry.get_ranked_dna(limit=50)
    generated_winners = [item for item in ranked if item.version == "generated_winner"]
    assert summary["status"] == "complete"
    assert generated_winners
    assert orchestrator._generated_bible_path.exists()

    lines = [line for line in orchestrator._generated_bible_path.read_text(encoding="utf-8").splitlines() if line]
    assert lines
    payload = json.loads(lines[-1])
    assert payload.get("dna_hash")


def test_evolution_orchestrator_generated_winner_blocked_without_shadow_pass(monkeypatch, tmp_path: Path) -> None:
    import lumina_core.evolution.evolution_orchestrator as eo

    monkeypatch.setattr(eo.EvolutionOrchestrator, "_instance", None)
    monkeypatch.setattr(eo, "ABExperimentFramework", _ABFrameworkStub)

    orchestrator = EvolutionOrchestrator()
    orchestrator._shadow_state_path = tmp_path / "shadow_generated_fail.json"
    orchestrator._lumina_bible.path = tmp_path / "generated_bible_fail.jsonl"
    orchestrator._generated_bible_path = orchestrator._lumina_bible.path
    registry = _RegistryStub()
    orchestrator._registry = cast(Any, registry)
    orchestrator._sim_runner = cast(Any, _SimRunnerWithGeneratedShadowFailStub())
    orchestrator._strategy_generator = cast(Any, _StrategyGeneratorStub())

    summary = orchestrator.run_nightly_evolution_cycle(
        generations=1,
        sim_duration_hours=24,
        nightly_report={"net_pnl": 100.0, "max_drawdown": 50.0, "sharpe": 1.2},
        mode="sim",
    )

    ranked = registry.get_ranked_dna(limit=50)
    generated_winners = [item for item in ranked if item.version == "generated_winner"]
    assert summary["status"] == "complete"
    assert generated_winners == []
    assert not orchestrator._generated_bible_path.exists()


def test_evolution_orchestrator_runs_neuroevolution_when_ppo_trainer_bound(monkeypatch, tmp_path: Path) -> None:
    import lumina_core.evolution.evolution_orchestrator as eo

    monkeypatch.setattr(eo.EvolutionOrchestrator, "_instance", None)
    monkeypatch.setattr(eo, "ABExperimentFramework", _ABFrameworkStub)

    orchestrator = EvolutionOrchestrator()
    orchestrator._shadow_state_path = tmp_path / "shadow_neuro.json"
    orchestrator._neuro_weights_path = tmp_path / "neuro_weights"
    registry = _RegistryStub()
    orchestrator._registry = cast(Any, registry)
    orchestrator._sim_runner = cast(Any, _SimRunnerStub())
    orchestrator.bind_ppo_trainer(_PPOTrainerStub())

    summary = orchestrator.run_nightly_evolution_cycle(
        generations=1,
        sim_duration_hours=24,
        nightly_report={"net_pnl": 100.0, "max_drawdown": 50.0, "sharpe": 1.2},
        mode="sim",
    )

    assert summary["status"] == "complete"
    generation = summary["generations"][0]
    assert int(generation.get("neuro_tested", 0) or 0) >= 5
    assert int(generation.get("neuro_winners", 0) or 0) in {0, 1}
    zip_files = list((tmp_path / "neuro_weights").glob("*.zip"))
    assert zip_files


def test_evolution_orchestrator_forwards_resolved_parallel_realities_to_sim(monkeypatch, tmp_path: Path) -> None:
    """Fase 1: ``LUMINA_PARALLEL_REALITIES`` → ``_run_single_generation`` → ``evaluate_variants(..., parallel_realities=…)``."""
    from lumina_core.evolution.parallel_reality_config import ENV_PARALLEL_REALITIES
    import lumina_core.evolution.evolution_orchestrator as eo

    monkeypatch.setattr(eo.EvolutionOrchestrator, "_instance", None)
    monkeypatch.setattr(eo, "ABExperimentFramework", _ABFrameworkStub)
    monkeypatch.setenv(ENV_PARALLEL_REALITIES, "14")

    orchestrator = EvolutionOrchestrator()
    orchestrator._shadow_state_path = tmp_path / "shadow_parallel.json"
    registry = _RegistryStub()
    orchestrator._registry = cast(Any, registry)
    cap = _SimRunnerParallelCapture()
    orchestrator._sim_runner = cast(Any, cap)

    try:
        summary = orchestrator.run_nightly_evolution_cycle(
            generations=1,
            sim_duration_hours=24,
            nightly_report={"net_pnl": 100.0, "max_drawdown": 50.0, "sharpe": 1.2},
            mode="sim",
        )
        assert summary["status"] == "complete"
        assert cap.last_parallel == 14
    finally:
        monkeypatch.delenv(ENV_PARALLEL_REALITIES, raising=False)
        os.environ.pop(ENV_PARALLEL_REALITIES, None)


@pytest.mark.safety_gate
def test_real_radical_mutation_requires_explicit_human_approval(monkeypatch, tmp_path: Path) -> None:
    """Safety gate: REAL radical winner cannot be promoted without human approval."""
    import lumina_core.evolution.evolution_orchestrator as eo

    monkeypatch.setattr(eo.EvolutionOrchestrator, "_instance", None)
    monkeypatch.setattr(eo, "ABExperimentFramework", _ABFrameworkStub)
    monkeypatch.setattr(
        eo.EvolutionGuard,
        "resolve_shadow_days",
        lambda self, minimum_days=3, maximum_days=7: 1,
    )

    orchestrator = EvolutionOrchestrator()
    orchestrator._shadow_state_path = tmp_path / "shadow_human_gate.json"
    orchestrator._metrics_path = tmp_path / "evolution_metrics.jsonl"

    registry = _RegistryStub()
    orchestrator._registry = cast(Any, registry)
    orchestrator._sim_runner = cast(Any, _SimRunnerStub())
    orchestrator._approval_twin = cast(Any, _TwinStub(recommendation=True))
    orchestrator._promotion_gate = cast(Any, _PromotionGatePassStub())

    fixed_candidate = PolicyDNA.create(
        prompt_id="rollout-human-gate",
        version="candidate",
        content={"name": "fixed"},
        fitness_score=42.0,
        generation=1,
        lineage_hash="L1",
    )

    def _fixed_candidates(*, top_dna, active_dna, generation_offset, dream_report=None, evolution_mode="sim", **kw):
        del top_dna, active_dna, generation_offset, dream_report, evolution_mode, kw
        return [fixed_candidate]

    orchestrator._generate_candidates = cast(Any, _fixed_candidates)

    summary = orchestrator.run_nightly_evolution_cycle(
        generations=2,
        sim_duration_hours=24,
        nightly_report={"net_pnl": 150.0, "max_drawdown": 40.0, "sharpe": 1.5},
        mode="real",
        explicit_human_approval=False,
    )

    assert summary["status"] == "complete"
    assert int(summary["promotions"]) == 0
    active = registry.get_latest_dna("active")
    assert active is not None
    assert int(active.generation) == 0

    lines = [
        json.loads(line) for line in orchestrator._metrics_path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    generations = [row for row in lines if row.get("event") == "generation_completed"]
    assert generations
    assert any(
        bool(row.get("rollout_human_approval_required"))
        and not bool(row.get("rollout_human_approval_granted"))
        and str(row.get("rollout_stage", "")) == "pending_human_approval"
        and str(row.get("shadow_status", "")) in {"passed", "promoted", "pending"}
        for row in generations
    )


@pytest.mark.safety_gate
def test_real_radical_mutation_promotes_with_explicit_human_approval(monkeypatch, tmp_path: Path) -> None:
    """Safety gate: REAL radical winner may promote only after explicit human approval."""
    import lumina_core.evolution.evolution_orchestrator as eo

    monkeypatch.setattr(eo.EvolutionOrchestrator, "_instance", None)
    monkeypatch.setattr(eo, "ABExperimentFramework", _ABFrameworkStub)
    monkeypatch.setattr(
        eo.EvolutionGuard,
        "resolve_shadow_days",
        lambda self, minimum_days=3, maximum_days=7: 1,
    )

    orchestrator = EvolutionOrchestrator()
    orchestrator._shadow_state_path = tmp_path / "shadow_human_gate_positive.json"
    orchestrator._metrics_path = tmp_path / "evolution_metrics_positive.jsonl"

    registry = _RegistryStub()
    orchestrator._registry = cast(Any, registry)
    orchestrator._sim_runner = cast(Any, _SimRunnerStub())
    orchestrator._approval_twin = cast(Any, _TwinStub(recommendation=True))
    orchestrator._promotion_gate = cast(Any, _PromotionGatePassStub())
    orchestrator._approval_chain = cast(Any, _ApprovalChainStub(approved=True))

    fixed_candidate = PolicyDNA.create(
        prompt_id="rollout-human-gate-positive",
        version="candidate",
        content={"name": "fixed"},
        fitness_score=42.0,
        generation=1,
        lineage_hash="L1",
    )

    def _fixed_candidates(*, top_dna, active_dna, generation_offset, dream_report=None, evolution_mode="sim", **kw):
        del top_dna, active_dna, generation_offset, dream_report, evolution_mode, kw
        return [fixed_candidate]

    orchestrator._generate_candidates = cast(Any, _fixed_candidates)

    summary = orchestrator.run_nightly_evolution_cycle(
        generations=2,
        sim_duration_hours=24,
        nightly_report={"net_pnl": 150.0, "max_drawdown": 40.0, "sharpe": 1.5},
        mode="real",
        explicit_human_approval=True,
    )

    assert summary["status"] == "complete"
    assert int(summary["promotions"]) >= 1
    active = registry.get_latest_dna("active")
    assert active is not None
    assert int(active.generation) >= 1

    lines = [
        json.loads(line) for line in orchestrator._metrics_path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    generations = [row for row in lines if row.get("event") == "generation_completed"]
    assert generations
    assert any(
        bool(row.get("rollout_human_approval_required"))
        and bool(row.get("rollout_human_approval_granted"))
        and str(row.get("rollout_stage", "")) in {"ready_for_promotion"}
        and bool(row.get("promoted"))
        for row in generations
    )


@pytest.mark.safety_gate
def test_real_promotion_is_blocked_without_valid_approval_signatures(monkeypatch, tmp_path: Path) -> None:
    """Safety gate: REAL promotion remains blocked when signatures are missing."""
    import lumina_core.evolution.evolution_orchestrator as eo

    monkeypatch.setattr(eo.EvolutionOrchestrator, "_instance", None)
    monkeypatch.setattr(eo, "ABExperimentFramework", _ABFrameworkStub)
    monkeypatch.setattr(
        eo.EvolutionGuard,
        "resolve_shadow_days",
        lambda self, minimum_days=3, maximum_days=7: 1,
    )

    orchestrator = EvolutionOrchestrator()
    orchestrator._shadow_state_path = tmp_path / "shadow_missing_signatures.json"
    orchestrator._metrics_path = tmp_path / "evolution_metrics_missing_signatures.jsonl"

    registry = _RegistryStub()
    orchestrator._registry = cast(Any, registry)
    orchestrator._sim_runner = cast(Any, _SimRunnerStub())
    orchestrator._approval_twin = cast(Any, _TwinStub(recommendation=True))
    orchestrator._promotion_gate = cast(Any, _PromotionGatePassStub())

    fixed_candidate = PolicyDNA.create(
        prompt_id="approval-chain-missing-signatures",
        version="candidate",
        content={"name": "fixed"},
        fitness_score=42.0,
        generation=1,
        lineage_hash="L1",
    )

    def _fixed_candidates(*, top_dna, active_dna, generation_offset, dream_report=None, evolution_mode="sim", **kw):
        del top_dna, active_dna, generation_offset, dream_report, evolution_mode, kw
        return [fixed_candidate]

    orchestrator._generate_candidates = cast(Any, _fixed_candidates)

    governance_private_key = Ed25519PrivateKey.generate()
    policy = ApprovalPolicy(
        threshold=1,
        signer_public_keys_ed25519=(_public_hex(governance_private_key),),
    )
    approval_chain = ApprovalChain(audit_path=tmp_path / "approval_chain_audit.jsonl")
    monkeypatch.setattr(approval_chain, "load_policy", lambda: policy)
    orchestrator._approval_chain = cast(Any, approval_chain)

    summary = orchestrator.run_nightly_evolution_cycle(
        generations=2,
        sim_duration_hours=24,
        nightly_report={"net_pnl": 150.0, "max_drawdown": 40.0, "sharpe": 1.5},
        mode="real",
        explicit_human_approval=True,
        require_human_approval=True,
        real_promotion_approvals=[],
    )

    assert summary["status"] == "complete"
    assert int(summary["promotions"]) == 0
    active = registry.get_latest_dna("active")
    assert active is not None
    assert int(active.generation) == 0

    lines = [
        json.loads(line) for line in orchestrator._metrics_path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    generations = [row for row in lines if row.get("event") == "generation_completed"]
    assert generations
    assert any(
        not bool(row.get("approval_chain_passed"))
        and str(row.get("approval_chain_reason", "")) == "threshold_not_met"
        and not bool(row.get("promoted"))
        for row in generations
    )
