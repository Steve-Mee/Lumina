"""Birth Phase v2 orchestrator (ADR-0012/0013/0014)."""

from __future__ import annotations

import hashlib
import random
import threading
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.birth_certificate import (
    build_certificate_from_eval,
    certificate_path,
    write_certificate,
)
from lumina_core.birth.birth_constitution_guard import BirthConstitutionGuard
from lumina_core.birth.checkpoint import (
    can_resume_checkpoint,
    clear_checkpoint,
    load_checkpoint_state,
    read_checkpoint_payload,
    reset_adaptation_budget_for_manual_resume,
    save_checkpoint,
    write_checkpoint_payload,
)
from lumina_core.birth.buffer_persist import clear_buffer, load_buffer, save_buffer
from lumina_core.birth.tick_cache_persist import (
    load_split_cache,
    load_ticks_cache,
    save_split_cache,
    save_ticks_cache,
)
from lumina_core.birth.certificate_evaluator import evaluate_holdout_certificate
from lumina_core.birth.config import (
    BRO_ENGINE_VERSION,
    BirthCurriculumConfig,
    load_birth_v2_config,
    resolve_effective_trade_budget,
)
from lumina_core.birth.curriculum import (
    CurriculumStage,
    Stage1IntraCurriculumState,
    evaluate_stage_pass,
    filter_ticks_for_stage,
    ordered_stages,
    sample_intra_stage1_pool,
    should_gen0_soft_pass,
    split_stage1_trend_ticks,
    stage1_intra_state_from_metrics,
    stage_pass_trades,
    stage_trade_target,
    update_stage1_intra_state,
)
from lumina_core.birth.data_expansion import expand_birth_data
from lumina_core.birth.history_loader import load_historical_ticks
from lumina_core.birth.news_enricher import enrich_ticks_with_news
from lumina_core.birth.pattern_miner import mine_winning_patterns
from lumina_core.birth.meta_controller import (
    AdaptationDecision,
    BirthMetaController,
    LearningHealth,
    MetaActionPlan,
    RecoveryStrategy,
    StallDetectionResult,
    detect_stall,
    get_adaptation_decision,
)
from lumina_core.birth.meta_self_eval import SelfEvalPhase
from lumina_core.birth.remediation import (
    RemediationAction,
    filter_train_ticks_for_holdout_profile,
    manifest_train_hash_matches,
    select_regime_diverse_train_ticks,
    select_remediation_plan,
    should_fast_path_remediation_from_state,
    reconstruct_checkpoint_from_progress,
)
from lumina_core.birth.stall_remediation import (
    HUMAN_GATE_REASON,
    StallRemediationAction,
    StallRemediationState,
    begin_remediation_cycle,
    begin_remediation_step,
    can_start_remediation,
    curate_buffer_bottom_half,
    curate_buffer_top_quartile,
    increment_remediation_rollout,
    is_remediation_exhausted,
    record_remediation_outcome,
    should_advance_remediation_step,
    should_run_remediation_instead_of_human_gate,
)
from lumina_core.birth.preflight import assess_split_preflight, data_manifest_from_split
from lumina_core.birth.progress import read_birth_progress, write_birth_progress
from lumina_core.birth.plateau_escalator import (
    TERMINAL_STALL_REASON,
    EvolutionAction,
    PlateauEnterContext,
    PlateauState,
    begin_evolution_step,
    build_plateau_audit,
    can_force_never_stop_recovery,
    detect_hold_trap,
    enter_plateau,
    increment_evolution_rollout,
    is_valid_best_policy_snapshot,
    maybe_update_best_winrate,
    progress_fields as plateau_progress_fields,
    record_evolution_outcome,
    record_forced_recovery,
    remediation_is_exhausted,
    reset_plateau_for_new_cycle,
    sanitize_plateau_best_snapshot,
    should_block_plateau_recovery,
    should_enter_plateau,
    should_force_advance_evolution_step,
    should_phoenix_reset,
    should_terminal_plateau_stall,
    should_trigger_plateau_evolution_step,
)
from lumina_core.birth.stage_scorecard import (
    build_scorecard_payload,
    calculate_simple_slope,
    compute_stage_blocker,
    enrich_adaptation_payload,
    pass_criteria_for_stage,
)
from lumina_core.birth.stage_pass_receipt import (
    StagePassReceipt,
    audit_curriculum_integrity,
    fresh_stage_metrics_for_stage,
    parse_stage_pass_receipts,
    receipt_for_stage,
    receipt_from_stage_result,
    verify_stage_pass_receipt,
)
from lumina_core.birth.purged_split import purged_train_holdout_split
from lumina_core.birth.sim_runner import run_policy_rollout
from lumina_core.birth.tick_enricher import enrich_ticks_for_sim, real_data_percentage
from lumina_core.rl.trend_features import MIN_TREND_LOOKBACK
from lumina_core.birth.dna_handoff import register_birth_gen0_dna
from lumina_core.birth.bible_meta import update_bible_after_birth
from lumina_core.first_boot_progress import ensure_first_boot_hardware_profile
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
        self._remediation_attempt = 0
        self._last_checkpoint_at = 0.0
        self._active_stage_metrics: dict[str, Any] = {}
        self._hardware_profile_payload: dict[str, Any] | None = None
        event_bus = getattr(runtime, "event_bus", None)
        self._constitution_guard = BirthConstitutionGuard(event_bus=event_bus, mode="birth")
        self._constitution_violations_cumulative = 0
        self._trade_budget_source = "birth_v2.trade_budget_cap"

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
        if self.stop_event is not None and self.stop_event.is_set():
            return True
        return self.pause_flag_path.exists()

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

    def _create_birth_policy(self, *, allow_load_existing: bool, policy_path: str | None = None) -> Any:
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
            return create(allow_load_existing=bool(allow_load_existing))
        except TypeError:
            return create()

    def _generate_synthetic_ticks(self, n_ticks: int, *, start_price: float) -> list[dict[str, Any]]:
        rng = random.Random(51)
        price = max(100.0, float(start_price))
        out: list[dict[str, Any]] = []
        for i in range(max(1, n_ticks)):
            shock = rng.gauss(0.0, 0.0016)
            price = max(10.0, price * (1.0 + shock))
            out.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "last": float(price),
                    "close": float(price),
                    "bid": float(price - 0.125),
                    "ask": float(price + 0.125),
                    "volume": 1000,
                    "regime": "SYNTHETIC",
                    "imbalance": 1.0,
                    "source": "synthetic",
                    "bar_index": i,
                }
            )
        return out

    def _train_hash(self, ticks: list[dict[str, Any]]) -> str:
        if not ticks:
            return ""
        head = str(ticks[0].get("timestamp", ""))
        tail = str(ticks[-1].get("timestamp", ""))
        payload = f"{len(ticks)}:{head}:{tail}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

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
        kwargs: dict[str, Any] = {}
        if processed is not None:
            kwargs["loading_chunk"] = int(processed)
        if total is not None:
            kwargs["chunk_total"] = int(total)
        write_birth_progress(
            self.workspace_root,
            stage="loading_data",
            phase=phase,
            message=message,
            progress_pct=float(progress_pct),
            cumulative_trades=0,
            target_trades=self.birth_config.trade_budget_cap,
            birth_start_time=self.birth_start_time,
            training_mode=training_mode,
            **kwargs,
        )

    def _notify_milestone(self, event: Any) -> None:
        try:
            from lumina_core.notifications.milestone_notifier import notify_milestone

            notify_milestone(event, workspace_root=self.workspace_root)
        except Exception as exc:
            logger.warning("birth.milestone_notify_failed: %s", exc)

    def _notify_attention(self, event: Any) -> None:
        try:
            from lumina_core.notifications.operator_notifier import notify_problem

            notify_problem(event, workspace_root=self.workspace_root)
        except Exception as exc:
            logger.warning("birth.attention_notify_failed: %s", exc)

    def _notify_history_unavailable(self, detail: str) -> None:
        from lumina_core.notifications.attention_events import birth_history_unavailable_event

        self._notify_attention(birth_history_unavailable_event(detail=detail))

    def _restore_buffer_from_checkpoint(self, state: dict[str, Any]) -> None:
        buffer_file = str(state.get("buffer_path", "") or "").strip()
        if buffer_file and Path(buffer_file).is_file():
            for traj in load_buffer(self.workspace_root):
                self.buffer.add(traj)
            return
        if int(state.get("version", 2) or 2) >= 3:
            for traj in load_buffer(self.workspace_root):
                self.buffer.add(traj)

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
    ) -> None:
        if self._pending_stage_pass_receipt is not None:
            self._stage_pass_receipts.append(self._pending_stage_pass_receipt)
            self._pending_stage_pass_receipt = None
        self._stages_passed.append(stage.value)
        receipt = receipt_for_stage(self._stage_pass_receipts, stage.value)
        if receipt is not None:
            from lumina_core.notifications.milestone_events import curriculum_stage_passed_event

            self._notify_milestone(curriculum_stage_passed_event(stage, receipt))
        stages = ordered_stages()
        try:
            idx = next(i for i, s in enumerate(stages) if s == stage)
        except StopIteration:
            idx = -1
        if idx >= 0 and idx + 1 < len(stages):
            next_stage = stages[idx + 1]
            if next_stage != CurriculumStage.STAGE4_POLISH:
                self._active_stage_metrics = fresh_stage_metrics_for_stage(next_stage)
        self.ppo_trainer.save_final_birth_policy(str(self.final_policy_path))
        self._persist_checkpoint(
            training_mode=training_mode,
            curriculum_stage=curriculum_stage,
            policy_path=policy_path,
            phase=phase,
        )

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
    ) -> None:
        if stage_metrics:
            merged = dict(self._active_stage_metrics)
            merged.update(stage_metrics)
            self._active_stage_metrics = merged
        metrics = (
            dict(self._active_stage_metrics)
            if self._active_stage_metrics
            else self._stage_metrics_snapshot()
        )
        saved_buffer = save_buffer(self.workspace_root, self.buffer.trajectories)
        save_checkpoint(
            self.workspace_root,
            cumulative_trades=self.cumulative_trades,
            ppo_steps=self.ppo_steps,
            training_mode=training_mode,
            stages_passed=self._stages_passed,
            curriculum_stage=curriculum_stage,
            policy_path=str(policy_path or self.final_policy_path),
            stage_metrics=metrics,
            buffer_path=saved_buffer,
            data_manifest=self._data_manifest,
            phase=phase,
            remediation_attempt=self._remediation_attempt,
            stage_pass_receipts=[r.to_dict() for r in self._stage_pass_receipts],
        )
        self._last_checkpoint_at = time.time()

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
        """Expand history until holdout preflight passes or fail closed."""
        cur_cfg = self.birth_config.curriculum
        news_cfg = self.birth_config.news
        active_ticks = list(ticks)
        active_split = split
        current_hash = self._train_hash(active_split.train)
        if reuse_manifest and manifest_train_hash_matches(
            current_hash=current_hash,
            saved_manifest=saved_manifest,
        ):
            preflight = assess_split_preflight(
                active_split,
                thresholds=self.birth_config.certificate_thresholds,
            )
            if preflight.ok:
                manifest = dict(saved_manifest or {})
                manifest.update(
                    data_manifest_from_split(
                        active_split,
                        days_loaded=max(1, len(active_ticks) // 450),
                        real_data_pct=self._real_data_pct,
                        train_hash=current_hash,
                    )
                )
                manifest["preflight_ok"] = True
                manifest["holdout_regimes"] = list(preflight.holdout_regimes)
                manifest["reused_manifest"] = True
                return active_ticks, active_split, manifest
        expansion_step = 0
        preflight = assess_split_preflight(
            active_split,
            thresholds=self.birth_config.certificate_thresholds,
        )
        max_attempts = max(1, len(cur_cfg.data_expansion_steps))
        attempts = 0
        while not preflight.ok and attempts < max_attempts:
            attempts += 1
            prev_regimes = len(preflight.holdout_regimes)
            expanded = expand_birth_data(
                market_data_service=self.market_data_service,
                runtime=self.runtime,
                current_step=expansion_step + 1,
                expansion_steps=list(cur_cfg.data_expansion_steps),
                holdout_pct=self.birth_config.holdout_pct,
                enrich_news_fn=lambda rows: enrich_ticks_with_news(
                    rows,
                    workspace_root=self.workspace_root,
                    primary=news_cfg.primary,
                    enable_cache=news_cfg.enable_cache,
                    cache_path=news_cfg.cache_path,
                ),
                synthetic_fallback_fn=(
                    None
                    if prefer_real
                    else lambda n, p: self._generate_synthetic_ticks(n, start_price=p or start_price)
                ),
                start_price=start_price,
            )
            expansion_step = expanded.step_index
            if expanded.exhausted and len(expanded.train_ticks) <= len(active_split.train):
                write_birth_progress(
                    self.workspace_root,
                    stage="history_unavailable",
                    phase="holdout_preflight_failed",
                    message=preflight.message,
                    progress_pct=100.0,
                    cumulative_trades=0,
                    target_trades=self.birth_config.trade_budget_cap,
                    birth_start_time=self.birth_start_time,
                    preflight_report={
                        "ok": False,
                        "failure_reasons": list(preflight.failure_reasons),
                        "holdout_regimes": list(preflight.holdout_regimes),
                    },
                    retryable=True,
                )
                self._notify_history_unavailable(preflight.message or "Holdout preflight failed.")
                return {
                    "status": "history_unavailable",
                    "total_trades": 0,
                    "ppo_steps": 0,
                    "training_mode": training_mode,
                    "preflight": preflight.failure_reasons,
                }
            active_ticks = list(expanded.all_ticks)
            active_split = expanded.split
            self._real_data_pct = expanded.real_data_pct
            preflight = assess_split_preflight(
                active_split,
                thresholds=self.birth_config.certificate_thresholds,
            )
            write_birth_progress(
                self.workspace_root,
                stage="historical_loaded",
                phase="holdout_preflight_expansion",
                message=(
                    f"Holdout preflight expansion: {len(preflight.holdout_regimes)} regimes, "
                    f"{preflight.holdout_tick_count:,} holdout ticks"
                ),
                progress_pct=min(24.0, 21.0 + float(attempts)),
                cumulative_trades=0,
                target_trades=self.birth_config.trade_budget_cap,
                birth_start_time=self.birth_start_time,
                preflight_report={
                    "ok": preflight.ok,
                    "failure_reasons": list(preflight.failure_reasons),
                    "holdout_regimes": list(preflight.holdout_regimes),
                },
            )
            if preflight.ok:
                break
            if len(preflight.holdout_regimes) <= prev_regimes and expanded.exhausted:
                break

        if not preflight.ok:
            write_birth_progress(
                self.workspace_root,
                stage="history_unavailable",
                phase="holdout_preflight_failed",
                message=preflight.message,
                progress_pct=100.0,
                cumulative_trades=0,
                target_trades=self.birth_config.trade_budget_cap,
                birth_start_time=self.birth_start_time,
                preflight_report={
                    "ok": False,
                    "failure_reasons": list(preflight.failure_reasons),
                    "holdout_regimes": list(preflight.holdout_regimes),
                },
                retryable=True,
            )
            self._notify_history_unavailable(preflight.message or "Holdout preflight exhausted.")
            return {
                "status": "history_unavailable",
                "total_trades": 0,
                "ppo_steps": 0,
                "training_mode": training_mode,
                "preflight": preflight.failure_reasons,
            }

        manifest = data_manifest_from_split(
            active_split,
            days_loaded=max(1, len(active_ticks) // 450),
            real_data_pct=self._real_data_pct,
            train_hash=self._train_hash(active_split.train),
        )
        manifest["preflight_ok"] = True
        manifest["holdout_regimes"] = list(preflight.holdout_regimes)
        manifest["ticks_cache_path"] = save_ticks_cache(self.workspace_root, active_ticks)
        manifest["split_cache_path"] = save_split_cache(
            self.workspace_root,
            split=active_split,
            holdout_pct=self.birth_config.holdout_pct,
        )
        return active_ticks, active_split, manifest

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
        cur_cfg = self.birth_config.curriculum
        news_cfg = self.birth_config.news
        max_attempts = max(1, int(cur_cfg.max_certificate_remediation_attempts))
        curriculum_timesteps = max(1000, int(cur_cfg.curriculum_ppo_timesteps))
        polish_timesteps = max(1000, int(cur_cfg.polish_ppo_timesteps))
        current_eval = dict(eval_result)
        remediation_expansion_step = max(
            0, int(self._data_manifest.get("remediation_expansion_step", 0) or 0)
        )
        holdout_data = list(split.holdout)

        for attempt in range(1, max_attempts + 1):
            self._remediation_attempt = attempt
            reasons = list(current_eval.get("failure_reasons") or [])
            plan = select_remediation_plan(
                reasons,
                attempt=attempt,
                curriculum_ppo_timesteps=curriculum_timesteps,
                polish_ppo_timesteps=polish_timesteps,
                rollout_chunk_trades=cur_cfg.rollout_chunk_trades,
            )
            write_birth_progress(
                self.workspace_root,
                stage="training_running",
                phase="certificate_remediation",
                message=(
                    f"Certificate remediation {attempt}/{max_attempts} "
                    f"[{plan.label}]: {', '.join(reasons) or 'diagnose'}"
                ),
                progress_pct=min(99.0, 94.0 + (attempt / max_attempts) * 4.0),
                cumulative_trades=self.cumulative_trades,
                target_trades=trade_budget_cap,
                ppo_steps=self.ppo_steps,
                birth_start_time=self.birth_start_time,
                remediation_attempt=attempt,
                remediation_max=max_attempts,
                remediation_action=plan.action.value,
                oos_metrics=current_eval,
                failure_reasons=reasons,
                quality_score=float(self._data_manifest.get("quality_score", 0.0) or 0.0),
            )
            if self._stop_requested():
                self._persist_checkpoint(
                    training_mode=training_mode,
                    curriculum_stage=CurriculumStage.STAGE4_POLISH.value,
                    phase="certificate_remediation",
                )
                return self._paused_result()

            active_train = list(split.train)
            if plan.expand_data:
                expanded = expand_birth_data(
                    market_data_service=self.market_data_service,
                    runtime=self.runtime,
                    current_step=remediation_expansion_step + 1,
                    expansion_steps=list(cur_cfg.data_expansion_steps),
                    holdout_pct=self.birth_config.holdout_pct,
                    enrich_news_fn=lambda rows: enrich_ticks_with_news(
                        rows,
                        workspace_root=self.workspace_root,
                        primary=news_cfg.primary,
                        enable_cache=news_cfg.enable_cache,
                        cache_path=news_cfg.cache_path,
                    ),
                    synthetic_fallback_fn=(
                        None
                        if prefer_real
                        else lambda n, p: self._generate_synthetic_ticks(n, start_price=p or start_price)
                    ),
                    start_price=start_price,
                )
                remediation_expansion_step = expanded.step_index
                self._data_manifest["remediation_expansion_step"] = remediation_expansion_step
                if expanded.train_ticks:
                    active_train = list(expanded.train_ticks)
                    self._real_data_pct = expanded.real_data_pct

            if plan.action == RemediationAction.REGIME_EXPAND:
                rollout_ticks = select_regime_diverse_train_ticks(active_train)
            elif plan.action == RemediationAction.HOLDOUT_ACTIVITY:
                rollout_ticks = filter_train_ticks_for_holdout_profile(active_train, holdout_data)
            else:
                rollout_ticks = active_train

            explore_steps = cur_cfg.exploration_steps * plan.explore_multiplier
            remediation_rollout = run_policy_rollout(
                runtime=self.runtime,
                data=rollout_ticks,
                policy=self.current_policy,
                target_trades=plan.rollout_target_trades,
                workspace_root=self.workspace_root,
                constitution_guard=self._constitution_guard,
                exploration_steps=explore_steps,
                escalation_level=2 if plan.action != RemediationAction.SHARPE_POLISH else 1,
            )
            for traj in remediation_rollout.trajectories:
                self.buffer.add(traj, priority=2.0)
            self.cumulative_trades += remediation_rollout.trades

            ppo_steps = plan.ppo_timesteps
            if plan.action == RemediationAction.SHARPE_POLISH:
                ppo_steps = max(1000, polish_timesteps // max(1, attempt))
            elif len(self.buffer) < 80:
                ppo_steps = min(ppo_steps, 2000)

            if len(self.buffer) >= 80:
                self.current_policy = self.ppo_trainer.update_from_buffer(
                    buffer=self.buffer,
                    timesteps=ppo_steps,
                    birth_phase=True,
                )
                self.ppo_steps += ppo_steps
                self._persist_checkpoint(
                    training_mode=training_mode,
                    curriculum_stage=CurriculumStage.STAGE4_POLISH.value,
                    phase="certificate_remediation",
                )

            current_eval = evaluate_holdout_certificate(
                runtime=self.runtime,
                holdout_data=holdout_data,
                policy=self.current_policy,
                real_data_pct=self._real_data_pct,
                holdout_days=split.holdout_days,
                constitution_violations=self._constitution_guard.violations,
                workspace_root=self.workspace_root,
                thresholds=self.birth_config.certificate_thresholds,
            )
            if current_eval.get("certificate_passed"):
                return current_eval

        write_birth_progress(
            self.workspace_root,
            stage="failed",
            phase="certificate_failed",
            message="Birth Certificate v2 thresholds not met after remediation.",
            progress_pct=100.0,
            cumulative_trades=self.cumulative_trades,
            target_trades=trade_budget_cap,
            birth_start_time=self.birth_start_time,
            oos_metrics=current_eval,
            failure_reasons=list(current_eval.get("failure_reasons") or []),
            remediation_attempt=self._remediation_attempt,
            stages_passed=list(self._stages_passed),
            data_manifest=dict(self._data_manifest),
            needs_attention=True,
            retryable=True,
        )
        try:
            from lumina_core.notifications.attention_events import birth_certificate_failed_event
            from lumina_core.notifications.attention_notifier import notify_attention

            notify_attention(
                birth_certificate_failed_event(
                    failure_reasons=list(current_eval.get("failure_reasons") or []),
                ),
                workspace_root=self.workspace_root,
            )
        except Exception as exc:
            logger.warning("birth.cert_attention_failed: %s", exc)
        self._persist_checkpoint(
            training_mode=training_mode,
            curriculum_stage=CurriculumStage.STAGE4_POLISH.value,
            phase="certificate_failed",
        )
        return current_eval

    def _complete_certified_birth(
        self,
        *,
        split: Any,
        eval_result: dict[str, Any],
        training_mode: str,
        trade_budget_cap: int,
    ) -> dict[str, Any]:
        self._stages_passed.append(CurriculumStage.STAGE4_POLISH.value)
        certificate = build_certificate_from_eval(
            workspace_root=self.workspace_root,
            eval_result=eval_result,
            curriculum_stages_passed=self._stages_passed,
            training_trades=self.cumulative_trades,
            ppo_steps=self.ppo_steps,
        )
        write_certificate(self.workspace_root, certificate)
        clear_checkpoint(self.workspace_root)
        clear_buffer(self.workspace_root)
        stamp = datetime.now(timezone.utc).isoformat()
        for path in (self.completion_flag_path, self.legacy_completion_flag_path):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(stamp, encoding="utf-8")

        register_birth_gen0_dna(self.workspace_root, certificate)
        update_bible_after_birth(self.workspace_root, certificate, eval_result)

        from lumina_core.birth.evolution_proof_gate import (
            EvolutionProofConfig,
            record_and_evaluate_at_certificate,
        )
        from lumina_core.notifications.milestone_events import (
            birth_certificate_issued_event,
            evolution_proof_failed_event,
            evolution_proof_passed_event,
        )

        birth_exit_wr = float(
            eval_result.get("training_winrate", eval_result.get("winrate", 0.0)) or 0.0
        )
        curriculum_cfg = self.birth_config.curriculum
        proof_cfg = EvolutionProofConfig(
            min_trades=int(curriculum_cfg.evolution_proof_min_trades),
            min_winrate_lift=float(curriculum_cfg.evolution_proof_min_winrate_lift),
            polish_oos_winrate_min=float(curriculum_cfg.evolution_proof_polish_oos_winrate_min),
        )
        proof_result = record_and_evaluate_at_certificate(
            self.workspace_root,
            eval_result=eval_result,
            birth_exit_winrate=birth_exit_wr,
            cfg=proof_cfg,
        )
        if proof_result.passed:
            self._notify_milestone(
                evolution_proof_passed_event(
                    oos_winrate=float(proof_result.polish_oos_winrate or 0.0),
                    lift=proof_result.winrate_lift,
                )
            )
            from lumina_core.maturity.milestone_hooks import hook_evolution_proof_passed

            hook_evolution_proof_passed(
                self.workspace_root,
                oos_winrate=float(proof_result.polish_oos_winrate or 0.0),
                lift=proof_result.winrate_lift,
            )
        else:
            self._notify_milestone(
                evolution_proof_failed_event(reasons=list(proof_result.reasons))
            )
            from lumina_core.notifications.attention_events import evolution_proof_failed_attention_event

            self._notify_attention(
                evolution_proof_failed_attention_event(reasons=list(proof_result.reasons))
            )

        self._notify_milestone(
            birth_certificate_issued_event(
                eval_result=eval_result,
                stages_passed=list(self._stages_passed),
                cumulative_trades=self.cumulative_trades,
                ppo_steps=self.ppo_steps,
            )
        )
        from lumina_core.maturity.milestone_hooks import hook_birth_certificate_issued

        hook_birth_certificate_issued(
            self.workspace_root,
            cumulative_trades=self.cumulative_trades,
            stages_passed=list(self._stages_passed),
        )

        write_birth_progress(
            self.workspace_root,
            stage="completed",
            phase="certificate_issued",
            message="Birth Certificate v2 issued.",
            progress_pct=100.0,
            cumulative_trades=self.cumulative_trades,
            target_trades=trade_budget_cap,
            ppo_steps=self.ppo_steps,
            birth_start_time=self.birth_start_time,
            certificate_ok=True,
            oos_metrics=eval_result,
            curriculum_stages_passed=self._stages_passed,
        )

        target_policy = self.final_policy_path
        return {
            "status": "completed",
            "total_trades": self.cumulative_trades,
            "ppo_steps": self.ppo_steps,
            "real_data_pct": self._real_data_pct,
            "policy_path": str(target_policy),
            "certificate_path": str(certificate_path(self.workspace_root)),
            "eval": eval_result,
            "training_mode": training_mode,
        }

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
        _ = (chunk_size, force)
        cfg = self.birth_config
        raw_yaml = self._load_workspace_yaml()
        max_days = max(30, min(3650, int(max_real_days or cfg.max_real_days)))
        prefer_real = bool(prefer_real_data_only if prefer_real_data_only is not None else cfg.prefer_real_data_only)
        effective_cap, budget_source = resolve_effective_trade_budget(raw_yaml, target_trades=target_trades)
        self._trade_budget_source = budget_source
        cfg = replace(
            cfg,
            trade_budget_cap=effective_cap,
            max_real_days=max_days,
            prefer_real_data_only=prefer_real,
        )
        self.birth_config = cfg
        allow_minimal_synthetic = self._allow_minimal_synthetic_fallback()
        self._hardware_profile_payload = ensure_first_boot_hardware_profile(self.workspace_root)
        self._apply_hardware_profile()
        logger.info(
            "birth.engine.version=%s budget_cap=%s source=%s max_real_days=%s",
            BRO_ENGINE_VERSION,
            effective_cap,
            budget_source,
            max_days,
        )
        training_mode = "practice" if practice_mode else "certified"
        ppo_steps_per_update = max(1000, int(ppo_update_timesteps or cfg.ppo_update_timesteps))
        self.birth_start_time = time.time()
        self._stages_passed = []
        self._stage_pass_receipts = []
        self._pending_stage_pass_receipt = None
        self.cumulative_trades = 0
        self.ppo_steps = 0
        self._data_manifest = {}
        self._remediation_attempt = 0
        self._last_checkpoint_at = 0.0
        self._active_stage_metrics = {}
        self.buffer.clear()
        self._constitution_violations_cumulative = 0
        self._constitution_guard.reset()

        progress_snapshot = read_birth_progress(self.workspace_root)
        existing_checkpoint = load_checkpoint_state(self.workspace_root)
        if (
            not force
            and not practice_mode
            and not read_checkpoint_payload(self.workspace_root)
            and should_fast_path_remediation_from_state(progress_snapshot, existing_checkpoint)
        ):
            policy_hint = str(self.final_policy_path)
            reconstruct_checkpoint_from_progress(
                self.workspace_root,
                progress_snapshot,
                policy_path=policy_hint if Path(policy_hint).is_file() else "",
                checkpoint=existing_checkpoint,
            )

        completion_flags = (self.completion_flag_path, self.legacy_completion_flag_path)
        resume = can_resume_checkpoint(
            self.workspace_root,
            training_mode=training_mode,
            completion_flag_paths=completion_flags,
        ) and not force
        resume_policy_path = ""
        checkpoint_state: dict[str, Any] = {}
        checkpoint_phase = ""
        if resume:
            checkpoint_state = load_checkpoint_state(self.workspace_root)
            checkpoint_phase = str(checkpoint_state.get("phase", "") or "")
            self.cumulative_trades = int(checkpoint_state.get("cumulative_trades", 0) or 0)
            self.ppo_steps = int(checkpoint_state.get("ppo_steps", 0) or 0)
            self._stages_passed = list(checkpoint_state.get("stages_passed") or [])
            self._stage_pass_receipts = parse_stage_pass_receipts(
                checkpoint_state.get("stage_pass_receipts")
            )
            self._apply_curriculum_integrity_audit(training_mode=training_mode)
            resume_policy_path = str(checkpoint_state.get("policy_path", "") or "")
            self._data_manifest = dict(checkpoint_state.get("data_manifest") or {})
            self._remediation_attempt = max(
                0, int(checkpoint_state.get("remediation_attempt", 0) or 0)
            )
            self._active_stage_metrics = dict(checkpoint_state.get("stage_metrics") or {})
            self.buffer.clear()
            self._restore_buffer_from_checkpoint(checkpoint_state)
            if checkpoint_phase.strip().lower() == "stage_stalled":
                reset_adaptation_budget_for_manual_resume(self.workspace_root)
                checkpoint_state = load_checkpoint_state(self.workspace_root)
                self._active_stage_metrics = dict(checkpoint_state.get("stage_metrics") or {})
            if expand_data and resume:
                metrics = dict(self._active_stage_metrics)
                metrics["pending_data_expand"] = True
                self._active_stage_metrics = metrics
                payload = read_checkpoint_payload(self.workspace_root)
                if payload:
                    payload["stage_metrics"] = metrics
                    write_checkpoint_payload(self.workspace_root, payload)

        allow_load = resume if reuse_existing_policy is None else bool(reuse_existing_policy)
        if resume_policy_path and Path(resume_policy_path).is_file():
            allow_load = True

        try:
            from lumina_core.notifications.milestone_notifier import (
                get_milestone_notifier,
                seed_milestones_from_birth_state,
            )

            if resume:
                resume_metrics = dict(checkpoint_state.get("stage_metrics") or {})
                proof_passed: bool | None = None
                try:
                    from lumina_core.birth.evolution_proof_gate import (
                        load_evolution_proof_record,
                    )

                    proof_record = load_evolution_proof_record(self.workspace_root)
                    if proof_record:
                        proof_passed = bool(proof_record.get("passed"))
                except Exception:
                    proof_passed = None
                seed_milestones_from_birth_state(
                    stages_passed=list(self._stages_passed),
                    phase=checkpoint_phase or str(progress_snapshot.get("phase", "") or ""),
                    training_mode=training_mode,
                    workspace_root=self.workspace_root,
                    plateau_active=bool(resume_metrics.get("plateau_active")),
                    evolution_step=int(resume_metrics.get("plateau_evolution_step", 0) or 0),
                    hold_trap_detected=bool(progress_snapshot.get("hold_trap_detected")),
                    evolution_proof_passed=proof_passed,
                )
            else:
                get_milestone_notifier(workspace_root=self.workspace_root).reset_notified()
        except Exception as exc:
            logger.warning("birth.milestone_seed_failed: %s", exc)

        write_birth_progress(
            self.workspace_root,
            stage="detected",
            phase="detected",
            message="Birth Phase v2 gestart.",
            progress_pct=5.0,
            cumulative_trades=0,
            target_trades=cfg.trade_budget_cap,
            ppo_steps=0,
            birth_start_time=self.birth_start_time,
            training_mode=training_mode,
            resumed=resume,
            **self._budget_progress_fields(),
        )

        from lumina_core.notifications.milestone_events import birth_started_event

        self._notify_milestone(
            birth_started_event(
                training_mode=training_mode,
                trade_budget=cfg.trade_budget_cap,
                resumed=resume,
            )
        )
        from lumina_core.maturity.milestone_hooks import hook_birth_started

        hook_birth_started(
            self.workspace_root,
            training_mode=training_mode,
            trade_budget=cfg.trade_budget_cap,
            resumed=resume,
        )
        wr_threshold = float(cfg.curriculum.stage1_winrate_pass_threshold)
        wr_recommended = float(cfg.curriculum.stage1_winrate_recommended)
        if wr_threshold < wr_recommended - 0.001:
            try:
                from lumina_core.notifications.milestone_events import birth_gate_warning_event

                self._notify_milestone(
                    birth_gate_warning_event(threshold=wr_threshold, recommended=wr_recommended)
                )
            except Exception as exc:
                logger.debug("birth.milestone_gate_warning_failed: %s", exc)

        ticks: list[dict[str, Any]] = []
        split: Any = None
        if resume and reuse_data_manifest and self._data_manifest:
            cached_split = load_split_cache(
                self.workspace_root,
                holdout_pct=cfg.holdout_pct,
            )
            cached_ticks = load_ticks_cache(self.workspace_root)
            cached_hash = self._train_hash(cached_split.train) if cached_split else ""
            if (
                cached_ticks
                and cached_split
                and manifest_train_hash_matches(
                    current_hash=cached_hash,
                    saved_manifest=self._data_manifest,
                )
            ):
                ticks = cached_ticks
                split = cached_split
                self._real_data_pct = float(self._data_manifest.get("real_data_pct", 0.0) or 0.0)

        if not ticks:
            write_birth_progress(
                self.workspace_root,
                stage="loading_data",
                phase="loading_history",
                message=f"Historische data laden ({max_days} dagen)…",
                progress_pct=8.0,
                cumulative_trades=0,
                target_trades=cfg.trade_budget_cap,
                birth_start_time=self.birth_start_time,
                training_mode=training_mode,
            )

            def _history_chunk_progress(**chunk_meta: Any) -> None:
                if self._stop_requested():
                    return
                chunk_idx = int(
                    chunk_meta.get("chunk_index")
                    or chunk_meta.get("chunk")
                    or chunk_meta.get("loading_chunk")
                    or 0
                )
                chunk_total = int(
                    chunk_meta.get("chunk_total")
                    or chunk_meta.get("total_chunks")
                    or 0
                )
                bars_loaded = int(
                    chunk_meta.get("bars_merged")
                    or chunk_meta.get("bars_loaded")
                    or chunk_meta.get("chunk_bars")
                    or 0
                )
                chunk_phase = str(chunk_meta.get("chunk_phase", "fetch") or "fetch").strip().lower()
                pct = 8.0
                if chunk_total > 0 and chunk_idx > 0:
                    if chunk_phase == "expand":
                        pct = 15.0 + min(5.0, (chunk_idx / chunk_total) * 5.0)
                    else:
                        pct = 8.0 + min(7.0, (chunk_idx / chunk_total) * 7.0)
                if chunk_idx > 0 and chunk_total > 0:
                    if chunk_phase == "expand":
                        message = (
                            f"Ticks uitbreiden: {chunk_idx:,}/{chunk_total:,} bars "
                            f"({bars_loaded:,} merged)"
                        )
                    else:
                        message = (
                            f"Historische data laden: chunk {chunk_idx}/{chunk_total} "
                            f"({bars_loaded:,} bars)"
                        )
                else:
                    message = f"Historische data laden ({max_days} dagen)…"
                write_birth_progress(
                    self.workspace_root,
                    stage="loading_data",
                    phase="loading_history",
                    message=message,
                    progress_pct=pct,
                    cumulative_trades=0,
                    target_trades=cfg.trade_budget_cap,
                    birth_start_time=self.birth_start_time,
                    training_mode=training_mode,
                    loading_chunk=chunk_idx,
                    chunk_total=chunk_total,
                    bars_loaded=bars_loaded,
                    chunk_phase=chunk_phase,
                )

            ticks = load_historical_ticks(
                market_data_service=self.market_data_service,
                runtime=self.runtime,
                days_back=max_days,
                limit=None,
                on_chunk=_history_chunk_progress,
            )
            if self._stop_requested():
                return {"status": "paused", "total_trades": 0, "ppo_steps": 0, "training_mode": training_mode}
            self._write_data_prep_progress(
                phase="enriching_news",
                message=f"Historische data geladen ({len(ticks):,} ticks) — news enrichment…",
                progress_pct=20.5,
                training_mode=training_mode,
            )
        if not ticks and not prefer_real:
            ticks = self._generate_synthetic_ticks(max(20_000, max_days * 1000), start_price=5000.0)
        elif not ticks and prefer_real and practice_mode:
            ticks = self._generate_synthetic_ticks(20_000, start_price=5000.0)
        elif not ticks and prefer_real and allow_minimal_synthetic:
            logger.info("birth.synthetic.minimal_fallback reason=allow_minimal_synthetic_fallback")
            ticks = self._generate_synthetic_ticks(20_000, start_price=5000.0)
        elif not ticks:
            write_birth_progress(
                self.workspace_root,
                stage="history_unavailable",
                phase="loading_history_failed",
                message="Geen historische data beschikbaar.",
                progress_pct=100.0,
                cumulative_trades=0,
                target_trades=cfg.trade_budget_cap,
                birth_start_time=self.birth_start_time,
                retryable=True,
            )
            self._notify_history_unavailable("Geen historische data beschikbaar.")
            return {"status": "history_unavailable", "total_trades": 0, "ppo_steps": 0, "training_mode": "certified"}

        if split is None:
            news_cfg = cfg.news
            try:
                ticks = enrich_ticks_with_news(
                    ticks,
                    workspace_root=self.workspace_root,
                    primary=news_cfg.primary,
                    enable_cache=news_cfg.enable_cache,
                    cache_path=news_cfg.cache_path,
                )
            except Exception as exc:
                logger.warning("birth.news.enrich_skipped detail=%s", exc)

            if self._stop_requested():
                return {"status": "paused", "total_trades": 0, "ppo_steps": 0, "training_mode": training_mode}

            total_ticks = len(ticks)

            def _regime_enrich_progress(processed: int, total: int) -> None:
                if self._stop_requested():
                    return
                pct = 21.0
                if total > 0:
                    pct = 21.0 + min(3.0, (processed / total) * 3.0)
                self._write_data_prep_progress(
                    phase="enriching_regimes",
                    message=(
                        f"Regime map bouwen: {processed:,}/{total:,} ticks "
                        f"({total_ticks:,} totaal)"
                    ),
                    progress_pct=pct,
                    training_mode=training_mode,
                    processed=processed,
                    total=total,
                )

            self._write_data_prep_progress(
                phase="enriching_regimes",
                message=f"Regime map bouwen (0/{max(0, total_ticks - MIN_TREND_LOOKBACK):,} ticks)…",
                progress_pct=21.0,
                training_mode=training_mode,
            )
            ticks = enrich_ticks_for_sim(ticks, on_progress=_regime_enrich_progress)
            if self._stop_requested():
                return {"status": "paused", "total_trades": 0, "ppo_steps": 0, "training_mode": training_mode}

            self._real_data_pct = real_data_percentage(ticks)
            self._write_data_prep_progress(
                phase="train_holdout_split",
                message="Train/holdout split (purged)…",
                progress_pct=24.0,
                training_mode=training_mode,
            )
            split = purged_train_holdout_split(ticks, holdout_pct=cfg.holdout_pct)
            self._write_data_prep_progress(
                phase="holdout_preflight",
                message="Holdout preflight controleren…",
                progress_pct=24.5,
                training_mode=training_mode,
            )
        elif not ticks:
            return {"status": "history_unavailable", "total_trades": 0, "ppo_steps": 0, "training_mode": "certified"}

        preflight_result = self._ensure_holdout_preflight(
            ticks=ticks,
            split=split,
            max_days=max_days,
            prefer_real=prefer_real,
            start_price=float(ticks[-1].get("last", 5000.0) or 5000.0) if ticks else 5000.0,
            training_mode=training_mode,
            reuse_manifest=bool(reuse_data_manifest and resume),
            saved_manifest=self._data_manifest if resume else None,
        )
        if isinstance(preflight_result, dict):
            return preflight_result
        ticks, split, self._data_manifest = preflight_result

        write_birth_progress(
            self.workspace_root,
            stage="historical_loaded",
            phase="ticks_ready",
            message=(
                f"Data geladen: {len(ticks):,} ticks, holdout {split.holdout_days} dagen, "
                f"regimes {','.join(self._data_manifest.get('holdout_regimes', []))}."
            ),
            progress_pct=25.0,
            cumulative_trades=0,
            target_trades=cfg.trade_budget_cap,
            birth_start_time=self.birth_start_time,
            actual_real_days_loaded=max(1, len(ticks) // 450),
            real_data_pct=self._real_data_pct,
            preflight_report={
                "ok": True,
                "holdout_regimes": self._data_manifest.get("holdout_regimes", []),
            },
            data_manifest=self._data_manifest,
        )

        from lumina_core.notifications.milestone_events import (
            history_loaded_event,
            regime_map_ready_event,
        )

        self._notify_milestone(
            history_loaded_event(
                tick_count=len(ticks),
                real_data_pct=self._real_data_pct,
                max_real_days=max_days,
            )
        )
        self._notify_milestone(
            regime_map_ready_event(
                tick_count=len(ticks),
                train_bars=len(split.train),
                holdout_bars=len(split.holdout),
                holdout_days=int(split.holdout_days),
                real_data_pct=self._real_data_pct,
            )
        )

        self._write_data_prep_progress(
            phase="policy_init",
            message="Birth policy initialiseren…",
            progress_pct=26.0,
            training_mode=training_mode,
        )
        self.current_policy = self._create_birth_policy(
            allow_load_existing=allow_load and resume,
            policy_path=resume_policy_path or None,
        )
        start_price = float(ticks[-1].get("last", 5000.0) or 5000.0) if ticks else 5000.0

        if resume and not checkpoint_phase:
            progress_phase = str(progress_snapshot.get("phase", "") or "").strip().lower()
            if progress_phase in {"certificate_failed", "certificate_remediation"}:
                checkpoint_phase = progress_phase
                if not self._stages_passed:
                    self._stages_passed = list(progress_snapshot.get("stages_passed") or [])
                self._remediation_attempt = max(
                    self._remediation_attempt,
                    int(progress_snapshot.get("remediation_attempt", 0) or 0),
                )
                if not self._data_manifest:
                    manifest = progress_snapshot.get("data_manifest")
                    if isinstance(manifest, dict):
                        self._data_manifest = dict(manifest)

        if (
            not practice_mode
            and resume
            and should_fast_path_remediation_from_state(progress_snapshot, checkpoint_state)
        ):
            write_birth_progress(
                self.workspace_root,
                stage="training_running",
                phase="certificate_remediation",
                message="Resuming certificate remediation from checkpoint (fast path).",
                progress_pct=93.0,
                cumulative_trades=self.cumulative_trades,
                target_trades=cfg.trade_budget_cap,
                ppo_steps=self.ppo_steps,
                birth_start_time=self.birth_start_time,
                fast_path_resume=True,
            )
            prior_progress = read_birth_progress(self.workspace_root)
            prior_eval = prior_progress.get("oos_metrics")
            if not isinstance(prior_eval, dict) or not prior_eval.get("failure_reasons"):
                prior_eval = evaluate_holdout_certificate(
                    runtime=self.runtime,
                    holdout_data=split.holdout,
                    policy=self.current_policy,
                    real_data_pct=self._real_data_pct,
                    holdout_days=split.holdout_days,
                    constitution_violations=self._constitution_guard.violations,
                    workspace_root=self.workspace_root,
                    thresholds=cfg.certificate_thresholds,
                )
            eval_result = self._run_certificate_remediation(
                split=split,
                eval_result=dict(prior_eval),
                training_mode=training_mode,
                ppo_steps_per_update=ppo_steps_per_update,
                trade_budget_cap=cfg.trade_budget_cap,
                prefer_real=prefer_real,
                start_price=start_price,
            )
            if isinstance(eval_result, dict) and eval_result.get("status") == "paused":
                return eval_result
            if not eval_result.get("certificate_passed"):
                return {
                    "status": "certificate_failed",
                    "total_trades": self.cumulative_trades,
                    "ppo_steps": self.ppo_steps,
                    "real_data_pct": self._real_data_pct,
                    "eval": eval_result,
                    "training_mode": "certified",
                }
            from lumina_core.notifications.milestone_events import oos_evaluation_passed_event

            self._notify_milestone(oos_evaluation_passed_event(eval_result=eval_result))

            return self._complete_certified_birth(
                split=split,
                eval_result=eval_result,
                training_mode=training_mode,
                trade_budget_cap=cfg.trade_budget_cap,
            )

        total_stages = len(ordered_stages())
        stage_index = 0
        curriculum_timesteps = max(1000, int(cfg.curriculum.curriculum_ppo_timesteps))

        write_birth_progress(
            self.workspace_root,
            stage="training_running",
            phase="curriculum_stage",
            message="Curriculum training starten…",
            progress_pct=27.0,
            cumulative_trades=0,
            target_trades=cfg.trade_budget_cap,
            birth_start_time=self.birth_start_time,
            training_mode=training_mode,
        )

        for stage in ordered_stages():
            if self._stop_requested():
                policy_hint = str(self.final_policy_path)
                if self.final_policy_path.is_file():
                    policy_hint = str(self.final_policy_path)
                self._persist_checkpoint(
                    training_mode=training_mode,
                    curriculum_stage=stage.value,
                    policy_path=policy_hint,
                    phase="paused",
                )
                return self._paused_result()

            if stage == CurriculumStage.STAGE4_POLISH:
                break

            if stage.value in self._stages_passed:
                if self._verify_stage_pass_receipt_for_skip(stage, training_mode=training_mode):
                    stage_index += 1
                    continue

            stage_ticks = filter_ticks_for_stage(stage, split.train)
            if not stage_ticks:
                stage_ticks = list(split.train)
            target = stage_trade_target(stage, cfg.curriculum)
            self._accumulate_constitution_violations_before_stage_reset()

            stage_progress_pct = 27.0 + (stage_index / total_stages) * 53.0
            stage_error = self._run_stage_research_loop(
                stage=stage,
                stage_index=stage_index,
                stage_ticks=stage_ticks,
                train_ticks=list(split.train),
                holdout_ticks=list(split.holdout),
                target=target,
                stage_progress_pct=stage_progress_pct,
                training_mode=training_mode,
                ppo_steps_per_update=curriculum_timesteps,
                polish_ppo_timesteps=max(1000, int(cfg.curriculum.polish_ppo_timesteps)),
                trade_budget_cap=cfg.trade_budget_cap,
                prefer_real=prefer_real,
                start_price=start_price,
            )
            if stage_error is not None:
                return stage_error

            self._commit_stage_graduation(
                stage,
                training_mode=training_mode,
                curriculum_stage=stage.value,
                policy_path=str(self.final_policy_path),
                phase="curriculum_stage_complete",
            )
            stage_index += 1

        polish_scorecard = build_scorecard_payload(
            stage=CurriculumStage.STAGE4_POLISH,
            curriculum_index=4,
            stages_passed=list(self._stages_passed),
            stage_trades=0,
            stage_wins=0,
            stage_hold_signals=0,
            stage_total_signals=0,
            constitution_violations=self._constitution_guard.violations,
            target_trades=0,
            phase="ppo_polish",
            patterns_mined=0,
            learning_attempt=0,
            cfg=cfg.curriculum,
        )
        write_birth_progress(
            self.workspace_root,
            stage="ppo_training",
            phase="ppo_polish",
            message="Final PPO polish (stage4).",
            progress_pct=85.0,
            cumulative_trades=self.cumulative_trades,
            target_trades=cfg.trade_budget_cap,
            ppo_steps=self.ppo_steps,
            birth_start_time=self.birth_start_time,
            curriculum_stage=CurriculumStage.STAGE4_POLISH.value,
            **polish_scorecard,
        )

        from lumina_core.notifications.milestone_events import (
            curriculum_stage4_polish_passed_event,
            refinement_started_event,
        )

        self._notify_milestone(
            curriculum_stage4_polish_passed_event(
                stages_passed=list(self._stages_passed),
                cumulative_trades=self.cumulative_trades,
            )
        )
        self._notify_milestone(
            refinement_started_event(
                cumulative_trades=self.cumulative_trades,
                ppo_steps=self.ppo_steps,
            )
        )

        polish_steps = cfg.curriculum.polish_ppo_timesteps
        if len(self.buffer) >= 256:
            self.ppo_trainer.final_birth_polish(self.buffer)
            self.ppo_steps += polish_steps
        else:
            polish_batch = min(polish_steps, 10_000)
            self.ppo_trainer.update_from_buffer(
                buffer=self.buffer,
                timesteps=polish_batch,
                birth_phase=True,
            )
            self.ppo_steps += polish_batch
        self._persist_checkpoint(
            training_mode=training_mode,
            curriculum_stage=CurriculumStage.STAGE4_POLISH.value,
            policy_path=str(self.final_policy_path),
            phase="ppo_polish",
        )

        target_policy = self.practice_policy_path if practice_mode else self.final_policy_path
        self.ppo_trainer.save_final_birth_policy(str(target_policy))

        if practice_mode:
            self.practice_completed_flag_path.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
            clear_checkpoint(self.workspace_root)
            clear_buffer(self.workspace_root)
            write_birth_progress(
                self.workspace_root,
                stage="practice_completed",
                phase="practice_completed",
                message="Practice Birth voltooid (geen certificate).",
                progress_pct=100.0,
                cumulative_trades=self.cumulative_trades,
                target_trades=cfg.trade_budget_cap,
                birth_start_time=self.birth_start_time,
            )
            from lumina_core.notifications.milestone_events import practice_birth_completed_event

            self._notify_milestone(
                practice_birth_completed_event(
                    cumulative_trades=self.cumulative_trades,
                    ppo_steps=self.ppo_steps,
                    policy_path=str(target_policy),
                )
            )
            return {
                "status": "practice_completed",
                "total_trades": self.cumulative_trades,
                "ppo_steps": self.ppo_steps,
                "real_data_pct": self._real_data_pct,
                "policy_path": str(target_policy),
                "training_mode": "practice",
            }

        oos_scorecard = build_scorecard_payload(
            stage=CurriculumStage.STAGE4_POLISH,
            curriculum_index=3,
            stages_passed=list(self._stages_passed),
            stage_trades=0,
            stage_wins=0,
            stage_hold_signals=0,
            stage_total_signals=0,
            constitution_violations=self._constitution_guard.violations,
            target_trades=0,
            phase="oos_evaluation",
            patterns_mined=0,
            learning_attempt=0,
            cfg=cfg.curriculum,
        )
        write_birth_progress(
            self.workspace_root,
            stage="training_running",
            phase="oos_evaluation",
            message="OOS certificate evaluatie…",
            progress_pct=92.0,
            cumulative_trades=self.cumulative_trades,
            target_trades=cfg.trade_budget_cap,
            birth_start_time=self.birth_start_time,
            **oos_scorecard,
        )

        eval_result = evaluate_holdout_certificate(
            runtime=self.runtime,
            holdout_data=split.holdout,
            policy=self.current_policy,
            real_data_pct=self._real_data_pct,
            holdout_days=split.holdout_days,
            constitution_violations=self._constitution_guard.violations,
            workspace_root=self.workspace_root,
            thresholds=cfg.certificate_thresholds,
        )

        if not eval_result.get("certificate_passed"):
            eval_result = self._run_certificate_remediation(
                split=split,
                eval_result=eval_result,
                training_mode=training_mode,
                ppo_steps_per_update=ppo_steps_per_update,
                trade_budget_cap=cfg.trade_budget_cap,
                prefer_real=prefer_real,
                start_price=start_price,
            )
            if isinstance(eval_result, dict) and eval_result.get("status") == "paused":
                return eval_result
            if not eval_result.get("certificate_passed"):
                return {
                    "status": "certificate_failed",
                    "total_trades": self.cumulative_trades,
                    "ppo_steps": self.ppo_steps,
                    "real_data_pct": self._real_data_pct,
                    "eval": eval_result,
                    "training_mode": "certified",
                }

        from lumina_core.notifications.milestone_events import oos_evaluation_passed_event

        self._notify_milestone(oos_evaluation_passed_event(eval_result=eval_result))

        return self._complete_certified_birth(
            split=split,
            eval_result=eval_result,
            training_mode=training_mode,
            trade_budget_cap=cfg.trade_budget_cap,
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
    ) -> StallDetectionResult:
        """Detect learning stall from combined winrate and reward velocity trends."""
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
        """BRO stage loop: oracle mine, expand data, rollout — never stop on underperformance."""
        holdout_ticks_ref = list(holdout_ticks)
        cur_cfg = self.birth_config.curriculum
        news_cfg = self.birth_config.news
        required = stage_pass_trades(stage, cur_cfg)
        stage_pass_criteria = pass_criteria_for_stage(stage, cfg=cur_cfg)
        pass_metric_target = float(stage_pass_criteria.metric_target or 0.45)
        allow_provisional = training_mode == "practice" or cur_cfg.allow_provisional_pass
        max_rollouts = (
            cur_cfg.max_rollouts_per_stage
            if allow_provisional
            else min(cur_cfg.max_rollouts_per_stage, cur_cfg.certified_max_rollouts_per_stage)
        )
        stage_trades = 0
        stage_wins = 0
        stage_hold_signals = 0
        stage_total_signals = 0
        stage_range_hold_signals = 0
        stage_range_total_signals = 0
        stage_range_flat_bars = 0
        stage_range_round_trips = 0
        attempt = 0
        escalation_level = 0
        gen0_provisional = False
        patterns_mined = 0
        oracle_wins = 0
        expansion_step = 0
        data_days_loaded = self.birth_config.max_real_days
        hold_stagnation_count = 0
        winrate_stagnation_count = 0
        wall_budget_exhausted = False
        winrate_history: list[float] = []
        budget_milestones_notified: set[int] = set()
        hold_trap_milestone_sent = False
        reward_history: list[float] = []
        low_velocity_attempts = 0
        strong_recovery_mode = False
        strong_recovery_attempts = 0
        provisional_pass_considered = False
        retries_this_stage = 0
        adaptation_tier = 0
        adaptation_history: list[dict[str, Any]] = []
        original_rollout_chunk = cur_cfg.rollout_chunk_trades
        stage_started_at = time.time()
        effective_trade_budget_cap = trade_budget_cap
        checkpoint_state = load_checkpoint_state(self.workspace_root)
        checkpoint_curriculum = str(checkpoint_state.get("curriculum_stage", "") or "").strip().lower()
        stage_metrics = checkpoint_state.get("stage_metrics")
        metrics_match_stage = (
            isinstance(stage_metrics, dict)
            and checkpoint_curriculum == stage.value
            and str(stage_metrics.get("curriculum_stage_scope", stage.value) or stage.value).strip().lower()
            == stage.value
        )
        if metrics_match_stage:
            patterns_mined = max(0, int(stage_metrics.get("patterns_mined", patterns_mined) or patterns_mined))
            stage_trades = max(0, int(stage_metrics.get("stage_trades", stage_trades) or stage_trades))
            stage_wins = max(0, int(stage_metrics.get("stage_wins", stage_wins) or stage_wins))
            stage_hold_signals = max(
                0, int(stage_metrics.get("stage_hold_signals", stage_hold_signals) or stage_hold_signals)
            )
            stage_total_signals = max(
                0, int(stage_metrics.get("stage_total_signals", stage_total_signals) or stage_total_signals)
            )
            stage_range_hold_signals = max(
                0,
                int(stage_metrics.get("stage_range_hold_signals", stage_range_hold_signals) or stage_range_hold_signals),
            )
            stage_range_total_signals = max(
                0,
                int(
                    stage_metrics.get("stage_range_total_signals", stage_range_total_signals)
                    or stage_range_total_signals
                ),
            )
            stage_range_flat_bars = max(
                0,
                int(stage_metrics.get("stage_range_flat_bars", stage_range_flat_bars) or stage_range_flat_bars),
            )
            stage_range_round_trips = max(
                0,
                int(
                    stage_metrics.get("stage_range_round_trips", stage_range_round_trips)
                    or stage_range_round_trips
                ),
            )
            raw_history = stage_metrics.get("winrate_history")
            if isinstance(raw_history, list):
                winrate_history = [float(x) for x in raw_history if isinstance(x, (int, float))]
            raw_reward_history = stage_metrics.get("reward_history")
            if isinstance(raw_reward_history, list):
                reward_history = [float(x) for x in raw_reward_history if isinstance(x, (int, float))]
            low_velocity_attempts = max(
                0, int(stage_metrics.get("velocity_stall_attempts", low_velocity_attempts) or 0)
            )
            strong_recovery_mode = bool(stage_metrics.get("strong_recovery_mode", False))
            strong_recovery_attempts = max(
                0, int(stage_metrics.get("strong_recovery_attempts", 0) or 0)
            )
            retries_this_stage = max(0, int(stage_metrics.get("retries_this_stage", 0) or 0))
            adaptation_tier = max(0, int(stage_metrics.get("adaptation_tier", 0) or 0))
            raw_adaptations = stage_metrics.get("adaptation_history")
            if isinstance(raw_adaptations, list):
                adaptation_history = [dict(x) for x in raw_adaptations if isinstance(x, dict)]
            if stage_metrics.get("escalation_level") is not None:
                escalation_level = max(0, int(stage_metrics.get("escalation_level", 0) or 0))
        plateau_state = PlateauState.from_metrics(stage_metrics if metrics_match_stage else {})
        remediation_state = StallRemediationState.from_metrics(
            stage_metrics if metrics_match_stage else {}
        )
        prev_progress = read_birth_progress(self.workspace_root)
        if str(prev_progress.get("curriculum_stage", "") or "").strip().lower() == stage.value:
            stage_trades = max(0, int(prev_progress.get("stage_trades", 0) or 0))
            if prev_progress.get("stage_wins") is not None:
                stage_wins = max(0, int(prev_progress.get("stage_wins", 0) or 0))
            stage_hold_signals = max(0, int(prev_progress.get("stage_hold_signals", 0) or 0))
            stage_total_signals = max(0, int(prev_progress.get("stage_total_signals", 0) or 0))
            stage_range_flat_bars = max(0, int(prev_progress.get("stage_range_flat_bars", 0) or 0))
            stage_range_round_trips = max(0, int(prev_progress.get("stage_range_round_trips", 0) or 0))
            stage_range_total_signals = max(
                0, int(prev_progress.get("stage_range_total_signals", 0) or 0)
            )
            patterns_mined = max(0, int(prev_progress.get("patterns_mined", 0) or 0))
            oracle_wins = max(0, int(prev_progress.get("oracle_wins", 0) or 0))
            attempt = max(0, int(prev_progress.get("learning_attempt", 0) or 0) - 1)
            escalation_level = max(0, int(prev_progress.get("escalation_level", 0) or 0))
            gen0_provisional = bool(prev_progress.get("gen0_provisional", False))
            expansion_step = max(0, int(prev_progress.get("expansion_step", 0) or 0))
            data_days_loaded = max(
                0,
                int(prev_progress.get("data_days_loaded", data_days_loaded) or data_days_loaded),
            )
        if adaptation_history:
            last_chunk = adaptation_history[-1].get("chunk_target")
            if last_chunk is not None:
                cur_cfg.rollout_chunk_trades = max(
                    cur_cfg.exploration_chunk_size,
                    int(last_chunk),
                )
        elif strong_recovery_mode:
            cur_cfg.rollout_chunk_trades = max(
                cur_cfg.exploration_chunk_size,
                cur_cfg.exploration_chunk_size * 2,
            )
        if plateau_state.active:
            sanitize_plateau_best_snapshot(
                plateau_state,
                cfg=cur_cfg,
                stage_trades=stage_trades,
                stage_wins=stage_wins,
            )
        last_stage_trades = -1
        stagnation_count = 0
        chunk_budget = max(5_000, cur_cfg.rollout_chunk_trades * cur_cfg.rollout_step_budget_multiplier)
        active_train = list(train_ticks)
        active_stage_ticks = list(stage_ticks)
        data_exhausted = False
        scorecard_snapshot_trades = stage_trades
        scorecard_snapshot_patterns = patterns_mined
        scorecard_snapshot_at = time.time()
        last_progress_write_at = 0.0
        last_hold_ratio = 0.0

        def _trade_budget_remaining() -> int:
            return max(0, int(effective_trade_budget_cap) - int(self.cumulative_trades))

        def _remediation_exhausted_now() -> bool:
            return remediation_is_exhausted(
                remediation_active=remediation_state.active,
                remediation_step=remediation_state.remediation_step,
                remediation_cycle=remediation_state.remediation_cycle,
                cfg=cur_cfg,
            )

        intra_state: Stage1IntraCurriculumState | None = None
        intra_easy_pool: list[dict[str, Any]] = []
        intra_hard_pool: list[dict[str, Any]] = []
        intra_meta: dict[str, Any] = {}
        current_intra_sample_pool: list[dict[str, Any]] = []

        def _rebuild_intra_pools(ticks: list[dict[str, Any]]) -> None:
            nonlocal intra_easy_pool, intra_hard_pool, intra_meta
            if stage != CurriculumStage.STAGE1_TREND or not cur_cfg.intra_stage1_enabled:
                intra_easy_pool = []
                intra_hard_pool = []
                intra_meta = {}
                return
            intra_easy_pool, intra_hard_pool, intra_meta = split_stage1_trend_ticks(
                ticks,
                easy_percentile=cur_cfg.intra_easy_percentile,
                hard_percentile=cur_cfg.intra_hard_percentile,
            )

        if stage == CurriculumStage.STAGE1_TREND and cur_cfg.intra_stage1_enabled:
            if isinstance(stage_metrics, dict) and stage_metrics.get("intra_stage1_hard_pct") is not None:
                intra_state = stage1_intra_state_from_metrics(
                    stage_metrics,
                    default_hard_pct=cur_cfg.intra_initial_hard_pct,
                )
            else:
                intra_state = Stage1IntraCurriculumState(hard_pct=cur_cfg.intra_initial_hard_pct)
            _rebuild_intra_pools(active_stage_ticks)
        last_winrate = 0.0
        meta_controller = BirthMetaController(cur_cfg, self.birth_config.reward)
        meta_controller.restore_state(stage_metrics if isinstance(stage_metrics, dict) else None)
        meta_last_plan: MetaActionPlan | None = None
        meta_message_suffix = ""

        def _apply_oracle_distill() -> str:
            removed = curate_buffer_top_quartile(
                self.buffer,
                keep_pct=float(cur_cfg.plateau_oracle_distill_top_pct),
            )
            if len(self.buffer) >= 256:
                polish = max(1000, int(getattr(cur_cfg, "polish_ppo_timesteps", 10_000)))
                batch = min(5000, polish)
                self.ppo_trainer.update_from_buffer(
                    buffer=self.buffer,
                    timesteps=batch,
                    birth_phase=True,
                )
                self.ppo_steps += batch
            return f"oracle distill (removed {removed} low-reward trajectories)"

        def _apply_phoenix_reset() -> str:
            nonlocal escalation_level, strong_recovery_mode
            self.current_policy = self._create_birth_policy(allow_load_existing=False)
            removed = curate_buffer_top_quartile(
                self.buffer,
                keep_pct=float(cur_cfg.plateau_oracle_distill_top_pct),
            )
            if intra_state is not None:
                intra_state.hard_pct = 0.0
                intra_state.easy_trades = 0
                intra_state.easy_wins = 0
                intra_state.easy_winrate_history.clear()
                _rebuild_intra_pools(active_stage_ticks)
            escalation_level = min(cur_cfg.max_escalation_level, escalation_level + 2)
            strong_recovery_mode = True
            detail = f"phoenix reset (buffer curated, removed {removed})"
            try:
                from lumina_core.notifications.milestone_events import phoenix_reset_event

                self._notify_milestone(
                    phoenix_reset_event(
                        cycle=plateau_state.full_recovery_cycles,
                        winrate=float(stage_wins) / float(max(1, stage_trades)),
                        detail=detail,
                    )
                )
            except Exception as exc:
                logger.debug("birth.milestone_phoenix_failed: %s", exc)
            return detail

        def _observe_snapshot() -> tuple[Any, StallDetectionResult]:
            return meta_controller.observe(
                winrate_history=winrate_history,
                reward_history=reward_history,
                stage_trades=stage_trades,
                required_trades=required,
                patterns_mined=patterns_mined,
                buffer_size=len(self.buffer),
                escalation_level=escalation_level,
                strong_recovery_mode=strong_recovery_mode,
                strong_recovery_attempts=strong_recovery_attempts,
                low_velocity_attempts=low_velocity_attempts,
                data_exhausted=data_exhausted,
                stage=stage,
                intra_hard_pct=intra_state.hard_pct if intra_state else None,
                attempt=attempt,
            )

        def _stage_metrics_payload() -> dict[str, Any]:
            payload = self._stage_metrics_snapshot(
                stage_trades=stage_trades,
                stage_wins=stage_wins,
                stage_hold_signals=stage_hold_signals,
                stage_total_signals=stage_total_signals,
                stage_range_hold_signals=stage_range_hold_signals,
                stage_range_total_signals=stage_range_total_signals,
                stage_range_flat_bars=stage_range_flat_bars,
                stage_range_round_trips=stage_range_round_trips,
                patterns_mined=patterns_mined,
            )
            payload["winrate_history"] = list(winrate_history)
            payload["reward_history"] = list(reward_history)
            payload["velocity_stall_attempts"] = int(low_velocity_attempts)
            payload["strong_recovery_mode"] = bool(strong_recovery_mode)
            payload["strong_recovery_attempts"] = int(strong_recovery_attempts)
            payload["retries_this_stage"] = int(retries_this_stage)
            payload["adaptation_tier"] = int(adaptation_tier)
            payload["adaptation_history"] = list(adaptation_history)
            payload["escalation_level"] = int(escalation_level)
            payload["curriculum_stage_scope"] = stage.value
            if intra_state is not None:
                payload["intra_stage1_hard_pct"] = round(float(intra_state.hard_pct), 4)
                payload["intra_stage1_easy_trades"] = int(intra_state.easy_trades)
                payload["intra_stage1_easy_wins"] = int(intra_state.easy_wins)
                payload["intra_stage1_easy_winrate_history"] = list(intra_state.easy_winrate_history)
                payload["intra_stage1_meta"] = dict(intra_meta)
            if cur_cfg.meta_controller_enabled:
                payload.update(meta_controller.metrics_payload())
            payload.update(plateau_state.to_metrics())
            payload.update(remediation_state.to_metrics())
            return payload

        def _maybe_periodic_checkpoint(phase: str) -> None:
            interval = max(60, int(cur_cfg.checkpoint_interval_sec))
            if self._last_checkpoint_at <= 0.0 or time.time() - self._last_checkpoint_at >= interval:
                self._persist_checkpoint(
                    training_mode=training_mode,
                    curriculum_stage=stage.value,
                    phase=phase,
                    stage_metrics=_stage_metrics_payload(),
                )

        def _write_progress(
            *,
            phase: str,
            message: str,
            chunk_trades: int = 0,
            rollout_steps: int = 0,
            exploration_active: bool = False,
            hold_ratio: float = 0.0,
        ) -> None:
            nonlocal scorecard_snapshot_trades, scorecard_snapshot_patterns, scorecard_snapshot_at
            nonlocal last_progress_write_at
            current_stage_trades = stage_trades + chunk_trades
            elapsed_snapshot = max(0.0, time.time() - scorecard_snapshot_at)
            scorecard = build_scorecard_payload(
                stage=stage,
                curriculum_index=stage_index + 1,
                stages_passed=list(self._stages_passed),
                stage_trades=current_stage_trades,
                stage_wins=stage_wins,
                stage_hold_signals=stage_hold_signals,
                stage_total_signals=stage_total_signals,
                constitution_violations=self._constitution_guard.violations,
                target_trades=target,
                phase=phase,
                patterns_mined=patterns_mined,
                learning_attempt=attempt + 1,
                prev_stage_trades=scorecard_snapshot_trades,
                prev_patterns_mined=scorecard_snapshot_patterns,
                snapshot_elapsed_sec=elapsed_snapshot,
                stage_range_flat_bars=stage_range_flat_bars,
                stage_range_total_signals=stage_range_total_signals,
                stage_range_round_trips=stage_range_round_trips,
                provisional_pass=gen0_provisional,
                cfg=cur_cfg,
            )
            adaptation_fields = enrich_adaptation_payload(
                stage_trades=current_stage_trades,
                required=required,
                winrate_history=winrate_history,
                retries_this_stage=retries_this_stage,
                adaptation_tier=adaptation_tier,
                max_adaptation_tiers=cur_cfg.max_adaptation_tiers,
                max_stage_retries=cur_cfg.max_stage_retries,
                adaptation_history=adaptation_history,
                adaptation_enabled=cur_cfg.adaptation_enabled,
                wall_behavior=cur_cfg.wall_behavior,
                reward_history=reward_history,
                strong_recovery_mode=strong_recovery_mode,
                velocity_stall_attempts=low_velocity_attempts,
                strong_recovery_attempts=strong_recovery_attempts,
                provisional_pass_considered=provisional_pass_considered,
            )
            scorecard.update(adaptation_fields)
            scorecard.update(
                plateau_progress_fields(
                    plateau_state,
                    stage_trades=current_stage_trades,
                    required=required,
                    cfg=cur_cfg,
                )
            )
            scorecard.update(
                build_plateau_audit(
                    plateau_state,
                    stage_trades=current_stage_trades,
                    required=required,
                    cfg=cur_cfg,
                    progress=scorecard,
                    remediation_exhausted=remediation_is_exhausted(
                        remediation_active=remediation_state.active,
                        remediation_step=remediation_state.remediation_step,
                        remediation_cycle=remediation_state.remediation_cycle,
                        cfg=cur_cfg,
                    ),
                    trade_budget_remaining=max(0, trade_budget_cap - self.cumulative_trades),
                )
            )
            scorecard["stall_remediation_cycle"] = int(remediation_state.remediation_cycle)
            scorecard["stall_remediation_step"] = int(remediation_state.remediation_step)
            scorecard["stall_remediation_max_steps"] = int(cur_cfg.stall_remediation_max_steps)
            scorecard["stall_remediation_max_cycles"] = int(cur_cfg.stall_remediation_max_cycles)
            scorecard["stage1_winrate_gate"] = float(
                getattr(cur_cfg, "stage1_winrate_pass_threshold", 0.45)
            )
            scorecard["stage1_winrate_recommended"] = float(
                getattr(cur_cfg, "stage1_winrate_recommended", 0.45)
            )
            if cur_cfg.meta_controller_enabled:
                scorecard.update(meta_controller.scorecard_fields(meta_last_plan))
            elapsed_stage_sec = max(0.0, time.time() - stage_started_at)
            write_birth_progress(
                self.workspace_root,
                stage="training_running",
                phase=phase,
                message=message,
                progress_pct=stage_progress_pct,
                cumulative_trades=self.cumulative_trades + chunk_trades,
                target_trades=trade_budget_cap,
                ppo_steps=self.ppo_steps,
                birth_start_time=self.birth_start_time,
                curriculum_stage=stage.value,
                stage_trades=current_stage_trades,
                stage_hold_signals=stage_hold_signals,
                stage_total_signals=stage_total_signals,
                stage_range_hold_signals=stage_range_hold_signals,
                stage_range_total_signals=stage_range_total_signals,
                stage_range_flat_bars=stage_range_flat_bars,
                stage_range_round_trips=stage_range_round_trips,
                stage_range_flat_ratio=round(
                    float(stage_range_flat_bars) / float(max(1, stage_range_total_signals)),
                    4,
                ),
                rollout_trades=chunk_trades,
                rollout_steps=rollout_steps,
                hold_ratio=round(hold_ratio, 4),
                exploration_active=exploration_active,
                learning_attempt=attempt + 1,
                escalation_level=escalation_level,
                gen0_provisional=gen0_provisional,
                patterns_mined=patterns_mined,
                oracle_wins=oracle_wins,
                data_days_loaded=data_days_loaded,
                expansion_step=expansion_step,
                stage_wall_remaining_sec=max(
                    0, int(cur_cfg.max_stage_wall_sec) - int(elapsed_stage_sec)
                ),
                quality_score=float(self._data_manifest.get("quality_score", 0.0) or 0.0),
                intra_hard_pct=round(float(intra_state.hard_pct), 4) if intra_state else None,
                intra_easy_winrate=round(
                    float(intra_state.easy_wins) / float(max(1, intra_state.easy_trades)),
                    4,
                )
                if intra_state and intra_state.easy_trades > 0
                else None,
                **scorecard,
            )
            if (
                current_stage_trades > scorecard_snapshot_trades
                or patterns_mined > scorecard_snapshot_patterns
            ):
                scorecard_snapshot_trades = current_stage_trades
                scorecard_snapshot_patterns = patterns_mined
                scorecard_snapshot_at = time.time()
            last_progress_write_at = time.time()

        def _log_meta_decision(plan: MetaActionPlan, trigger: str) -> None:
            event = BirthMetaController.format_decision_log(plan, trigger=trigger)
            logger.info(
                "birth.meta.decision trigger=%s primary=%s rationale=%s "
                "health=%s combined_velocity=%.6f is_stalled=%s",
                event.get("trigger"),
                event.get("primary"),
                event.get("rationale"),
                event.get("learning_health"),
                float(event.get("combined_velocity", 0.0) or 0.0),
                event.get("is_stalled"),
                extra={"event_data": event},
            )

        def _log_stall_event(
            *,
            event: str,
            stall: StallDetectionResult,
            strong_recovery: bool,
        ) -> None:
            logger.info(
                "birth.%s stage=%s winrate_velocity=%.6f reward_velocity=%.6f "
                "combined=%.6f attempts=%s/%s strong_recovery=%s escalation=%s",
                event,
                stage.value,
                stall.winrate_velocity,
                stall.reward_velocity,
                stall.combined_velocity,
                stall.low_velocity_attempts,
                stall.threshold,
                strong_recovery,
                escalation_level,
            )

        def _log_provisional_pass_outcome(
            *,
            source: str,
            should_grant: bool,
            blocked_reason: str | None,
            safeguards: dict[str, Any],
        ) -> None:
            logger.info(
                "birth.provisional_pass source=%s stage=%s should_grant=%s "
                "blocked_reason=%s safeguards=%s",
                source,
                stage.value,
                should_grant,
                blocked_reason or "",
                safeguards,
            )

        def _apply_meta_plan(plan: MetaActionPlan, *, trigger: str = "") -> None:
            nonlocal escalation_level, strong_recovery_mode, strong_recovery_attempts
            nonlocal low_velocity_attempts, meta_last_plan, meta_message_suffix
            meta_last_plan = plan
            if plan.escalation_delta > 0:
                escalation_level = min(
                    cur_cfg.max_escalation_level,
                    escalation_level + plan.escalation_delta,
                )
            elif plan.escalation_delta < 0:
                escalation_level = max(0, escalation_level + plan.escalation_delta)
            if plan.chunk_target is not None:
                cur_cfg.rollout_chunk_trades = plan.chunk_target
            if plan.enter_strong_recovery:
                strong_recovery_mode = True
                strong_recovery_attempts = 0
                low_velocity_attempts = 0
                meta_controller.explore_multiplier = max(
                    0.4,
                    min(1.0, float(cur_cfg.meta_explore_decay_stall)),
                )
            if plan.exit_strong_recovery:
                strong_recovery_mode = False
                strong_recovery_attempts = 0
                cur_cfg.rollout_chunk_trades = max(
                    cur_cfg.exploration_chunk_size,
                    original_rollout_chunk,
                )
                meta_controller.explore_multiplier = 1.0
            if plan.explore_steps_multiplier != 1.0:
                meta_controller.explore_multiplier = max(
                    0.4,
                    min(1.0, float(plan.explore_steps_multiplier)),
                )
            if plan.intra_hard_pct_delta is not None and intra_state is not None:
                intra_state.hard_pct = max(
                    cur_cfg.intra_initial_hard_pct,
                    min(
                        cur_cfg.intra_max_hard_pct,
                        intra_state.hard_pct + plan.intra_hard_pct_delta,
                    ),
                )
            if plan.mine:
                _mine_and_inject(aggressive=plan.mine_aggressive)
            if plan.expand_data:
                _maybe_expand_data()
            if plan.reward_tweak is not None:
                meta_controller.active_reward = plan.reward_tweak
            if plan.primary != RecoveryStrategy.HOLD:
                meta_message_suffix = (
                    f" · meta: {plan.primary.value} ({plan.rationale})"
                )
            self_eval_suffix = meta_controller.format_self_eval_suffix()
            if self_eval_suffix:
                meta_message_suffix = self_eval_suffix
            if trigger:
                _log_meta_decision(plan, trigger)
            else:
                logger.info(
                    "birth.meta.applied primary=%s rationale=%s",
                    plan.primary.value,
                    plan.rationale,
                )

        def _mine_and_inject(*, aggressive: bool = False) -> None:
            nonlocal patterns_mined, oracle_wins, active_stage_ticks
            if current_intra_sample_pool:
                pool = list(current_intra_sample_pool)
            elif len(active_train) > len(active_stage_ticks):
                pool = list(active_train)
            else:
                pool = list(active_stage_ticks)
            max_patterns, scan_stride = self._resolve_oracle_mining_params(
                cur_cfg,
                aggressive=aggressive,
            )
            mine_result = mine_winning_patterns(
                ticks=pool,
                stage=stage,
                runtime=self.runtime,
                workspace_root=self.workspace_root,
                max_patterns=max_patterns,
                scan_stride=scan_stride,
                max_hold_bars=cur_cfg.oracle_max_hold_bars,
            )
            patterns_mined += len(mine_result.patterns)
            oracle_wins += mine_result.wins
            meta_controller.record_inject(
                patterns=len(mine_result.patterns),
                oracle_wins=mine_result.wins,
            )
            for pattern in mine_result.patterns:
                self.buffer.add(pattern, priority=3.0 + min(10.0, abs(float(pattern.get("reward", 0.0)))))
            active_stage_ticks = filter_ticks_for_stage(stage, active_train) or list(active_train)
            _rebuild_intra_pools(active_stage_ticks)

        def _maybe_expand_data() -> bool:
            nonlocal active_train, active_stage_ticks, expansion_step, data_days_loaded, data_exhausted
            if data_exhausted:
                return False
            expanded = expand_birth_data(
                market_data_service=self.market_data_service,
                runtime=self.runtime,
                current_step=expansion_step,
                expansion_steps=list(cur_cfg.data_expansion_steps),
                holdout_pct=self.birth_config.holdout_pct,
                enrich_news_fn=lambda rows: enrich_ticks_with_news(
                    rows,
                    workspace_root=self.workspace_root,
                    primary=news_cfg.primary,
                    enable_cache=news_cfg.enable_cache,
                    cache_path=news_cfg.cache_path,
                ),
                synthetic_fallback_fn=(
                    None
                    if prefer_real
                    else lambda n, p: self._generate_synthetic_ticks(n, start_price=p or start_price)
                ),
                start_price=start_price,
            )
            expansion_step = expanded.step_index
            data_days_loaded = expanded.days_back
            if expanded.exhausted and not expanded.train_ticks:
                data_exhausted = True
                return False
            active_train = list(expanded.train_ticks)
            active_stage_ticks = filter_ticks_for_stage(stage, active_train) or list(active_train)
            _rebuild_intra_pools(active_stage_ticks)
            self._real_data_pct = expanded.real_data_pct
            _write_progress(
                phase="data_expansion",
                message=(
                    f"Data expansion: {data_days_loaded} dagen, "
                    f"{len(active_train):,} train ticks · {stage.value}"
                ),
            )
            return True

        _write_progress(
            phase="curriculum_research",
            message=f"Curriculum {stage.value}: oracle scan start (doel {required:,} trades).",
        )
        if isinstance(stage_metrics, dict) and stage_metrics.get("pending_data_expand"):
            _maybe_expand_data()
            pending_cleared = dict(_stage_metrics_payload())
            pending_cleared.pop("pending_data_expand", None)
            self._persist_checkpoint(
                training_mode=training_mode,
                curriculum_stage=stage.value,
                policy_path=str(self.final_policy_path),
                phase="curriculum_learning",
                stage_metrics=pending_cleared,
            )
        _mine_and_inject()
        if len(self.buffer) >= 80:
            self.current_policy = self.ppo_trainer.update_from_buffer(
                buffer=self.buffer,
                timesteps=ppo_steps_per_update,
                birth_phase=True,
            )
            self.ppo_steps += ppo_steps_per_update

        def _would_certified_stage_stall(
            *,
            elapsed_stage_sec: float,
            failure_key: str,
            force: bool = False,
        ) -> dict[str, Any] | None:
            if allow_provisional or stage_trades < required:
                return None
            blocker_metric, blocker_value, blocker_reason = compute_stage_blocker(
                stage,
                stage_trades=stage_trades,
                stage_wins=stage_wins,
                hold_ratio=float(stage_hold_signals) / float(max(1, stage_total_signals)),
                required=required,
                constitution_violations=self._constitution_guard.violations,
                range_flat_ratio=float(stage_range_flat_bars)
                / float(max(1, stage_range_total_signals)),
                range_round_trips=stage_range_round_trips,
                range_total_signals=stage_range_total_signals,
                cfg=cur_cfg,
            )
            if not blocker_metric:
                return None
            if not force:
                stagnation_met = False
                if stage == CurriculumStage.STAGE1_TREND:
                    stagnation_met = (
                        winrate_stagnation_count >= cur_cfg.stage1_winrate_stagnation_rollouts
                    )
                elif stage == CurriculumStage.STAGE2_RANGE:
                    stagnation_met = (
                        hold_stagnation_count >= cur_cfg.stage2_hold_stagnation_rollouts
                    )
                elif stage == CurriculumStage.STAGE3_MIXED:
                    stagnation_met = self._constitution_guard.violations > 0
                stall_wall = max(300, int(cur_cfg.certified_stage_stall_wall_sec))
                if not stagnation_met:
                    return None
                if not (elapsed_stage_sec >= stall_wall or wall_budget_exhausted):
                    return None
            return {
                "failure_key": failure_key,
                "blocker_metric": blocker_metric,
                "blocker_value": blocker_value,
                "blocker_reason": blocker_reason,
            }

        def _finalize_certified_stage_stall(
            pending: dict[str, Any],
            *,
            human_gate: bool = False,
        ) -> dict[str, Any]:
            failure_key = str(pending["failure_key"])
            blocker_metric = pending["blocker_metric"]
            blocker_value = pending["blocker_value"]
            blocker_reason = pending.get("blocker_reason")
            logger.info(
                "birth.terminal_stall reason=%s cumulative_trades=%s cap=%s "
                "adaptation_tier=%s retries=%s data_exhausted=%s buffer=%s human_gate=%s",
                blocker_reason or failure_key,
                self.cumulative_trades,
                effective_trade_budget_cap,
                adaptation_tier,
                retries_this_stage,
                data_exhausted,
                len(self.buffer),
                human_gate,
            )
            stall_reason = str(
                pending.get("terminal_stall_reason")
                or pending.get("blocker_reason")
                or failure_key
                or blocker_metric
                or "stage_stalled"
            )
            needs_attention = bool(human_gate) or stall_reason in {
                TERMINAL_STALL_REASON,
                HUMAN_GATE_REASON,
            }
            retryable = not needs_attention
            write_birth_progress(
                self.workspace_root,
                stage="stage_stalled",
                phase="stage_stalled",
                message=(
                    f"Stage {stage.value} stalled: "
                    f"{blocker_reason or blocker_metric or failure_key}"
                ),
                progress_pct=stage_progress_pct,
                cumulative_trades=self.cumulative_trades,
                target_trades=effective_trade_budget_cap,
                birth_start_time=self.birth_start_time,
                curriculum_stage=stage.value,
                stages_passed=list(self._stages_passed),
                stage_blocker_metric=blocker_metric,
                stage_blocker_value=blocker_value,
                pass_reason=blocker_reason,
                retryable=retryable,
                needs_attention=needs_attention,
                **self._budget_progress_fields(terminal_stall_reason=stall_reason),
                **self._constitution_progress_fields(),
            )
            policy_hint = str(self.final_policy_path)
            if self.final_policy_path.is_file():
                policy_hint = str(self.final_policy_path)
            self._persist_checkpoint(
                training_mode=training_mode,
                curriculum_stage=stage.value,
                policy_path=policy_hint,
                phase="stage_stalled",
                stage_metrics=_stage_metrics_payload(),
            )
            if needs_attention:
                try:
                    from lumina_core.notifications.attention_events import birth_stage_stalled_event
                    from lumina_core.notifications.attention_notifier import notify_attention

                    winrate = float(stage_wins) / float(max(1, stage_trades))
                    notify_attention(
                        birth_stage_stalled_event(
                            curriculum_stage=stage.value,
                            stall_reason=stall_reason,
                            blocker_detail=str(blocker_reason or blocker_metric or failure_key),
                            stage_trades=stage_trades,
                            winrate=winrate,
                            retryable=retryable,
                            phase2_active=remediation_state.active,
                        ),
                        workspace_root=self.workspace_root,
                    )
                except Exception as exc:
                    logger.warning("birth.attention_notify_failed: %s", exc)
            return {
                "status": "stage_stalled",
                "failure_reason": failure_key,
                "total_trades": self.cumulative_trades,
                "ppo_steps": self.ppo_steps,
                "training_mode": training_mode,
            }

        def _apply_stall_remediation_action(action: StallRemediationAction | None) -> str:
            nonlocal attempt, active_train, active_stage_ticks, strong_recovery_mode, escalation_level
            if action is None:
                return "no action"
            detail = ""
            if action == StallRemediationAction.EXPAND_AND_RETRY:
                _maybe_expand_data()
                detail = "expanded data window"
            elif action == StallRemediationAction.BUFFER_CURATE_ORACLE:
                removed = curate_buffer_bottom_half(self.buffer)
                strong_recovery_mode = True
                _mine_and_inject(aggressive=True)
                detail = f"curated {removed} low-reward buffer trajectories"
            elif action == StallRemediationAction.REGIME_DIVERSE_SLICE:
                filtered = filter_train_ticks_for_holdout_profile(
                    active_train,
                    holdout_ticks_ref,
                )
                if filtered:
                    active_train = list(filtered)
                    active_stage_ticks = filter_ticks_for_stage(stage, active_train)
                detail = "regime-diverse train slice applied"
            elif action == StallRemediationAction.META_SWEEP:
                remediation_state.meta_sweep_index += 1
                escalation_level = min(
                    cur_cfg.max_escalation_level,
                    escalation_level + 1,
                )
                detail = f"meta explore sweep #{remediation_state.meta_sweep_index}"
            elif action == StallRemediationAction.ORACLE_DISTILL:
                detail = _apply_oracle_distill()
            if remediation_state.remediation_cycle >= 2:
                self.current_policy = self._create_birth_policy(allow_load_existing=False)
                if intra_state is not None:
                    intra_state.hard_pct = 0.0
                    _rebuild_intra_pools(active_stage_ticks)
                strong_recovery_mode = True
                if detail:
                    detail = f"{detail}; aggressive cycle {remediation_state.remediation_cycle}"
                else:
                    detail = f"aggressive cycle {remediation_state.remediation_cycle}"
            return detail

        def _try_stall_remediation_on_terminal(pending: dict[str, Any]) -> bool:
            """Return True when remediation applied and loop should continue."""
            nonlocal attempt
            stall_reason = str(
                pending.get("terminal_stall_reason") or pending.get("blocker_reason") or ""
            )
            if stall_reason != TERMINAL_STALL_REASON:
                return False
            if not should_run_remediation_instead_of_human_gate(
                remediation_state,
                cfg=cur_cfg,
                plateau_exhausted=True,
            ):
                return False
            if can_start_remediation(remediation_state, cfg=cur_cfg):
                begin_remediation_cycle(
                    remediation_state,
                    stage_trades=stage_trades,
                    stage_wins=stage_wins,
                )
                try:
                    from lumina_core.notifications.milestone_events import (
                        stall_remediation_cycle_event,
                    )

                    self._notify_milestone(
                        stall_remediation_cycle_event(
                            cycle=remediation_state.remediation_cycle,
                            max_cycles=int(cur_cfg.stall_remediation_max_cycles),
                        )
                    )
                except Exception as exc:
                    logger.debug("birth.milestone_remediation_cycle_failed: %s", exc)
                plateau_state.active = False
                plateau_state.evolution_step = 0
                plateau_state.forced_recoveries_count = 0
            if is_remediation_exhausted(remediation_state, cfg=cur_cfg):
                if _trade_budget_remaining() > 0 and can_start_remediation(
                    remediation_state, cfg=cur_cfg
                ):
                    reset_plateau_for_new_cycle(
                        plateau_state,
                        stage_trades=stage_trades,
                        stage_wins=stage_wins,
                    )
                    remediation_state.active = False
                    remediation_state.remediation_step = 0
                    remediation_state.remediation_rollouts_this_step = 0
                    return _try_plateau_evolution(failure_key=failure_key)
                if _trade_budget_remaining() > 0 and should_phoenix_reset(
                    plateau_state,
                    cfg=cur_cfg,
                    winrate=float(stage_wins) / float(max(1, stage_trades)),
                ):
                    _apply_phoenix_reset()
                    reset_plateau_for_new_cycle(
                        plateau_state,
                        stage_trades=stage_trades,
                        stage_wins=stage_wins,
                    )
                    remediation_state.active = False
                    return _try_plateau_evolution(failure_key=failure_key)
                return False
            action = begin_remediation_step(
                remediation_state,
                stage_trades=stage_trades,
                stage_wins=stage_wins,
            )
            detail = _apply_stall_remediation_action(action)
            record_remediation_outcome(
                remediation_state,
                action=action,
                stage_trades=stage_trades,
                stage_wins=stage_wins,
                detail=detail,
            )
            attempt = 0
            self._persist_checkpoint(
                training_mode=training_mode,
                curriculum_stage=stage.value,
                policy_path=str(self.final_policy_path),
                phase="stall_remediation",
                stage_metrics=_stage_metrics_payload(),
            )
            _write_progress(
                phase="stall_remediation",
                message=(
                    f"Stall remediation step {remediation_state.remediation_step}/"
                    f"{cur_cfg.stall_remediation_max_steps}: {detail}"
                ),
            )
            logger.info(
                "birth.stall_remediation.applied step=%s action=%s",
                remediation_state.remediation_step,
                action.value if action else "none",
            )
            return True

        def _maybe_advance_stall_remediation_in_loop() -> bool:
            """Advance remediation between rollouts; True if human gate finalize needed."""
            nonlocal attempt
            if not remediation_state.active:
                return False
            current_winrate = float(stage_wins) / float(max(1, stage_trades))
            if not should_advance_remediation_step(
                remediation_state,
                cfg=cur_cfg,
                current_winrate=current_winrate,
            ):
                return False
            if remediation_state.remediation_step >= int(cur_cfg.stall_remediation_max_steps):
                return True
            action = begin_remediation_step(
                remediation_state,
                stage_trades=stage_trades,
                stage_wins=stage_wins,
            )
            detail = _apply_stall_remediation_action(action)
            record_remediation_outcome(
                remediation_state,
                action=action,
                stage_trades=stage_trades,
                stage_wins=stage_wins,
                detail=detail,
            )
            attempt = 0
            _write_progress(
                phase="stall_remediation",
                message=f"Stall remediation advanced: {detail}",
            )
            try:
                from lumina_core.notifications.milestone_events import (
                    stall_remediation_step_event,
                )

                self._notify_milestone(
                    stall_remediation_step_event(
                        cycle=remediation_state.remediation_cycle,
                        step=remediation_state.remediation_step,
                        max_steps=int(cur_cfg.stall_remediation_max_steps),
                        action=action.value if action else "",
                        detail=detail,
                        winrate=current_winrate,
                    )
                )
            except Exception as exc:
                logger.debug("birth.milestone_remediation_step_failed: %s", exc)
            return remediation_state.remediation_step >= int(cur_cfg.stall_remediation_max_steps)

        def _apply_plateau_evolution_action(action: EvolutionAction) -> str:
            nonlocal intra_state
            if action == EvolutionAction.EXPAND_DATA:
                _maybe_expand_data()
                return "expanded data window"
            if action == EvolutionAction.POLICY_ROLLBACK:
                if not is_valid_best_policy_snapshot(plateau_state, cfg=cur_cfg):
                    return "rollback skipped — no valid best policy snapshot (min trades)"
                rollback_path = str(plateau_state.best_policy_path or "").strip()
                if rollback_path and Path(rollback_path).is_file():
                    self.current_policy = self._create_birth_policy(
                        allow_load_existing=True,
                        policy_path=rollback_path,
                    )
                    return f"rollback to {plateau_state.best_winrate:.1%} winrate"
                return "rollback skipped — no best policy snapshot"
            if action == EvolutionAction.INTRA_EASY_ONLY:
                if intra_state is not None:
                    intra_state.hard_pct = 0.0
                    intra_state.easy_trades = 0
                    intra_state.easy_wins = 0
                    intra_state.easy_winrate_history.clear()
                    _rebuild_intra_pools(active_stage_ticks)
                return "intra stage1 easy-only pool"
            if action == EvolutionAction.FRESH_POLICY:
                self.current_policy = self._create_birth_policy(allow_load_existing=False)
                return "fresh policy (buffer/oracle retained)"
            if action == EvolutionAction.ORACLE_DISTILL:
                return _apply_oracle_distill()
            if action == EvolutionAction.PHOENIX_RESET:
                return _apply_phoenix_reset()
            return ""

        def _finalize_plateau_evolution_step(
            *,
            action: EvolutionAction,
            detail: str,
            failure_key: str,
            forced_advance: bool = False,
        ) -> None:
            nonlocal attempt
            current_winrate = float(stage_wins) / float(max(1, stage_trades))
            record_evolution_outcome(
                plateau_state,
                action=action,
                stage_trades=stage_trades,
                stage_wins=stage_wins,
                detail=detail,
            )
            attempt = 0
            self._persist_checkpoint(
                training_mode=training_mode,
                curriculum_stage=stage.value,
                policy_path=str(self.final_policy_path),
                phase="plateau_evolution",
                stage_metrics=_stage_metrics_payload(),
            )
            forced_suffix = " (forced advance)" if forced_advance else ""
            _write_progress(
                phase="plateau_evolution",
                message=(
                    f"Plateau evolution step {plateau_state.evolution_step}/"
                    f"{cur_cfg.plateau_max_evolution_steps}: {detail}{forced_suffix}"
                ),
            )
            logger.info(
                "birth.plateau.evolution_applied step=%s action=%s detail=%s failure=%s forced=%s",
                plateau_state.evolution_step,
                action.value,
                detail,
                failure_key,
                forced_advance,
            )
            try:
                from lumina_core.notifications.milestone_events import plateau_evolution_step_event

                self._notify_milestone(
                    plateau_evolution_step_event(
                        step=plateau_state.evolution_step,
                        max_steps=int(cur_cfg.plateau_max_evolution_steps),
                        action=action.value,
                        detail=f"{detail}{forced_suffix}",
                        winrate=current_winrate,
                    )
                )
            except Exception as exc:
                logger.debug("birth.milestone_evolution_notify_failed: %s", exc)
            if forced_advance:
                try:
                    from lumina_core.notifications.milestone_events import (
                        plateau_evolution_forced_advance_event,
                    )

                    self._notify_milestone(
                        plateau_evolution_forced_advance_event(
                            step=plateau_state.evolution_step,
                            max_steps=int(cur_cfg.plateau_max_evolution_steps),
                            action=action.value,
                            winrate=current_winrate,
                        )
                    )
                except Exception as exc:
                    logger.debug("birth.milestone_forced_advance_notify_failed: %s", exc)

        def _maybe_advance_plateau_evolution_in_loop() -> bool:
            """Advance plateau evolution between rollouts (mirrors remediation loop)."""
            nonlocal attempt
            if not plateau_state.active or allow_provisional:
                return False
            current_winrate = float(stage_wins) / float(max(1, stage_trades))
            forced = should_force_advance_evolution_step(
                plateau_state,
                cfg=cur_cfg,
                current_winrate=current_winrate,
            )
            if not should_trigger_plateau_evolution_step(
                plateau_state,
                cfg=cur_cfg,
                current_winrate=current_winrate,
                allow_start=False,
            ):
                return False
            action = begin_evolution_step(
                plateau_state,
                stage_trades=stage_trades,
                stage_wins=stage_wins,
            )
            if action == EvolutionAction.TERMINAL:
                return False
            detail = _apply_plateau_evolution_action(action)
            _finalize_plateau_evolution_step(
                action=action,
                detail=detail,
                failure_key="stage1_winrate",
                forced_advance=forced,
            )
            return True

        def _resolve_terminal_stall(pending: dict[str, Any]) -> dict[str, Any] | None:
            """None => continue loop; dict => terminal stall result."""
            if _try_stall_remediation_on_terminal(pending):
                return None
            stall_reason = str(
                pending.get("terminal_stall_reason") or pending.get("blocker_reason") or ""
            )
            human_gate = stall_reason in {TERMINAL_STALL_REASON, HUMAN_GATE_REASON}
            return _finalize_certified_stage_stall(pending, human_gate=human_gate)

        def _best_policy_snapshot_path() -> Path:
            return self.workspace_root / "lumina_agents" / "ppo" / f"birth_best_{stage.value}.zip"

        def _meta_self_eval_phase_str() -> str:
            if cur_cfg.meta_controller_enabled and cur_cfg.meta_self_eval_enabled:
                return str(meta_controller.self_eval.phase.value)
            return ""

        def _maybe_save_best_policy(*, stage_trades: int, stage_wins: int) -> None:
            snapshot_path = _best_policy_snapshot_path()
            if maybe_update_best_winrate(
                plateau_state,
                stage_trades=stage_trades,
                stage_wins=stage_wins,
                policy_path=str(snapshot_path),
                cfg=cur_cfg,
            ):
                snapshot_path.parent.mkdir(parents=True, exist_ok=True)
                save_fn = getattr(self.ppo_trainer, "save_final_birth_policy", None)
                if callable(save_fn):
                    save_fn(str(snapshot_path))
                    logger.info(
                        "birth.plateau.best_policy_saved path=%s winrate=%.2f%% trades=%s",
                        snapshot_path,
                        plateau_state.best_winrate * 100.0,
                        stage_trades,
                    )
                    try:
                        from lumina_core.notifications.milestone_events import (
                            best_policy_updated_event,
                        )

                        self._notify_milestone(
                            best_policy_updated_event(
                                winrate=plateau_state.best_winrate,
                                stage_trades=stage_trades,
                                policy_path=str(snapshot_path),
                            )
                        )
                    except Exception as exc:
                        logger.debug("birth.milestone_best_policy_failed: %s", exc)

        def _maybe_detect_plateau(*, stage_trades: int, stage_wins: int) -> None:
            if plateau_state.active or allow_provisional:
                return
            ctx = PlateauEnterContext(
                stage_trades=stage_trades,
                stage_wins=stage_wins,
                required=required,
                winrate_trend_slope=calculate_simple_slope(winrate_history),
                velocity_stall_attempts=low_velocity_attempts,
                meta_self_eval_phase=_meta_self_eval_phase_str(),
                pass_metric_target=pass_metric_target,
            )
            if should_enter_plateau(ctx, cfg=cur_cfg):
                enter_plateau(
                    plateau_state,
                    stage_trades=stage_trades,
                    stage_wins=stage_wins,
                )
                sanitize_plateau_best_snapshot(
                    plateau_state,
                    cfg=cur_cfg,
                    stage_trades=stage_trades,
                    stage_wins=stage_wins,
                )
                wr = float(stage_wins) / float(max(1, stage_trades))
                try:
                    from lumina_core.notifications.milestone_events import plateau_entered_event

                    self._notify_milestone(
                        plateau_entered_event(
                            stage_trades=stage_trades,
                            winrate=wr,
                            pass_target=pass_metric_target,
                        )
                    )
                except Exception as exc:
                    logger.debug("birth.milestone_plateau_enter_failed: %s", exc)
                _try_plateau_evolution(failure_key="stage1_winrate")

        def _effective_max_rollouts() -> int:
            if not plateau_state.active and not remediation_state.active:
                if allow_provisional:
                    return max_rollouts
                return max_rollouts
            if allow_provisional:
                return max_rollouts
            if remediation_state.active:
                return min(max_rollouts, cur_cfg.stall_remediation_rollouts_per_step)
            if (
                plateau_state.evolution_step > 0
                or plateau_state.active
            ):
                return min(max_rollouts, cur_cfg.plateau_evolution_rollouts_per_step)
            return max_rollouts

        def _plateau_terminal_pending(*, failure_key: str) -> dict[str, Any] | None:
            if not should_terminal_plateau_stall(
                plateau_state,
                stage_trades=stage_trades,
                required=required,
                cfg=cur_cfg,
                meta_self_eval_phase=_meta_self_eval_phase_str(),
                remediation_exhausted=_remediation_exhausted_now(),
                trade_budget_remaining=_trade_budget_remaining(),
            ):
                return None
            hold_ratio = float(stage_hold_signals) / float(max(1, stage_total_signals))
            range_flat_ratio = float(stage_range_flat_bars) / float(max(1, stage_range_total_signals))
            blocker_metric, blocker_value, blocker_reason = compute_stage_blocker(
                stage,
                stage_trades=stage_trades,
                stage_wins=stage_wins,
                hold_ratio=hold_ratio,
                required=required,
                constitution_violations=self._constitution_guard.violations,
                range_flat_ratio=range_flat_ratio,
                range_round_trips=stage_range_round_trips,
                range_total_signals=stage_range_total_signals,
                cfg=cur_cfg,
            )
            return {
                "failure_key": failure_key,
                "blocker_metric": blocker_metric,
                "blocker_value": blocker_value,
                "blocker_reason": TERMINAL_STALL_REASON,
                "terminal_stall_reason": TERMINAL_STALL_REASON,
            }

        def _try_plateau_evolution(*, failure_key: str) -> bool:
            nonlocal attempt, intra_state
            if not plateau_state.active or allow_provisional:
                return False
            current_winrate = float(stage_wins) / float(max(1, stage_trades))
            forced = should_force_advance_evolution_step(
                plateau_state,
                cfg=cur_cfg,
                current_winrate=current_winrate,
            )
            if not should_trigger_plateau_evolution_step(
                plateau_state,
                cfg=cur_cfg,
                current_winrate=current_winrate,
                allow_start=True,
            ):
                return False
            action = begin_evolution_step(
                plateau_state,
                stage_trades=stage_trades,
                stage_wins=stage_wins,
            )
            if action == EvolutionAction.TERMINAL:
                return False
            detail = _apply_plateau_evolution_action(action)
            _finalize_plateau_evolution_step(
                action=action,
                detail=detail,
                failure_key=failure_key,
                forced_advance=forced,
            )
            return True

        def _should_terminal_stall_in_adaptive() -> bool:
            """True when plateau recovery must stop (budget-gated never-stop)."""
            if plateau_state.active and should_block_plateau_recovery(
                plateau_state,
                cfg=cur_cfg,
                remediation_exhausted=_remediation_exhausted_now(),
                trade_budget_remaining=_trade_budget_remaining(),
            ):
                return True
            if plateau_state.active:
                return False
            if (
                data_exhausted
                and len(self.buffer) < 80
                and adaptation_tier >= cur_cfg.max_adaptation_tiers - 1
            ):
                return True
            return False

        def _maybe_extend_trade_budget() -> bool:
            nonlocal effective_trade_budget_cap
            if self.cumulative_trades < effective_trade_budget_cap:
                return False
            old_cap = effective_trade_budget_cap
            effective_trade_budget_cap = int(effective_trade_budget_cap * 1.25) + 1000
            logger.info(
                "birth.budget_extended old_cap=%s new_cap=%s cumulative_trades=%s tier=%s",
                old_cap,
                effective_trade_budget_cap,
                self.cumulative_trades,
                adaptation_tier,
            )
            return True

        def _apply_adaptation_recovery(decision: AdaptationDecision, *, failure_key: str) -> bool:
            nonlocal escalation_level, retries_this_stage, attempt, adaptation_tier
            nonlocal winrate_stagnation_count, hold_stagnation_count, wall_budget_exhausted
            nonlocal stage_started_at
            current_winrate = float(stage_wins) / float(max(1, stage_trades))
            if adaptation_tier >= cur_cfg.max_adaptation_tiers - 1:
                winrate_stagnation_count = 0
                hold_stagnation_count = 0
                wall_budget_exhausted = False
                escalation_level = min(cur_cfg.max_escalation_level, cur_cfg.max_escalation_level)
                cur_cfg.rollout_chunk_trades = max(
                    cur_cfg.exploration_chunk_size,
                    original_rollout_chunk,
                )
            else:
                escalation_level = min(
                    cur_cfg.max_escalation_level,
                    escalation_level + decision.escalation_increase,
                )
                cur_cfg.rollout_chunk_trades = decision.new_chunk_target
            adaptation_history.append(
                {
                    "timestamp": time.time(),
                    "reason": decision.reason,
                    "chunk_target": cur_cfg.rollout_chunk_trades,
                    "escalation": escalation_level,
                    "tier": adaptation_tier,
                    "winrate": current_winrate,
                    "failure_key": failure_key,
                }
            )
            retries_this_stage += 1
            if retries_this_stage >= cur_cfg.max_stage_retries:
                if adaptation_tier + 1 < cur_cfg.max_adaptation_tiers:
                    adaptation_tier += 1
                    retries_this_stage = 0
                    logger.info(
                        "birth.adaptation.tier_advanced tier=%s max=%s",
                        adaptation_tier,
                        cur_cfg.max_adaptation_tiers,
                    )
                else:
                    retries_this_stage = 0
                    logger.info(
                        "birth.adaptation.persistent_recovery tier=%s failure=%s",
                        adaptation_tier,
                        failure_key,
                    )
            attempt = 0
            winrate_stagnation_count = 0
            hold_stagnation_count = 0
            wall_budget_exhausted = False
            stage_started_at = time.time()
            self._persist_checkpoint(
                training_mode=training_mode,
                curriculum_stage=stage.value,
                policy_path=str(self.final_policy_path),
                phase="curriculum_learning",
                stage_metrics=_stage_metrics_payload(),
            )
            logger.info(
                "birth.adaptation.applied reason=%s tier=%s new_chunk=%s escalation=%s",
                decision.reason,
                adaptation_tier,
                cur_cfg.rollout_chunk_trades,
                escalation_level,
            )
            _write_progress(
                phase="curriculum_learning",
                message=(
                    f"Adaptive recovery tier {adaptation_tier + 1}/{cur_cfg.max_adaptation_tiers} "
                    f"· retry {retries_this_stage}/{cur_cfg.max_stage_retries}: "
                    f"{decision.log_message}"
                ),
            )
            return True

        def _resolve_meta_adaptation_decision(adapt_plan: MetaActionPlan) -> AdaptationDecision | None:
            decision = adapt_plan.adaptation
            if decision is not None and decision.should_retry:
                return decision
            if adaptation_tier == 0 and retries_this_stage == 0:
                return AdaptationDecision(
                    should_retry=True,
                    reason="stall_escalation",
                    new_chunk_target=max(
                        cur_cfg.exploration_chunk_size,
                        min(cur_cfg.rollout_chunk_trades * 2, original_rollout_chunk),
                    ),
                    escalation_increase=1,
                    log_message="Escalation ladder: forced recovery at stall boundary",
                )
            if adaptation_tier >= 1:
                return AdaptationDecision(
                    should_retry=True,
                    reason="persistent_recovery",
                    new_chunk_target=max(
                        cur_cfg.exploration_chunk_size,
                        cur_cfg.rollout_chunk_trades,
                    ),
                    escalation_increase=0,
                    log_message=(
                        f"Persistent recovery tier {adaptation_tier + 1}/"
                        f"{cur_cfg.max_adaptation_tiers}"
                    ),
                )
            return None

        def _try_adaptive_stall_recovery(*, failure_key: str) -> bool:
            nonlocal escalation_level, retries_this_stage, attempt, adaptation_tier
            if not cur_cfg.adaptation_enabled or cur_cfg.wall_behavior != "adaptive":
                return False
            _maybe_extend_trade_budget()
            if _should_terminal_stall_in_adaptive():
                return False
            current_winrate = float(stage_wins) / float(max(1, stage_trades))
            if cur_cfg.meta_controller_enabled:
                snap, _ = _observe_snapshot()
                adapt_plan = meta_controller.decide_adaptation(
                    snap,
                    winrate=current_winrate,
                    escalation_level=escalation_level,
                    adaptation_tier=adaptation_tier,
                    retries_this_stage=retries_this_stage,
                    original_rollout_chunk=original_rollout_chunk,
                    failure_key=failure_key,
                )
                decision = _resolve_meta_adaptation_decision(adapt_plan)
                if decision is None:
                    return False
                if adapt_plan.mine:
                    _mine_and_inject(aggressive=adapt_plan.mine_aggressive)
                if adapt_plan.expand_data:
                    _maybe_expand_data()
            else:
                decision = get_adaptation_decision(
                    stage_trades=stage_trades,
                    required=required,
                    winrate=current_winrate,
                    winrate_history=winrate_history,
                    escalation_level=escalation_level,
                    cfg=cur_cfg,
                )
                if not decision.should_retry and adaptation_tier == 0 and retries_this_stage == 0:
                    decision = AdaptationDecision(
                        should_retry=True,
                        reason="stall_escalation",
                        new_chunk_target=max(
                            cur_cfg.exploration_chunk_size,
                            min(cur_cfg.rollout_chunk_trades * 2, original_rollout_chunk),
                        ),
                        escalation_increase=1,
                        log_message="Escalation ladder: forced recovery at stall boundary",
                    )
                if not decision.should_retry and adaptation_tier >= 1:
                    decision = AdaptationDecision(
                        should_retry=True,
                        reason="persistent_recovery",
                        new_chunk_target=max(
                            cur_cfg.exploration_chunk_size,
                            cur_cfg.rollout_chunk_trades,
                        ),
                        escalation_increase=0,
                        log_message=(
                            f"Persistent recovery tier {adaptation_tier + 1}/"
                            f"{cur_cfg.max_adaptation_tiers}"
                        ),
                    )
                if not decision.should_retry:
                    return False
                if adaptation_tier >= 1:
                    _mine_and_inject()
                if adaptation_tier >= 2 and cur_cfg.auto_expand_on_adaptation:
                    _maybe_expand_data()
            return _apply_adaptation_recovery(decision, failure_key=failure_key)

        def _force_never_stop_recovery(*, failure_key: str) -> bool:
            """Keep curriculum loop alive when recovery tiers remain (ADR-0017)."""
            if not cur_cfg.adaptation_enabled or cur_cfg.wall_behavior != "adaptive":
                return False
            if _should_terminal_stall_in_adaptive():
                return False
            _maybe_extend_trade_budget()
            if plateau_state.active and not can_force_never_stop_recovery(
                plateau_state, cfg=cur_cfg
            ):
                return _try_plateau_evolution(failure_key=failure_key)
            if plateau_state.active:
                record_forced_recovery(plateau_state)
            logger.info(
                "birth.never_stop force_recovery failure=%s tier=%s retries=%s",
                failure_key,
                adaptation_tier,
                retries_this_stage,
            )
            decision = AdaptationDecision(
                should_retry=True,
                reason="never_stop_forced",
                new_chunk_target=max(
                    cur_cfg.exploration_chunk_size,
                    cur_cfg.rollout_chunk_trades,
                ),
                escalation_increase=1 if adaptation_tier == 0 else 0,
                log_message="Never-stop: forcing adaptive recovery instead of terminal stall",
            )
            if adaptation_tier >= 1:
                _mine_and_inject()
            if adaptation_tier >= 2 and cur_cfg.auto_expand_on_adaptation:
                _maybe_expand_data()
            return _apply_adaptation_recovery(decision, failure_key=failure_key)

        while True:
            if last_progress_write_at > 0 and time.time() - last_progress_write_at >= 60.0:
                _write_progress(
                    phase="curriculum_learning",
                    message=(
                        f"Curriculum {stage.value}: heartbeat · {stage_trades:,} / "
                        f"{required:,} trades · patronen {patterns_mined:,}"
                    ),
                )

            if self._stop_requested():
                self._persist_checkpoint(
                    training_mode=training_mode,
                    curriculum_stage=stage.value,
                    policy_path=str(self.final_policy_path),
                    phase="paused",
                    stage_metrics=_stage_metrics_payload(),
                )
                return self._paused_result()

            elapsed_stage_sec = time.time() - stage_started_at
            failure_key = {
                CurriculumStage.STAGE1_TREND: "stage1_winrate",
                CurriculumStage.STAGE2_RANGE: "stage2_metric",
                CurriculumStage.STAGE3_MIXED: "stage3_constitution",
            }.get(stage, "stage_metrics")
            stall_pending = _would_certified_stage_stall(
                elapsed_stage_sec=elapsed_stage_sec,
                failure_key=failure_key,
            )
            if stall_pending is not None:
                if _try_adaptive_stall_recovery(failure_key=failure_key):
                    continue
                current_wr = float(stage_wins) / float(max(1, stage_trades))
                if plateau_state.active and should_trigger_plateau_evolution_step(
                    plateau_state,
                    cfg=cur_cfg,
                    current_winrate=current_wr,
                    allow_start=False,
                ) and _try_plateau_evolution(failure_key=failure_key):
                    continue
                if _force_never_stop_recovery(failure_key=failure_key):
                    continue
                if plateau_state.active and _try_plateau_evolution(failure_key=failure_key):
                    continue
                plateau_terminal = _plateau_terminal_pending(failure_key=failure_key)
                if plateau_terminal is not None:
                    cur_cfg.rollout_chunk_trades = original_rollout_chunk
                    stall_result = _resolve_terminal_stall(plateau_terminal)
                    if stall_result is None:
                        continue
                    return stall_result
                cur_cfg.rollout_chunk_trades = original_rollout_chunk
                stall_result = _resolve_terminal_stall(stall_pending)
                if stall_result is None:
                    continue
                return stall_result

            if elapsed_stage_sec >= max(300, int(cur_cfg.max_stage_wall_sec)):
                if (
                    len(self.buffer) >= 256
                    and self._constitution_guard.violations == 0
                    and (patterns_mined >= 100 or stage_trades >= 1)
                ):
                    if allow_provisional:
                        gen0_provisional = True
                        logger.info(
                            "birth.stage.wall_budget_provisional",
                            extra={"event_data": {"stage": stage.value, "elapsed_sec": elapsed_stage_sec}},
                        )
                    elif not wall_budget_exhausted:
                        wall_budget_exhausted = True
                        escalation_level = min(cur_cfg.max_escalation_level, escalation_level + 1)
                        logger.info(
                            "birth.stage.wall_budget_exhausted",
                            extra={"event_data": {"stage": stage.value, "elapsed_sec": elapsed_stage_sec}},
                        )

            stage_result = evaluate_stage_pass(
                stage,
                trades=stage_trades,
                wins=stage_wins,
                hold_signals=stage_hold_signals,
                total_signals=stage_total_signals,
                range_hold_signals=stage_range_hold_signals,
                range_total_signals=stage_range_total_signals,
                range_flat_bars=stage_range_flat_bars,
                range_round_trips=stage_range_round_trips,
                constitution_violations=self._constitution_guard.violations,
                target_trades=target,
                cfg=cur_cfg,
                provisional=gen0_provisional,
                allow_provisional=allow_provisional,
                oracle_patterns=patterns_mined,
                buffer_size=len(self.buffer),
            )
            if stage_result.passed:
                required = stage_pass_trades(stage, cur_cfg)
                pass_winrate = float(stage_wins) / float(max(1, stage_trades))
                logger.info(
                    "birth.stage.passed stage=%s trades=%s wins=%s required=%s "
                    "winrate=%.2f%% provisional=%s reason=%s",
                    stage.value,
                    stage_trades,
                    stage_wins,
                    required,
                    pass_winrate * 100.0,
                    bool(stage_result.provisional),
                    stage_result.message,
                    extra={
                        "event_data": {
                            "stage": stage.value,
                            "trades": stage_trades,
                            "wins": stage_wins,
                            "required": required,
                            "winrate": round(pass_winrate, 4),
                            "patterns_mined": patterns_mined,
                            "attempts": attempt,
                            "pass_reason": stage_result.message,
                            "provisional": stage_result.provisional,
                        }
                    },
                )
                self._pending_stage_pass_receipt = receipt_from_stage_result(
                    stage,
                    stage_result,
                    cfg=cur_cfg,
                )
                return None

            if stage_trades == last_stage_trades:
                stagnation_count += 1
            else:
                stagnation_count = 0
                last_stage_trades = stage_trades

            if stagnation_count >= cur_cfg.stagnation_rollouts_before_expand:
                _mine_and_inject()
                if not _maybe_expand_data():
                    if allow_provisional and (
                        stage_trades > 0 or patterns_mined > 0 or len(self.buffer) >= 256
                    ):
                        gen0_provisional = True
                        continue
                    if data_exhausted:
                        write_birth_progress(
                            self.workspace_root,
                            stage="history_unavailable",
                            phase="data_expansion_exhausted",
                            message="Birth research: geen extra data/patronen beschikbaar.",
                            progress_pct=stage_progress_pct,
                            cumulative_trades=self.cumulative_trades,
                            target_trades=trade_budget_cap,
                            birth_start_time=self.birth_start_time,
                            curriculum_stage=stage.value,
                            retryable=True,
                        )
                        return {
                            "status": "history_unavailable",
                            "total_trades": self.cumulative_trades,
                            "ppo_steps": self.ppo_steps,
                            "training_mode": "certified",
                        }
                stagnation_count = 0
                if len(self.buffer) >= 80:
                    self.current_policy = self.ppo_trainer.update_from_buffer(
                        buffer=self.buffer,
                        timesteps=ppo_steps_per_update,
                        birth_phase=True,
                    )
                    self.ppo_steps += ppo_steps_per_update

            if attempt >= _effective_max_rollouts():
                if allow_provisional and (
                    should_gen0_soft_pass(
                        stage_trades=stage_trades,
                        buffer_size=len(self.buffer),
                        attempt=attempt,
                        cfg=cur_cfg,
                    )
                    or patterns_mined >= 100
                ):
                    gen0_provisional = True
                elif allow_provisional and (stage_trades > 0 or patterns_mined > 0):
                    gen0_provisional = True
                elif not allow_provisional and stage_trades >= required:
                    force_failure_key = {
                        CurriculumStage.STAGE1_TREND: "stage1_winrate",
                        CurriculumStage.STAGE2_RANGE: "stage2_metric",
                        CurriculumStage.STAGE3_MIXED: "stage3_constitution",
                    }.get(stage, "stage_metrics")
                    stall_pending = _would_certified_stage_stall(
                        elapsed_stage_sec=time.time() - stage_started_at,
                        failure_key=force_failure_key,
                        force=True,
                    )
                    if stall_pending is not None:
                        if _try_adaptive_stall_recovery(failure_key=force_failure_key):
                            attempt = 0
                            continue
                        force_wr = float(stage_wins) / float(max(1, stage_trades))
                        if plateau_state.active and should_trigger_plateau_evolution_step(
                            plateau_state,
                            cfg=cur_cfg,
                            current_winrate=force_wr,
                            allow_start=False,
                        ) and _try_plateau_evolution(failure_key=force_failure_key):
                            attempt = 0
                            continue
                        if _force_never_stop_recovery(failure_key=force_failure_key):
                            attempt = 0
                            continue
                        if plateau_state.active and _try_plateau_evolution(
                            failure_key=force_failure_key
                        ):
                            attempt = 0
                            continue
                        plateau_terminal = _plateau_terminal_pending(
                            failure_key=force_failure_key
                        )
                        if plateau_terminal is not None:
                            cur_cfg.rollout_chunk_trades = original_rollout_chunk
                            stall_result = _resolve_terminal_stall(plateau_terminal)
                            if stall_result is None:
                                attempt = 0
                                continue
                            return stall_result
                        cur_cfg.rollout_chunk_trades = original_rollout_chunk
                        stall_result = _resolve_terminal_stall(stall_pending)
                        if stall_result is None:
                            attempt = 0
                            continue
                        return stall_result
                else:
                    if _maybe_expand_data():
                        attempt = 0
                        continue
                    write_birth_progress(
                        self.workspace_root,
                        stage="history_unavailable",
                        phase="data_expansion_exhausted",
                        message="Birth research: max rollouts bereikt zonder patronen.",
                        progress_pct=stage_progress_pct,
                        cumulative_trades=self.cumulative_trades,
                        target_trades=trade_budget_cap,
                        birth_start_time=self.birth_start_time,
                        retryable=True,
                    )
                    return {
                        "status": "history_unavailable",
                        "total_trades": self.cumulative_trades,
                        "ppo_steps": self.ppo_steps,
                        "training_mode": "certified",
                    }
                attempt = 0
                continue

            if stage_trades >= required:
                chunk_target = cur_cfg.rollout_chunk_trades
            else:
                remaining = max(1, required - stage_trades)
                chunk_target = min(remaining, cur_cfg.rollout_chunk_trades)
            active_ticks = self._stage_tick_pool(
                stage=stage,
                stage_ticks=active_stage_ticks,
                train_ticks=active_train,
                escalation_level=escalation_level,
                attempt=attempt,
                chunk_target=chunk_target,
                cur_cfg=cur_cfg,
                intra_state=intra_state,
                easy_pool=intra_easy_pool,
                hard_pool=intra_hard_pool,
            )
            current_intra_sample_pool = list(active_ticks)

            chunk_trades_snapshot = 0

            def _rollout_progress(snapshot: dict[str, Any]) -> None:
                nonlocal chunk_trades_snapshot
                chunk_trades_snapshot = int(snapshot.get("rollout_trades", 0) or 0)
                explore_suffix = " (exploratie actief)" if snapshot.get("exploration_active") else ""
                _write_progress(
                    phase="curriculum_learning",
                    message=(
                        f"Curriculum {stage.value}: {stage_trades + chunk_trades_snapshot:,} / "
                        f"{required:,} trades · poging {attempt + 1} · L{escalation_level} · "
                        f"patronen {patterns_mined:,}{explore_suffix}"
                    ),
                    chunk_trades=chunk_trades_snapshot,
                    rollout_steps=int(snapshot.get("rollout_steps", 0) or 0),
                    exploration_active=bool(snapshot.get("exploration_active")),
                    hold_ratio=float(snapshot.get("hold_ratio", 0.0) or 0.0),
                )

            base_explore_steps = cur_cfg.exploration_steps * (1 + escalation_level)
            reward_override = None
            if cur_cfg.meta_controller_enabled:
                pre_snap, _ = _observe_snapshot()
                if cur_cfg.meta_self_eval_enabled:
                    meta_controller.maybe_start_self_eval(
                        pre_snap,
                        strong_recovery_attempts=strong_recovery_attempts,
                        attempt=attempt + 1,
                    )
                if (
                    cur_cfg.meta_self_eval_enabled
                    and meta_controller.is_self_eval_active()
                ):
                    if meta_controller.self_eval.phase == SelfEvalPhase.PROBING:
                        pre_plan = meta_controller.decide_probe_rollout(pre_snap)
                    elif meta_controller.self_eval.phase == SelfEvalPhase.COMMITTED:
                        pre_plan = meta_controller.decide_committed_rollout(pre_snap)
                    else:
                        pre_plan = MetaActionPlan(
                            primary=RecoveryStrategy.HOLD,
                            rationale="self_eval_exhausted",
                            snapshot=pre_snap,
                            self_eval_phase=SelfEvalPhase.EXHAUSTED.value,
                        )
                else:
                    pre_plan = meta_controller.decide_review(
                        pre_snap,
                        trigger="pre_rollout",
                        base_explore_steps=base_explore_steps,
                        wall_budget_exhausted=wall_budget_exhausted,
                        winrate_stagnation_count=winrate_stagnation_count,
                        hold_stagnation_count=hold_stagnation_count,
                    )
                current_wr = float(stage_wins) / float(max(1, stage_trades))
                current_hold = (
                    float(stage_hold_signals) / float(max(1, stage_total_signals))
                    if stage_total_signals
                    else 0.0
                )
                if detect_hold_trap(
                    hold_ratio=current_hold,
                    winrate=current_wr,
                    pass_metric_target=pass_metric_target,
                    velocity_stall=low_velocity_attempts
                    >= int(cur_cfg.velocity_stall_attempt_threshold),
                    cfg=cur_cfg,
                ):
                    pre_plan = MetaActionPlan(
                        primary=RecoveryStrategy.EXPLORE_BOOST,
                        explore_steps=max(
                            base_explore_steps,
                            int(cur_cfg.exploration_steps) * 4,
                        ),
                        escalation_delta=1,
                        rationale="hold_trap_forced_explore",
                        snapshot=pre_snap,
                    )
                    if not hold_trap_milestone_sent:
                        hold_trap_milestone_sent = True
                        try:
                            from lumina_core.notifications.milestone_events import (
                                hold_trap_detected_event,
                            )

                            self._notify_milestone(
                                hold_trap_detected_event(
                                    hold_ratio=current_hold,
                                    winrate=current_wr,
                                )
                            )
                        except Exception as exc:
                            logger.debug("birth.milestone_hold_trap_failed: %s", exc)
                elif (
                    pre_plan.primary == RecoveryStrategy.HOLD
                    and _meta_self_eval_phase_str() == "exhausted"
                    and plateau_state.active
                ):
                    pre_plan = MetaActionPlan(
                        primary=RecoveryStrategy.EXPLORE_BOOST,
                        explore_steps=max(
                            base_explore_steps,
                            int(cur_cfg.exploration_steps) * 4,
                        ),
                        escalation_delta=1,
                        rationale="meta_exhausted_forced_explore",
                        snapshot=pre_snap,
                    )
                if pre_plan.mine:
                    _mine_and_inject(aggressive=pre_plan.mine_aggressive)
                if pre_plan.escalation_delta > 0:
                    escalation_level = min(
                        cur_cfg.max_escalation_level,
                        escalation_level + pre_plan.escalation_delta,
                    )
                elif pre_plan.escalation_delta < 0:
                    escalation_level = max(0, escalation_level + pre_plan.escalation_delta)
                explore_steps = meta_controller.apply_explore_multiplier(
                    pre_plan.explore_steps or base_explore_steps,
                )
                meta_last_plan = pre_plan
                if pre_plan.primary != RecoveryStrategy.HOLD or pre_plan.mine or pre_plan.expand_data:
                    _log_meta_decision(pre_plan, trigger="pre_rollout")
                if meta_controller.reward_tweak_active:
                    reward_override = meta_controller.active_reward
            else:
                explore_steps = base_explore_steps
                if not strong_recovery_mode:
                    if (
                        stage == CurriculumStage.STAGE2_RANGE
                        and stage_trades >= required
                        and hold_stagnation_count >= cur_cfg.stage2_hold_stagnation_rollouts
                    ):
                        explore_steps = max(explore_steps, cur_cfg.exploration_steps * 4)
                        escalation_level = min(cur_cfg.max_escalation_level, escalation_level + 1)
                    if (
                        stage == CurriculumStage.STAGE1_TREND
                        and stage_trades >= required
                        and winrate_stagnation_count >= cur_cfg.stage1_winrate_stagnation_rollouts
                    ):
                        explore_steps = max(explore_steps, cur_cfg.exploration_steps * 4)
                        escalation_level = min(cur_cfg.max_escalation_level, escalation_level + 1)
                        _mine_and_inject()
                    if wall_budget_exhausted:
                        explore_steps = max(explore_steps, cur_cfg.exploration_steps * 4)
                else:
                    if (
                        strong_recovery_attempts > 0
                        and strong_recovery_attempts
                        % cur_cfg.strong_recovery_expand_every_attempts
                        == 0
                    ):
                        _maybe_expand_data()
                        _mine_and_inject(aggressive=True)
                    explore_steps = max(
                        200,
                        int(
                            cur_cfg.exploration_steps
                            * cur_cfg.strong_recovery_explore_fraction
                        ),
                    )
            pre_rollout_hold = (
                float(stage_hold_signals) / float(max(1, stage_total_signals))
                if stage_total_signals
                else 0.0
            )
            plateau_recovery = plateau_state.active or remediation_state.active
            hold_cap: float | None = None
            if plateau_recovery or detect_hold_trap(
                hold_ratio=pre_rollout_hold,
                winrate=float(stage_wins) / float(max(1, stage_trades)),
                pass_metric_target=pass_metric_target,
                velocity_stall=low_velocity_attempts
                >= int(cur_cfg.velocity_stall_attempt_threshold),
                cfg=cur_cfg,
            ):
                hold_cap = float(cur_cfg.hold_trap_recovery_hold_cap)
            rollout = run_policy_rollout(
                runtime=self.runtime,
                data=active_ticks,
                policy=self.current_policy,
                target_trades=chunk_target,
                workspace_root=self.workspace_root,
                constitution_guard=self._constitution_guard,
                rollout_step_budget=chunk_budget,
                stall_probe_steps=max(200, cur_cfg.stall_probe_steps // (1 + escalation_level)),
                exploration_steps=explore_steps,
                escalation_level=escalation_level,
                hold_cap_ratio=hold_cap,
                plateau_active=plateau_recovery,
                on_progress=_rollout_progress,
                reward_override=reward_override,
            )

            stage_trades += rollout.trades
            stage_wins += rollout.wins
            stage_hold_signals += rollout.hold_signals
            stage_total_signals += rollout.total_signals
            stage_range_hold_signals += rollout.range_hold_signals
            stage_range_total_signals += rollout.range_total_signals
            stage_range_flat_bars += rollout.range_flat_bars
            stage_range_round_trips += rollout.range_round_trips
            self.cumulative_trades += rollout.trades

            if intra_state is not None and rollout.easy_trades > 0:
                update_stage1_intra_state(
                    intra_state,
                    chunk_easy_trades=rollout.easy_trades,
                    chunk_easy_wins=rollout.easy_wins,
                    cfg=cur_cfg,
                )

            current_hold_ratio = float(stage_hold_signals) / float(max(1, stage_total_signals))
            range_flat_ratio = float(stage_range_flat_bars) / float(max(1, stage_range_total_signals))
            metric_band = range_flat_ratio if stage_range_total_signals >= 50 else current_hold_ratio
            current_winrate = float(stage_wins) / float(max(1, stage_trades))
            if rollout.trades > 0:
                winrate_history.append(current_winrate)
                if len(winrate_history) > cur_cfg.winrate_trend_window:
                    winrate_history.pop(0)
                mean_reward = float(rollout.total_pnl) / float(max(1, rollout.trades))
                reward_history.append(mean_reward)
                if len(reward_history) > cur_cfg.reward_trend_window:
                    reward_history.pop(0)

            snap: Any | None = None
            stall_result: StallDetectionResult | None = None
            if cur_cfg.meta_controller_enabled:
                meta_controller.rollouts_since_review += 1
                snap, stall_result = _observe_snapshot()
                low_velocity_attempts = stall_result.low_velocity_attempts
                self_eval_skip_review = (
                    cur_cfg.meta_self_eval_enabled
                    and meta_controller.is_self_eval_active()
                    and meta_controller.self_eval.phase
                    in (SelfEvalPhase.PROBING, SelfEvalPhase.COMMITTED)
                )
                if self_eval_skip_review:
                    complete_plan = meta_controller.on_probe_rollout_complete(
                        snap,
                        attempt=attempt + 1,
                    )
                    if complete_plan is not None:
                        _apply_meta_plan(complete_plan, trigger="self_eval")
                        if complete_plan.suggest_provisional_pass:
                            prov = meta_controller.evaluate_provisional_fallback(
                                snap,
                                allow_provisional=allow_provisional,
                                strong_recovery_attempts=strong_recovery_attempts,
                                stage_trades=stage_trades,
                                required=required,
                                attempt=attempt,
                                patterns_mined=patterns_mined,
                                buffer_size=len(self.buffer),
                                constitution_violations=self._constitution_guard.violations,
                            )
                            provisional_pass_considered = True
                            _log_provisional_pass_outcome(
                                source="self_eval_probe_complete",
                                should_grant=prov.should_grant,
                                blocked_reason=prov.blocked_reason,
                                safeguards=prov.safeguards,
                            )
                            if prov.should_grant:
                                gen0_provisional = True
                    elif meta_controller.self_eval.phase == SelfEvalPhase.COMMITTED:
                        committed_plan = meta_controller.decide_committed_rollout(snap)
                        _apply_meta_plan(committed_plan, trigger="self_eval_committed")
                    meta_message_suffix = meta_controller.format_self_eval_suffix()
                else:
                    next_attempt = attempt + 1
                    should_review = (
                        (
                            next_attempt > 0
                            and next_attempt % cur_cfg.meta_review_interval_rollouts == 0
                        )
                        or stall_result.is_stalled
                        or rollout.stalled
                        or snap.learning_health == LearningHealth.DECLINING
                    )
                    exhausted_self_eval = (
                        cur_cfg.meta_self_eval_enabled
                        and meta_controller.self_eval.phase == SelfEvalPhase.EXHAUSTED
                    )
                    if exhausted_self_eval:
                        should_review = True
                    review_plan: MetaActionPlan | None = None
                    review_trigger = "periodic"
                    if should_review:
                        if exhausted_self_eval:
                            review_plan = MetaActionPlan(
                                primary=RecoveryStrategy.HOLD,
                                suggest_provisional_pass=True,
                                rationale="self_eval_exhausted",
                                snapshot=snap,
                                self_eval_phase=SelfEvalPhase.EXHAUSTED.value,
                            )
                            review_trigger = "self_eval_exhausted"
                        else:
                            review_trigger = (
                                "stall"
                                if stall_result.is_stalled or rollout.stalled
                                else "periodic"
                            )
                            review_plan = meta_controller.decide_review(
                                snap,
                                trigger=review_trigger,
                                base_explore_steps=cur_cfg.exploration_steps
                                * (1 + escalation_level),
                                wall_budget_exhausted=wall_budget_exhausted,
                                winrate_stagnation_count=winrate_stagnation_count,
                                hold_stagnation_count=hold_stagnation_count,
                            )
                        _apply_meta_plan(review_plan, trigger=review_trigger)
                        if review_plan.suggest_provisional_pass:
                            prov = meta_controller.evaluate_provisional_fallback(
                                snap,
                                allow_provisional=allow_provisional,
                                strong_recovery_attempts=strong_recovery_attempts,
                                stage_trades=stage_trades,
                                required=required,
                                attempt=attempt,
                                patterns_mined=patterns_mined,
                                buffer_size=len(self.buffer),
                                constitution_violations=self._constitution_guard.violations,
                            )
                            provisional_pass_considered = True
                            _log_provisional_pass_outcome(
                                source=(
                                    "self_eval_exhausted"
                                    if review_trigger == "self_eval_exhausted"
                                    else "meta_review"
                                ),
                                should_grant=prov.should_grant,
                                blocked_reason=prov.blocked_reason,
                                safeguards=prov.safeguards,
                            )
                            if prov.should_grant:
                                gen0_provisional = True
                        if review_plan.enter_strong_recovery:
                            _log_stall_event(
                                event="stall_detected",
                                stall=stall_result,
                                strong_recovery=True,
                            )
                            if (
                                cur_cfg.adaptation_enabled
                                and cur_cfg.wall_behavior == "adaptive"
                            ):
                                _try_adaptive_stall_recovery(failure_key="velocity_stall")
                        elif review_plan.exit_strong_recovery:
                            _log_stall_event(
                                event="stall_recovered",
                                stall=stall_result,
                                strong_recovery=False,
                            )
                if strong_recovery_mode:
                    strong_recovery_attempts += 1
                    prov = self._maybe_trigger_provisional_pass(
                        stage=stage,
                        stage_trades=stage_trades,
                        required=required,
                        attempt=attempt,
                        strong_recovery_attempts=strong_recovery_attempts,
                        patterns_mined=patterns_mined,
                        buffer_size=len(self.buffer),
                        constitution_violations=self._constitution_guard.violations,
                        combined_velocity=snap.combined_velocity,
                        allow_provisional=allow_provisional,
                        cfg=cur_cfg,
                    )
                    provisional_pass_considered = True
                    _log_provisional_pass_outcome(
                        source="strong_recovery",
                        should_grant=prov.should_grant,
                        blocked_reason=prov.blocked_reason,
                        safeguards=prov.safeguards,
                    )
                    if prov.should_grant:
                        gen0_provisional = True
            elif stage_trades >= required:
                stall_result = self._detect_stall(
                    winrate_history=winrate_history,
                    reward_history=reward_history,
                    low_velocity_attempts=low_velocity_attempts,
                    cfg=cur_cfg,
                )
                low_velocity_attempts = stall_result.low_velocity_attempts
                if stall_result.is_stalled:
                    if not strong_recovery_mode:
                        strong_recovery_mode = True
                        strong_recovery_attempts = 0
                        escalation_level = min(
                            cur_cfg.max_escalation_level,
                            escalation_level + cur_cfg.strong_recovery_escalation_boost,
                        )
                        cur_cfg.rollout_chunk_trades = max(
                            cur_cfg.exploration_chunk_size,
                            cur_cfg.exploration_chunk_size * 2,
                        )
                        low_velocity_attempts = 0
                        _log_stall_event(
                            event="stall_detected",
                            stall=stall_result,
                            strong_recovery=True,
                        )
                        _mine_and_inject(aggressive=True)
                        if cur_cfg.adaptation_enabled and cur_cfg.wall_behavior == "adaptive":
                            _try_adaptive_stall_recovery(failure_key="velocity_stall")
                elif (
                    strong_recovery_mode
                    and stall_result.combined_velocity > cur_cfg.velocity_stall_epsilon
                ):
                    strong_recovery_mode = False
                    strong_recovery_attempts = 0
                    cur_cfg.rollout_chunk_trades = max(
                        cur_cfg.exploration_chunk_size,
                        original_rollout_chunk,
                    )
                    _log_stall_event(
                        event="stall_recovered",
                        stall=stall_result,
                        strong_recovery=False,
                    )
                if strong_recovery_mode:
                    strong_recovery_attempts += 1
                    prov = self._maybe_trigger_provisional_pass(
                        stage=stage,
                        stage_trades=stage_trades,
                        required=required,
                        attempt=attempt,
                        strong_recovery_attempts=strong_recovery_attempts,
                        patterns_mined=patterns_mined,
                        buffer_size=len(self.buffer),
                        constitution_violations=self._constitution_guard.violations,
                        combined_velocity=stall_result.combined_velocity,
                        allow_provisional=allow_provisional,
                        cfg=cur_cfg,
                    )
                    provisional_pass_considered = True
                    _log_provisional_pass_outcome(
                        source="strong_recovery_legacy",
                        should_grant=prov.should_grant,
                        blocked_reason=prov.blocked_reason,
                        safeguards=prov.safeguards,
                    )
                    if prov.should_grant:
                        gen0_provisional = True

            if (
                stage == CurriculumStage.STAGE1_TREND
                and stage_trades >= required
                and (current_winrate < pass_metric_target or current_hold_ratio > 0.85)
            ):
                if abs(current_winrate - last_winrate) < 0.01 and abs(
                    current_hold_ratio - last_hold_ratio
                ) < 0.01:
                    winrate_stagnation_count += 1
                else:
                    winrate_stagnation_count = 0
                last_winrate = current_winrate
                last_hold_ratio = current_hold_ratio
            elif (
                stage == CurriculumStage.STAGE2_RANGE
                and stage_trades >= required
                and (metric_band > 0.70 or metric_band < 0.30)
            ):
                if abs(metric_band - last_hold_ratio) < 0.01:
                    hold_stagnation_count += 1
                else:
                    hold_stagnation_count = 0
                last_hold_ratio = metric_band
            else:
                hold_stagnation_count = 0
                if stage != CurriculumStage.STAGE1_TREND:
                    winrate_stagnation_count = 0

            for traj in rollout.trajectories:
                self.buffer.add(traj, priority=1.0 + min(10.0, abs(float(traj.get("reward", 0.0)))))

            if len(self.buffer) >= 256:
                stage_winrate = float(stage_wins) / float(max(1, stage_trades))
                _write_progress(
                    phase="ppo_training",
                    message=(
                        f"PPO batch start · {stage_trades:,}/{required:,} trades · "
                        f"winrate {stage_winrate:.1%} · patronen {patterns_mined:,}"
                    ),
                    hold_ratio=float(stage_hold_signals) / float(max(1, stage_total_signals)),
                )
                self.current_policy = self.ppo_trainer.update_from_buffer(
                    buffer=self.buffer,
                    timesteps=ppo_steps_per_update,
                    birth_phase=True,
                )
                self.ppo_steps += ppo_steps_per_update
                self._persist_checkpoint(
                    training_mode=training_mode,
                    curriculum_stage=stage.value,
                    phase="ppo_training",
                    stage_metrics=_stage_metrics_payload(),
                )

            if rollout.stalled and stage_trades == 0 and patterns_mined == 0:
                escalation_level += 1
                if escalation_level >= cur_cfg.max_escalation_level:
                    _mine_and_inject()
                    _maybe_expand_data()
                    escalation_level = 0
            elif rollout.trades == 0 or rollout.partial_complete:
                escalation_level = min(escalation_level + 1, cur_cfg.max_escalation_level - 1)
            elif rollout.trades < max(1, chunk_target // 4):
                escalation_level = min(escalation_level + 1, cur_cfg.max_escalation_level - 1)

            attempt += 1
            for pct in (50, 75, 90):
                if (
                    pct not in budget_milestones_notified
                    and effective_trade_budget_cap > 0
                    and self.cumulative_trades * 100 // effective_trade_budget_cap >= pct
                ):
                    budget_milestones_notified.add(pct)
                    try:
                        from lumina_core.notifications.milestone_events import (
                            trade_budget_milestone_event,
                        )

                        self._notify_milestone(
                            trade_budget_milestone_event(
                                pct=pct,
                                cumulative_trades=self.cumulative_trades,
                                cap=effective_trade_budget_cap,
                            )
                        )
                    except Exception as exc:
                        logger.debug("birth.milestone_budget_failed: %s", exc)
            if winrate_history:
                prior_mean = sum(winrate_history) / float(len(winrate_history))
                if current_winrate >= prior_mean + 0.02:
                    try:
                        from lumina_core.notifications.milestone_events import (
                            learning_breakthrough_event,
                        )

                        self._notify_milestone(
                            learning_breakthrough_event(
                                winrate=current_winrate,
                                prior_mean=prior_mean,
                                delta=current_winrate - prior_mean,
                            )
                        )
                    except Exception as exc:
                        logger.debug("birth.milestone_breakthrough_failed: %s", exc)
            if plateau_state.active:
                increment_evolution_rollout(plateau_state)
                _maybe_advance_plateau_evolution_in_loop()
            if remediation_state.active:
                increment_remediation_rollout(remediation_state)
                if _maybe_advance_stall_remediation_in_loop():
                    pending = _plateau_terminal_pending(failure_key="stage1_winrate") or {
                        "failure_key": "stage1_winrate",
                        "blocker_metric": "trend_winrate",
                        "blocker_value": float(stage_wins) / float(max(1, stage_trades)),
                        "blocker_reason": HUMAN_GATE_REASON,
                        "terminal_stall_reason": HUMAN_GATE_REASON,
                    }
                    stall_result = _finalize_certified_stage_stall(pending, human_gate=True)
                    return stall_result
            _maybe_detect_plateau(stage_trades=stage_trades, stage_wins=stage_wins)
            _maybe_save_best_policy(stage_trades=stage_trades, stage_wins=stage_wins)
            _maybe_periodic_checkpoint("curriculum_learning")
            _write_progress(
                phase="curriculum_learning",
                message=(
                    f"Curriculum {stage.value}: {stage_trades:,} / {required:,} trades · "
                    f"poging {attempt} · patronen {patterns_mined:,}{meta_message_suffix}"
                ),
                hold_ratio=current_hold_ratio,
            )
            meta_message_suffix = ""

