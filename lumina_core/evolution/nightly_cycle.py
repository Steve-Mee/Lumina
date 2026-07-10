"""Nightly self-evolution cycle orchestration."""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from lumina_core.evolution.dream_integration import run_multi_gen_nightly_cycle
from lumina_core.evolution.multi_day_sim_runner import MultiDaySimRunner
from lumina_core.evolution.mutation_executor import apply_evolution_candidate
from lumina_core.evolution.simulator_data_support import enrich_nightly_report_simulator_data
from lumina_core.experiments.ab_framework import ABExperimentFramework

if TYPE_CHECKING:
    from lumina_core.engine.meta_agent_core import SelfEvolutionMetaAgent

logger = logging.getLogger(__name__)

def run_nightly_evolution_cycle(
    agent: "SelfEvolutionMetaAgent",
    *,
    nightly_report: dict[str, Any],
    dry_run: bool = False,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    nightly_report = agent._hydrate_report_from_blackboard(dict(nightly_report))
    enrich_nightly_report_simulator_data(nightly_report, agent.engine)
    if not agent.enabled:
        result = {
            "status": "disabled",
            "timestamp": now.isoformat(),
            "dry_run": dry_run,
        }
        agent._append_immutable_log(result)
        return result

    meta_review = agent._meta_review(nightly_report)
    mode_key = agent._runtime_mode_key()
    guard = agent.evolution_guard
    mutation_allowed = guard.can_mutate(mode=mode_key)

    active_dna = agent._register_active_dna(nightly_report=nightly_report, meta_review=meta_review)
    top_dna = agent._top_ranked_dna(active_dna=active_dna)
    fine_tune_trigger = agent._auto_fine_tuning_trigger(meta_review=meta_review)
    fine_tune_result = (
        agent._execute_auto_fine_tune(nightly_report, dry_run=dry_run)
        if fine_tune_trigger["triggered"]
        else {
            "triggered": False,
            "executed": False,
            "reason": fine_tune_trigger["reason"],
        }
    )
    champion = agent._current_champion()
    if fine_tune_result.get("executed") and fine_tune_result.get("champion_candidate"):
        champion = dict(fine_tune_result["champion_candidate"])
    challengers = agent._build_challengers(champion, meta_review) if mutation_allowed else []
    genetic_candidates, genetic_candidate_map = (
        agent._build_genetic_candidates(
            champion=champion,
            top_dna=top_dna,
            nightly_report=nightly_report,
            meta_review=meta_review,
        )
        if mutation_allowed
        else ([], {})
    )
    candidate_pool = challengers + genetic_candidates
    scored = [
        agent._score_challenger(champion, candidate, nightly_report, meta_review) for candidate in candidate_pool
    ]

    ab_result: dict[str, Any] | None = None
    if agent.sim_mode and mutation_allowed and candidate_pool:
        ab_framework = ABExperimentFramework(min_forks=5, max_forks=10, max_workers=10)
        base_candidate = dict(candidate_pool[0])
        experiment = ab_framework.run_auto_forks(
            base_agent=base_candidate,
            score_fn=lambda fork: agent._score_challenger(champion, fork, nightly_report, meta_review),
            promote_fn=agent._apply_candidate,
            seed=int(now.timestamp()),
            candidate_pool=candidate_pool,
        )
        scored = list(experiment.variants)
        ab_result = {
            "experiment_id": str(experiment.experiment_id),
            "selected_variant": dict(experiment.selected_variant),
            "variant_count": len(experiment.variants),
            "genetic_candidates": len(genetic_candidates),
        }

    best = max(scored, key=lambda item: float(item.get("score", 0.0))) if scored else None
    candidate_dna = None
    if isinstance(best, dict):
        candidate_dna = genetic_candidate_map.get(str(best.get("dna_hash", "")))
    if candidate_dna is None and mutation_allowed:
        candidate_dna = agent._register_candidate_dna(
            active_dna=active_dna,
            best=best,
            nightly_report=nightly_report,
            meta_review=meta_review,
        )

    confidence = float(best.get("confidence", 0.0)) if best else 0.0
    backtest_green = agent._backtest_green(nightly_report)
    safety_ok = agent._safety_contract_ok()
    swarm_payload = meta_review.get("meta_swarm") if isinstance(meta_review.get("meta_swarm"), dict) else {}
    swarm_ok = bool(swarm_payload.get("allow_promotion", True))

    stability_gate = bool(float(meta_review.get("win_rate", 0.0) or 0.0) >= 0.45)
    realism_gate = bool(float(meta_review.get("emotional_twin_accuracy", 0.0) or 0.0) >= 0.4)
    consistency_gate = bool(float(meta_review.get("regime_drift", 1.0) or 1.0) <= 0.75)
    external_release_gates = agent._external_release_gates_ok()
    shadow_evidence = agent._shadow_rollout_evidence_ok()
    gates = {
        "stability": stability_gate,
        "risk": bool(safety_ok),
        "realism": realism_gate,
        "consistency": consistency_gate,
        "backtest_green": bool(backtest_green),
        "external_release_gates": bool(external_release_gates),
        "shadow_evidence": bool(shadow_evidence),
        "live_promotion_eligible": bool(not agent.sim_mode),
        "swarm_governance": bool(swarm_ok),
    }

    current_guard_fitness = float(active_dna.fitness_score) if active_dna is not None else float("-inf")
    candidate_guard_fitness = float(best.get("score", float("-inf"))) if isinstance(best, dict) else float("-inf")
    approval_twin = getattr(agent, "approval_twin_agent", None)
    confidence_for_guard = float(confidence)
    twin_risk_flags: list[str] = []
    shadow_runner: Any | None = None
    if str(mode_key).strip().lower() == "real" and candidate_dna is not None and approval_twin is not None:
        try:
            td_raw = approval_twin.evaluate_dna_promotion(candidate_dna)
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/meta_agent_core.py:279")
            td_raw = {}
        if not isinstance(td_raw, dict):
            td_raw = {}
        approval_twin_recommendation = bool(td_raw.get("recommendation", False))
        confidence_for_guard = float(td_raw.get("confidence", confidence) or 0.0)
        twin_risk_flags = [str(x) for x in list(td_raw.get("risk_flags", []) or [])]
        shadow_runner = MultiDaySimRunner(max_workers=8, drawdown_limit_ratio=0.02)
    else:
        approval_twin_recommendation = guard.resolve_approval_twin_recommendation(
            approval_twin=approval_twin,
            dna=candidate_dna,
        )
    signed_approval = guard.has_signed_approval(
        confidence=confidence_for_guard,
        candidate_fitness=candidate_guard_fitness,
        current_fitness=current_guard_fitness,
        mode=mode_key,
        approval_twin_recommendation=approval_twin_recommendation,
        approval_twin=approval_twin,
        dna=candidate_dna,
        shadow_runner=shadow_runner,
        twin_risk_flags=twin_risk_flags,
    )

    forced_sim_apply = bool(agent.sim_mode and best is not None)
    baseline_auto_apply = bool(forced_sim_apply or (confidence > 85.0 and backtest_green and safety_ok))
    should_auto_apply = bool(mutation_allowed and baseline_auto_apply and signed_approval and swarm_ok)
    approval_blocked = bool(agent.approval_required and should_auto_apply)
    if should_auto_apply and not approval_blocked and not dry_run and best is not None:
        from lumina_core.engine.self_evolution_promotion_gates import promotion_readiness_blocks_auto_apply

        if promotion_readiness_blocks_auto_apply(str(mode_key), best):
            should_auto_apply = False
    promoted_active_dna = agent._promote_winning_dna(
        active_dna=active_dna,
        winner_dna=candidate_dna,
        should_promote=bool(should_auto_apply and not approval_blocked and not dry_run),
    )

    promoted_at = now if bool(should_auto_apply and not approval_blocked and not dry_run) else None
    mk = str(mode_key).strip().lower()
    zero_touch_real = bool(
        mk == "real"
        and candidate_dna is not None
        and signed_approval
        and guard.is_confidence_gated_promotion(
            candidate_dna,
            confidence_for_guard,
            shadow_evidence,
            candidate_guard_fitness,
            current_guard_fitness,
            twin_risk_flags=twin_risk_flags,
        )
    )
    guard_decision = guard.evaluate(
        mode=mode_key,
        confidence=confidence_for_guard,
        candidate_fitness=candidate_guard_fitness,
        previous_fitness=current_guard_fitness,
        approval_twin_recommendation=approval_twin_recommendation,
        approval_twin=approval_twin if mk == "real" else None,
        dna=candidate_dna if mk == "real" else None,
        shadow_runner=shadow_runner,
        twin_risk_flags=twin_risk_flags,
        current_hash=active_dna.hash if active_dna is not None else None,
        promoted_at=promoted_at,
        now=now,
        zero_touch_real=zero_touch_real,
    )
    if guard_decision.rollback_required:
        promoted_active_dna = active_dna
        should_auto_apply = False
        approval_blocked = False

    lifecycle = agent._build_lifecycle(best=best, gates=gates)
    outcome = {
        "status": "awaiting_human_approval"
        if approval_blocked
        else ("proposed" if not should_auto_apply else "applied"),
        "timestamp": now.isoformat(),
        "dry_run": dry_run,
        "meta_review": meta_review,
        "auto_fine_tune": fine_tune_result,
        "champion": champion,
        "challengers": scored,
        "best_candidate": best,
        "proposal": {
            "confidence": round(confidence, 2),
            "guard_confidence": round(float(confidence_for_guard), 4)
            if math.isfinite(float(confidence_for_guard))
            else None,
            "backtest_green": backtest_green,
            "safety_ok": safety_ok,
            "approval_required": agent.approval_required,
            "forced_by_sim_mode": forced_sim_apply,
            "sim_live_readiness": "not_live_eligible" if agent.sim_mode else "eligible_after_gates",
            "would_auto_apply": should_auto_apply,
            "auto_apply_executed": bool(should_auto_apply and not agent.approval_required and not dry_run),
            "signed_approval": bool(signed_approval),
            "mutation_allowed": bool(mutation_allowed),
            "candidate_fitness": round(candidate_guard_fitness, 6)
            if math.isfinite(candidate_guard_fitness)
            else None,
            "current_fitness": round(current_guard_fitness, 6) if math.isfinite(current_guard_fitness) else None,
            "external_release_gates": bool(external_release_gates),
            "shadow_evidence": bool(shadow_evidence),
            "meta_swarm_allow": bool(swarm_ok),
            "zero_touch_real": bool(zero_touch_real),
        },
        "lifecycle": lifecycle,
        "governance": {
            "mode": mode_key,
            "mutation_allowed": bool(guard_decision.mutation_allowed),
            "signed_approval": bool(guard_decision.signed_approval),
            "zero_touch_real": bool(zero_touch_real),
            "rollback_triggered": bool(guard_decision.rollback_required),
            "revert_to_hash": guard_decision.revert_to_hash,
        },
    }
    promoted_or_active_dna = promoted_active_dna if promoted_active_dna is not None else active_dna
    if active_dna is not None or candidate_dna is not None:
        outcome["dna"] = {
            "active": agent._dna_summary(promoted_or_active_dna),
            "candidate": agent._dna_summary(candidate_dna),
        }
    if top_dna or genetic_candidates:
        outcome["genetic_evolution"] = {
            "top_dna_count": len(top_dna),
            "candidate_count": len(genetic_candidates),
            "promoted_hash": str(promoted_or_active_dna.hash) if promoted_or_active_dna is not None else "",
        }
    if isinstance(ab_result, dict):
        outcome["ab_experiment"] = ab_result

    if should_auto_apply and not agent.approval_required and not dry_run and best is not None:
        apply_evolution_candidate(agent, best)

    # Record proposal to observability metrics (no-op when obs_service is None)
    if agent.obs_service is not None:
        best_name = str(best.get("name")) if best else None
        agent.obs_service.record_evolution_proposal(
            status=str(outcome.get("status", "unknown")),
            confidence=float(confidence_for_guard),
            best_candidate=best_name,
        )

    # Multi-generation orchestrator (dream + DNA generations). Nightly sim/paper may pass
    # dry_run=True to avoid live hyperparam side-effects; we still run the cycle so dream/SIM
    # exercises evolution. dry_run above still blocks _apply_candidate / certain promotions.
    run_multi_gen_nightly_cycle(
        agent,
        nightly_report=nightly_report,
        outcome=outcome,
        mode_key=str(mode_key),
        mutation_allowed=bool(mutation_allowed),
        dry_run=bool(dry_run),
    )

    agent._append_immutable_log(outcome)
    agent._log_agent_decision(
        raw_input={"nightly_report": nightly_report, "dry_run": dry_run},
        raw_output=outcome,
        confidence=float(outcome.get("proposal", {}).get("confidence", 0.0) or 0.0),
        policy_outcome=str(outcome.get("status", "unknown")),
        decision_context_id="nightly_evolution",
        evolution_log_hash=str(outcome.get("hash", "")) if isinstance(outcome, dict) else None,
    )
    if agent.blackboard is not None and hasattr(agent.blackboard, "add_proposal"):
        agent.blackboard.add_proposal(
            topic="agent.meta.proposal",
            producer="self_evolution_meta_agent",
            payload={
                "status": str(outcome.get("status", "unknown")),
                "proposal": dict(outcome.get("proposal", {})),
                "dna": dict(outcome.get("dna", {})) if isinstance(outcome.get("dna"), dict) else {},
                "timestamp": now.isoformat(),
            },
            confidence=max(0.0, min(1.0, float(outcome.get("proposal", {}).get("confidence", 0.0) or 0.0) / 100.0)),
        )
    return outcome
