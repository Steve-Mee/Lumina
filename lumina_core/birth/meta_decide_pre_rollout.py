"""meta_decide_pre_rollout."""
from __future__ import annotations


from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.meta_controller_types import (
    LearningHealth,
    LearningSnapshot,
    MetaActionPlan,
    RecoveryStrategy,
)


class MetaDecidePreRolloutMixin:
    """decide_pre_rollout."""

    def decide_pre_rollout(
        self,
        snap: LearningSnapshot,
        *,
        base_explore_steps: int,
        wall_budget_exhausted: bool,
        winrate_stagnation_count: int,
        hold_stagnation_count: int,
        over_trading_trap: bool = False,
    ) -> MetaActionPlan:
        if not self.enabled:
            return MetaActionPlan(
                primary=RecoveryStrategy.HOLD,
                explore_steps=base_explore_steps,
                snapshot=snap,
            )

        constitution_plan = self._constitution_remediation_plan(snap)
        if constitution_plan is not None:
            return constitution_plan

        explore_steps = base_explore_steps
        explore_fraction: float | None = None
        escalation_delta = 0
        primary = RecoveryStrategy.HOLD
        secondary: list[RecoveryStrategy] = []
        rationale = "default_rollout"
        force_mine = False

        if snap.strong_recovery_mode:
            explore_fraction = float(self.cfg.strong_recovery_explore_fraction)
            explore_steps = max(
                200,
                int(self.cfg.exploration_steps * explore_fraction),
            )
            primary = RecoveryStrategy.EXPLORE_REDUCE
            rationale = "strong_recovery_exploit"
        elif (
            snap.stage == CurriculumStage.STAGE1_TREND
            and snap.volume_gate_passed
            and bool(getattr(self.cfg, "stage1_foundation_pressure_enabled", True))
        ):
            from lumina_core.birth.stage1_foundation import (
                compute_stage1_foundation,
                stage1_foundation_meta_fields,
            )

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
            s1f = stage1_foundation_meta_fields(
                s1,
                exploration_steps=int(self.cfg.exploration_steps),
                strong_recovery_explore_fraction=float(
                    self.cfg.strong_recovery_explore_fraction
                ),
                median_loss_r=getattr(snap, "median_loss_r", None),
            )
            if s1f is not None:
                primary = RecoveryStrategy(str(s1f.get("primary") or "explore_reduce"))
                if primary == RecoveryStrategy.EXPLORE_BOOST:
                    primary = RecoveryStrategy.EXPLORE_REDUCE
                for sec in s1f.get("secondary") or ():
                    try:
                        s = RecoveryStrategy(str(sec))
                    except ValueError:
                        continue
                    if s == RecoveryStrategy.EXPLORE_BOOST:
                        continue
                    secondary.append(s)
                explore_steps = max(
                    explore_steps, int(s1f.get("explore_steps") or explore_steps)
                )
                escalation_delta = max(
                    escalation_delta, int(s1f.get("escalation_delta") or 1)
                )
                force_mine = bool(s1f.get("mine"))
                rationale = str(s1f.get("rationale") or "stage1_foundation_pre_rollout")
        elif snap.stage in (
            CurriculumStage.STAGE2_RANGE,
            CurriculumStage.STAGE3_MIXED,
        ) and (
            snap.volume_gate_passed
            or snap.stage == CurriculumStage.STAGE3_MIXED
        ):
            from lumina_core.birth.expectancy_stall import (
                build_expectancy_quality_meta_fields,
                snapshot_expectancy_stall,
            )
            from lumina_core.birth.stage2_pass_vector import plan_stage2_from_snapshot

            flat = float(getattr(snap, "range_flat_ratio", 0.0) or 0.0)
            # Stage-3: occupancy first — skip pass-vector inject thrash when over-trading.
            stage3_over_trade = (
                snap.stage == CurriculumStage.STAGE3_MIXED
                and flat < 0.25
                and int(getattr(snap, "range_total_signals", 0) or 0) >= 50
            )
            if stage3_over_trade:
                explore_steps = max(
                    200,
                    int(
                        self.cfg.exploration_steps
                        * self.cfg.strong_recovery_explore_fraction
                    ),
                )
                primary = RecoveryStrategy.EXPLORE_REDUCE
                secondary = [RecoveryStrategy.REWARD_SHAPING_TWEAK]
                force_mine = False
                escalation_delta = 1
                rationale = "stage3_over_trading"
            # Pass-vector single controller first (multi-blocker) — Stage-2 primarily.
            try:
                pv_fields = (
                    plan_stage2_from_snapshot(snap, cfg=self.cfg)
                    if snap.stage == CurriculumStage.STAGE2_RANGE
                    else None
                )
            except Exception:
                pv_fields = None
            if (
                not stage3_over_trade
                and pv_fields is not None
                and str(pv_fields.get("primary") or "") not in {"", "hold"}
            ):
                try:
                    primary = RecoveryStrategy(str(pv_fields.get("primary") or "explore_reduce"))
                    if primary == RecoveryStrategy.EXPLORE_BOOST:
                        primary = RecoveryStrategy.EXPLORE_REDUCE
                    for sec in pv_fields.get("secondary") or ():
                        try:
                            s = RecoveryStrategy(str(sec))
                        except ValueError:
                            continue
                        if s == RecoveryStrategy.EXPLORE_BOOST:
                            continue
                        secondary.append(s)
                    explore_steps = max(
                        explore_steps, int(pv_fields.get("explore_steps") or explore_steps)
                    )
                    escalation_delta = max(
                        escalation_delta, int(pv_fields.get("escalation_delta") or 1)
                    )
                    force_mine = bool(pv_fields.get("mine"))
                    rationale = str(
                        pv_fields.get("rationale") or "pass_vector_pre_rollout"
                    )
                except Exception:
                    primary = RecoveryStrategy.EXPLORE_REDUCE
                    secondary = [RecoveryStrategy.REWARD_SHAPING_TWEAK]
                    force_mine = True
                    rationale = "pass_vector_failclosed"
                    escalation_delta = max(escalation_delta, 1)
            elif not stage3_over_trade:
                try:
                    exp_stall = snapshot_expectancy_stall(snap, cfg=self.cfg)
                except Exception:
                    exp_stall = False
                # Quality ownership: Stage-2 in-band stall OR Stage-3 hygiene gap (any flat).
                quality_flat_ok = (
                    0.25 <= flat <= 0.75
                    if snap.stage == CurriculumStage.STAGE2_RANGE
                    else True
                )
                if exp_stall and quality_flat_ok:
                    try:
                        quality_step = int(getattr(snap, "expectancy_quality_step", 0) or 0)
                        if quality_step <= 0:
                            quality_step = max(0, int(getattr(snap, "escalation_level", 0) or 0))
                        edge_vr = getattr(snap, "edge_vs_random", None)
                        try:
                            edge_vr_f = float(edge_vr) if edge_vr is not None else None
                        except (TypeError, ValueError):
                            edge_vr_f = None
                        fields = build_expectancy_quality_meta_fields(
                            range_flat_ratio=flat,
                            remediation_step=quality_step,
                            base_explore_steps=explore_steps,
                            exploration_steps=int(self.cfg.exploration_steps),
                            strong_recovery_explore_fraction=float(
                                self.cfg.strong_recovery_explore_fraction
                            ),
                            edge_vs_random=edge_vr_f,
                        )
                        primary = RecoveryStrategy(str(fields.get("primary") or "explore_reduce"))
                        for sec in fields.get("secondary") or ():
                            try:
                                s = RecoveryStrategy(str(sec))
                            except ValueError:
                                continue
                            if s == RecoveryStrategy.EXPLORE_BOOST:
                                continue
                            secondary.append(s)
                        explore_steps = max(
                            explore_steps, int(fields.get("explore_steps") or explore_steps)
                        )
                        escalation_delta = max(
                            escalation_delta, int(fields.get("escalation_delta") or 1)
                        )
                        force_mine = bool(fields.get("mine"))
                        rationale = str(
                            fields.get("rationale") or "stage2_expectancy_quality"
                        )
                    except Exception:
                        primary = RecoveryStrategy.EXPLORE_REDUCE
                        secondary = [RecoveryStrategy.REWARD_SHAPING_TWEAK]
                        force_mine = True
                        rationale = "stage2_expectancy_failclosed"
                        escalation_delta = max(escalation_delta, 1)
                elif over_trading_trap or (
                    float(getattr(snap, "range_flat_ratio", 0.5) or 0.5) < 0.25
                    and int(getattr(snap, "range_total_signals", 0) or 0) >= 50
                ):
                    # Over-trading (flat≪30%): never flood pattern_inject — suppress churn.
                    explore_steps = max(
                        200,
                        int(
                            self.cfg.exploration_steps
                            * self.cfg.strong_recovery_explore_fraction
                        ),
                    )
                    primary = RecoveryStrategy.EXPLORE_REDUCE
                    secondary = [RecoveryStrategy.REWARD_SHAPING_TWEAK]
                    force_mine = False
                    escalation_delta = 1
                    stage_s = str(getattr(getattr(snap, "stage", None), "value", "") or "")
                    rationale = (
                        "stage3_over_trading"
                        if "stage3" in stage_s
                        else "stage2_over_trading"
                    )
                elif flat > 0.70:
                    # Under-activity: selective quality when anti-edge, else explore.
                    edge_ua = getattr(snap, "edge_vs_random", None)
                    try:
                        edge_ua_f = float(edge_ua) if edge_ua is not None else None
                    except (TypeError, ValueError):
                        edge_ua_f = None
                    if edge_ua_f is not None and edge_ua_f < -1e-12:
                        explore_steps = max(explore_steps, self.cfg.exploration_steps)
                        primary = RecoveryStrategy.EXPLORE_REDUCE
                        secondary = [RecoveryStrategy.PATTERN_INJECT]
                        force_mine = True
                        escalation_delta = max(escalation_delta, 1)
                        rationale = "stage2_under_activity_selective_quality"
                    else:
                        explore_steps = max(explore_steps, self.cfg.exploration_steps * 3)
                        primary = RecoveryStrategy.EXPLORE_BOOST
                        escalation_delta = max(escalation_delta, 1)
                        rationale = "stage2_under_activity_ban_hold"
                elif hold_stagnation_count >= self.cfg.stage2_hold_stagnation_rollouts:
                    explore_steps = max(explore_steps, self.cfg.exploration_steps * 4)
                    primary = RecoveryStrategy.EXPLORE_BOOST
                    escalation_delta = 1
                    rationale = "stage2_hold_stagnation"
                elif flat <= 0.40:
                    quality_step = int(getattr(snap, "expectancy_quality_step", 0) or 0)
                    fields = build_expectancy_quality_meta_fields(
                        range_flat_ratio=flat,
                        remediation_step=quality_step,
                        base_explore_steps=explore_steps,
                        exploration_steps=int(self.cfg.exploration_steps),
                        strong_recovery_explore_fraction=float(
                            self.cfg.strong_recovery_explore_fraction
                        ),
                    )
                    primary = RecoveryStrategy(str(fields.get("primary") or "explore_reduce"))
                    for sec in fields.get("secondary") or ():
                        try:
                            s = RecoveryStrategy(str(sec))
                        except ValueError:
                            continue
                        if s == RecoveryStrategy.EXPLORE_BOOST:
                            continue
                        secondary.append(s)
                    explore_steps = max(
                        explore_steps, int(fields.get("explore_steps") or explore_steps)
                    )
                    escalation_delta = max(
                        escalation_delta, int(fields.get("escalation_delta") or 1)
                    )
                    force_mine = bool(fields.get("mine"))
                    rationale = str(fields.get("rationale") or "stage2_expectancy_soft")
                elif wall_budget_exhausted:
                    explore_steps = max(explore_steps, self.cfg.exploration_steps * 4)
                    primary = RecoveryStrategy.EXPLORE_BOOST
                    escalation_delta = 1
                    rationale = "wall_budget_exhausted"
        elif wall_budget_exhausted:
            explore_steps = max(explore_steps, self.cfg.exploration_steps * 4)
            primary = RecoveryStrategy.EXPLORE_BOOST
            escalation_delta = 1
            rationale = "wall_budget_exhausted"
        elif (
            snap.stage == CurriculumStage.STAGE1_TREND
            and snap.volume_gate_passed
            and winrate_stagnation_count >= self.cfg.stage1_winrate_stagnation_rollouts
        ):
            explore_steps = max(explore_steps, self.cfg.exploration_steps * 4)
            primary = RecoveryStrategy.EXPLORE_BOOST
            secondary.append(RecoveryStrategy.PATTERN_INJECT)
            escalation_delta = 1
            rationale = "stage1_winrate_stagnation"

        if snap.learning_health == LearningHealth.IMPROVING and not snap.strong_recovery_mode:
            escalation_delta = min(escalation_delta, -1)

        mine = bool(
            force_mine
            or RecoveryStrategy.PATTERN_INJECT in secondary
            or primary
            in {
                RecoveryStrategy.PATTERN_INJECT,
                RecoveryStrategy.PATTERN_INJECT_AGGRESSIVE,
            }
        )
        # Never attach explore_boost secondary under Stage-2 expectancy quality rationales.
        if "stage2_expectancy" in rationale or rationale.startswith("stage2_"):
            secondary = [s for s in secondary if s != RecoveryStrategy.EXPLORE_BOOST]
        plan = MetaActionPlan(
            primary=primary,
            secondary=tuple(secondary),
            explore_steps=explore_steps,
            explore_fraction=explore_fraction,
            escalation_delta=escalation_delta,
            mine=mine,
            rationale=rationale,
            snapshot=snap,
        )
        # Record pre-rollout quality decisions so history matches scorecard.
        if "stage2_expectancy" in rationale or "stage2_" in rationale:
            try:
                self._record_plan(plan)
            except Exception:
                pass
        return plan
