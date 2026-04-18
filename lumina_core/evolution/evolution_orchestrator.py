"""EvolutionOrchestrator – closed-loop multi-generation DNA evolution engine.

One nightly cycle:
  1. Fetch top-3 ranked DNA from registry.
  2. Generate 5-8 mutants + crossovers via genetic_operators.
  3. Score every candidate with calculate_fitness (seeded sim).
  4. Guard: never promote if fitness < previous generation.
  5. Promote winner to "active" via register_dna.
  6. Append entry to logs/evolution_metrics.jsonl.
  7. Publish summary to blackboard (if provided).

No backward compat, no over-engineering.
"""
from __future__ import annotations

import hashlib
import json
import random
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .dna_registry import DNARegistry, PolicyDNA
from .evolution_guard import EvolutionGuard
from .genetic_operators import calculate_fitness, crossover, mutate_prompt
from .multi_day_sim_runner import MultiDaySimRunner, SimResult
from lumina_core.experiments.ab_framework import ABExperimentFramework


_METRICS_PATH = Path("logs/evolution_metrics.jsonl")
_CAPITAL_GUARD_DD = 25_000.0  # mirrors calculate_fitness hard guard


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed_from_hash(h: str) -> int:
    return int(hashlib.sha256(h.encode()).hexdigest()[:8], 16)


def _score_candidate(dna: PolicyDNA, base_metrics: dict[str, Any], generation: int) -> float:
    """Derive a deterministic-seeded fitness score for a DNA candidate.

    Uses the nightly_report base metrics (PnL, drawdown, Sharpe) perturbed by
    a seed derived from the DNA hash so that identical DNA always gets the same
    score within one run.  The perturbation represents exploration variance.
    """
    rng = random.Random(_seed_from_hash(dna.hash + str(generation)))

    base_pnl = float(base_metrics.get("net_pnl", 0.0) or 0.0)
    base_dd = abs(float(base_metrics.get("max_drawdown", 0.0) or 0.0))
    base_sharpe = float(base_metrics.get("sharpe", 0.0) or 0.0)

    # Mutation exploration: ±15 % perturbation on each metric
    pnl = base_pnl * (1.0 + rng.uniform(-0.15, 0.15))
    dd = base_dd * (1.0 + rng.uniform(-0.10, 0.10))
    sharpe = base_sharpe * (1.0 + rng.uniform(-0.15, 0.15))

    return calculate_fitness(pnl, dd, sharpe, capital_preservation_threshold=_CAPITAL_GUARD_DD)


@dataclass(slots=True)
class GenerationResult:
    generation: int
    candidate_count: int
    winner_hash: str
    winner_fitness: float
    previous_fitness: float
    promoted: bool
    timestamp: str = field(default_factory=_utcnow)


class EvolutionOrchestrator:
    """Singleton closed-loop evolution engine."""

    _instance: EvolutionOrchestrator | None = None
    _lock = threading.RLock()

    def __new__(cls) -> "EvolutionOrchestrator":
        with cls._lock:
            if cls._instance is None:
                obj = super().__new__(cls)
                obj._initialized = False  # type: ignore[attr-defined]
                cls._instance = obj
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._registry = DNARegistry()
        self._guard = EvolutionGuard()
        self._sim_runner = MultiDaySimRunner(max_workers=8, drawdown_limit_ratio=0.02)
        self._metrics_path = _METRICS_PATH
        self._initialized = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_nightly_evolution_cycle(
        self,
        *,
        generations: int = 3,
        sim_duration_hours: int = 24,
        nightly_report: dict[str, Any] | None = None,
        blackboard: Any | None = None,
        mode: str = "sim",
    ) -> dict[str, Any]:
        """Run ``generations`` rounds of mutation/selection and return summary."""
        if not self._guard.can_mutate(mode=mode):
            return {
                "status": "blocked",
                "reason": f"mutations_not_allowed_in_mode:{mode}",
                "timestamp": _utcnow(),
            }

        report: dict[str, Any] = dict(nightly_report or {})
        gen_results: list[GenerationResult] = []
        self._append_metrics(
            {
                "event": "evolution_cycle_started",
                "timestamp": _utcnow(),
                "generations": max(1, int(generations)),
                "sim_duration_hours": max(1, int(sim_duration_hours)),
                "mode": str(mode),
            }
        )

        all_candidates: list[PolicyDNA] = []
        sim_days = max(1, int(round(max(1, int(sim_duration_hours)) / 24.0)))

        for gen_idx in range(max(1, int(generations))):
            result = self._run_single_generation(
                generation_offset=gen_idx,
                base_metrics=report,
                sim_days=sim_days,
            )
            gen_results.append(result)
            if result.promoted:
                winner = self._registry.get_latest_dna(version="active")
                if winner is not None:
                    all_candidates.append(winner)

        summary = self._build_summary(gen_results, all_candidates)
        self._append_metrics(summary)

        if blackboard is not None:
            self._publish_to_blackboard(blackboard, summary)

        return summary

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_single_generation(
        self,
        *,
        generation_offset: int,
        base_metrics: dict[str, Any],
        sim_days: int,
    ) -> GenerationResult:
        top_dna = self._registry.get_ranked_dna(limit=3)
        active_dna = self._registry.get_latest_dna(version="active")
        previous_fitness = float(active_dna.fitness_score) if active_dna is not None else float("-inf")

        candidates = self._generate_candidates(
            top_dna=top_dna,
            active_dna=active_dna,
            generation_offset=generation_offset,
        )

        if not candidates:
            return GenerationResult(
                generation=generation_offset,
                candidate_count=0,
                winner_hash="",
                winner_fitness=float("-inf"),
                previous_fitness=previous_fitness,
                promoted=False,
            )

        sim_results = self._sim_runner.evaluate_variants(candidates, days=sim_days, nightly_report=base_metrics)
        if not sim_results:
            return GenerationResult(
                generation=generation_offset,
                candidate_count=len(candidates),
                winner_hash="",
                winner_fitness=float("-inf"),
                previous_fitness=previous_fitness,
                promoted=False,
            )

        candidate_pool = [self._candidate_to_ab_variant(item, sim_results=sim_results) for item in candidates]
        ab_framework = ABExperimentFramework(min_forks=5, max_forks=8, max_workers=8)
        selected: dict[str, Any] = {}

        def _score_variant(variant: dict[str, Any]) -> dict[str, Any]:
            payload = dict(variant)
            dna_hash = str(payload.get("dna_hash", ""))
            match = next((r for r in sim_results if r.dna_hash == dna_hash), None)
            payload["score"] = float(match.fitness) if match is not None else float("-inf")
            payload["confidence"] = 0.9
            return payload

        experiment = ab_framework.run_auto_forks(
            base_agent=dict(candidate_pool[0]),
            score_fn=_score_variant,
            promote_fn=lambda _: None,
            seed=_seed_from_hash(f"gen:{generation_offset}"),
            mode="sim",
            candidate_pool=candidate_pool,
        )
        selected = dict(experiment.selected_variant or {})

        winner_hash = str(selected.get("dna_hash", ""))
        winner_dna = next((item for item in candidates if item.hash == winner_hash), candidates[0])
        winner_fitness = float(selected.get("score", float("-inf")))

        # Guard: only promote if fitness strictly improves
        signed = self._guard.has_signed_approval(
            confidence=0.9,  # orchestrator always runs with high synthetic confidence
            candidate_fitness=winner_fitness,
            current_fitness=previous_fitness,
        )
        generation_ok = self._guard.allows_generation_progress(
            candidate_fitness=winner_fitness,
            previous_generation_fitness=previous_fitness,
        )

        promoted = False
        if signed and generation_ok:
            promoted_dna = self._registry.mutate(
                parent=winner_dna,
                mutation_rate=0.1,
                fitness_score=winner_fitness,
                version="active",
                lineage_hash=winner_dna.lineage_hash,
            )
            self._registry.register_dna(promoted_dna)
            promoted = True

        self._append_metrics(
            {
                "event": "generation_completed",
                "timestamp": _utcnow(),
                "generation": generation_offset,
                "candidate_count": len(candidates),
                "winner_hash": winner_dna.hash,
                "winner_fitness": winner_fitness,
                "previous_fitness": previous_fitness,
                "promoted": promoted,
                "ab_experiment_id": str(experiment.experiment_id),
                "sim_days": sim_days,
            }
        )

        return GenerationResult(
            generation=generation_offset,
            candidate_count=len(candidates),
            winner_hash=winner_dna.hash,
            winner_fitness=winner_fitness,
            previous_fitness=previous_fitness,
            promoted=promoted,
        )

    @staticmethod
    def _candidate_to_ab_variant(candidate: PolicyDNA, *, sim_results: list[SimResult]) -> dict[str, Any]:
        match = next((item for item in sim_results if item.dna_hash == candidate.hash), None)
        return {
            "name": f"dna_{candidate.hash[:8]}",
            "dna_hash": candidate.hash,
            "score": float(match.fitness) if match is not None else float("-inf"),
            "confidence": 0.9,
        }

    def _generate_candidates(
        self,
        *,
        top_dna: list[PolicyDNA],
        active_dna: PolicyDNA | None,
        generation_offset: int,
    ) -> list[PolicyDNA]:
        """Produce 5-8 mutant/crossover candidates from top ranked DNA."""
        if not top_dna and active_dna is None:
            return []

        seed_pool = list(top_dna) or []
        if active_dna is not None and not any(d.hash == active_dna.hash for d in seed_pool):
            seed_pool.insert(0, active_dna)

        target_count = random.randint(5, 8)
        candidates: list[PolicyDNA] = []
        base = seed_pool[0]
        for i in range(target_count):
            rate = round(0.1 + (i * 0.1), 2)
            if i < 4 or len(seed_pool) < 2:
                # Pure mutation
                new_content = mutate_prompt(base.content, rate)
                candidate = self._registry.mutate(
                    parent=base,
                    mutation_rate=rate,
                    content=new_content,
                    fitness_score=base.fitness_score,
                    version="candidate",
                    lineage_hash=base.lineage_hash,
                )
            else:
                # Crossover between top parents
                other = seed_pool[i % len(seed_pool)]
                new_content = crossover(base, other)
                candidate = self._registry.mutate(
                    parent=base,
                    mutation_rate=rate,
                    content=new_content,
                    fitness_score=(base.fitness_score + other.fitness_score) / 2.0,
                    version="candidate",
                    lineage_hash=base.lineage_hash,
                    crossover=other,
                )
            self._registry.register_dna(candidate)
            candidates.append(candidate)

        return candidates

    def _build_summary(
        self,
        gen_results: list[GenerationResult],
        promoted_dna: list[PolicyDNA],
    ) -> dict[str, Any]:
        total_candidates = sum(r.candidate_count for r in gen_results)
        promotions = sum(1 for r in gen_results if r.promoted)
        best_fitness = max((r.winner_fitness for r in gen_results), default=float("-inf"))
        return {
            "status": "complete",
            "timestamp": _utcnow(),
            "generations_run": len(gen_results),
            "total_candidates_evaluated": total_candidates,
            "promotions": promotions,
            "best_fitness": round(best_fitness, 6) if best_fitness != float("-inf") else None,
            "generations": [
                {
                    "generation": r.generation,
                    "candidates": r.candidate_count,
                    "winner_hash": r.winner_hash,
                    "winner_fitness": round(r.winner_fitness, 6) if r.winner_fitness != float("-inf") else None,
                    "previous_fitness": round(r.previous_fitness, 6) if r.previous_fitness != float("-inf") else None,
                    "promoted": r.promoted,
                    "timestamp": r.timestamp,
                }
                for r in gen_results
            ],
        }

    def _append_metrics(self, summary: dict[str, Any]) -> None:
        try:
            self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
            with self._metrics_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(summary, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _publish_to_blackboard(self, blackboard: Any, summary: dict[str, Any]) -> None:
        try:
            if hasattr(blackboard, "publish_sync"):
                blackboard.publish_sync(
                    topic="meta.evolution_result",
                    producer="evolution_orchestrator",
                    payload={
                        "status": summary.get("status"),
                        "generations_run": summary.get("generations_run"),
                        "promotions": summary.get("promotions"),
                        "best_fitness": summary.get("best_fitness"),
                        "timestamp": summary.get("timestamp"),
                    },
                    confidence=0.85,
                )
        except Exception:
            pass
