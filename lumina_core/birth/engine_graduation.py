"""Birth engine stage graduation + pass-receipt integrity."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.checkpoint import (
    read_checkpoint_payload,
    write_checkpoint_payload,
)
from lumina_core.birth.curriculum import (
    CurriculumStage,
    is_runway_stage,
    ordered_runway_stages,
    ordered_stages,
)
from lumina_core.birth.graduation_result import GraduationResult
from lumina_core.birth.progress import (
    read_birth_progress,
    write_birth_progress,
)
from lumina_core.birth.stage_pass_receipt import (
    StagePassReceipt,
    audit_curriculum_integrity,
    fresh_stage_metrics_for_stage,
    receipt_for_stage,
    verify_stage_pass_receipt,
)
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.engine")


class EngineGraduationMixin:
    _stages_passed: list[str]
    _stage_pass_receipts: list[StagePassReceipt]
    _pending_stage_pass_receipt: StagePassReceipt | None

    def _stage_metrics_snapshot(
        self,
        *,
        stage_trades: int = 0,
        stage_wins: int = 0,
        stage_hold_signals: int = 0,
        stage_total_signals: int = 0,
        stage_range_hold_signals: int = 0,
        stage_range_total_signals: int = 0,
        stage_range_flat_bars: int = 0,
        stage_range_round_trips: int = 0,
        patterns_mined: int = 0,
        constitution_violations: int | None = None,
    ) -> dict[str, Any]:
        return {
            "stage_trades": int(stage_trades),
            "stage_wins": int(stage_wins),
            "stage_hold_signals": int(stage_hold_signals),
            "stage_total_signals": int(stage_total_signals),
            "stage_range_hold_signals": int(stage_range_hold_signals),
            "stage_range_total_signals": int(stage_range_total_signals),
            "stage_range_flat_bars": int(stage_range_flat_bars),
            "stage_range_round_trips": int(stage_range_round_trips),
            "stage_range_flat_ratio": round(
                float(stage_range_flat_bars) / float(max(1, stage_range_total_signals)),
                4,
            ),
            "patterns_mined": int(patterns_mined),
            "stages_passed": list(self._stages_passed),
            "buffer_size": len(self.buffer),
            "constitution_violations": int(
                self._constitution_guard.violations
                if constitution_violations is None
                else constitution_violations
            ),
        }

    def _apply_curriculum_integrity_audit(self, *, training_mode: str) -> None:
        """Fail-closed: truncate stages_passed without valid pass receipts."""
        audit = audit_curriculum_integrity(
            stages_passed=list(self._stages_passed),
            stage_pass_receipts=list(self._stage_pass_receipts),
            cfg=self.birth_config.curriculum,
            training_mode=training_mode,
        )
        if audit.reset_applied or not audit.ok:
            self._stages_passed = list(audit.stages_passed)
            self._stage_pass_receipts = list(audit.stage_pass_receipts)
            progress_fields = audit.to_progress_fields()
            progress_fields["stages_passed"] = list(self._stages_passed)
            prev = read_birth_progress(self.workspace_root)
            write_birth_progress(
                self.workspace_root,
                stage=str(prev.get("stage", "training_running") or "training_running"),
                phase=str(prev.get("phase", "curriculum_learning") or "curriculum_learning"),
                message=(
                    "Curriculum integrity reset: replaying stage(s) without valid pass receipt."
                    if audit.reset_applied
                    else str(prev.get("message") or "Birth curriculum learning.")
                ),
                progress_pct=float(prev.get("progress_pct", 0) or 0),
                cumulative_trades=self.cumulative_trades,
                target_trades=int(prev.get("target_trades", self.birth_config.trade_budget_cap) or 0),
                ppo_steps=self.ppo_steps,
                birth_start_time=self.birth_start_time or float(prev.get("birth_start_time", 0) or 0),
                **progress_fields,
            )
            payload = read_checkpoint_payload(self.workspace_root)
            if payload:
                payload["stages_passed"] = list(self._stages_passed)
                payload["stage_pass_receipts"] = [r.to_dict() for r in self._stage_pass_receipts]
                write_checkpoint_payload(self.workspace_root, payload)

    def _verify_stage_pass_receipt_for_skip(
        self,
        stage: CurriculumStage,
        *,
        training_mode: str,
    ) -> bool:
        receipt = receipt_for_stage(self._stage_pass_receipts, stage.value)
        ok, reason = verify_stage_pass_receipt(
            stage,
            receipt,
            cfg=self.birth_config.curriculum,
            training_mode=training_mode,
        )
        if ok:
            return True
        logger.warning(
            "birth.stage.pass_invalidated stage=%s reason=%s",
            stage.value,
            reason,
        )
        self._stages_passed = [s for s in self._stages_passed if s != stage.value]
        self._stage_pass_receipts = [r for r in self._stage_pass_receipts if r.stage != stage.value]
        return False

    def _commit_stage_graduation(
        self,
        stage: CurriculumStage,
        *,
        training_mode: str,
        curriculum_stage: str,
        policy_path: str,
        phase: str,
    ) -> GraduationResult:
        # Fail-closed: any constitution violation blocks graduation.
        violations = int(getattr(self._constitution_guard, "violations", 0) or 0)
        if violations > 0:
            if self.event_bus is not None:
                try:
                    from lumina_core.agent_orchestration.schemas import ConstitutionViolation

                    v = ConstitutionViolation(
                        principle_name="birth_constitution_guard",
                        severity="critical",
                        description="violations_detected_on_graduation_attempt",
                        mode="birth",
                    )
                    self.event_bus.publish_validated(
                        topic="safety.constitution.violation",
                        producer="birth.engine",
                        payload=v.model_dump(mode="json"),
                    )
                except Exception:
                    pass
            return GraduationResult(
                ok=False,
                reason=f"constitution_violations_pending:{violations}",
            )

        if self._pending_stage_pass_receipt is not None:
            self._stage_pass_receipts.append(self._pending_stage_pass_receipt)
            self._pending_stage_pass_receipt = None
        self._stages_passed.append(stage.value)
        receipt = receipt_for_stage(self._stage_pass_receipts, stage.value)
        if receipt is not None:
            from lumina_core.notifications.milestone_events import curriculum_stage_passed_event

            self._notify_milestone(curriculum_stage_passed_event(stage, receipt))
        # Stage-2 → Stage-3 handoff: detox weak range prior before mixed regimes.
        if stage == CurriculumStage.STAGE2_RANGE:
            try:
                from lumina_core.birth.stage2_transfer_handoff import (
                    execute_stage2_transfer_handoff,
                )

                s2_trades = 0
                s2_wins = 0
                s2_roll = None
                if receipt is not None:
                    s2_trades = int(getattr(receipt, "trades", 0) or 0)
                    s2_wins = int(getattr(receipt, "wins", 0) or 0)
                    try:
                        s2_roll = getattr(receipt, "rolling_winrate", None)
                        s2_roll = float(s2_roll) if s2_roll is not None else None
                    except (TypeError, ValueError):
                        s2_roll = None
                handoff2 = execute_stage2_transfer_handoff(
                    host=self,
                    cfg=self.birth_config.curriculum,
                    stage_trades=s2_trades,
                    stage_wins=s2_wins,
                    rolling_winrate=s2_roll,
                )
                logger.info(
                    "birth.stage2.graduation_handoff ok=%s wr=%.3f purge=%s reinit=%s",
                    handoff2.get("ok"),
                    float(handoff2.get("stage2_wr") or 0.0),
                    (handoff2.get("buffer_purge") or {}).get("mode"),
                    (handoff2.get("action_head_reinit") or {}).get("ok"),
                )
            except Exception as handoff2_exc:
                logger.warning(
                    "birth.stage2.graduation_handoff_failed: %s", handoff2_exc
                )
        # Stage-1 → Stage-2 hard transfer handoff: cut toxic action prior + buffer.
        # Pass floors unchanged (survival still graduated). Nursery stays growable.
        if stage == CurriculumStage.STAGE1_TREND:
            try:
                from lumina_core.birth.stage1_foundation import (
                    execute_stage1_transfer_handoff,
                )

                s1_trades = 0
                s1_wins = 0
                if receipt is not None:
                    s1_trades = int(getattr(receipt, "trades", 0) or 0)
                    s1_wins = int(getattr(receipt, "wins", 0) or 0)
                handoff = execute_stage1_transfer_handoff(
                    host=self,
                    cfg=self.birth_config.curriculum,
                    stage_trades=s1_trades,
                    stage_wins=s1_wins,
                    edge_vs_random=None,
                )
                logger.info(
                    "birth.stage1.graduation_handoff ok=%s wr=%.3f purge=%s reinit=%s",
                    handoff.get("ok"),
                    float(handoff.get("stage1_wr") or 0.0),
                    (handoff.get("buffer_purge") or {}).get("mode"),
                    (handoff.get("action_head_reinit") or {}).get("ok"),
                )
                # Persist handoff honesty onto birth progress (operator SSOT).
                try:
                    from lumina_core.birth.progress import (
                        read_birth_progress,
                        write_birth_progress,
                    )

                    prev = read_birth_progress(self.workspace_root)
                    write_birth_progress(
                        self.workspace_root,
                        stage=str(
                            prev.get("stage") or "curriculum_stage_complete"
                        ),
                        phase=str(prev.get("phase") or "curriculum_stage_complete"),
                        message=str(
                            prev.get("message")
                            or "Stage1 graduated — transfer handoff complete."
                        ),
                        progress_pct=float(prev.get("progress_pct", 0) or 0),
                        cumulative_trades=int(
                            prev.get("cumulative_trades", self.cumulative_trades) or 0
                        ),
                        target_trades=int(prev.get("target_trades", 0) or 0),
                        ppo_steps=int(prev.get("ppo_steps", self.ppo_steps) or 0),
                        birth_start_time=float(
                            prev.get("birth_start_time", self.birth_start_time or 0)
                            or 0
                        ),
                        stage1_transfer_handoff_ok=bool(handoff.get("ok")),
                        stage1_transfer_purge_mode=str(
                            (handoff.get("buffer_purge") or {}).get("mode") or ""
                        ),
                        stage1_transfer_reinit_ok=bool(
                            (handoff.get("action_head_reinit") or {}).get("ok")
                        ),
                        stage1_transfer_wr=float(handoff.get("stage1_wr") or 0.0),
                    )
                except Exception as prog_exc:
                    logger.debug(
                        "birth.stage1.handoff_progress_persist_failed: %s", prog_exc
                    )
            except Exception as handoff_exc:
                logger.warning(
                    "birth.stage1.graduation_handoff_failed: %s", handoff_exc
                )
        stages = ordered_runway_stages() if is_runway_stage(stage) else ordered_stages()
        try:
            idx = next(i for i, s in enumerate(stages) if s == stage)
        except StopIteration:
            idx = -1
        if idx >= 0 and idx + 1 < len(stages):
            next_stage = stages[idx + 1]
            self._active_stage_metrics = fresh_stage_metrics_for_stage(next_stage)
        elif stage == CurriculumStage.STAGE7_HOLDOUT_PROFILE:
            self._active_stage_metrics = fresh_stage_metrics_for_stage(
                CurriculumStage.STAGE5_PROBE_HANDOFF
            )
        self.ppo_trainer.save_final_birth_policy(str(self.final_policy_path))
        self._persist_checkpoint(
            training_mode=training_mode,
            curriculum_stage=curriculum_stage,
            policy_path=policy_path,
            phase=phase,
        )
        return GraduationResult(ok=True, reason="graduated")
