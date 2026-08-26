"""Organism Autonomy Engine — never-stop recovery orchestration for birth phase."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.death_spiral_guard import (
    DeathSpiralState,
    consume_novelty_budget,
    record_stall_signature,
    reset_after_novelty,
    should_widen_data_horizon,
)
from lumina_core.birth.organism_autonomy_types import (
    AutonomyDecision,
    OrganismAutonomyState,
    RecoveryDispatch,
)
from lumina_core.birth.phoenix_loop import (
    PHOENIX_CYCLE_REASON,
    PhoenixLoopState,
    select_phoenix_novelty,
)
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.organism_autonomy")


def map_recommended_to_service_action(recommended: str) -> str:
    """Map plateau audit recommendation to birth_service recovery method."""
    action = str(recommended or "").strip().lower()
    return {
        "continue_evolution": "resume_stalled_stage",
        "policy_rollback": "resume_stalled_stage",
        "explore_boost_anti_hold": "resume_stalled_stage",
        "explore_boost_anti_flat": "resume_stalled_stage",
        "range_patience_recovery": "resume_stalled_stage",
        "expectancy_quality_reward": "resume_stalled_stage",
        "expectancy_quality_stack": "resume_stalled_stage",
        "phoenix_reset": "phoenix_recovery",
        "expand_and_retry": "expand_and_retry",
        "expand_data": "expand_and_retry",
        "widen_horizon": "expand_and_retry",
        "accept_champion": "accept_champion",
        "accept_champion_or_wipe": "accept_champion",
    }.get(action, "resume_stalled_stage")


def organism_autonomy_status(
    cfg: BirthCurriculumConfig,
    autonomy_state: OrganismAutonomyState | None = None,
) -> dict[str, Any]:
    """Operator-facing C2 snapshot: defaults, phoenix budget, notify-as-exception posture."""
    state = autonomy_state or OrganismAutonomyState(
        phoenix=PhoenixLoopState(), death_spiral=DeathSpiralState()
    )
    max_cycles = max(1, int(cfg.phoenix_max_cycles))
    used = int(state.phoenix.phoenix_count)
    remaining = max(0, max_cycles - used)
    return {
        "autonomous_recovery_enabled": bool(cfg.autonomous_recovery_enabled),
        "phoenix_loop_enabled": bool(cfg.phoenix_loop_enabled),
        "phoenix_max_cycles": max_cycles,
        "phoenix_cycles_used": used,
        "phoenix_cycles_remaining": remaining,
        "phoenix_budget_exhausted": remaining <= 0 or not bool(cfg.phoenix_loop_enabled),
        "autonomous_recovery_count": int(state.autonomous_recovery_count),
        "last_recommended_action": str(state.last_recommended_action or ""),
        "terminal_notify_is_exception": True,
        "no_lift_uses_phoenix_before_notify": True,
        "capital_gates_untouched": True,
        "c2_posture": (
            "active"
            if bool(cfg.autonomous_recovery_enabled)
            else "disabled_operator_notify"
        ),
    }

def _phoenix_eligible(cfg: BirthCurriculumConfig, autonomy_state: OrganismAutonomyState) -> bool:
    if not cfg.phoenix_loop_enabled:
        return False
    return autonomy_state.phoenix.phoenix_count < max(1, int(cfg.phoenix_max_cycles))


def _twin_escalate_or_notify(
    *,
    approval_twin: Any,
    autonomy_state: OrganismAutonomyState,
    stall_reason: str,
    curriculum_stage: str,
    fitness_signal: float,
    fork: str,
    twin_res: dict[str, Any] | None = None,
    t_conf: float = 0.0,
    t_risks: list[str] | None = None,
) -> AutonomyDecision:
    """When Twin is unsure: escalate to operator (exception path). Never silent grind."""
    metrics = autonomy_state.to_metrics()
    metrics["twin_terminal_fork"] = fork
    metrics["twin_confidence"] = round(float(t_conf), 4)
    try:
        from lumina_core.evolution.twin_training_service import TwinTrainingService

        svc = TwinTrainingService()
        conf = float(t_conf)
        risks = list(t_risks or [])
        should, reasons = svc.should_escalate_decision(
            confidence=conf if conf > 0 else 0.5,
            risk_flags=risks or ["terminal_fork"],
            dna_hash=f"birth_terminal_{fork}_{curriculum_stage}",
        )
        if should or conf < 0.80:
            esc = svc.create_escalation(
                dna_hash=f"birth_terminal_{fork}_{curriculum_stage}",
                confidence=conf if conf > 0 else 0.5,
                risk_flags=risks or ["terminal_fork", fork],
                explanation=(
                    str((twin_res or {}).get("explanation") or "")[:300]
                    or f"Birth terminal fork: {fork} at {curriculum_stage}"
                ),
                twin_recommendation=bool((twin_res or {}).get("recommendation", False)),
                doubt_reasons=reasons or ["low_conf", "terminal_fork"],
                notify_telegram=True,
            )
            metrics["twin_escalation_id"] = esc.get("escalation_id")
            metrics["twin_doubt_reasons"] = reasons or ["low_conf"]
            return AutonomyDecision(
                dispatch=RecoveryDispatch.TERMINAL_NOTIFY_ONLY,
                needs_attention=True,
                retryable=False,
                stall_reason=stall_reason,
                recommended_action=fork,
                autonomy_metrics=metrics,
                message=(
                    f"Twin vraagt raad (fork={fork}, conf={conf:.2%}) — "
                    f"escalation id={esc.get('escalation_id')}. "
                    "Deck/Telegram: expand_data | accept_champion | wipe. Geen auto-grind."
                ),
            )
    except Exception:
        logger.debug("birth.twin_terminal_escalate_failed", exc_info=True)
    return AutonomyDecision(
        dispatch=RecoveryDispatch.TERMINAL_NOTIFY_ONLY,
        needs_attention=True,
        retryable=False,
        stall_reason=stall_reason,
        recommended_action=fork,
        autonomy_metrics=metrics,
        message=(
            f"Terminal fork {fork} — Twin niet zeker; operator uitzondering "
            f"(expand_data | accept_champion | wipe). Geen silent resume."
        ),
    )


def evaluate_terminal_stall(
    *,
    cfg: BirthCurriculumConfig,
    autonomy_state: OrganismAutonomyState,
    pending: dict[str, Any],
    curriculum_stage: str,
    approval_twin: Any = None,
    stage_trades: int,
    required: int,
    constitution_violations: int,
    fitness_signal: float,
    recommended_recovery_action: str = "",
    remediation_cycles_exhausted: bool = False,
    plateau_exhausted: bool = False,
    recovery_no_lift_brake: bool = False,
    swarm_tournament_resolved: bool = False,
    starship_context: dict[str, Any] | None = None,
) -> AutonomyDecision:
    """Decide how to handle a terminal stall without human gate when autonomy enabled."""
    if not cfg.autonomous_recovery_enabled:
        stall_reason = str(
            pending.get("terminal_stall_reason") or pending.get("blocker_reason") or "stage_stalled"
        )
        if approval_twin is not None:
            try:
                from lumina_core.evolution.dna_registry import PolicyDNA
                dna = PolicyDNA.create("birth_autonomy", "terminal", {"stage": curriculum_stage}, 0.3, 0, 0.0, "auto")
                _ = approval_twin.evaluate_dna_promotion(dna)
            except Exception:
                pass
        return AutonomyDecision(
            dispatch=RecoveryDispatch.TERMINAL_NOTIFY_ONLY,
            needs_attention=True,
            retryable=False,
            stall_reason=stall_reason,
            message="Autonomous recovery disabled — operator attention required.",
        )

    blocker_metric = str(pending.get("blocker_metric") or "unknown")
    blocker_value = float(pending.get("blocker_value") or 0.0)
    stall_reason = str(
        pending.get("terminal_stall_reason") or pending.get("blocker_reason") or "stage_stalled"
    )
    recommended = str(recommended_recovery_action or autonomy_state.last_recommended_action or "").strip()
    autonomy_state.last_recommended_action = recommended

    # No-lift brake: phoenix first; then Twin accept_champion (birth/SIM); else notify.
    # Never train-through-freeze; never auto-wipe.
    if recovery_no_lift_brake and not bool(swarm_tournament_resolved):
        if _phoenix_eligible(cfg, autonomy_state):
            from lumina_core.birth.organism_autonomy_phoenix import try_no_lift_phoenix_decision

            decision = try_no_lift_phoenix_decision(
                cfg=cfg,
                autonomy_state=autonomy_state,
                stall_reason=stall_reason,
            )
            if decision is not None:
                return decision
        # Twin as human replacement for accept_champion only (ADR-0032, birth/SIM).
        if approval_twin is not None:
            try:
                from lumina_core.birth.birth_control_plane import twin_accept_champion_eligible
                from lumina_core.evolution.dna_registry import PolicyDNA
                from pathlib import Path

                starship = dict(starship_context or {})
                champ_path = str(
                    starship.get("best_edgescore_policy_path")
                    or starship.get("best_policy_path")
                    or ""
                ).strip()
                champ_ok = bool(champ_path) and Path(champ_path).is_file()
                if hasattr(approval_twin, "sync_mode_from_controller"):
                    try:
                        approval_twin.sync_mode_from_controller()
                    except Exception:
                        pass
                proxy = PolicyDNA.create(
                    prompt_id="birth_freeze_accept_champion",
                    version="autonomy",
                    content={
                        "stage": curriculum_stage,
                        "stall_reason": stall_reason,
                        "action": "accept_champion",
                        "swarm_rejected_no_lift": True,
                        "champion_path": champ_path,
                    },
                    fitness_score=float(fitness_signal),
                    generation=0,
                    mutation_rate=0.0,
                    lineage_hash="birth-freeze-accept",
                )
                twin_res = approval_twin.evaluate_dna_promotion(proxy)
                t_conf = float(twin_res.get("confidence", 0.0) or 0.0)
                t_raw = bool(twin_res.get("recommendation", False))
                t_rec = bool(twin_res.get("effective_recommendation", t_raw))
                twin_mode = str(
                    twin_res.get("mode") or getattr(approval_twin, "mode", "shadow") or "shadow"
                )
                if twin_accept_champion_eligible(
                    cfg=cfg,
                    twin_confidence=t_conf,
                    twin_recommendation=bool(t_rec or t_raw),
                    constitution_violations=int(constitution_violations or 0),
                    champion_path_exists=champ_ok,
                    swarm_rejected_no_lift=True,
                    twin_mode=twin_mode,
                ):
                    autonomy_state.autonomous_recovery_count += 1
                    metrics = autonomy_state.to_metrics()
                    metrics["twin_accept_champion"] = True
                    metrics["twin_confidence"] = round(t_conf, 4)
                    metrics["twin_mode"] = twin_mode
                    return AutonomyDecision(
                        dispatch=RecoveryDispatch.ACCEPT_CHAMPION_RESUME,
                        needs_attention=False,
                        retryable=True,
                        stall_reason=stall_reason,
                        recommended_action="accept_champion",
                        autonomy_metrics=metrics,
                        message=(
                            f"Twin accept_champion (conf={t_conf:.2%}, mode={twin_mode}) "
                            "— keep champion, clear freeze, continue quality ladder."
                        ),
                    )
                # Twin present but not eligible: escalate (human exception), never grind.
                return _twin_escalate_or_notify(
                    approval_twin=approval_twin,
                    autonomy_state=autonomy_state,
                    stall_reason=stall_reason,
                    curriculum_stage=curriculum_stage,
                    fitness_signal=fitness_signal,
                    fork="accept_champion_or_wipe",
                    twin_res=twin_res if isinstance(twin_res, dict) else {},
                    t_conf=t_conf,
                    t_risks=list(twin_res.get("risk_flags") or [])
                    if isinstance(twin_res, dict)
                    else [],
                )
            except Exception:
                logger.debug("birth.twin_accept_champion_failed", exc_info=True)
        return AutonomyDecision(
            dispatch=RecoveryDispatch.TERMINAL_NOTIFY_ONLY,
            needs_attention=True,
            # Not auto-resumable: expand_data / wipe / accept_champion only.
            retryable=False,
            stall_reason=stall_reason,
            autonomy_metrics=autonomy_state.to_metrics(),
            message=(
                "Recovery ladder completed without best-winrate lift and phoenix "
                "budget exhausted — Twin absent/unavailable; operator exception "
                "(accept_champion | wipe). Geen train-through-freeze."
            ),
        )

    circuit_breaker = record_stall_signature(
        autonomy_state.death_spiral,
        curriculum_stage=curriculum_stage,
        blocker_metric=blocker_metric,
        blocker_value=blocker_value,
        cfg=cfg,
    )

    provisional_ok = (
        cfg.allow_provisional_pass
        and cfg.graduation_mode == "evolution_deferred"
        and constitution_violations == 0
        and stage_trades >= required
        and fitness_signal >= float(cfg.provisional_oos_floor)
        and (plateau_exhausted or remediation_cycles_exhausted)
    )
    if provisional_ok:
        return AutonomyDecision(
            dispatch=RecoveryDispatch.PROVISIONAL_GRADUATE,
            needs_attention=False,
            retryable=True,
            stall_reason=stall_reason,
            recommended_action=recommended or "provisional_graduation",
            autonomy_metrics=autonomy_state.to_metrics(),
            message="Provisional graduation granted — evolution deferred path.",
        )

    # === Twin as default in birth-phase autonomy loops when confidence high ===
    # When the ApprovalTwin (trained on Steve labels) is confident, it replaces the
    # human gate. This is the primary 24/7 evolution path.
    # Mode authority: shadow never sole-executes; promotion only via TwinModePromotionGate.
    if approval_twin is not None:
        try:
            from lumina_core.evolution.dna_registry import PolicyDNA

            # Fail-closed mode checkpoint (auto-demote on metric breach before judgment).
            if hasattr(approval_twin, "sync_mode_from_controller"):
                try:
                    approval_twin.sync_mode_from_controller()
                except Exception:
                    pass

            starship = dict(starship_context or {})
            proxy = PolicyDNA.create(
                prompt_id="birth_autonomy_twin_gate",
                version="autonomy",
                content={
                    "stage": curriculum_stage,
                    "stall_reason": stall_reason,
                    "fitness": fitness_signal,
                    "trades": stage_trades,
                    "edgescore": starship.get("edgescore"),
                    "best_edgescore": starship.get("best_edgescore"),
                    "swarm_rejected_no_lift": starship.get("swarm_rejected_no_lift"),
                    "swarm_champion_accepted": starship.get("swarm_champion_accepted"),
                    "swarm_tournament_resolved": bool(swarm_tournament_resolved),
                },
                fitness_score=float(fitness_signal),
                generation=0,
                mutation_rate=0.03,
                lineage_hash="birth-autonomy",
            )
            twin_res = approval_twin.evaluate_dna_promotion(proxy)
            t_conf = float(twin_res.get("confidence", 0.0) or 0.0)
            t_raw = bool(twin_res.get("recommendation", False))
            # Mode authority: use effective_recommendation for auto paths (shadow never executes)
            t_executable = bool(twin_res.get("executable", False))
            t_rec = bool(twin_res.get("effective_recommendation", False))
            if "effective_recommendation" not in twin_res:
                # Legacy twin without mode authority — fail-closed to non-executable
                t_rec = False
                t_executable = False
            t_risks = list(twin_res.get("risk_flags", []) or [])
            twin_mode = str(twin_res.get("mode") or getattr(approval_twin, "mode", "shadow") or "shadow")
            high_conf = t_conf >= 0.80
            from lumina_core.birth.birth_control_plane import twin_continue_eligible

            # Explicit fail-closed subordination of twin: respect constitution_violations already
            # accumulated from BirthConstitutionGuard / trading constitution in this stage.
            # Twin judgment never overrides a detected constitutional violation.
            if (t_rec or t_raw) and int(constitution_violations or 0) > 0:
                t_rec = False
                t_executable = False
                if "prior_constitution_violations" not in t_risks:
                    t_risks.append("prior_constitution_violations")
                high_conf = False

            twin_continue_ok = twin_continue_eligible(
                cfg=cfg,
                twin_mode=twin_mode,
                twin_executable=t_executable,
                twin_confidence=t_conf,
                swarm_resolved=bool(swarm_tournament_resolved),
                constitution_risks=bool(t_risks) or int(constitution_violations or 0) > 0,
            )
            # ADR-0038: One Twin DNA · Dual Authority — birth is explore_pass.
            from lumina_core.evolution.twin_discipline import (
                twin_primary_judgment_for_decision,
                twin_values_role,
            )

            birth_capital_mode = "birth"
            values_role = twin_values_role(birth_capital_mode)
            primary = twin_primary_judgment_for_decision(
                twin_mode=twin_mode,
                twin_confidence=t_conf,
                twin_raw_recommendation=t_raw,
                twin_executable=t_executable,
                twin_effective_recommendation=t_rec,
                capital_mode=birth_capital_mode,
                constitution_violations=int(constitution_violations or 0),
            )

            # ADR-0037/0038: escalate ONLY when values gate is on (not explore_pass).
            # Free SIM/birth: Twin may shadow-score; does not freeze the learn loop.
            failures = list(primary.get("failures") or [])
            authority_only_block = bool(failures) and all(
                f.startswith("mode_")
                or f in {
                    "not_executable",
                    "effective_recommendation_false",
                    "base_training_incomplete",
                    "mode_shadow_propose_only",
                    "mode_not_full_auto_for_primary_approve",
                    "explore_pass_values_not_gating",
                }
                or "mode_" in f
                for f in failures
            )
            if (
                values_role != "explore_pass"
                and not primary.get("primary")
                and not authority_only_block
                and t_conf >= 0.45
                and (t_conf < 0.80 or bool(t_risks))
            ):
                try:
                    from lumina_core.evolution.twin_training_service import TwinTrainingService

                    svc = TwinTrainingService()
                    should, reasons = svc.should_escalate_decision(
                        confidence=t_conf,
                        risk_flags=t_risks,
                        dna_hash=str(getattr(proxy, "hash", "") or "birth_autonomy"),
                    )
                    if should and (t_conf >= 0.55 or bool(t_risks)):
                        esc = svc.create_escalation(
                            dna_hash=str(getattr(proxy, "hash", "") or "birth_autonomy"),
                            confidence=t_conf,
                            risk_flags=t_risks,
                            explanation=str(twin_res.get("explanation") or "")[:300],
                            twin_recommendation=bool(t_raw),
                            doubt_reasons=reasons or ["low_conf"],
                            notify_telegram=True,
                        )
                        metrics = autonomy_state.to_metrics()
                        metrics["twin_escalation_id"] = esc.get("escalation_id")
                        metrics["twin_doubt_reasons"] = reasons
                        return AutonomyDecision(
                            dispatch=RecoveryDispatch.TERMINAL_NOTIFY_ONLY,
                            needs_attention=True,
                            retryable=True,
                            stall_reason=stall_reason,
                            autonomy_metrics=metrics,
                            message=(
                                f"Twin twijfelt (conf={t_conf:.2%}, {reasons}) — "
                                f"advies vóór besluit id={esc.get('escalation_id')} "
                                "(Deck of Telegram). Geen pre-approval van high-conf Twin."
                            ),
                        )
                except Exception:
                    logger.debug("birth.twin_escalation_failed", exc_info=True)

            # Note: the proxy DNA here is synthetic (birth stage metadata). Real trading DNA
            # mutations are always routed through ConstitutionalGuard.check_pre_* + SandboxedMutationExecutor
            # regardless of any twin recommendation (see mutation_pipeline / generation_runner / orchestrator).

            # High-conf Twin VETO stops path only when values gate is active.
            # explore_pass (birth/SIM): Twin preference never blocks the learn loop.
            if values_role != "explore_pass" and high_conf and not t_raw:
                return AutonomyDecision(
                    dispatch=RecoveryDispatch.TERMINAL_NOTIFY_ONLY,
                    needs_attention=False,
                    retryable=False,
                    stall_reason=stall_reason,
                    message=(
                        f"Twin high-conf VETO (conf={t_conf:.2%}, mode={twin_mode}, "
                        f"role={values_role}) — besluit genomen; post-hoc review via Telegram/Deck."
                    ),
                )
            if high_conf and t_raw and not t_executable and values_role != "explore_pass":
                # Propose only / assisted approve — do not sole-auto; fall through to other recovery.
                pass
            elif primary.get("primary") and (
                # ADR-0038: free SIM/birth — Twin preference never gates CONTINUE
                # (constitution already enforced in primary; swarm still required).
                (
                    values_role == "explore_pass"
                    and bool(swarm_tournament_resolved)
                    and int(constitution_violations or 0) == 0
                )
                or (twin_continue_ok and t_rec)
            ):
                autonomy_state.autonomous_recovery_count += 1
                return AutonomyDecision(
                    dispatch=RecoveryDispatch.CONTINUE_LOOP,
                    needs_attention=False,
                    retryable=True,
                    stall_reason=stall_reason,
                    recommended_action=map_recommended_to_service_action(recommended or "resume_stalled_stage"),
                    autonomy_metrics=autonomy_state.to_metrics(),
                    message=(
                        f"Explore-pass CONTINUE (twin shadow conf={t_conf:.2%}, mode={twin_mode})"
                        if values_role == "explore_pass"
                        else (
                            f"Twin high-conf autonomous approval "
                            f"(conf={t_conf:.2%}, mode={twin_mode})"
                        )
                    ),
                )
        except Exception:
            # Never break autonomy on twin error; fall through to cfg logic
            pass
    # ================================================================================

    if _phoenix_eligible(cfg, autonomy_state) and (
        remediation_cycles_exhausted
        or plateau_exhausted
        or stall_reason
        in {
            "plateau_evolution_exhausted",
            "stall_remediation_exhausted",
            PHOENIX_CYCLE_REASON,
        }
    ):
        widen = should_widen_data_horizon(
            autonomy_state.death_spiral,
            phoenix_count=autonomy_state.phoenix.phoenix_count,
            cfg=cfg,
        )
        novelty = select_phoenix_novelty(
            autonomy_state.phoenix,
            cfg=cfg,
            circuit_breaker=widen or circuit_breaker,
        ).value
        if consume_novelty_budget(autonomy_state.death_spiral) or widen:
            reset_after_novelty(autonomy_state.death_spiral, cfg=cfg)
            autonomy_state.autonomous_recovery_count += 1
            service_action = map_recommended_to_service_action(
                "widen_horizon" if novelty == "widen_horizon" else recommended
            )
            if novelty in {"expand_data", "widen_horizon"}:
                service_action = "expand_and_retry"
            metrics = autonomy_state.to_metrics()
            metrics["phoenix_novelty"] = novelty
            metrics["curriculum_stage"] = curriculum_stage
            return AutonomyDecision(
                dispatch=RecoveryDispatch.PHOENIX_RESUME,
                needs_attention=False,
                retryable=True,
                stall_reason=PHOENIX_CYCLE_REASON,
                recommended_action=service_action,
                checkpoint_patch=None,
                autonomy_metrics=metrics,
                message=f"Phoenix cycle requested: {novelty}",
            )

    # Explicit recovery recommendation (meta/recovery engines) — honor before hard terminal.
    if recommended:
        autonomy_state.autonomous_recovery_count += 1
        mapped = map_recommended_to_service_action(recommended)
        return AutonomyDecision(
            dispatch=RecoveryDispatch.CONTINUE_LOOP,
            needs_attention=False,
            retryable=True,
            stall_reason=stall_reason,
            recommended_action=mapped,
            autonomy_metrics=autonomy_state.to_metrics(),
            message=f"Autonomous recovery: {recommended}",
        )

    ladder_exhausted = bool(plateau_exhausted) or stall_reason in {
        "plateau_evolution_exhausted",
        "stall_remediation_exhausted",
    }
    phoenix_gone = not _phoenix_eligible(cfg, autonomy_state)

    # Twin owns expand_data only after phoenix budget is truly gone (never wipe).
    if ladder_exhausted and phoenix_gone:
        if approval_twin is not None:
            try:
                from lumina_core.birth.birth_control_plane import twin_expand_data_eligible
                from lumina_core.evolution.dna_registry import PolicyDNA

                if hasattr(approval_twin, "sync_mode_from_controller"):
                    try:
                        approval_twin.sync_mode_from_controller()
                    except Exception:
                        pass
                proxy = PolicyDNA.create(
                    prompt_id="birth_terminal_expand_data",
                    version="autonomy",
                    content={
                        "stage": curriculum_stage,
                        "stall_reason": stall_reason,
                        "action": "expand_data",
                        "fitness": fitness_signal,
                        "trades": stage_trades,
                    },
                    fitness_score=float(fitness_signal),
                    generation=0,
                    mutation_rate=0.0,
                    lineage_hash="birth-terminal-expand",
                )
                twin_res = approval_twin.evaluate_dna_promotion(proxy)
                t_conf = float(twin_res.get("confidence", 0.0) or 0.0)
                t_raw = bool(twin_res.get("recommendation", False))
                t_rec = bool(twin_res.get("effective_recommendation", t_raw))
                twin_mode = str(
                    twin_res.get("mode") or getattr(approval_twin, "mode", "shadow") or "shadow"
                )
                if twin_expand_data_eligible(
                    cfg=cfg,
                    twin_confidence=t_conf,
                    twin_recommendation=bool(t_rec or t_raw),
                    constitution_violations=int(constitution_violations or 0),
                    twin_mode=twin_mode,
                    plateau_exhausted=True,
                ):
                    autonomy_state.autonomous_recovery_count += 1
                    metrics = autonomy_state.to_metrics()
                    metrics["twin_expand_data"] = True
                    metrics["twin_confidence"] = round(t_conf, 4)
                    metrics["twin_mode"] = twin_mode
                    return AutonomyDecision(
                        dispatch=RecoveryDispatch.PHOENIX_RESUME,
                        needs_attention=False,
                        retryable=True,
                        stall_reason=PHOENIX_CYCLE_REASON,
                        recommended_action="expand_and_retry",
                        autonomy_metrics=metrics,
                        message=(
                            f"Twin expand_data (conf={t_conf:.2%}, mode={twin_mode}) "
                            "— widen horizon, preserve checkpoint, continue Birth."
                        ),
                    )
                return _twin_escalate_or_notify(
                    approval_twin=approval_twin,
                    autonomy_state=autonomy_state,
                    stall_reason=stall_reason,
                    curriculum_stage=curriculum_stage,
                    fitness_signal=fitness_signal,
                    fork="expand_data_or_wipe_genesis",
                    twin_res=twin_res if isinstance(twin_res, dict) else {},
                    t_conf=t_conf,
                    t_risks=list(twin_res.get("risk_flags") or [])
                    if isinstance(twin_res, dict)
                    else [],
                )
            except Exception:
                logger.debug("birth.twin_expand_data_failed", exc_info=True)
        return AutonomyDecision(
            dispatch=RecoveryDispatch.TERMINAL_NOTIFY_ONLY,
            needs_attention=True,
            retryable=False,
            stall_reason=stall_reason,
            recommended_action="expand_data",
            autonomy_metrics=autonomy_state.to_metrics(),
            message=(
                "Plateau exhausted and phoenix budget gone — Twin unavailable; "
                "operator exception (expand_data | wipe). Geen silent auto-resume."
            ),
        )

    # Soft mid-ladder stall: keep organism breathing (not terminal freeze).
    if _phoenix_eligible(cfg, autonomy_state):
        autonomy_state.autonomous_recovery_count += 1
        return AutonomyDecision(
            dispatch=RecoveryDispatch.PHOENIX_RESUME,
            needs_attention=False,
            retryable=True,
            stall_reason=PHOENIX_CYCLE_REASON,
            recommended_action="resume_stalled_stage",
            autonomy_metrics=autonomy_state.to_metrics(),
            message="Autonomous resume after stall.",
        )

    return AutonomyDecision(
        dispatch=RecoveryDispatch.TERMINAL_NOTIFY_ONLY,
        needs_attention=True,
        retryable=False,
        stall_reason=stall_reason or "stage_stalled",
        recommended_action="expand_data",
        autonomy_metrics=autonomy_state.to_metrics(),
        message="Terminal stall — operator exception (expand_data | wipe). Geen blind resume.",
    )

__all__ = [
    "AutonomyDecision",
    "OrganismAutonomyState",
    "PHOENIX_CYCLE_REASON",
    "RecoveryDispatch",
    "evaluate_terminal_stall",
    "map_recommended_to_service_action",
]
