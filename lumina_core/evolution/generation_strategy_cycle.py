"""Generated-strategy cycle for EvolutionOrchestrator."""
from __future__ import annotations

import logging
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from lumina_core.config_loader import ConfigLoader
from lumina_core.engine.errors import ErrorSeverity, LuminaError
from lumina_core.governance import SignedApproval
from lumina_core.state.state_manager import safe_append_jsonl

from .bot_stress_choices import resolve_neuro_ohlc_stress_rollouts
from .community_knowledge import run_community_knowledge_nightly
from .dna_registry import PolicyDNA
from .dream_engine import (
    dream_engine_config,
    enrich_metrics_with_birth_prior,
    run_dream_batch,
)
from .fitness_evaluator import (
    dream_engine_commit_hints_enabled as _dream_engine_commit_hints_to_bible,
    seed_from_hash as _seed_from_hash,
    utc_file_stamp as _utc_file_stamp,
    utcnow as _utcnow,
)
from .meta_swarm import SwarmConsensus, meta_swarm_governance_enabled, parallel_realities_from_config
from .multi_day_sim_runner import SimResult
from .mutation_pipeline import MutationPipeline
from .neuroevolution import evaluate_weight_population
from .reality_generator import aggregate_ppo_eval_worst_reality, stress_simulator_ohlc
from .simulator_data_support import resolve_neuro_simulator_rows_for_neuro_cycle
from .generation_types import GenerationResult

logger = logging.getLogger(__name__)

class OrchestratorStrategyCycleMixin:
    """LLM/sandbox generated strategy cycle + bible append."""

    def _run_generated_strategy_cycle(
        self,
        *,
        generation_offset: int,
        mode: str,
        base_metrics: dict[str, Any],
        baseline_fitness: float,
        anchor_dna: PolicyDNA,
    ) -> dict[str, Any]:
        if not hasattr(self._sim_runner, "_test_generated_strategy"):
            return {"ideas": 0, "tested": 0, "winners": 0}

        cfg = ConfigLoader.section("evolution", "generated_strategies", default={})
        cfg = cfg if isinstance(cfg, dict) else {}
        min_ideas = max(3, int(cfg.get("min_ideas", 3) or 3))
        max_ideas = max(min_ideas, int(cfg.get("max_ideas", 5) or 5))
        idea_count = random.randint(min_ideas, max_ideas)
        min_backtest_fitness = float(cfg.get("min_backtest_fitness", 0.25) or 0.25)
        min_improvement = float(cfg.get("min_improvement", 0.10) or 0.10)

        generated: list[dict[str, Any]] = []
        for index in range(idea_count):
            hypothesis = self._build_generated_hypothesis(index=index, generation_offset=generation_offset)
            try:
                code = self._strategy_generator.generate_new_strategy(hypothesis)
                sandbox = self._strategy_generator.compile_and_validate(code)
            except Exception:
                logging.exception(
                    "Unhandled broad exception fallback in lumina_core/evolution/orchestrator_core.py:1060"
                )
                continue
            generated.append(
                {
                    "hypothesis": hypothesis,
                    "code": sandbox.code,
                    "metadata": dict(sandbox.metadata),
                }
            )

        if not generated:
            return {"ideas": idea_count, "tested": 0, "winners": 0}

        test_fn = getattr(self._sim_runner, "_test_generated_strategy")
        use_real_data = bool(getattr(self._sim_runner, "real_market_data", False))
        use_backtest_mode = bool(getattr(self._sim_runner, "true_backtest_mode", False))
        evaluated: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=min(5, len(generated))) as pool:
            future_map = {pool.submit(test_fn, item["code"]): item for item in generated}
            for future in as_completed(future_map):
                item = future_map[future]
                try:
                    fitness = float(future.result())
                except Exception:
                    logging.exception(
                        "Unhandled broad exception fallback in lumina_core/evolution/orchestrator_core.py:1083"
                    )
                    fitness = float("-inf")
                evaluated.append({**item, "fitness": fitness})

        winners: list[dict[str, Any]] = []
        for item in evaluated:
            metadata = dict(item.get("metadata", {}) or {})
            confidence = float(metadata.get("confidence", 0.0) or 0.0)
            fitness = float(item.get("fitness", float("-inf")) or float("-inf"))
            payload = {
                "strategy_type": "generated",
                "hypothesis": str(item.get("hypothesis", "") or ""),
                "generated_code": str(item.get("code", "") or ""),
                "name": str(metadata.get("name", "generated_strategy") or "generated_strategy"),
                "regime_focus": str(metadata.get("regime_focus", "neutral") or "neutral"),
                "signal_bias": str(metadata.get("signal_bias", "neutral") or "neutral"),
                "confidence": confidence,
            }
            generated_dna = self._registry.mutate(
                parent=anchor_dna,
                mutation_rate=1.0,
                content=payload,
                fitness_score=fitness,
                version="generated_winner",
                lineage_hash=anchor_dna.lineage_hash,
            )

            # === Phase 2 Deliverable 5 (Aperture Hardening) — LLM-generated strategy winners ===
            # Best-effort risk shadow validation for proposals created via the LLM strategy
            # generator path. Uses the official bridge exactly like all prior D5 sites
            # (meta, dream nudges, mutation pipeline, etc.). Never breaks the cycle.
            try:
                from lumina_core.evolution.risk_shadow_bridge import validate_risk_proposal_in_shadow
                from pathlib import Path as _Path

                validate_risk_proposal_in_shadow(
                    proposal={
                        "experiment_id": f"risk-generated-strategy-{generated_dna.hash[:12]}",
                        "dna_hash": generated_dna.hash,
                        "signal": "PROPOSAL",
                        "confluence_score": float(payload.get("confidence", 0.5)),
                        "proposed_risk": 1.0,  # generated strategies currently carry behavior via code; risk hyperparams handled in other layers
                        "generated_strategy": True,
                        "hypothesis": str(payload.get("hypothesis", ""))[:200],
                        "name": str(payload.get("name", "generated_strategy")),
                        "regime_focus": str(payload.get("regime_focus", "neutral")),
                    },
                    engine=None,
                    storage_path=_Path("state/risk_shadow_evolution.jsonl"),
                    auto_record_promotion=True,
                )
            except Exception:
                # Best-effort: shadow validation must never break generated strategy creation.
                pass
            # ================================================================================

            try:
                shadow_results = self._sim_runner.evaluate_variants(
                    [generated_dna],
                    days=1,
                    nightly_report=base_metrics,
                    shadow_mode=True,
                    real_market_data=use_real_data,
                    true_backtest_mode=use_backtest_mode,
                    parallel_realities=1,
                )
            except TypeError:
                shadow_results = self._sim_runner.evaluate_variants(
                    [generated_dna],
                    days=1,
                    nightly_report=base_metrics,
                    shadow_mode=True,
                    real_market_data=use_real_data,
                    true_backtest_mode=use_backtest_mode,
                )
            shadow_total_pnl = float(shadow_results[0].avg_pnl) if shadow_results else 0.0

            twin_recommendation = True
            twin_risk_flags: list[str] = []
            if str(mode).strip().lower() == "real":
                twin_result = self._approval_twin.evaluate_dna_promotion(generated_dna)
                twin_recommendation = bool(twin_result.get("recommendation", False))
                twin_risk_flags = [str(flag) for flag in list(twin_result.get("risk_flags", []) or [])]
                # Explicit fail-closed: constitution always wins over twin (defense against tricked twin)
                try:
                    if not self._constitutional_guard.veto_unless_constitutional(
                        dna_content=getattr(generated_dna, "content", generated_dna),
                        mode=mode,
                        current_recommendation=twin_recommendation,
                    ):
                        twin_recommendation = False
                        twin_risk_flags.append("constitution_veto_on_generated")
                except Exception:
                    twin_recommendation = False

            if not self._guard.generated_strategy_survives(
                mode=mode,
                candidate_confidence=confidence,
                candidate_fitness=fitness,
                current_fitness=baseline_fitness,
                shadow_total_pnl=shadow_total_pnl,
                shadow_risk_flags=twin_risk_flags,
                approval_twin_recommendation=twin_recommendation,
                min_backtest_fitness=min_backtest_fitness,
                min_improvement=min_improvement,
            ):
                continue

            self._registry.register_dna(generated_dna)
            self._append_generated_bible_entry(
                dna=generated_dna,
                hypothesis=payload["hypothesis"],
                code=payload["generated_code"],
                fitness=fitness,
            )
            winners.append({"hash": generated_dna.hash, "fitness": fitness})

        self._append_metrics(
            {
                "event": "generated_strategy_cycle",
                "timestamp": _utcnow(),
                "generation": generation_offset,
                "ideas": idea_count,
                "tested": len(evaluated),
                "winners": len(winners),
                "winner_hashes": [str(item.get("hash", "")) for item in winners],
            }
        )

        return {"ideas": idea_count, "tested": len(evaluated), "winners": len(winners)}

    @staticmethod
    def _build_generated_hypothesis(*, index: int, generation_offset: int) -> str:
        templates = [
            "Design a trend-regime detector with volatility confluence and strict drawdown protection.",
            "Create a mean-reversion entry model with adaptive cooldown in high volatility.",
            "Build a liquidity-aware breakout filter combining volume pulse and momentum fade protection.",
            "Generate an entry-exit logic that avoids chop via regime gating and confidence thresholding.",
            "Invent a confluence rule that combines trend strength, volatility state, and risk-off override.",
        ]
        template = templates[index % len(templates)]
        return f"gen={generation_offset};idea={index};{template}"

    def _append_generated_bible_entry(
        self,
        *,
        dna: PolicyDNA,
        hypothesis: str,
        code: str,
        fitness: float,
    ) -> None:
        self._lumina_bible.append_generated_rule(
            dna_hash=str(dna.hash),
            lineage_hash=str(dna.lineage_hash),
            generation=int(dna.generation),
            fitness=float(fitness),
            hypothesis=str(hypothesis),
            code=str(code),
            status="winner",
        )

