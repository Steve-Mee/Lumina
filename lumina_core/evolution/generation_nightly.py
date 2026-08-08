"""Nightly evolution cycle + generation helpers."""
from __future__ import annotations

import logging
from typing import Any, Sequence

from lumina_core.config_loader import ConfigLoader
from lumina_core.engine.errors import ErrorSeverity, LuminaError
from lumina_core.governance import SignedApproval
from lumina_core.state.state_manager import safe_append_jsonl

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
    utcnow as _utcnow,
)
from .meta_swarm import SwarmConsensus, meta_swarm_governance_enabled, parallel_realities_from_config
from .multi_day_sim_runner import SimResult
from .mutation_pipeline import MutationPipeline
from .generation_types import GenerationResult

logger = logging.getLogger(__name__)

class OrchestratorNightlyMixin:
    """Nightly cycle orchestration, candidates, summary, metrics."""

    def _run_meta_swarm_deliberation(
        self,
        *,
        winner_dna: PolicyDNA,
        winner_fitness: float,
        previous_fitness: float,
        base_metrics: dict[str, Any],
        mode: str,
        generation_offset: int,
        parallel_realities: int,
        sim_days: int,
        neuro_summary: dict[str, Any],
    ) -> SwarmConsensus:
        if not meta_swarm_governance_enabled():
            return SwarmConsensus(True, 0.9, False)
        br = dict(base_metrics or {})
        de = br.get("dream_engine") if isinstance(br.get("dream_engine"), dict) else None
        ctx: dict[str, Any] = {
            "winner_fitness": float(winner_fitness),
            "previous_fitness": float(previous_fitness),
            "nightly_report": dict(base_metrics),
            "mode": str(mode),
            "sim_days": max(1, int(sim_days)),
            "parallel_realities": max(1, int(parallel_realities)),
            "generation": int(generation_offset),
            "neuro_winner_accepted": bool(neuro_summary.get("winner_accepted", False)),
            "winner_prompt_id": str(getattr(winner_dna, "prompt_id", "") or ""),
        }
        if de:
            ctx["dream_engine"] = dict(de)
        return self._meta_swarm.deliberate(ctx)

    def _run_dream_engine_batch(
        self,
        *,
        base_metrics: dict[str, Any],
        sim_days: int,
        generation_offset: int,
    ) -> dict[str, Any]:
        enabled, count, horizon_cfg, ddr = dream_engine_config()
        if not enabled:
            return {
                "enabled": False,
                "dream_count": 0,
                "breach_count": 0,
                "breach_rate": 0.0,
                "worst_dd_ratio": 0.0,
                "median_terminal_equity_delta": 0.0,
                "rule_hints": [],
            }
        horizon = max(1, min(int(horizon_cfg), int(sim_days)))
        seed = _seed_from_hash(f"dream:{generation_offset}")
        metrics_with_prior = enrich_metrics_with_birth_prior(base_metrics)
        report = run_dream_batch(
            metrics_with_prior,
            dream_count=count,
            horizon_days=horizon,
            seed=seed,
            drawdown_limit_ratio=ddr,
        )
        if report.rule_hints and _dream_engine_commit_hints_to_bible():
            br = float(report.breach_rate)
            for raw_hint in report.rule_hints:
                try:
                    self._lumina_bible.append_dream_rule_hint(
                        hint=str(raw_hint),
                        generation=int(generation_offset),
                        breach_rate=br,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("[DREAM_ENGINE] could not append rule hint to bible: %s", exc)
        payload = {
            "enabled": True,
            "dream_count": report.dream_count,
            "breach_count": report.breach_count,
            "breach_rate": round(float(report.breach_rate), 6),
            "worst_dd_ratio": round(float(report.worst_dd_ratio), 6),
            "median_terminal_equity_delta": round(float(report.median_terminal_equity_delta), 6),
            "rule_hints": list(report.rule_hints),
        }
        self._append_metrics(
            {
                "event": "dream_engine_batch",
                "timestamp": _utcnow(),
                "generation": generation_offset,
                **payload,
            }
        )
        return payload

    def _run_community_knowledge_cycle(
        self,
        *,
        base_metrics: dict[str, Any],
        active_dna: PolicyDNA | None,
        generation_offset: int,
    ) -> dict[str, Any]:
        summary = run_community_knowledge_nightly(
            bible=self._lumina_bible,
            sim_runner=self._sim_runner,
            approval_twin=self._approval_twin,
            guard=self._guard,
            active_dna=active_dna,
            base_metrics=base_metrics,
            generation_offset=generation_offset,
            vector_collection=getattr(self, "_vector_collection", None),
        )
        if summary.get("enabled") and int(summary.get("examined", 0) or 0) + int(summary.get("committed", 0) or 0) > 0:
            self._append_metrics(
                {
                    "event": "community_knowledge_cycle",
                    "timestamp": _utcnow(),
                    "generation": generation_offset,
                    **summary,
                }
            )
        return summary

    def run_nightly_evolution_cycle(
        self,
        *,
        generations: int = 3,
        sim_duration_hours: int = 24,
        nightly_report: dict[str, Any] | None = None,
        explicit_human_approval: bool = False,
        require_human_approval: bool | None = None,
        real_promotion_approvals: Sequence[SignedApproval] | None = None,
        blackboard: Any | None = None,
        mode: str = "sim",
    ) -> dict[str, Any]:
        """Run ``generations`` rounds of mutation/selection and return summary."""
        if not isinstance(nightly_report, dict):
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="EVOLUTION_REPORT_REQUIRED",
                message="run_nightly_evolution_cycle requires nightly_report: dict[str, Any].",
            )
        normalized_mode = str(mode or "sim").strip().lower()
        if normalized_mode in {"paper", "sim"} and not self._guard.can_mutate(mode=normalized_mode):
            return {
                "status": "blocked",
                "reason": f"mutations_not_allowed_in_mode:{mode}",
                "timestamp": _utcnow(),
            }
        require_human_approval_effective = (
            bool(require_human_approval) if require_human_approval is not None else normalized_mode == "real"
        )
        report: dict[str, Any] = dict(nightly_report)
        gen_results: list[GenerationResult] = []
        self._append_metrics(
            {
                "event": "evolution_cycle_started",
                "timestamp": _utcnow(),
                "generations": max(1, int(generations)),
                "sim_duration_hours": max(1, int(sim_duration_hours)),
                "mode": str(mode),
                "parallel_realities": int(parallel_realities_from_config()),
                "require_human_approval": bool(require_human_approval_effective),
            }
        )

        all_candidates: list[PolicyDNA] = []
        sim_days = max(1, int(round(max(1, int(sim_duration_hours)) / 24.0)))

        # FASE 2 Meta-RL: override sim_days from multiweek_fitness config when enabled
        evolution_cfg = ConfigLoader.section("evolution", default={}) or {}
        mw_cfg = evolution_cfg.get("multiweek_fitness", {}) if isinstance(evolution_cfg, dict) else {}
        if isinstance(mw_cfg, dict) and mw_cfg.get("enabled"):
            sim_days = max(sim_days, int(mw_cfg.get("days", 14) or 14))
            logger.info("[META-RL] multiweek_fitness enabled – sim_days=%d", sim_days)

        for gen_idx in range(max(1, int(generations))):
            result = self._run_single_generation(
                generation_offset=gen_idx,
                base_metrics=report,
                sim_days=sim_days,
                mode=normalized_mode,
                explicit_human_approval=bool(explicit_human_approval),
                require_human_approval=bool(require_human_approval_effective),
                real_promotion_approvals=real_promotion_approvals,
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

    def _bootstrap_active_dna(self, *, base_metrics: dict[str, Any]) -> PolicyDNA:
        from lumina_core.evolution.birth_gen0_bootstrap import bootstrap_active_dna

        return bootstrap_active_dna(self, base_metrics=base_metrics)

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
        dream_report: dict[str, Any] | None = None,
        evolution_mode: str = "sim",
    ) -> list[PolicyDNA]:
        self._mutation_pipeline = MutationPipeline(
            registry=self._registry,
            constitutional_guard=self._constitutional_guard,
            logger=logger,
        )
        return self._mutation_pipeline.generate_candidates(
            top_dna=top_dna,
            active_dna=active_dna,
            generation_offset=generation_offset,
            dream_report=dream_report,
            evolution_mode=evolution_mode,
        )

    def _build_summary(
        self,
        gen_results: list[GenerationResult],
        promoted_dna: list[PolicyDNA],
    ) -> dict[str, Any]:
        total_candidates = sum(r.candidate_count for r in gen_results)
        promotions = sum(1 for r in gen_results if r.promoted)
        if not gen_results:
            raise LuminaError(
                severity=ErrorSeverity.FATAL_UNRECOVERABLE,
                code="EVOLUTION_RESULTS_EMPTY",
                message="No generation results available to build summary.",
            )
        best_fitness = max(r.winner_fitness for r in gen_results)
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
                    "generated_tested": int(r.generated_tested),
                    "generated_winners": int(r.generated_winners),
                    "neuro_tested": int(r.neuro_tested),
                    "neuro_winners": int(r.neuro_winners),
                    "timestamp": r.timestamp,
                }
                for r in gen_results
            ],
        }

    def _append_metrics(self, summary: dict[str, Any]) -> None:
        safe_append_jsonl(self._metrics_path, summary, hash_chain=False)

    def _publish_to_blackboard(self, blackboard: Any, summary: dict[str, Any]) -> None:
        if not hasattr(blackboard, "publish_sync"):
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="EVOLUTION_BLACKBOARD_PUBLISH_UNAVAILABLE",
                message="Blackboard does not expose publish_sync for evolution result publishing.",
            )
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


