"""Birth Phase v2 orchestrator (ADR-0012/0013/0014)."""

from __future__ import annotations

import random
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lumina_core.birth.birth_constitution_guard import BirthConstitutionGuard
from lumina_core.birth.checkpoint import (
    read_checkpoint_payload,
    write_checkpoint_payload,
)
from lumina_core.birth.config import (
    BirthCurriculumConfig,
    load_birth_v2_config,
)
from lumina_core.birth.constitution_enforcer import ConstitutionEnforcer
from lumina_core.birth.curriculum_orchestrator import CurriculumOrchestrator
from lumina_core.birth.curriculum_stage_handler import create_and_attach_stage_handler
from lumina_core.birth.curriculum import (
    CurriculumStage,
    Stage1IntraCurriculumState,
    Stage2IntraCurriculumState,
    is_runway_stage,
    ordered_runway_stages,
    ordered_stages,
    sample_intra_stage1_pool,
    sample_intra_stage2_pool,
    should_gen0_soft_pass,
)
from lumina_core.birth.certificate_pipeline import BirthCertificatePipeline
from lumina_core.birth.graduation_result import GraduationResult
from lumina_core.birth.checkpoint_coordinator import BirthCheckpointCoordinator
from lumina_core.birth.data_pipeline import (
    BirthDataPipeline,
    generate_synthetic_ticks,
    train_hash,
)
from lumina_core.birth.progress_reporter import BirthProgressReporter
from lumina_core.birth.birth_bus_client import BirthBusClient
from lumina_core.birth.birth_handler_registry import BirthHandlerRegistry
from lumina_core.birth.meta_controller import StallDetectionResult
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
from lumina_core.hardware_intelligence import HARDWARE_PROFILES
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.engine")


@dataclass(frozen=True, slots=True)
class ProvisionalPassDecision:
    should_grant: bool
    reason: str
    blocked_reason: str | None
    safeguards: dict[str, bool]


@dataclass(slots=True)
class TrajectoryBuffer:
    capacity: int = 500_000
    trajectories: list[dict[str, Any]] = field(default_factory=list)
    priorities: list[float] = field(default_factory=list)

    def add(self, trajectory: dict[str, Any], priority: float = 1.0) -> None:
        if len(self.trajectories) >= self.capacity:
            self.trajectories.pop(0)
            self.priorities.pop(0)
        self.trajectories.append(trajectory)
        self.priorities.append(priority)

    def sample(self, batch_size: int) -> list[dict[str, Any]]:
        if not self.trajectories:
            return []
        import numpy as np

        idx = np.random.choice(len(self.trajectories), size=min(batch_size, len(self.trajectories)), replace=False)
        return [self.trajectories[int(i)] for i in idx]

    def __len__(self) -> int:
        return len(self.trajectories)

    def clear(self) -> None:
        self.trajectories.clear()
        self.priorities.clear()


class BirthPhaseEngineV2:
    def __init__(
        self,
        runtime: Any = None,
        ppo_trainer: Any = None,
        market_data_service: Any = None,
        config: dict[str, Any] | None = None,
        workspace_root: str | Path = Path.cwd(),
        stop_event: threading.Event | None = None,
    ) -> None:
        self.runtime = runtime
        self.ppo_trainer = ppo_trainer
        self.market_data_service = market_data_service
        self.config = config or {}
        self.workspace_root = Path(workspace_root)
        self.stop_event = stop_event
        self.birth_config = load_birth_v2_config(self.workspace_root)
        self.cumulative_trades = 0
        self.ppo_steps = 0
        self.birth_start_time = 0.0
        self.buffer = TrajectoryBuffer()
        self.current_policy: Any = None
        self._stages_passed: list[str] = []
        self._stage_pass_receipts: list[StagePassReceipt] = []
        self._pending_stage_pass_receipt: StagePassReceipt | None = None
        self._real_data_pct = 0.0
        self._data_manifest: dict[str, Any] = {}
        self._last_raw_ticks_hash: str = ""
        self._remediation_attempt = 0
        self._last_checkpoint_at = 0.0
        self._active_stage_metrics: dict[str, Any] = {}
        self._hardware_profile_payload: dict[str, Any] | None = None
        event_bus = getattr(runtime, "event_bus", None)
        if event_bus is None:
            # Ensure birth always has a bus for event-driven orchestration and fail-closed.
            from lumina_core.agent_orchestration.event_bus import EventBus as _EventBus

            event_bus = _EventBus()
        self._constitution_guard = BirthConstitutionGuard(event_bus=event_bus, mode="birth")
        self._constitution_violations_cumulative = 0
        self._trade_budget_source = "birth_v2.trade_budget_cap"

        # Central EventBus wiring for thin curriculum orchestration (ADR-0001)
        self.event_bus = event_bus
        self._curriculum_orchestrator: CurriculumOrchestrator | None = None
        self._constitution_enforcer: ConstitutionEnforcer | None = None
        self._stage_handler: Any | None = None
        self._birth_handler_registry: BirthHandlerRegistry | None = None
        self._birth_bus_client: BirthBusClient | None = None
        try:
            self._curriculum_orchestrator = CurriculumOrchestrator(self.event_bus)
            self._constitution_enforcer = ConstitutionEnforcer(self.event_bus)
            self._constitution_enforcer.attach()
            self._birth_handler_registry = BirthHandlerRegistry(
                self.event_bus,
                self.birth_config.curriculum,
                self.birth_config.reward,
            )
            self._birth_handler_registry.attach_all()
            self._birth_bus_client = BirthBusClient(
                self.event_bus,
                self.birth_config.curriculum,
                self.birth_config.reward,
                registry=self._birth_handler_registry,
            )
            # Attach dedicated stage execution handler (owns the moved curriculum logic)
            self._stage_handler = create_and_attach_stage_handler(self.event_bus, self)
        except Exception:
            logger.warning("birth.event_bus wiring for CurriculumOrchestrator failed; falling back to direct path")
            self._curriculum_orchestrator = None

        self.completion_flag_path = self.workspace_root / "state" / "lumina_birth_completed.flag"
        self.legacy_completion_flag_path = self.workspace_root / "state" / "first_boot_completed.flag"
        self.final_policy_path = self.workspace_root / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
        self.practice_policy_path = self.workspace_root / "lumina_agents" / "ppo" / "lumina_ppo_policy_practice.zip"
        self.pause_flag_path = self.workspace_root / "state" / "first_boot_pause_requested"
        self.practice_completed_flag_path = self.workspace_root / "state" / "lumina_birth_practice_completed.flag"

    def _load_workspace_yaml(self) -> dict[str, Any]:
        cfg_path = self.workspace_root / "config.yaml"
        if not cfg_path.is_file():
            return {}
        try:
            import yaml

            loaded = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            return loaded if isinstance(loaded, dict) else {}
        except Exception:
            return {}

    def _allow_minimal_synthetic_fallback(self) -> bool:
        first_boot = self.config.get("first_boot")
        if isinstance(first_boot, dict) and "allow_minimal_synthetic_fallback" in first_boot:
            return bool(first_boot.get("allow_minimal_synthetic_fallback"))
        yaml_cfg = self._load_workspace_yaml()
        section = yaml_cfg.get("first_boot")
        if isinstance(section, dict):
            return bool(section.get("allow_minimal_synthetic_fallback", False))
        return False

    def _constitution_progress_fields(self) -> dict[str, int]:
        session = int(self._constitution_guard.violations)
        cumulative = int(self._constitution_violations_cumulative) + session
        return {
            "constitution_violations": cumulative,
            "constitution_violations_session": session,
            "constitution_violations_cumulative": cumulative,
        }

    def _budget_progress_fields(self, *, terminal_stall_reason: str | None = None) -> dict[str, Any]:
        cap = int(self.birth_config.trade_budget_cap)
        cumulative = int(self.cumulative_trades)
        fields: dict[str, Any] = {
            "trade_budget_cap": cap,
            "trade_budget_remaining": max(0, cap - cumulative),
            "trade_budget_source": str(self._trade_budget_source),
        }
        if terminal_stall_reason:
            fields["terminal_stall_reason"] = terminal_stall_reason
        return fields

    def _accumulate_constitution_violations_before_stage_reset(self) -> None:
        self._constitution_violations_cumulative += int(self._constitution_guard.violations)
        self._constitution_guard.reset()

    def _stop_requested(self) -> bool:
        if self.stop_event is not None and self.stop_event.is_set():
            return True
        return self.pause_flag_path.exists()

    def _data_pipeline(self) -> BirthDataPipeline:
        return BirthDataPipeline(self)

    def _progress_reporter(self) -> BirthProgressReporter:
        return BirthProgressReporter(self.workspace_root)

    def _checkpoint_coordinator(self) -> BirthCheckpointCoordinator:
        return BirthCheckpointCoordinator(self)

    def _certificate_pipeline(self) -> BirthCertificatePipeline:
        return BirthCertificatePipeline(self)

    def _apply_hardware_profile(self) -> None:
        """Apply cached hardware tuning to birth curriculum performance knobs only."""
        profile_payload = self._hardware_profile_payload or {}
        profile_name = str(profile_payload.get("profile", "cpu_efficient"))
        tuning_raw = profile_payload.get("tuning")
        if isinstance(tuning_raw, dict):
            tuning = tuning_raw
        elif profile_name in HARDWARE_PROFILES:
            tuning = HARDWARE_PROFILES[profile_name].to_dict()
        else:
            profile_name = "cpu_efficient"
            tuning = HARDWARE_PROFILES["cpu_efficient"].to_dict()

        cur = self.birth_config.curriculum
        changes: list[str] = []

        def _apply_curriculum_int(field: str, attr: str, *, minimum: int = 1) -> None:
            if field not in tuning:
                return
            before = int(getattr(cur, attr))
            after = max(minimum, int(tuning[field]))
            setattr(cur, attr, after)
            if before != after:
                changes.append(f"{attr}={before}->{after}")

        _apply_curriculum_int("rollout_chunk_trades", "rollout_chunk_trades")
        _apply_curriculum_int("curriculum_ppo_timesteps", "curriculum_ppo_timesteps", minimum=1000)
        _apply_curriculum_int("max_escalation_level", "max_escalation_level")
        _apply_curriculum_int("oracle_scan_stride", "oracle_scan_stride")

        if "ppo_update_timesteps" in tuning:
            before = int(self.birth_config.ppo_update_timesteps)
            after = max(1000, int(tuning["ppo_update_timesteps"]))
            self.birth_config.ppo_update_timesteps = after
            if before != after:
                changes.append(f"ppo_update_timesteps={before}->{after}")

        detection_raw = profile_payload.get("detection")
        detection = detection_raw if isinstance(detection_raw, dict) else {}
        recommended = str(detection.get("recommended_profile", profile_name))
        if changes:
            logger.info(
                "birth.hardware_profile profile=%s recommended=%s %s",
                profile_name,
                recommended,
                " ".join(changes),
            )
        else:
            logger.info(
                "birth.hardware_profile profile=%s recommended=%s no_changes",
                profile_name,
                recommended,
            )

    def _create_birth_policy(
        self,
        *,
        allow_load_existing: bool,
        policy_path: str | None = None,
        force_reinit: bool = False,
    ) -> Any:
        create = getattr(self.ppo_trainer, "create_fresh_birth_policy", None)
        if not callable(create):
            raise RuntimeError("PPO trainer missing create_fresh_birth_policy")
        resolved_path = str(policy_path or "").strip()
        if resolved_path:
            candidate = Path(resolved_path)
            if candidate.is_file():
                load_policy = getattr(self.ppo_trainer, "load_policy", None)
                if callable(load_policy):
                    load_policy(resolved_path)
                active = getattr(self.ppo_trainer, "_resolve_active_model", None)
                if callable(active):
                    loaded = active()
                    if loaded is not None:
                        return loaded
                load_weights = getattr(self.ppo_trainer, "load_weights", None)
                if callable(load_weights):
                    loaded = load_weights(resolved_path)
                    if loaded is not None:
                        return loaded
        try:
            return create(
                allow_load_existing=bool(allow_load_existing),
                force_reinit=bool(force_reinit),
            )
        except TypeError:
            return create(allow_load_existing=bool(allow_load_existing))

    def _generate_synthetic_ticks(self, n_ticks: int, *, start_price: float) -> list[dict[str, Any]]:
        return generate_synthetic_ticks(n_ticks, start_price=start_price)

    def _train_hash(self, ticks: list[dict[str, Any]]) -> str:
        return train_hash(ticks)

    def _emit_birth_progress(
        self,
        *,
        stage: str,
        phase: str,
        message: str,
        progress_pct: float,
        cumulative_trades: int = 0,
        target_trades: int = 0,
        ppo_steps: int = 0,
        birth_start_time: float = 0.0,
        extra_parts: tuple[dict[str, Any], ...] | None = None,
        **extra: Any,
    ) -> None:
        self._progress_reporter().emit_birth_progress(
            stage=stage,
            phase=phase,
            message=message,
            progress_pct=progress_pct,
            cumulative_trades=cumulative_trades,
            target_trades=target_trades,
            ppo_steps=ppo_steps,
            birth_start_time=birth_start_time,
            extra_parts=extra_parts,
            **extra,
        )

    def _write_data_prep_progress(
        self,
        *,
        phase: str,
        message: str,
        progress_pct: float,
        training_mode: str,
        processed: int | None = None,
        total: int | None = None,
    ) -> None:
        self._data_pipeline().write_data_prep_progress(
            phase=phase,
            message=message,
            progress_pct=progress_pct,
            training_mode=training_mode,
            processed=processed,
            total=total,
        )

    def _notify_milestone(self, event: Any) -> None:
        self._progress_reporter().notify_milestone(event)

    def _notify_attention(self, event: Any) -> None:
        self._progress_reporter().notify_attention(event)

    def _notify_history_unavailable(self, detail: str) -> None:
        self._progress_reporter().notify_history_unavailable(detail)

    def _restore_buffer_from_checkpoint(self, state: dict[str, Any]) -> None:
        self._checkpoint_coordinator().restore_buffer_from_checkpoint(state)

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
        stages = ordered_runway_stages() if is_runway_stage(stage) else ordered_stages()
        try:
            idx = next(i for i, s in enumerate(stages) if s == stage)
        except StopIteration:
            idx = -1
        if idx >= 0 and idx + 1 < len(stages):
            next_stage = stages[idx + 1]
            self._active_stage_metrics = fresh_stage_metrics_for_stage(next_stage)
        elif stage == CurriculumStage.STAGE7_HOLDOUT_PROFILE:
            self._active_stage_metrics = fresh_stage_metrics_for_stage(CurriculumStage.STAGE4_POLISH)
        self.ppo_trainer.save_final_birth_policy(str(self.final_policy_path))
        self._persist_checkpoint(
            training_mode=training_mode,
            curriculum_stage=curriculum_stage,
            policy_path=policy_path,
            phase=phase,
        )
        return GraduationResult(ok=True, reason="graduated")

    def _apply_checkpoint_stage_metrics(self, checkpoint_state: dict[str, Any]) -> dict[str, Any]:
        metrics = checkpoint_state.get("stage_metrics")
        return metrics if isinstance(metrics, dict) else {}

    def _persist_checkpoint(
        self,
        *,
        training_mode: str,
        curriculum_stage: str,
        policy_path: str | None = None,
        phase: str = "",
        stage_metrics: dict[str, Any] | None = None,
        oos_metrics: dict[str, Any] | None = None,
    ) -> None:
        self._checkpoint_coordinator().persist_checkpoint(
            training_mode=training_mode,
            curriculum_stage=curriculum_stage,
            policy_path=policy_path,
            phase=phase,
            stage_metrics=stage_metrics,
            oos_metrics=oos_metrics,
        )


    def _ensure_holdout_preflight(
        self,
        *,
        ticks: list[dict[str, Any]],
        split: Any,
        max_days: int,
        prefer_real: bool,
        start_price: float,
        training_mode: str,
        reuse_manifest: bool = False,
        saved_manifest: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], Any, dict[str, Any]] | dict[str, Any]:
        return self._certificate_pipeline().ensure_holdout_preflight(ticks=ticks, split=split, max_days=max_days, prefer_real=prefer_real, start_price=start_price, training_mode=training_mode, reuse_manifest=reuse_manifest, saved_manifest=saved_manifest)

    def _run_certificate_remediation(
        self,
        *,
        split: Any,
        eval_result: dict[str, Any],
        training_mode: str,
        ppo_steps_per_update: int,
        trade_budget_cap: int,
        prefer_real: bool,
        start_price: float,
    ) -> dict[str, Any]:
        return self._certificate_pipeline().run_certificate_remediation(split=split, eval_result=eval_result, training_mode=training_mode, ppo_steps_per_update=ppo_steps_per_update, trade_budget_cap=trade_budget_cap, prefer_real=prefer_real, start_price=start_price)

    def _resolve_birth_exit_winrate(self) -> float:
        return self._certificate_pipeline().resolve_birth_exit_winrate()

    def _resolve_baseline_oos_winrate(self, *, checkpoint_state: dict[str, Any] | None = None) -> float:
        return self._certificate_pipeline().resolve_baseline_oos_winrate(checkpoint_state=checkpoint_state)

    def _bootstrap_runway_stage5(self, *, train_ticks: list[dict[str, Any]]) -> None:
        return self._certificate_pipeline().bootstrap_runway_stage5(train_ticks=train_ticks)

    def _run_certificate_runway_stages(
        self,
        *,
        split: Any,
        validation_ticks: list[dict[str, Any]],
        train_core_ticks: list[dict[str, Any]],
        training_mode: str,
        ppo_steps_per_update: int,
        trade_budget_cap: int,
        prefer_real: bool,
        start_price: float,
        baseline_oos_winrate: float,
        birth_exit_winrate: float,
    ) -> dict[str, Any] | None:
        return self._certificate_pipeline().run_certificate_runway_stages(split=split, validation_ticks=validation_ticks, train_core_ticks=train_core_ticks, training_mode=training_mode, ppo_steps_per_update=ppo_steps_per_update, trade_budget_cap=trade_budget_cap, prefer_real=prefer_real, start_price=start_price, baseline_oos_winrate=baseline_oos_winrate, birth_exit_winrate=birth_exit_winrate)

    def _fail_certificate_with_runway_checkpoint(
        self,
        *,
        eval_result: dict[str, Any],
        training_mode: str,
        trade_budget_cap: int,
    ) -> dict[str, Any]:
        return self._certificate_pipeline().fail_certificate_with_runway_checkpoint(eval_result=eval_result, training_mode=training_mode, trade_budget_cap=trade_budget_cap)

    def _run_stage8_polish_and_certificate(
        self,
        *,
        split: Any,
        training_mode: str,
        ppo_steps_per_update: int,
        trade_budget_cap: int,
        prefer_real: bool,
        start_price: float,
    ) -> dict[str, Any]:
        return self._certificate_pipeline().run_stage8_polish_and_certificate(split=split, training_mode=training_mode, ppo_steps_per_update=ppo_steps_per_update, trade_budget_cap=trade_budget_cap, prefer_real=prefer_real, start_price=start_price)

    def _complete_certified_birth(
        self,
        *,
        split: Any,
        eval_result: dict[str, Any],
        training_mode: str,
        trade_budget_cap: int,
    ) -> dict[str, Any]:
        return self._certificate_pipeline().complete_certified_birth(split=split, eval_result=eval_result, training_mode=training_mode, trade_budget_cap=trade_budget_cap)


    def run_birth_phase(
        self,
        target_trades: int | None = None,
        max_real_days: int = 365,
        prefer_real_data_only: bool = True,
        chunk_size: int = 50_000,
        ppo_update_timesteps: int = 25_000,
        force: bool = False,
        practice_mode: bool = False,
        reuse_existing_policy: bool | None = None,
        reuse_data_manifest: bool = False,
        expand_data: bool = False,
    ) -> dict[str, Any]:
        from lumina_core.birth.birth_phase_orchestrator import run_birth_phase as _run_birth_phase

        return _run_birth_phase(
            self,
            target_trades=target_trades,
            max_real_days=max_real_days,
            prefer_real_data_only=prefer_real_data_only,
            chunk_size=chunk_size,
            ppo_update_timesteps=ppo_update_timesteps,
            force=force,
            practice_mode=practice_mode,
            reuse_existing_policy=reuse_existing_policy,
            reuse_data_manifest=reuse_data_manifest,
            expand_data=expand_data,
        )

    def _paused_result(self) -> dict[str, Any]:
        write_birth_progress(
            self.workspace_root,
            stage="paused",
            phase="paused",
            message="Birth Phase gepauzeerd.",
            progress_pct=min(
                99.0,
                float(self.cumulative_trades) / max(1.0, float(self.birth_config.trade_budget_cap)) * 100.0,
            ),
            cumulative_trades=self.cumulative_trades,
            target_trades=self.birth_config.trade_budget_cap,
            birth_start_time=self.birth_start_time,
            ppo_steps=self.ppo_steps,
        )
        return {"status": "paused", "total_trades": self.cumulative_trades, "ppo_steps": self.ppo_steps}

    def _stage_tick_pool(
        self,
        *,
        stage: CurriculumStage,
        stage_ticks: list[dict[str, Any]],
        train_ticks: list[dict[str, Any]],
        escalation_level: int,
        attempt: int,
        chunk_target: int = 250,
        cur_cfg: BirthCurriculumConfig | None = None,
        intra_state: Stage1IntraCurriculumState | None = None,
        easy_pool: list[dict[str, Any]] | None = None,
        hard_pool: list[dict[str, Any]] | None = None,
        intra_s2_state: Stage2IntraCurriculumState | None = None,
        s2_easy_pool: list[dict[str, Any]] | None = None,
        s2_hard_pool: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        cfg = cur_cfg or self.birth_config.curriculum
        if (
            stage == CurriculumStage.STAGE1_TREND
            and cfg.intra_stage1_enabled
            and intra_state is not None
            and easy_pool
            and hard_pool
        ):
            pool_size = max(
                chunk_target * max(1, int(cfg.intra_pool_size_multiplier)),
                len(easy_pool),
            )
            rng = random.Random(attempt + int(intra_state.hard_pct * 1000) + escalation_level * 17)
            return sample_intra_stage1_pool(
                easy_pool,
                hard_pool,
                intra_state,
                pool_size=pool_size,
                rng=rng,
            )
        if (
            stage == CurriculumStage.STAGE2_RANGE
            and cfg.intra_stage2_enabled
            and intra_s2_state is not None
            and s2_easy_pool
            and s2_hard_pool
        ):
            pool_size = max(
                chunk_target * max(1, int(cfg.intra_pool_size_multiplier)),
                len(s2_easy_pool),
            )
            rng = random.Random(attempt + int(intra_s2_state.hard_pct * 1000) + escalation_level * 23)
            return sample_intra_stage2_pool(
                s2_easy_pool,
                s2_hard_pool,
                intra_s2_state,
                pool_size=pool_size,
                rng=rng,
            )
        if escalation_level >= 2:
            pool = list(train_ticks)
            rng = random.Random(attempt + escalation_level * 17)
            rng.shuffle(pool)
            return pool
        if escalation_level >= 1 and len(stage_ticks) < len(train_ticks):
            extra = list(train_ticks)
            rng = random.Random(attempt + 3)
            rng.shuffle(extra)
            merged = list(stage_ticks) + extra[: max(len(stage_ticks), len(train_ticks) // 4)]
            return merged
        return list(stage_ticks)

    def _detect_stall(
        self,
        *,
        winrate_history: list[float],
        reward_history: list[float],
        low_velocity_attempts: int,
        cfg: BirthCurriculumConfig,
        stage: CurriculumStage = CurriculumStage.STAGE1_TREND,
    ) -> StallDetectionResult:
        """Detect learning stall via EventBus meta handler."""
        client = self._birth_bus_client
        if client is not None:
            if self._birth_handler_registry is not None:
                self._birth_handler_registry.sync_birth_cfg(cfg, self.birth_config.reward)
            client.cfg = cfg
            return client.detect_stall(
                stage,
                winrate_history=winrate_history,
                reward_history=reward_history,
                low_velocity_attempts=low_velocity_attempts,
            )
        from lumina_core.birth.meta_controller import detect_stall

        return detect_stall(
            winrate_history=winrate_history,
            reward_history=reward_history,
            low_velocity_attempts=low_velocity_attempts,
            cfg=cfg,
        )

    @staticmethod
    def _resolve_oracle_mining_params(
        cfg: BirthCurriculumConfig,
        *,
        aggressive: bool,
    ) -> tuple[int, int]:
        max_patterns = int(cfg.oracle_patterns_per_stage)
        scan_stride = int(cfg.oracle_scan_stride)
        if not aggressive:
            return max_patterns, scan_stride
        divisor = max(1, int(cfg.strong_recovery_oracle_stride_divisor))
        multiplier = max(1, int(cfg.strong_recovery_pattern_multiplier))
        scan_stride = max(1, scan_stride // divisor)
        max_patterns = min(max_patterns * multiplier, max_patterns * 2)
        return max_patterns, scan_stride

    def _maybe_trigger_provisional_pass(
        self,
        *,
        stage: CurriculumStage,
        stage_trades: int,
        required: int,
        attempt: int,
        strong_recovery_attempts: int,
        patterns_mined: int,
        buffer_size: int,
        constitution_violations: int,
        combined_velocity: float,
        allow_provisional: bool,
        cfg: BirthCurriculumConfig,
    ) -> ProvisionalPassDecision:
        """Autonomously decide provisional soft-pass (practice / allow_provisional only)."""
        _ = stage
        soft_pass_eligible = should_gen0_soft_pass(
            stage_trades=stage_trades,
            buffer_size=buffer_size,
            attempt=attempt,
            cfg=cfg,
        ) or (patterns_mined >= 100 and buffer_size >= 256)
        safeguards = {
            "allow_provisional": allow_provisional,
            "constitution_clean": constitution_violations == 0,
            "volume_gate_passed": stage_trades >= required,
            "recovery_attempts_met": strong_recovery_attempts
            >= cfg.strong_recovery_no_improvement_threshold,
            "velocity_still_low": combined_velocity <= cfg.velocity_stall_epsilon,
            "soft_pass_eligible": soft_pass_eligible,
        }
        if not allow_provisional:
            logger.info(
                "birth.provisional_pass_blocked reason=certified_mode_strict stage=%s "
                "strong_recovery_attempts=%s safeguards=%s",
                stage.value,
                strong_recovery_attempts,
                safeguards,
            )
            return ProvisionalPassDecision(
                should_grant=False,
                reason="",
                blocked_reason="certified_mode_strict",
                safeguards=safeguards,
            )
        if all(
            (
                safeguards["constitution_clean"],
                safeguards["volume_gate_passed"],
                safeguards["recovery_attempts_met"],
                safeguards["velocity_still_low"],
                safeguards["soft_pass_eligible"],
            )
        ):
            logger.info(
                "birth.provisional_pass_granted stage=%s strong_recovery_attempts=%s "
                "combined_velocity=%.6f patterns_mined=%s buffer_size=%s safeguards=%s",
                stage.value,
                strong_recovery_attempts,
                combined_velocity,
                patterns_mined,
                buffer_size,
                safeguards,
            )
            return ProvisionalPassDecision(
                should_grant=True,
                reason="strong_recovery_exhausted_soft_pass",
                blocked_reason=None,
                safeguards=safeguards,
            )
        blocked_reason = next(
            (
                key
                for key, ok in (
                    ("constitution_clean", safeguards["constitution_clean"]),
                    ("volume_gate_passed", safeguards["volume_gate_passed"]),
                    ("recovery_attempts_met", safeguards["recovery_attempts_met"]),
                    ("velocity_still_low", safeguards["velocity_still_low"]),
                    ("soft_pass_eligible", safeguards["soft_pass_eligible"]),
                )
                if not ok
            ),
            "safeguard_failed",
        )
        logger.info(
            "birth.provisional_pass_blocked reason=%s stage=%s strong_recovery_attempts=%s "
            "combined_velocity=%.6f safeguards=%s",
            blocked_reason,
            stage.value,
            strong_recovery_attempts,
            combined_velocity,
            safeguards,
        )
        return ProvisionalPassDecision(
            should_grant=False,
            reason="",
            blocked_reason=blocked_reason,
            safeguards=safeguards,
        )

    def _run_stage_research_loop(
        self,
        *,
        stage: CurriculumStage,
        stage_index: int,
        stage_ticks: list[dict[str, Any]],
        train_ticks: list[dict[str, Any]],
        holdout_ticks: list[dict[str, Any]],
        target: int,
        stage_progress_pct: float,
        training_mode: str,
        ppo_steps_per_update: int,
        polish_ppo_timesteps: int,
        trade_budget_cap: int,
        prefer_real: bool,
        start_price: float,
    ) -> dict[str, Any] | None:
        from lumina_core.birth.stage_training_loop import run_stage_research_loop

        return run_stage_research_loop(
            self,
            stage=stage,
            stage_index=stage_index,
            stage_ticks=stage_ticks,
            train_ticks=train_ticks,
            holdout_ticks=holdout_ticks,
            target=target,
            stage_progress_pct=stage_progress_pct,
            training_mode=training_mode,
            ppo_steps_per_update=ppo_steps_per_update,
            polish_ppo_timesteps=polish_ppo_timesteps,
            trade_budget_cap=trade_budget_cap,
            prefer_real=prefer_real,
            start_price=start_price,
        )

    # --- New event-driven curriculum orchestration (thin, fail-closed) ---

    def get_curriculum_orchestrator(self) -> CurriculumOrchestrator | None:
        """Return the thin event-only CurriculumOrchestrator if wired."""
        return self._curriculum_orchestrator

    def start_event_driven_curriculum(self, *, stages: list[str] | None = None) -> str | None:
        """Kick off curriculum using the thin orchestrator + dedicated handlers.

        Returns curriculum_id or None if not wired.
        All heavy logic (plateau, phoenix, intra, remediation) executes inside
        handlers that publish strict events back to the orchestrator.
        """
        orch = self._curriculum_orchestrator
        if orch is None:
            return None
        from lumina_core.birth.curriculum import ordered_stages as _ordered

        stage_list = stages or [s.value for s in _ordered()]
        cap = int(getattr(self.birth_config, "trade_budget_cap", 1_000_000))
        practice = False
        try:
            cid = orch.start_curriculum(
                stages=stage_list,
                target_trades_cap=cap,
                practice_mode=practice,
            )
            return cid
        except Exception as exc:
            logger.exception("event-driven curriculum start failed: %s", exc)
            return None

    def reload_birth_config(self) -> None:
        """Hot-reload birth_v2 section from workspace config.yaml."""
        self.birth_config = load_birth_v2_config(self.workspace_root)
        if self._birth_handler_registry is not None:
            self._birth_handler_registry.sync_birth_cfg(
                self.birth_config.curriculum,
                self.birth_config.reward,
            )
        if self._birth_bus_client is not None:
            self._birth_bus_client.cfg = self.birth_config.curriculum
        logger.info("birth.config.hot_reload workspace=%s", self.workspace_root)
