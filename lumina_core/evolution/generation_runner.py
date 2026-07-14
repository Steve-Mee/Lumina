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
    utcnow as _utcnow,
)
from lumina_core.evolution.meta_swarm import meta_swarm_governance_enabled
from lumina_core.evolution.multi_day_sim_runner import MultiDaySimRunner
from lumina_core.evolution.orchestrator_core import GenerationResult
from lumina_core.governance import SignedApproval

if TYPE_CHECKING:
    from lumina_core.evolution.orchestrator_core import EvolutionOrchestrator

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

    # === Phase 2 Deliverable 5 (Aperture Hardening) — Risk shadow is now the default path ===
    # For every candidate in the main evolution flow, we automatically run the
    # official reusable helper. This makes shadow validation for risk-affecting
    # DNA the normal, automatic behavior rather than an optional hook.
    try:
        from lumina_core.evolution.risk_shadow_bridge import validate_risk_proposal_in_shadow
        from pathlib import Path

        for candidate in candidates:
            content = getattr(candidate, "content", {}) or {}
            if isinstance(content, str):
                import json
                try:
                    content = json.loads(content)
                except Exception:
                    content = {}

            # Best-effort: use whatever engine context is available
            engine = getattr(orchestrator, "_engine", None) or getattr(orchestrator, "engine", None)
            validate_risk_proposal_in_shadow(
                proposal={
                    "experiment_id": f"risk-orchestrator-{candidate.hash[:12]}",
                    "dna_hash": candidate.hash,
                    "signal": content.get("signal") or "BUY",
                    "confluence_score": float(content.get("confluence_score", content.get("confluence", 0.6))),
                    "proposed_risk": float(content.get("proposed_risk", content.get("max_risk_percent", 150.0))),
                },
                engine=engine,
                storage_path=Path("state/risk_shadow_evolution.jsonl"),
                auto_record_promotion=True,
            )
    except Exception:
        # Risk shadow at orchestrator level is best-effort and must never break generation.
        pass
    # ================================================================================

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

    # Twin is primary auto-approval layer. For birth/SIM it can auto (when clean + above thresh).
    # REAL path still funnels through guard + shadow + PromotionGate.
    twin_decision: dict[str, Any] = {
        "recommendation": True,
        "confidence": 0.9,
        "risk_flags": [],
        "explanation": "sim/paper default (twin primary layer decides)",
    }
    if str(mode).strip().lower() in ("real", "paper"):
        twin_decision = orchestrator._approval_twin.evaluate_dna_promotion(winner_dna)
    else:
        # For pure sim/birth, proactively consult twin for the auto-approval signal
        try:
            twin_decision = orchestrator._approval_twin.evaluate_dna_promotion(winner_dna)
        except Exception:
            pass

    # Dedicated shadow runner for REAL promotion validation.
    shadow_runner: Any = MultiDaySimRunner(max_workers=8, drawdown_limit_ratio=0.02)
    # Keep compatibility with injected/custom runners in tests and dev overrides.
    if hasattr(orchestrator._sim_runner, "evaluate_variants") and not isinstance(orchestrator._sim_runner, MultiDaySimRunner):
        shadow_runner = orchestrator._sim_runner

    twin_confidence = float(twin_decision.get("confidence", 0.0) or 0.0)
    twin_risk_flags = [str(x) for x in list(twin_decision.get("risk_flags", []) or [])]
    signed_confidence = twin_confidence if str(mode).strip().lower() == "real" else 0.9

    # Explicit fail-closed: re-assert twin rec subordination to constitution right after twin consult.
    # The ApprovalTwin output is a signal, never a bypass. This (plus the later pre-promotion guard)
    # ensures even a fully tricked twin cannot promote bad DNA.
    try:
        cg = getattr(orchestrator, "_constitutional_guard", None)
        if cg is not None:
            twin_rec = bool(twin_decision.get("recommendation", False))
            if not cg.veto_unless_constitutional(
                dna_content=getattr(winner_dna, "content", winner_dna),
                mode=mode,
                current_recommendation=twin_rec,
            ):
                twin_decision = dict(twin_decision)
                twin_decision["recommendation"] = False
                rf = list(twin_decision.get("risk_flags", []) or [])
                if "constitution_veto_post_twin" not in rf:
                    rf.append("constitution_veto_post_twin")
                twin_decision["risk_flags"] = rf
                twin_risk_flags = [str(x) for x in rf]
    except Exception:
        twin_decision = {"recommendation": False, "confidence": 0.0, "risk_flags": ["guard_error_post_twin"]}
        twin_risk_flags = ["guard_error_post_twin"]

    # Guard: REAL uses twin confidence (0–1 or 0–100) for ultra zero-touch floor + shadow.
    signed = orchestrator._guard.has_signed_approval(
        confidence=signed_confidence,
        candidate_fitness=winner_fitness,
        current_fitness=previous_fitness,
        mode=mode,
        approval_twin_recommendation=bool(twin_decision.get("recommendation", False)),
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
        shadow_decision = orchestrator._run_shadow_validation_gate(
            dna=winner_dna,
            winner_fitness=winner_fitness,
            nightly_report=generation_metrics,
            signed=signed,
            generation_ok=generation_ok,
            shadow_runner=shadow_runner,
        )
        promoted = bool(shadow_decision.get("promote_now", False))
        veto_check = dict(shadow_decision.get("veto_check", veto_check) or veto_check)
        veto_blocked = bool(shadow_decision.get("veto_blocked", False))
        shadow_status = str(shadow_decision.get("shadow_status", shadow_status))
        shadow_passed = bool(shadow_decision.get("shadow_passed", False))
        shadow_days_completed = int(shadow_decision.get("shadow_days_completed", 0) or 0)
        shadow_days_target = int(shadow_decision.get("shadow_days_target", 0) or 0)
        shadow_total_pnl = float(shadow_decision.get("shadow_total_pnl", 0.0) or 0.0)
        promotion_gate = dict(shadow_decision.get("promotion_gate", {}) or {})

        gated_promotion = orchestrator._guard.is_confidence_gated_promotion(
            winner_dna,
            twin_confidence,
            shadow_passed,
            winner_fitness,
            previous_fitness,
            twin_risk_flags=twin_risk_flags,
        )
        promoted = bool(promoted and gated_promotion)

        if shadow_status in {"passed", "failed", "vetoed"}:
            fail_reasons = list(promotion_gate.get("fail_reasons", []) or [])
            gate_reason = str(fail_reasons[0]) if fail_reasons else ""
            orchestrator._send_promotion_status_telegram(
                dna_hash=winner_dna.hash,
                promoted=promoted,
                reason=gate_reason,
            )
            try:
                from lumina_launcher.core.workspace_root import resolve_birth_workspace_root
                from lumina_core.maturity.milestone_hooks import (
                    hook_promotion_gate_passed,
                    hook_shadow_validation_passed,
                )

                workspace = resolve_birth_workspace_root()
                if shadow_passed:
                    hook_shadow_validation_passed(
                        workspace,
                        shadow_status=shadow_status,
                        dna_hash=winner_dna.hash,
                    )
                if bool(promotion_gate.get("promoted", False)):
                    hook_promotion_gate_passed(
                        workspace,
                        mode=mode,
                        dna_hash=winner_dna.hash,
                    )
            except Exception:
                pass
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
    )
    promoted = bool(promoted and rollout_decision.allow_promotion)

    # ── Constitutional Guard (pre-promotion) ─────────────────────────────
    # The ConstitutionalGuard is the single authoritative safety gate.
    # It checks all 15 principles, writes an audit record, and is
    # fail-closed: any unexpected error blocks promotion.
    #
    # Twin recommendation (even high-confidence) is always ignored if this fails.
    # This is an explicit defense-in-depth path that makes it impossible for a tricked twin
    # to promote DNA that violates the Trading Constitution, sandbox rules, or aperture.
    constitutional_violations: list[str] = []
    if promoted:
        guard_result = orchestrator._constitutional_guard.check_pre_promotion(
            winner_dna.content, mode=mode, raise_on_fatal=False
        )
        if not guard_result.passed:
            constitutional_violations = guard_result.violation_names
            logger.error(
                "ConstitutionalGuard BLOCKED promotion dna=%s mode=%s violations=%s",
                winner_dna.hash[:12],
                mode,
                constitutional_violations,
            )
            promoted = False
            try:
                from lumina_core.notifications.attention_events import constitution_violation_event
                from lumina_core.notifications.operator_notifier import notify_problem
                from lumina_launcher.core.workspace_root import resolve_birth_workspace_root

                notify_problem(
                    constitution_violation_event(
                        detail="; ".join(constitutional_violations) or "Promotion blocked."
                    ),
                    workspace_root=resolve_birth_workspace_root(),
                )
            except Exception:
                pass
        elif guard_result.warn_violations:
            logger.warning(
                "ConstitutionalGuard WARN dna=%s mode=%s warns=%s",
                winner_dna.hash[:12],
                mode,
                [v.principle_name for v in guard_result.warn_violations],
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
        approval_chain_passed = False
        if not require_human_approval:
            promoted = False
            approval_chain_reason = "real_human_approval_mandatory"
        elif promoted:
            approval_payload = orchestrator._build_real_promotion_payload(
                dna=winner_dna,
                generation_offset=generation_offset,
            )
            approval_chain_passed, approval_chain_reason = orchestrator._approval_chain.verify(
                payload=approval_payload,
                signatures=real_promotion_approvals,
            )
            promoted = bool(promoted and approval_chain_passed)
        else:
            approval_chain_reason = "promotion_not_eligible_before_approval"

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
    orchestrator._append_metrics(
        {
            "event": "generation_completed",
            "timestamp": _utcnow(),
            "generation": generation_offset,
            "candidate_count": len(candidates),
            "winner_hash": winner_dna.hash,
            "winner_fitness": winner_fitness,
            "previous_fitness": previous_fitness,
            "promoted": promoted,
            "mode": mode,
            "explicit_human_approval": bool(explicit_human_approval),
            "require_human_approval": bool(require_human_approval),
            "approval_chain_passed": bool(approval_chain_passed),
            "approval_chain_reason": str(approval_chain_reason),
            "approval_twin_recommendation": bool(twin_decision.get("recommendation", False)),
            "approval_twin_confidence": float(twin_decision.get("confidence", 0.0) or 0.0),
            "approval_twin_risk_flags": list(twin_decision.get("risk_flags", []) or []),
            "veto_blocked": veto_blocked,
            "veto_reason": veto_check.get("reason", ""),
            "veto_active_records": len(veto_check.get("active_veto_records", [])),
            "shadow_status": shadow_status,
            "shadow_days_completed": shadow_days_completed,
            "shadow_days_target": shadow_days_target,
            "shadow_total_pnl": shadow_total_pnl,
            "promotion_gate_passed": bool(promotion_gate.get("promoted", False)),
            "promotion_gate_fail_reasons": list(promotion_gate.get("fail_reasons", []) or []),
            "promotion_gate": promotion_gate,
            "generated_ideas": int(generated_summary.get("ideas", 0) or 0),
            "generated_tested": int(generated_summary.get("tested", 0) or 0),
            "generated_winners": int(generated_summary.get("winners", 0) or 0),
            "neuro_tested": int(neuro_summary.get("tested", 0) or 0),
            "neuro_winners": int(neuro_summary.get("winners", 0) or 0),
            "neuro_best_fitness": (
                float(neuro_summary.get("winner_fitness", 0.0) or 0.0)
                if bool(neuro_summary.get("winner_accepted", False))
                else None
            ),
            "neuro_winner_path": str(neuro_summary.get("winner_path", "") or ""),
            "neuro_simulator_data_source": str(neuro_summary.get("neuro_simulator_data_source", "") or ""),
            "ab_experiment_id": str(experiment.experiment_id),
            "ab_variant_count": len(list(experiment.variants or [])),
            "rollout_stage": rollout_decision.stage,
            "rollout_reason": rollout_decision.reason,
            "rollout_shadow_required": bool(rollout_decision.shadow_required),
            "rollout_shadow_passed": bool(rollout_decision.shadow_passed),
            "rollout_live_orders_blocked": bool(rollout_decision.live_orders_blocked),
            "rollout_radical_mutation": bool(rollout_decision.radical_mutation),
            "rollout_human_approval_required": bool(rollout_decision.human_approval_required),
            "rollout_human_approval_granted": bool(rollout_decision.human_approval_granted),
            "rollout_ab_verdict": str(rollout_decision.ab_verdict),
            "rollout_metrics_delta": dict(rollout_decision.metrics_delta),
            "sim_days": sim_days,
            "parallel_realities": int(parallel_realities),
            "dream_engine": dict(dream_summary),
            "community_knowledge": dict(community_summary),
            "meta_swarm": {
                "enabled": bool(meta_swarm_governance_enabled()),
                "allow_promotion": bool(swarm_consensus.allow_promotion),
                "collective_score": round(float(swarm_consensus.collective_score), 6),
                "risk_veto": bool(swarm_consensus.risk_veto),
                "round_two": [
                    {
                        "agent": v.agent_id,
                        "approve": bool(v.approve),
                        "score": round(float(v.score), 4),
                        "veto": bool(v.veto),
                    }
                    for v in swarm_consensus.round_two
                ],
            },
        }
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
