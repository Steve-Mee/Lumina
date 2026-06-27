"""Birth Phase v2 orchestrator (ADR-0012/0013/0014)."""

from __future__ import annotations

import hashlib
import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List

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
from lumina_core.birth.config import BRO_ENGINE_VERSION, BirthCurriculumConfig, load_birth_v2_config
from lumina_core.birth.curriculum import (
    CurriculumStage,
    evaluate_stage_pass,
    filter_ticks_for_stage,
    ordered_stages,
    should_gen0_soft_pass,
    stage_pass_trades,
    stage_trade_target,
)
from lumina_core.birth.data_expansion import expand_birth_data
from lumina_core.birth.history_loader import load_historical_ticks
from lumina_core.birth.news_enricher import enrich_ticks_with_news
from lumina_core.birth.pattern_miner import mine_winning_patterns
from lumina_core.birth.remediation import (
    RemediationAction,
    filter_train_ticks_for_holdout_profile,
    manifest_train_hash_matches,
    select_regime_diverse_train_ticks,
    select_remediation_plan,
    should_fast_path_remediation_from_state,
    reconstruct_checkpoint_from_progress,
)
from lumina_core.birth.preflight import assess_split_preflight, data_manifest_from_split
from lumina_core.birth.progress import read_birth_progress, write_birth_progress
from lumina_core.birth.stage_scorecard import (
    build_scorecard_payload,
    compute_stage_blocker,
    enrich_adaptation_payload,
)
from lumina_core.birth.purged_split import purged_train_holdout_split
from lumina_core.birth.sim_runner import run_policy_rollout
from lumina_core.birth.tick_enricher import enrich_ticks_for_sim, real_data_percentage
from lumina_core.birth.dna_handoff import register_birth_gen0_dna
from lumina_core.birth.bible_meta import update_bible_after_birth
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.engine")


@dataclass(frozen=True, slots=True)
class AdaptationDecision:
    should_retry: bool
    reason: str
    new_chunk_target: int
    escalation_increase: int = 1
    log_message: str = ""


def _get_adaptation_decision(
    *,
    stage_trades: int,
    required: int,
    winrate: float,
    winrate_history: List[float],
    escalation_level: int,
    cfg: BirthCurriculumConfig,
) -> AdaptationDecision:
    """High-leverage rule: recent winrate trend after volume gate has been passed."""
    _ = winrate
    if len(winrate_history) >= 5:
        slope = (winrate_history[-1] - winrate_history[0]) / max(1, len(winrate_history) - 1)
    else:
        slope = 0.0

    is_negative_trend = slope < cfg.negative_slope_threshold

    if stage_trades >= required and is_negative_trend:
        new_chunk = min(25, cfg.exploration_chunk_size * (1 + escalation_level))
        return AdaptationDecision(
            should_retry=True,
            reason="negative_winrate_trend_after_volume_gate",
            new_chunk_target=new_chunk,
            escalation_increase=1,
            log_message=(
                f"Negative trend (slope={slope:.4f}). Boosting exploration to chunk={new_chunk}"
            ),
        )

    if stage_trades >= required:
        return AdaptationDecision(
            should_retry=True,
            reason="metrics_not_improving_within_wall",
            new_chunk_target=cfg.exploration_chunk_size,
            escalation_increase=1,
            log_message="Metrics stalled after volume gate. Applying exploration boost.",
        )

    return AdaptationDecision(
        should_retry=True,
        reason="default_stall_retry",
        new_chunk_target=cfg.rollout_chunk_trades,
        escalation_increase=1,
        log_message="Standard stall recovery.",
    )


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
        self._real_data_pct = 0.0
        self._data_manifest: dict[str, Any] = {}
        self._remediation_attempt = 0
        self._last_checkpoint_at = 0.0
        self._active_stage_metrics: dict[str, Any] = {}
        event_bus = getattr(runtime, "event_bus", None)
        self._constitution_guard = BirthConstitutionGuard(event_bus=event_bus, mode="birth")

        self.completion_flag_path = self.workspace_root / "state" / "lumina_birth_completed.flag"
        self.legacy_completion_flag_path = self.workspace_root / "state" / "first_boot_completed.flag"
        self.final_policy_path = self.workspace_root / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
        self.practice_policy_path = self.workspace_root / "lumina_agents" / "ppo" / "lumina_ppo_policy_practice.zip"
        self.pause_flag_path = self.workspace_root / "state" / "first_boot_pause_requested"
        self.practice_completed_flag_path = self.workspace_root / "state" / "lumina_birth_practice_completed.flag"

    def _stop_requested(self) -> bool:
        if self.stop_event is not None and self.stop_event.is_set():
            return True
        return self.pause_flag_path.exists()

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
                progress_pct=18.0,
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
        )
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
        _ = (target_trades, chunk_size, force)
        cfg = self.birth_config
        logger.info("birth.engine.version=%s", BRO_ENGINE_VERSION)
        training_mode = "practice" if practice_mode else "certified"
        max_days = max(30, min(3650, int(max_real_days or cfg.max_real_days)))
        prefer_real = bool(prefer_real_data_only if prefer_real_data_only is not None else cfg.prefer_real_data_only)
        ppo_steps_per_update = max(1000, int(ppo_update_timesteps or cfg.ppo_update_timesteps))
        self.birth_start_time = time.time()
        self._stages_passed = []
        self.cumulative_trades = 0
        self.ppo_steps = 0
        self._data_manifest = {}
        self._remediation_attempt = 0
        self._last_checkpoint_at = 0.0
        self._active_stage_metrics = {}
        self.buffer.clear()
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
        )

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
            ticks = load_historical_ticks(
                market_data_service=self.market_data_service,
                runtime=self.runtime,
                days_back=max_days,
                limit=None,
            )
        if not ticks and not prefer_real:
            ticks = self._generate_synthetic_ticks(max(20_000, max_days * 1000), start_price=5000.0)
        elif not ticks and prefer_real and practice_mode:
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

            ticks = enrich_ticks_for_sim(ticks)
            self._real_data_pct = real_data_percentage(ticks)
            split = purged_train_holdout_split(ticks, holdout_pct=cfg.holdout_pct)
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
            progress_pct=20.0,
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
            return self._complete_certified_birth(
                split=split,
                eval_result=eval_result,
                training_mode=training_mode,
                trade_budget_cap=cfg.trade_budget_cap,
            )

        total_stages = len(ordered_stages())
        stage_index = 0
        curriculum_timesteps = max(1000, int(cfg.curriculum.curriculum_ppo_timesteps))

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
                stage_index += 1
                continue

            stage_ticks = filter_ticks_for_stage(stage, split.train)
            if not stage_ticks:
                stage_ticks = list(split.train)
            target = stage_trade_target(stage, cfg.curriculum)
            self._constitution_guard.reset()

            stage_progress_pct = 20.0 + (stage_index / total_stages) * 60.0
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

            self._stages_passed.append(stage.value)
            stage_index += 1
            self.ppo_trainer.save_final_birth_policy(str(self.final_policy_path))
            self._persist_checkpoint(
                training_mode=training_mode,
                curriculum_stage=stage.value,
                policy_path=str(self.final_policy_path),
                phase="curriculum_stage_complete",
            )

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
    ) -> list[dict[str, Any]]:
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
        _ = holdout_ticks
        cur_cfg = self.birth_config.curriculum
        news_cfg = self.birth_config.news
        required = stage_pass_trades(stage, cur_cfg)
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
        retries_this_stage = 0
        adaptation_tier = 0
        adaptation_history: list[dict[str, Any]] = []
        original_rollout_chunk = cur_cfg.rollout_chunk_trades
        stage_started_at = time.time()
        checkpoint_state = load_checkpoint_state(self.workspace_root)
        stage_metrics = checkpoint_state.get("stage_metrics")
        if isinstance(stage_metrics, dict):
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
            retries_this_stage = max(0, int(stage_metrics.get("retries_this_stage", 0) or 0))
            adaptation_tier = max(0, int(stage_metrics.get("adaptation_tier", 0) or 0))
            raw_adaptations = stage_metrics.get("adaptation_history")
            if isinstance(raw_adaptations, list):
                adaptation_history = [dict(x) for x in raw_adaptations if isinstance(x, dict)]
            if stage_metrics.get("escalation_level") is not None:
                escalation_level = max(0, int(stage_metrics.get("escalation_level", 0) or 0))
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
        last_winrate = 0.0

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
            payload["retries_this_stage"] = int(retries_this_stage)
            payload["adaptation_tier"] = int(adaptation_tier)
            payload["adaptation_history"] = list(adaptation_history)
            payload["escalation_level"] = int(escalation_level)
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
            )
            scorecard.update(adaptation_fields)
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

        def _mine_and_inject() -> None:
            nonlocal patterns_mined, oracle_wins, active_stage_ticks
            pool = active_train if len(active_train) > len(active_stage_ticks) else active_stage_ticks
            mine_result = mine_winning_patterns(
                ticks=pool,
                stage=stage,
                runtime=self.runtime,
                workspace_root=self.workspace_root,
                max_patterns=cur_cfg.oracle_patterns_per_stage,
                scan_stride=cur_cfg.oracle_scan_stride,
                max_hold_bars=cur_cfg.oracle_max_hold_bars,
            )
            patterns_mined += len(mine_result.patterns)
            oracle_wins += mine_result.wins
            for pattern in mine_result.patterns:
                self.buffer.add(pattern, priority=3.0 + min(10.0, abs(float(pattern.get("reward", 0.0)))))
            active_stage_ticks = filter_ticks_for_stage(stage, active_train) or list(active_train)

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

        def _finalize_certified_stage_stall(pending: dict[str, Any]) -> dict[str, Any]:
            failure_key = str(pending["failure_key"])
            blocker_metric = pending["blocker_metric"]
            blocker_value = pending["blocker_value"]
            blocker_reason = pending.get("blocker_reason")
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
                target_trades=trade_budget_cap,
                birth_start_time=self.birth_start_time,
                curriculum_stage=stage.value,
                stage_blocker_metric=blocker_metric,
                stage_blocker_value=blocker_value,
                pass_reason=blocker_reason,
                retryable=True,
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
            return {
                "status": "stage_stalled",
                "failure_reason": failure_key,
                "total_trades": self.cumulative_trades,
                "ppo_steps": self.ppo_steps,
                "training_mode": training_mode,
            }

        def _should_terminal_stall_in_adaptive() -> bool:
            """True only when adaptive mode must stop (budget/data exhausted)."""
            if self.cumulative_trades >= trade_budget_cap:
                return True
            if (
                data_exhausted
                and len(self.buffer) < 80
                and adaptation_tier >= cur_cfg.max_adaptation_tiers - 1
            ):
                return True
            return False

        def _try_adaptive_stall_recovery(*, failure_key: str) -> bool:
            nonlocal escalation_level, retries_this_stage, attempt, adaptation_tier
            nonlocal winrate_stagnation_count, hold_stagnation_count, wall_budget_exhausted
            nonlocal stage_started_at
            if not cur_cfg.adaptation_enabled or cur_cfg.wall_behavior != "adaptive":
                return False
            if _should_terminal_stall_in_adaptive():
                return False
            current_winrate = float(stage_wins) / float(max(1, stage_trades))
            decision = _get_adaptation_decision(
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
                    new_chunk_target=max(cur_cfg.exploration_chunk_size, cur_cfg.rollout_chunk_trades),
                    escalation_increase=0,
                    log_message=f"Persistent recovery tier {adaptation_tier + 1}/{cur_cfg.max_adaptation_tiers}",
                )
            if not decision.should_retry:
                return False
            if adaptation_tier >= 1:
                _mine_and_inject()
            if adaptation_tier >= 2 and cur_cfg.auto_expand_on_adaptation:
                _maybe_expand_data()
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
                cur_cfg.rollout_chunk_trades = original_rollout_chunk
                return _finalize_certified_stage_stall(stall_pending)

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
                logger.info(
                    "birth.stage.passed",
                    extra={
                        "event_data": {
                            "stage": stage.value,
                            "trades": stage_trades,
                            "patterns_mined": patterns_mined,
                            "attempts": attempt,
                            "pass_reason": stage_result.message,
                            "provisional": stage_result.provisional,
                        }
                    },
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

            if attempt >= max_rollouts:
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
                        cur_cfg.rollout_chunk_trades = original_rollout_chunk
                        return _finalize_certified_stage_stall(stall_pending)
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
            )

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

            explore_steps = cur_cfg.exploration_steps * (1 + escalation_level)
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
                on_progress=_rollout_progress,
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

            current_hold_ratio = float(stage_hold_signals) / float(max(1, stage_total_signals))
            range_flat_ratio = float(stage_range_flat_bars) / float(max(1, stage_range_total_signals))
            metric_band = range_flat_ratio if stage_range_total_signals >= 50 else current_hold_ratio
            current_winrate = float(stage_wins) / float(max(1, stage_trades))
            if rollout.trades > 0:
                winrate_history.append(current_winrate)
                if len(winrate_history) > cur_cfg.winrate_trend_window:
                    winrate_history.pop(0)
            if (
                stage == CurriculumStage.STAGE1_TREND
                and stage_trades >= required
                and (current_winrate < 0.45 or current_hold_ratio > 0.85)
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
            _maybe_periodic_checkpoint("curriculum_learning")
            _write_progress(
                phase="curriculum_learning",
                message=(
                    f"Curriculum {stage.value}: {stage_trades:,} / {required:,} trades · "
                    f"poging {attempt} · patronen {patterns_mined:,}"
                ),
                hold_ratio=current_hold_ratio,
            )

