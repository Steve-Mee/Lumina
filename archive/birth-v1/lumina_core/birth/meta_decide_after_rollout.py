"""meta_decide_after_rollout."""
from __future__ import annotations


from lumina_core.birth.config import BirthRewardConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.meta_controller_signals import (
    _hold_plan,
)
from lumina_core.birth.meta_controller_types import (
    LearningHealth,
    LearningSnapshot,
    MetaActionPlan,
    RecoveryStrategy,
)


class MetaDecideAfterRolloutMixin:
    """decide_after_rollout."""

    def decide_after_rollout(self, snap: LearningSnapshot) -> MetaActionPlan:
        if not self.enabled:
            return _hold_plan(snap, "meta_controller_disabled")

        constitution_plan = self._constitution_remediation_plan(snap)
        if constitution_plan is not None:
            return constitution_plan

        # Proactive twin call (primary auto-approval layer) — best effort.
        # Triggers TwinDecisionEvent on bus when a usable DNA-like context exists.
        # In birth we synthesize a minimal PolicyDNA proxy from snapshot for scoring.
        if self.approval_twin is not None:
            try:
                from lumina_core.evolution.dna_registry import PolicyDNA
                proxy_content = {
                    "birth_stage": getattr(snap, "stage", None),
                    "winrate": float(getattr(snap, "winrate_velocity", 0.0) or 0.0),
                    "trades": int(getattr(snap, "stage_trades", 0) or 0),
                }
                proxy_dna = PolicyDNA.create(
                    prompt_id="birth_meta_proxy",
                    version="birth",
                    content=proxy_content,
                    fitness_score=float(snap.winrate_velocity or 0.5),
                    generation=0,
                    mutation_rate=0.05,
                    lineage_hash="birth",
                )
                _ = self.approval_twin.evaluate_dna_promotion(proxy_dna)
                # Twin signal only. Real DNA paths always enforce via ConstitutionalGuard + sandbox (see ADR-0032 + constitution invariant 1).
            except Exception:
                pass  # never break meta decision

        if snap.learning_health == LearningHealth.IMPROVING and snap.volume_gate_passed:
            reward_tweak = self._apply_reward_tweak(snap)
            if snap.strong_recovery_mode:
                return MetaActionPlan(
                    primary=RecoveryStrategy.HOLD,
                    exit_strong_recovery=True,
                    chunk_target=max(
                        self.cfg.exploration_chunk_size,
                        self.cfg.rollout_chunk_trades,
                    ),
                    reward_tweak=reward_tweak,
                    rationale="velocity_recovered",
                    snapshot=snap,
                )
            return MetaActionPlan(
                primary=RecoveryStrategy.HOLD,
                reward_tweak=reward_tweak,
                rationale="improving_learning",
                snapshot=snap,
            )

        # Stage-1 foundation: anti-thrash / pressure without raising survival pass floor.
        try:
            from lumina_core.birth.curriculum import CurriculumStage as _CS1
            from lumina_core.birth.stage1_foundation import (
                compute_stage1_foundation,
                stage1_foundation_meta_fields,
            )
            from lumina_core.logging_utils import get_logger

            if getattr(snap, "stage", None) == _CS1.STAGE1_TREND and bool(
                getattr(snap, "volume_gate_passed", False)
            ):
                _log_s1 = get_logger("lumina.birth.meta_decide_after_rollout")
                s1 = compute_stage1_foundation(
                    stage_trades=int(getattr(snap, "stage_trades", 0) or 0),
                    stage_wins=int(getattr(snap, "stage_wins", 0) or 0),
                    required=int(getattr(snap, "required_trades", 200) or 200),
                    survival_wr_floor=float(
                        getattr(self.cfg, "birth_survival_wr_floor", 0.20) or 0.20
                    ),
                    foundation_target_wr=float(
                        getattr(self.cfg, "stage1_foundation_target_wr", 0.30) or 0.30
                    ),
                    anti_thrash_wr=float(
                        getattr(self.cfg, "stage1_anti_thrash_wr", 0.25) or 0.25
                    ),
                    edge_vs_random=getattr(snap, "edge_vs_random", None),
                    rolling_winrate=getattr(snap, "rolling_winrate", None),
                )
                s1_fields = stage1_foundation_meta_fields(
                    s1,
                    exploration_steps=int(self.cfg.exploration_steps),
                    strong_recovery_explore_fraction=float(
                        self.cfg.strong_recovery_explore_fraction
                    ),
                    median_loss_r=getattr(snap, "median_loss_r", None),
                )
                if s1_fields is not None:
                    secondary_s1: list[RecoveryStrategy] = []
                    for sec in s1_fields.get("secondary") or ():
                        try:
                            s = RecoveryStrategy(str(sec))
                        except ValueError:
                            continue
                        if s == RecoveryStrategy.EXPLORE_BOOST:
                            continue
                        secondary_s1.append(s)
                    plan_s1 = MetaActionPlan(
                        primary=RecoveryStrategy(
                            str(s1_fields.get("primary") or "explore_reduce")
                        ),
                        secondary=tuple(dict.fromkeys(secondary_s1)),
                        explore_steps=int(
                            s1_fields.get("explore_steps") or self.cfg.exploration_steps
                        ),
                        mine=bool(s1_fields.get("mine")),
                        escalation_delta=int(s1_fields.get("escalation_delta") or 1),
                        explore_steps_multiplier=max(
                            0.4, min(1.0, float(self.cfg.meta_explore_decay_stall))
                        ),
                        rationale=str(
                            s1_fields.get("rationale") or "stage1_foundation_after_rollout"
                        ),
                        snapshot=snap,
                    )
                    self._record_plan(plan_s1)
                    _log_s1.info(
                        "birth.meta.stage1_foundation path=take wr=%.3f gap=%.3f thrash=%s",
                        s1.winrate,
                        s1.learning_gap,
                        s1.anti_thrash,
                    )
                    return plan_s1
        except Exception as s1_exc:
            from lumina_core.logging_utils import get_logger

            get_logger("lumina.birth.meta_decide_after_rollout").debug(
                "birth.meta.stage1_foundation skip err=%s", s1_exc
            )

        # Stage-2: pass-vector is the single multi-blocker controller (then quality).
        try:
            from lumina_core.birth.stage2_pass_vector import plan_stage2_from_snapshot
            from lumina_core.logging_utils import get_logger

            _log = get_logger("lumina.birth.meta_decide_after_rollout")
            fields = plan_stage2_from_snapshot(snap, cfg=self.cfg)
            if fields is not None and str(fields.get("primary") or "") not in {"", "hold"}:
                secondary_q: list[RecoveryStrategy] = []
                for sec in fields.get("secondary") or ():
                    try:
                        s = RecoveryStrategy(str(sec))
                    except ValueError:
                        continue
                    if s == RecoveryStrategy.EXPLORE_BOOST:
                        continue
                    secondary_q.append(s)
                reward_tweak_q = self._apply_reward_tweak(snap)
                if (
                    reward_tweak_q is not None
                    and RecoveryStrategy.REWARD_SHAPING_TWEAK not in secondary_q
                ):
                    secondary_q.append(RecoveryStrategy.REWARD_SHAPING_TWEAK)
                primary_s = str(fields.get("primary") or "explore_reduce")
                if primary_s in {"explore_boost", "EXPLORE_BOOST"}:
                    primary_s = "explore_reduce"
                plan_q = MetaActionPlan(
                    primary=RecoveryStrategy(primary_s),
                    secondary=tuple(dict.fromkeys(secondary_q)),
                    explore_steps=int(fields.get("explore_steps") or self.cfg.exploration_steps),
                    mine=bool(fields.get("mine")),
                    mine_aggressive=bool(fields.get("mine")),
                    reward_tweak=reward_tweak_q,
                    escalation_delta=int(fields.get("escalation_delta") or 1),
                    explore_steps_multiplier=float(
                        fields.get("explore_steps_multiplier")
                        or max(0.4, min(1.0, float(self.cfg.meta_explore_decay_stall)))
                    ),
                    rationale=str(fields.get("rationale") or "pass_vector_after_rollout"),
                    snapshot=snap,
                )
                self.explore_multiplier = max(
                    0.4, min(1.0, float(self.cfg.meta_explore_decay_stall))
                )
                self._record_plan(plan_q)
                _log.info(
                    "birth.meta.pass_vector path=take trigger=after_rollout primary=%s action=%s",
                    plan_q.primary.value,
                    fields.get("pass_vector_action"),
                )
                return plan_q
        except Exception as exc:
            from lumina_core.logging_utils import get_logger

            get_logger("lumina.birth.meta_decide_after_rollout").warning(
                "birth.meta.expectancy_quality path=error trigger=after_rollout err=%s",
                exc,
            )
            try:
                from lumina_core.birth.expectancy_stall import build_expectancy_quality_meta_fields

                fields = build_expectancy_quality_meta_fields(
                    range_flat_ratio=float(getattr(snap, "range_flat_ratio", 0.5) or 0.5),
                    remediation_step=0,
                    base_explore_steps=int(self.cfg.exploration_steps),
                    exploration_steps=int(self.cfg.exploration_steps),
                )
                plan_fc = MetaActionPlan(
                    primary=RecoveryStrategy.EXPLORE_REDUCE,
                    secondary=(RecoveryStrategy.REWARD_SHAPING_TWEAK,),
                    explore_steps=int(fields["explore_steps"]),
                    mine=True,
                    rationale="stage2_expectancy_failclosed",
                    snapshot=snap,
                )
                self._record_plan(plan_fc)
                return plan_fc
            except Exception:
                pass

        # Stage-2/3 expectancy stall owns after_rollout (pass-vector is Stage-2 only).
        try:
            from lumina_core.birth.expectancy_stall import (
                build_expectancy_quality_meta_fields,
                snapshot_expectancy_stall,
            )

            if snapshot_expectancy_stall(snap, cfg=self.cfg):
                quality_step = int(getattr(snap, "expectancy_quality_step", 0) or 0)
                if quality_step <= 0:
                    quality_step = max(0, int(getattr(snap, "escalation_level", 0) or 0))
                edge_vr = getattr(snap, "edge_vs_random", None)
                try:
                    edge_vr_f = float(edge_vr) if edge_vr is not None else None
                except (TypeError, ValueError):
                    edge_vr_f = None
                qf = build_expectancy_quality_meta_fields(
                    range_flat_ratio=float(getattr(snap, "range_flat_ratio", 0.5) or 0.5),
                    remediation_step=quality_step,
                    base_explore_steps=int(self.cfg.exploration_steps),
                    exploration_steps=int(self.cfg.exploration_steps),
                    strong_recovery_explore_fraction=float(
                        self.cfg.strong_recovery_explore_fraction
                    ),
                    edge_vs_random=edge_vr_f,
                )
                secondary_stall: list[RecoveryStrategy] = []
                for sec in qf.get("secondary") or ():
                    try:
                        s = RecoveryStrategy(str(sec))
                    except ValueError:
                        continue
                    if s == RecoveryStrategy.EXPLORE_BOOST:
                        continue
                    secondary_stall.append(s)
                primary_stall = str(qf.get("primary") or "explore_reduce")
                if primary_stall in {"explore_boost", "EXPLORE_BOOST"}:
                    primary_stall = "explore_reduce"
                plan_stall = MetaActionPlan(
                    primary=RecoveryStrategy(primary_stall),
                    secondary=tuple(dict.fromkeys(secondary_stall)),
                    explore_steps=int(qf.get("explore_steps") or self.cfg.exploration_steps),
                    mine=bool(qf.get("mine")),
                    escalation_delta=int(qf.get("escalation_delta") or 1),
                    explore_steps_multiplier=max(
                        0.4, min(1.0, float(self.cfg.meta_explore_decay_stall))
                    ),
                    rationale=str(qf.get("rationale") or "stage_expectancy_after_rollout"),
                    snapshot=snap,
                )
                self._record_plan(plan_stall)
                return plan_stall
        except Exception:
            pass

        if not snap.is_stalled:
            return _hold_plan(snap)

        # Stage-2/3: never default velocity-stall path to explore_boost thrash.
        if snap.stage in (
            CurriculumStage.STAGE2_RANGE,
            CurriculumStage.STAGE3_MIXED,
        ) and snap.volume_gate_passed:
            plan_s2 = MetaActionPlan(
                primary=RecoveryStrategy.EXPLORE_REDUCE,
                secondary=(RecoveryStrategy.PATTERN_INJECT, RecoveryStrategy.REWARD_SHAPING_TWEAK),
                mine=True,
                explore_steps_multiplier=max(
                    0.4, min(1.0, float(self.cfg.meta_explore_decay_stall))
                ),
                rationale="stage2_stall_quality_not_explore_boost"
                if snap.stage == CurriculumStage.STAGE2_RANGE
                else "stage3_stall_quality_not_explore_boost",
                snapshot=snap,
            )
            self._record_plan(plan_s2)
            return plan_s2

        primary = RecoveryStrategy.EXPLORE_BOOST
        secondary: list[RecoveryStrategy] = []
        mine = False
        mine_aggressive = False
        expand_data = False
        enter_strong = False
        escalation_delta = 0
        chunk_target: int | None = None
        intra_delta: float | None = None
        reward_tweak: BirthRewardConfig | None = None
        rationale = "velocity_stall"

        if snap.thin_buffer and not snap.data_exhausted:
            primary = RecoveryStrategy.DATA_EXPANSION
            expand_data = True
            rationale = "stall_thin_buffer_expand_data"
        elif (
            snap.pattern_quality < float(self.cfg.meta_pattern_yield_floor)
            and int(getattr(snap, "patterns_mined", 0) or 0) <= 0
            and int(snap.stage_trades) >= max(1, int(snap.required_trades))
        ):
            # Anti-thrash: low pattern yield with zero mined patterns = dead inject button.
            if not snap.data_exhausted:
                primary = RecoveryStrategy.DATA_EXPANSION
                expand_data = True
                secondary.append(RecoveryStrategy.INTRA_EASE)
                rationale = "stall_empty_patterns_expand"
            else:
                primary = RecoveryStrategy.EXPLORE_BOOST
                secondary.append(RecoveryStrategy.INTRA_EASE)
                rationale = "stall_empty_patterns_explore"
        elif snap.pattern_quality < float(self.cfg.meta_pattern_yield_floor):
            primary = RecoveryStrategy.PATTERN_INJECT_AGGRESSIVE
            mine = True
            mine_aggressive = True
            rationale = "stall_low_pattern_yield"
        elif snap.volume_gate_passed:
            primary = RecoveryStrategy.EXPLORE_REDUCE
            enter_strong = True
            escalation_delta = int(self.cfg.strong_recovery_escalation_boost)
            chunk_target = max(
                self.cfg.exploration_chunk_size,
                self.cfg.exploration_chunk_size * 2,
            )
            mine = True
            mine_aggressive = True
            rationale = "stall_enter_strong_recovery"
        else:
            primary = RecoveryStrategy.EXPLORE_BOOST
            secondary.append(RecoveryStrategy.PATTERN_INJECT)
            mine = True
            escalation_delta = 1
            rationale = "stall_pre_volume_gate"

        if (
            snap.pattern_quality >= float(self.cfg.meta_pattern_yield_floor)
            and snap.winrate_velocity <= 0.0
        ):
            secondary.append(RecoveryStrategy.REWARD_SHAPING_TWEAK)
            reward_tweak = self._apply_reward_tweak(snap)

        if (
            snap.learning_health == LearningHealth.FLAT
            and snap.volume_gate_passed
            and snap.stage == CurriculumStage.STAGE1_TREND
            and snap.intra_hard_pct is not None
            and snap.intra_hard_pct > self.cfg.intra_initial_hard_pct
        ):
            intra_delta = -float(self.cfg.intra_hard_pct_step)
            secondary.append(RecoveryStrategy.INTRA_EASE)

        if snap.strong_recovery_mode:
            expand_every = int(self.cfg.strong_recovery_expand_every_attempts)
            if snap.strong_recovery_attempts > 0 and snap.strong_recovery_attempts % expand_every == 0:
                expand_data = True
                mine = True
                mine_aggressive = True
                if RecoveryStrategy.DATA_EXPANSION not in secondary:
                    secondary.append(RecoveryStrategy.DATA_EXPANSION)

        plan = MetaActionPlan(
            primary=primary,
            secondary=tuple(dict.fromkeys(secondary)),
            chunk_target=chunk_target,
            escalation_delta=escalation_delta,
            mine=mine,
            mine_aggressive=mine_aggressive,
            expand_data=expand_data,
            reward_tweak=reward_tweak,
            intra_hard_pct_delta=intra_delta,
            enter_strong_recovery=enter_strong and not snap.strong_recovery_mode,
            explore_steps_multiplier=1.0 if enter_strong else self.explore_multiplier,
            rationale=rationale,
            snapshot=snap,
        )
        if enter_strong and not snap.strong_recovery_mode:
            self.explore_multiplier = max(
                0.4,
                min(1.0, float(self.cfg.meta_explore_decay_stall)),
            )
        self._record_plan(plan)
        return plan
