"""Single-generation evolution cycle runner."""

from __future__ import annotations

import logging
from typing import Any, Sequence, TYPE_CHECKING

from lumina_core.engine.errors import ErrorSeverity, LuminaError
from lumina_core.evolution.birth_gen0_bootstrap import resolve_initial_top_and_active_dna
from lumina_core.evolution.dream_engine import enrich_nightly_report_with_dream
from lumina_core.evolution.fitness_evaluator import (
    resolve_parallel_realities_count as _resolve_parallel_realities_count,
    seed_from_hash as _seed_from_hash,
)
from lumina_core.evolution.multi_day_sim_runner import MultiDaySimRunner
from lumina_core.evolution.orchestrator_core import GenerationResult
from lumina_core.governance import SignedApproval

if TYPE_CHECKING:
    from lumina_core.evolution.orchestrator_core import EvolutionOrchestrator

from lumina_core.evolution.generation_runner_phases import (
    append_generation_completed_metrics,
    apply_constitutional_pre_promotion,
    apply_post_twin_constitutional_veto,
    fail_closed_twin_decision,
    risk_shadow_validate_candidates,
    twin_effective_recommendation,
)

logger = logging.getLogger(__name__)


def _compat() -> Any:
    from lumina_core.evolution import evolution_orchestrator as compat_module

    return compat_module


def run_single_generation(
    orchestrator: "EvolutionOrchestrator",
    *,
    generation_offset: int,
    mode: str,
    explicit_human_approval: bool,
    require_human_approval: bool,
    real_promotion_approvals: Sequence[SignedApproval] | None,
    base_metrics: dict[str, Any],
    sim_days: int,
) -> GenerationResult:
    # Fail-closed twin mode checkpoint: auto-demote on metric breach; optional auto-promote.
    try:
        twin = getattr(orchestrator, "_approval_twin", None)
        if twin is not None and hasattr(twin, "sync_mode_from_controller"):
            twin.sync_mode_from_controller()
    except Exception:
        logger.debug("twin.sync_mode_from_controller failed at generation start", exc_info=True)

    top_dna, active_dna = resolve_initial_top_and_active_dna(
        orchestrator, base_metrics=base_metrics
    )
    previous_fitness = float(active_dna.fitness_score) if active_dna is not None else float("-inf")

    dream_summary = orchestrator._run_dream_engine_batch(
        base_metrics=base_metrics,
        sim_days=sim_days,
        generation_offset=generation_offset,
    )
    generation_metrics = enrich_nightly_report_with_dream(base_metrics, dream_summary)

    community_summary = orchestrator._run_community_knowledge_cycle(
        base_metrics=generation_metrics,
        active_dna=active_dna,
        generation_offset=generation_offset,
    )

    candidates = orchestrator._generate_candidates(
        top_dna=top_dna,
        active_dna=active_dna,
        generation_offset=generation_offset,
        dream_report=dream_summary,
        evolution_mode=mode,
    )
    from lumina_core.evolution.research_lab.cycle import gate_winner, merge_catalog_challengers
    candidates = merge_catalog_challengers(
        orchestrator._registry, candidates, generation_offset=generation_offset, mode=mode
    )
    risk_shadow_validate_candidates(orchestrator, candidates)

    if not candidates:
        raise LuminaError(
            severity=ErrorSeverity.FATAL_UNRECOVERABLE,
            code="EVOLUTION_CANDIDATE_GENERATION_EMPTY",
            message=f"No candidates generated for generation {generation_offset}.",
        )

    parallel_realities = _resolve_parallel_realities_count()

    # FASE 2: Pass real-market and true-backtest flags to evaluate_variants
    use_real_data = bool(getattr(orchestrator._sim_runner, "real_market_data", False))
    use_backtest_mode = bool(getattr(orchestrator._sim_runner, "true_backtest_mode", False))
    try:
        sim_results = orchestrator._sim_runner.evaluate_variants(
            candidates,
            days=sim_days,
            nightly_report=generation_metrics,
            real_market_data=use_real_data,
            true_backtest_mode=use_backtest_mode,
            parallel_realities=parallel_realities,
        )
    except TypeError:
        sim_results = orchestrator._sim_runner.evaluate_variants(
            candidates,
            days=sim_days,
            nightly_report=generation_metrics,
            real_market_data=use_real_data,
        )
    if not sim_results:
        raise LuminaError(
            severity=ErrorSeverity.FATAL_UNRECOVERABLE,
            code="EVOLUTION_SIM_RESULTS_EMPTY",
            message=f"Simulation returned no results for generation {generation_offset}.",
        )

    candidate_pool = [orchestrator._candidate_to_ab_variant(item, sim_results=sim_results) for item in candidates]
    ab_framework = _compat().ABExperimentFramework(min_forks=5, max_forks=8, max_workers=8)
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
    winner_dna, winner_fitness, _cc = gate_winner(
        champion=active_dna, challenger=winner_dna, challenger_fitness=winner_fitness,
        previous_fitness=previous_fitness, sim_results=sim_results, mode=mode,
    )
    twin_decision: dict[str, Any] = {
        "recommendation": True,
        "effective_recommendation": False,  # fail-closed until twin evaluate stamps authority
        "executable": False,
        "mode": "shadow",
        "confidence": 0.9,
        "risk_flags": [],
        "explanation": "sim/paper default (twin primary layer decides)",
    }
    if str(mode).strip().lower() in ("real", "paper"):
        twin_decision = orchestrator._approval_twin.evaluate_dna_promotion(winner_dna)
    else:
        try:
            twin_decision = orchestrator._approval_twin.evaluate_dna_promotion(winner_dna)
        except Exception:
            logger.exception("twin evaluate_dna_promotion failed; fail-closed")
            twin_decision = fail_closed_twin_decision("twin_evaluate_raised")

    shadow_runner: Any = orchestrator._sim_runner
    if not hasattr(shadow_runner, "evaluate_variants"):
        shadow_runner = MultiDaySimRunner(
            max_workers=8, drawdown_limit_ratio=0.02, real_market_data=True, true_backtest_mode=True,
            market_data_service=getattr(orchestrator, "_market_data_service", None),
        )

    twin_confidence = float(twin_decision.get("confidence", 0.0) or 0.0)
    twin_risk_flags = [str(x) for x in list(twin_decision.get("risk_flags", []) or [])]
    signed_confidence = twin_confidence if str(mode).strip().lower() == "real" else 0.9

    # Explicit fail-closed: re-assert twin rec subordination to constitution right after twin consult.
    # The ApprovalTwin output is a signal, never a bypass. This (plus the later pre-promotion guard)
    # ensures even a fully tricked twin cannot promote bad DNA.
    # Mode authority: consumers use effective_recommendation (shadow/assisted cannot sole-auto).
    twin_decision, twin_risk_flags = apply_post_twin_constitutional_veto(
        orchestrator,
        mode=mode,
        winner_dna=winner_dna,
        twin_decision=twin_decision,
    )

    # Guard: REAL uses twin confidence (0–1 or 0–100) for ultra zero-touch floor + shadow.
    # Shadow/assisted modes yield effective_recommendation=False → no zero-touch auto.
    signed = orchestrator._guard.has_signed_approval(
        confidence=signed_confidence,
        candidate_fitness=winner_fitness,
        current_fitness=previous_fitness,
        mode=mode,
        approval_twin_recommendation=twin_effective_recommendation(twin_decision),
        approval_twin=orchestrator._approval_twin,
        dna=winner_dna,
        shadow_runner=shadow_runner,
        twin_risk_flags=twin_risk_flags,
    )
    generation_ok = orchestrator._guard.allows_generation_progress(
        candidate_fitness=winner_fitness,
        previous_generation_fitness=previous_fitness,
    )

    promoted = False
    veto_check: dict[str, Any] = {"is_blocked": False, "reason": "no_veto", "active_veto_records": []}
    veto_blocked = False
    shadow_status = "not_required"
    shadow_passed = False
    shadow_days_completed = 0
    shadow_days_target = 0
    shadow_total_pnl = 0.0
    promotion_gate: dict[str, Any] = {}

    if mode == "real":
        from lumina_core.evolution.generation_runner_promotion import apply_real_mode_shadow_promotion

        _real = apply_real_mode_shadow_promotion(
            orchestrator,
            winner_dna=winner_dna,
            winner_fitness=winner_fitness,
            previous_fitness=previous_fitness,
            twin_confidence=twin_confidence,
            twin_risk_flags=twin_risk_flags,
            generation_metrics=generation_metrics,
            signed=signed,
            generation_ok=generation_ok,
            shadow_runner=shadow_runner,
        )
        promoted = bool(_real.get("promoted", False))
        veto_check = dict(_real.get("veto_check", veto_check) or veto_check)
        veto_blocked = bool(_real.get("veto_blocked", False))
        shadow_status = str(_real.get("shadow_status", shadow_status))
        shadow_passed = bool(_real.get("shadow_passed", False))
        shadow_days_completed = int(_real.get("shadow_days_completed", 0) or 0)
        shadow_days_target = int(_real.get("shadow_days_target", 0) or 0)
        shadow_total_pnl = float(_real.get("shadow_total_pnl", 0.0) or 0.0)
        promotion_gate = dict(_real.get("promotion_gate", {}) or {})
    else:
        promoted = bool(signed and generation_ok)

    rollout_decision = orchestrator._rollout_framework.evaluate_promotion(
        mode=mode,
        previous_fitness=previous_fitness,
        winner_fitness=winner_fitness,
        shadow_status=shadow_status,
        shadow_passed=shadow_passed,
        explicit_human_approval=explicit_human_approval,
        twin_risk_flags=twin_risk_flags,
        selected_variant=selected,
        all_variants=list(experiment.variants or []),
        twin_confidence=float(twin_confidence or 0.0),
        twin_recommendation=bool(
            twin_decision.get("effective_recommendation", twin_decision.get("recommendation", False))
        ),
    )
    promoted = bool(promoted and rollout_decision.allow_promotion)

    # ── Constitutional Guard (pre-promotion) ─────────────────────────────
    constitutional_violations: list[str] = []
    promoted, constitutional_violations = apply_constitutional_pre_promotion(
        orchestrator,
        mode=mode,
        winner_dna=winner_dna,
        promoted=promoted,
    )

    base_promoted = promoted

    neuro_summary = orchestrator._run_neuroevolution_cycle(
        generation_offset=generation_offset,
        mode=mode,
        baseline_fitness=max(float(previous_fitness), float(winner_fitness)),
        anchor_dna=winner_dna,
        nightly_report=generation_metrics,
        sim_days=sim_days,
    )
    if bool(neuro_summary.get("winner_accepted", False)):
        winner_fitness = max(float(winner_fitness), float(neuro_summary.get("winner_fitness", float("-inf"))))

    generated_summary = orchestrator._run_generated_strategy_cycle(
        generation_offset=generation_offset,
        mode=mode,
        base_metrics=generation_metrics,
        baseline_fitness=max(float(previous_fitness), float(winner_fitness)),
        anchor_dna=winner_dna,
    )

    swarm_consensus = orchestrator._run_meta_swarm_deliberation(
        winner_dna=winner_dna,
        winner_fitness=winner_fitness,
        previous_fitness=previous_fitness,
        base_metrics=generation_metrics,
        mode=mode,
        generation_offset=generation_offset,
        parallel_realities=parallel_realities,
        sim_days=sim_days,
        neuro_summary=neuro_summary,
    )
    promoted = bool(base_promoted and swarm_consensus.allow_promotion)
    approval_chain_passed = mode != "real"
    approval_chain_reason = "not_required"

    if mode == "real":
        # H2: Twin judgment is never consulted here — human chain only
        from lumina_core.risk.real_multi_gate import real_dna_promotion_allowed

        approval_chain_passed = False
        has_sigs = bool(real_promotion_approvals)
        allowed, gate_reason = real_dna_promotion_allowed(
            mode=mode,
            require_human_approval=bool(require_human_approval),
            explicit_human_approval=bool(explicit_human_approval),
            base_promoted=bool(promoted),
            has_approval_signatures=has_sigs,
        )
        if not allowed:
            promoted = False
            approval_chain_reason = gate_reason
        else:
            approval_payload = orchestrator._build_real_promotion_payload(
                dna=winner_dna,
                generation_offset=generation_offset,
            )
            approval_chain_passed, approval_chain_reason = orchestrator._approval_chain.verify(
                payload=approval_payload,
                signatures=real_promotion_approvals,
            )
            promoted = bool(promoted and approval_chain_passed)

    if promoted:
        promoted_dna = orchestrator._registry.mutate(
            parent=winner_dna,
            mutation_rate=0.1,
            fitness_score=winner_fitness,
            version="active",
            lineage_hash=winner_dna.lineage_hash,
        )
        orchestrator._registry.register_dna(promoted_dna)
        if mode == "real":
            orchestrator._mark_shadow_promoted(dna_hash=winner_dna.hash)
    append_generation_completed_metrics(
        orchestrator,
        generation_offset=generation_offset,
        candidates=candidates,
        winner_dna=winner_dna,
        winner_fitness=winner_fitness,
        previous_fitness=previous_fitness,
        promoted=promoted,
        mode=mode,
        explicit_human_approval=explicit_human_approval,
        require_human_approval=require_human_approval,
        approval_chain_passed=approval_chain_passed,
        approval_chain_reason=approval_chain_reason,
        twin_decision=twin_decision,
        veto_blocked=veto_blocked,
        veto_check=veto_check,
        shadow_status=shadow_status,
        shadow_days_completed=shadow_days_completed,
        shadow_days_target=shadow_days_target,
        shadow_total_pnl=shadow_total_pnl,
        promotion_gate=promotion_gate,
        generated_summary=generated_summary,
        neuro_summary=neuro_summary,
        experiment=experiment,
        rollout_decision=rollout_decision,
        sim_days=sim_days,
        parallel_realities=parallel_realities,
        dream_summary=dream_summary,
        community_summary=community_summary,
        swarm_consensus=swarm_consensus,
    )

    return GenerationResult(
        generation=generation_offset,
        candidate_count=(
            len(candidates)
            + int(generated_summary.get("tested", 0) or 0)
            + int(neuro_summary.get("tested", 0) or 0)
        ),
        winner_hash=winner_dna.hash,
        winner_fitness=winner_fitness,
        previous_fitness=previous_fitness,
        promoted=promoted,
        generated_tested=int(generated_summary.get("tested", 0) or 0),
        generated_winners=int(generated_summary.get("winners", 0) or 0),
        neuro_tested=int(neuro_summary.get("tested", 0) or 0),
        neuro_winners=int(neuro_summary.get("winners", 0) or 0),
    )
