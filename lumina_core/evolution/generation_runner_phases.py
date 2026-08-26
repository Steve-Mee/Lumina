"""Sequential helpers for run_single_generation (Wave H; behavior-preserving)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, TYPE_CHECKING

from lumina_core.evolution.fitness_evaluator import utcnow as _utcnow
from lumina_core.evolution.meta_swarm import meta_swarm_governance_enabled

if TYPE_CHECKING:
    from lumina_core.evolution.orchestrator_core import EvolutionOrchestrator

logger = logging.getLogger(__name__)


def risk_shadow_validate_candidates(orchestrator: "EvolutionOrchestrator", candidates: list[Any]) -> None:
    """Best-effort risk shadow for each candidate; never raises into generation."""
    try:
        from lumina_core.evolution.risk_shadow_bridge import validate_risk_proposal_in_shadow

        for candidate in candidates:
            content = getattr(candidate, "content", {}) or {}
            if isinstance(content, str):
                import json

                try:
                    content = json.loads(content)
                except Exception:
                    content = {}

            engine = getattr(orchestrator, "_engine", None) or getattr(orchestrator, "engine", None)
            validate_risk_proposal_in_shadow(
                proposal={
                    "experiment_id": f"risk-orchestrator-{candidate.hash[:12]}",
                    "dna_hash": candidate.hash,
                    "signal": content.get("signal") or "BUY",
                    "confluence_score": float(
                        content.get("confluence_score", content.get("confluence", 0.6))
                    ),
                    "proposed_risk": float(
                        content.get("proposed_risk", content.get("max_risk_percent", 150.0))
                    ),
                },
                engine=engine,
                storage_path=Path("state/risk_shadow_evolution.jsonl"),
                auto_record_promotion=True,
            )
    except Exception:
        # Risk shadow at orchestrator level is best-effort and must never break generation.
        pass


def fail_closed_twin_decision(reason: str) -> dict[str, Any]:
    """SIM twin evaluate failure must not keep recommendation=True (ADR-0045)."""
    return {
        "recommendation": False,
        "effective_recommendation": False,
        "executable": False,
        "mode": "shadow",
        "confidence": 0.0,
        "risk_flags": ["twin_evaluate_failed"],
        "explanation": str(reason or "fail-closed: twin evaluate raised"),
    }


def twin_effective_recommendation(decision: dict[str, Any]) -> bool:
    if "effective_recommendation" in decision:
        return bool(decision.get("effective_recommendation", False))
    # Legacy twin without mode fields — fail-closed (not executable)
    return False


def apply_post_twin_constitutional_veto(
    orchestrator: "EvolutionOrchestrator",
    *,
    mode: str,
    winner_dna: Any,
    twin_decision: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Re-assert twin rec subordination to constitution; fail-closed on error."""
    twin_risk_flags = [str(x) for x in list(twin_decision.get("risk_flags", []) or [])]
    try:
        cg = getattr(orchestrator, "_constitutional_guard", None)
        if cg is not None:
            twin_rec = twin_effective_recommendation(twin_decision)
            if not cg.veto_unless_constitutional(
                dna_content=getattr(winner_dna, "content", winner_dna),
                mode=mode,
                current_recommendation=twin_rec or bool(twin_decision.get("recommendation", False)),
            ):
                twin_decision = dict(twin_decision)
                twin_decision["recommendation"] = False
                twin_decision["effective_recommendation"] = False
                twin_decision["executable"] = False
                rf = list(twin_decision.get("risk_flags", []) or [])
                if "constitution_veto_post_twin" not in rf:
                    rf.append("constitution_veto_post_twin")
                twin_decision["risk_flags"] = rf
                twin_risk_flags = [str(x) for x in rf]
    except Exception:
        twin_decision = {
            "recommendation": False,
            "effective_recommendation": False,
            "executable": False,
            "confidence": 0.0,
            "risk_flags": ["guard_error_post_twin"],
        }
        twin_risk_flags = ["guard_error_post_twin"]
    return twin_decision, twin_risk_flags


def apply_constitutional_pre_promotion(
    orchestrator: "EvolutionOrchestrator",
    *,
    mode: str,
    winner_dna: Any,
    promoted: bool,
) -> tuple[bool, list[str]]:
    """Single authoritative safety gate before promotion."""
    constitutional_violations: list[str] = []
    if not promoted:
        return promoted, constitutional_violations
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
    return promoted, constitutional_violations


def append_generation_completed_metrics(
    orchestrator: "EvolutionOrchestrator",
    *,
    generation_offset: int,
    candidates: list[Any],
    winner_dna: Any,
    winner_fitness: float,
    previous_fitness: float,
    promoted: bool,
    mode: str,
    explicit_human_approval: bool,
    require_human_approval: bool,
    approval_chain_passed: bool,
    approval_chain_reason: str,
    twin_decision: dict[str, Any],
    veto_blocked: bool,
    veto_check: dict[str, Any],
    shadow_status: str,
    shadow_days_completed: int,
    shadow_days_target: int,
    shadow_total_pnl: float,
    promotion_gate: dict[str, Any],
    generated_summary: dict[str, Any],
    neuro_summary: dict[str, Any],
    experiment: Any,
    rollout_decision: Any,
    sim_days: int,
    parallel_realities: int,
    dream_summary: dict[str, Any],
    community_summary: dict[str, Any],
    swarm_consensus: Any,
) -> None:
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
