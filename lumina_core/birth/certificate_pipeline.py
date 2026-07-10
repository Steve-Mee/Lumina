"""Birth certificate preflight, runway, remediation, and completion pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from lumina_core.birth.birth_certificate import (
    build_certificate_from_eval,
    certificate_path,
    write_certificate,
)
from lumina_core.birth.buffer_persist import clear_buffer
from lumina_core.birth.checkpoint import clear_checkpoint
from lumina_core.birth.curriculum import (
    CurriculumStage,
    filter_ticks_for_stage,
    ordered_runway_stages,
    stage_trade_target,
)
from lumina_core.birth.data_expansion import expand_birth_data
from lumina_core.birth.certificate_evaluator import evaluate_holdout_certificate
from lumina_core.birth.dna_handoff import register_birth_gen0_dna
from lumina_core.birth.bible_meta import update_bible_after_birth
from lumina_core.birth.news_enricher import enrich_ticks_with_news
from lumina_core.birth.preflight import assess_split_preflight, data_manifest_from_split
from lumina_core.birth.pattern_miner import mine_winning_patterns
from lumina_core.birth.progress import read_birth_progress, write_birth_progress
from lumina_core.birth.remediation import (
    RemediationAction,
    filter_train_ticks_for_holdout_profile,
    manifest_train_hash_matches,
    select_regime_diverse_train_ticks,
    select_remediation_plan,
)
from lumina_core.birth.runway import (
    micro_oos_evolution_proof_passed,
    micro_oos_probe,
    micro_oos_sanity_passed,
    runway_stage_index,
    ticks_for_runway_stage,
)
from lumina_core.birth.sim_runner import run_policy_rollout
from lumina_core.birth.tick_cache_persist import compute_ticks_fingerprint, save_birth_data_cache
from lumina_core.birth.stage_pass_receipt import receipt_for_stage
from lumina_core.birth.stage_scorecard import build_scorecard_payload
from lumina_core.rl.trend_features import ENRICH_VERSION
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.certificate_pipeline")


class BirthCertificatePipeline:
    def __init__(self, host: Any) -> None:
        self._host = host

    def ensure_holdout_preflight(
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
        cur_cfg = self._host.birth_config.curriculum
        news_cfg = self._host.birth_config.news
        active_ticks = list(ticks)
        active_split = split
        current_hash = self._host._train_hash(active_split.train)
        if reuse_manifest and manifest_train_hash_matches(
            current_hash=current_hash,
            saved_manifest=saved_manifest,
        ):
            preflight = assess_split_preflight(
                active_split,
                thresholds=self._host.birth_config.certificate_thresholds,
            )
            if preflight.ok:
                manifest = dict(saved_manifest or {})
                manifest.update(
                    data_manifest_from_split(
                        active_split,
                        days_loaded=max(1, len(active_ticks) // 450),
                        real_data_pct=self._host._real_data_pct,
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
            thresholds=self._host.birth_config.certificate_thresholds,
        )
        max_attempts = max(1, len(cur_cfg.data_expansion_steps))
        attempts = 0
        while not preflight.ok and attempts < max_attempts:
            attempts += 1
            prev_regimes = len(preflight.holdout_regimes)
            expanded = expand_birth_data(
                market_data_service=self._host.market_data_service,
                runtime=self._host.runtime,
                current_step=expansion_step + 1,
                expansion_steps=list(cur_cfg.data_expansion_steps),
                holdout_pct=self._host.birth_config.holdout_pct,
                enrich_news_fn=lambda rows: enrich_ticks_with_news(
                    rows,
                    workspace_root=self._host.workspace_root,
                    primary=news_cfg.primary,
                    enable_cache=news_cfg.enable_cache,
                    cache_path=news_cfg.cache_path,
                ),
                synthetic_fallback_fn=(
                    None
                    if prefer_real
                    else lambda n, p: self._host._generate_synthetic_ticks(n, start_price=p or start_price)
                ),
                start_price=start_price,
            )
            expansion_step = expanded.step_index
            if expanded.exhausted and len(expanded.train_ticks) <= len(active_split.train):
                write_birth_progress(
                    self._host.workspace_root,
                    stage="history_unavailable",
                    phase="holdout_preflight_failed",
                    message=preflight.message,
                    progress_pct=100.0,
                    cumulative_trades=0,
                    target_trades=self._host.birth_config.trade_budget_cap,
                    birth_start_time=self._host.birth_start_time,
                    preflight_report={
                        "ok": False,
                        "failure_reasons": list(preflight.failure_reasons),
                        "holdout_regimes": list(preflight.holdout_regimes),
                    },
                    retryable=True,
                )
                self._host._notify_history_unavailable(preflight.message or "Holdout preflight failed.")
                return {
                    "status": "history_unavailable",
                    "total_trades": 0,
                    "ppo_steps": 0,
                    "training_mode": training_mode,
                    "preflight": preflight.failure_reasons,
                }
            active_ticks = list(expanded.all_ticks)
            active_split = expanded.split
            self._host._real_data_pct = expanded.real_data_pct
            preflight = assess_split_preflight(
                active_split,
                thresholds=self._host.birth_config.certificate_thresholds,
            )
            write_birth_progress(
                self._host.workspace_root,
                stage="historical_loaded",
                phase="holdout_preflight_expansion",
                message=(
                    f"Holdout preflight expansion: {len(preflight.holdout_regimes)} regimes, "
                    f"{preflight.holdout_tick_count:,} holdout ticks"
                ),
                progress_pct=min(24.0, 21.0 + float(attempts)),
                cumulative_trades=0,
                target_trades=self._host.birth_config.trade_budget_cap,
                birth_start_time=self._host.birth_start_time,
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
                self._host.workspace_root,
                stage="history_unavailable",
                phase="holdout_preflight_failed",
                message=preflight.message,
                progress_pct=100.0,
                cumulative_trades=0,
                target_trades=self._host.birth_config.trade_budget_cap,
                birth_start_time=self._host.birth_start_time,
                preflight_report={
                    "ok": False,
                    "failure_reasons": list(preflight.failure_reasons),
                    "holdout_regimes": list(preflight.holdout_regimes),
                },
                retryable=True,
            )
            self._host._notify_history_unavailable(preflight.message or "Holdout preflight exhausted.")
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
            real_data_pct=self._host._real_data_pct,
            train_hash=self._host._train_hash(active_split.train),
        )
        manifest["preflight_ok"] = True
        manifest["holdout_regimes"] = list(preflight.holdout_regimes)
        manifest["raw_ticks_hash"] = str(self._host._last_raw_ticks_hash or "")
        manifest["enrich_version"] = ENRICH_VERSION
        manifest["holdout_pct"] = float(self._host.birth_config.holdout_pct)
        cache_paths = save_birth_data_cache(
            self._host.workspace_root,
            ticks=active_ticks,
            split=active_split,
            holdout_pct=self._host.birth_config.holdout_pct,
            raw_ticks_hash=str(self._host._last_raw_ticks_hash or compute_ticks_fingerprint(active_ticks)),
            train_hash=str(manifest.get("train_hash", "") or ""),
            enrich_version=ENRICH_VERSION,
        )
        manifest.update(cache_paths)
        return active_ticks, active_split, manifest

    def run_certificate_remediation(
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
        cur_cfg = self._host.birth_config.curriculum
        news_cfg = self._host.birth_config.news
        max_attempts = max(1, int(cur_cfg.max_certificate_remediation_attempts))
        if cur_cfg.autonomous_recovery_enabled:
            max_attempts = max(max_attempts, 99)
        curriculum_timesteps = max(1000, int(cur_cfg.curriculum_ppo_timesteps))
        polish_timesteps = max(1000, int(cur_cfg.polish_ppo_timesteps))
        current_eval = dict(eval_result)
        remediation_expansion_step = max(
            0, int(self._host._data_manifest.get("remediation_expansion_step", 0) or 0)
        )
        holdout_data = list(split.holdout)

        for attempt in range(1, max_attempts + 1):
            self._host._remediation_attempt = attempt
            reasons = list(current_eval.get("failure_reasons") or [])
            plan = select_remediation_plan(
                reasons,
                attempt=attempt,
                curriculum_ppo_timesteps=curriculum_timesteps,
                polish_ppo_timesteps=polish_timesteps,
                rollout_chunk_trades=cur_cfg.rollout_chunk_trades,
            )
            write_birth_progress(
                self._host.workspace_root,
                stage="training_running",
                phase="certificate_remediation",
                message=(
                    f"Certificate remediation {attempt}/{max_attempts} "
                    f"[{plan.label}]: {', '.join(reasons) or 'diagnose'}"
                ),
                progress_pct=min(99.0, 94.0 + (attempt / max_attempts) * 4.0),
                cumulative_trades=self._host.cumulative_trades,
                target_trades=trade_budget_cap,
                ppo_steps=self._host.ppo_steps,
                birth_start_time=self._host.birth_start_time,
                remediation_attempt=attempt,
                remediation_max=max_attempts,
                remediation_action=plan.action.value,
                oos_metrics=current_eval,
                failure_reasons=reasons,
                quality_score=float(self._host._data_manifest.get("quality_score", 0.0) or 0.0),
            )
            if self._host._stop_requested():
                self._host._persist_checkpoint(
                    training_mode=training_mode,
                    curriculum_stage=CurriculumStage.STAGE4_POLISH.value,
                    phase="certificate_remediation",
                )
                return self._host._paused_result()

            active_train = list(split.train)
            if plan.expand_data:
                expanded = expand_birth_data(
                    market_data_service=self._host.market_data_service,
                    runtime=self._host.runtime,
                    current_step=remediation_expansion_step + 1,
                    expansion_steps=list(cur_cfg.data_expansion_steps),
                    holdout_pct=self._host.birth_config.holdout_pct,
                    enrich_news_fn=lambda rows: enrich_ticks_with_news(
                        rows,
                        workspace_root=self._host.workspace_root,
                        primary=news_cfg.primary,
                        enable_cache=news_cfg.enable_cache,
                        cache_path=news_cfg.cache_path,
                    ),
                    synthetic_fallback_fn=(
                        None
                        if prefer_real
                        else lambda n, p: self._host._generate_synthetic_ticks(n, start_price=p or start_price)
                    ),
                    start_price=start_price,
                )
                remediation_expansion_step = expanded.step_index
                self._host._data_manifest["remediation_expansion_step"] = remediation_expansion_step
                if expanded.train_ticks:
                    active_train = list(expanded.train_ticks)
                    self._host._real_data_pct = expanded.real_data_pct

            if plan.action == RemediationAction.REGIME_EXPAND:
                rollout_ticks = select_regime_diverse_train_ticks(active_train)
            elif plan.action == RemediationAction.HOLDOUT_ACTIVITY:
                rollout_ticks = filter_train_ticks_for_holdout_profile(active_train, holdout_data)
            else:
                rollout_ticks = active_train

            explore_steps = cur_cfg.exploration_steps * plan.explore_multiplier
            remediation_rollout = run_policy_rollout(
                runtime=self._host.runtime,
                data=rollout_ticks,
                policy=self._host.current_policy,
                target_trades=plan.rollout_target_trades,
                workspace_root=self._host.workspace_root,
                constitution_guard=self._host._constitution_guard,
                exploration_steps=explore_steps,
                escalation_level=2 if plan.action != RemediationAction.SHARPE_POLISH else 1,
            )
            for traj in remediation_rollout.trajectories:
                self._host.buffer.add(traj, priority=2.0)
            self._host.cumulative_trades += remediation_rollout.trades

            ppo_steps = plan.ppo_timesteps
            if plan.action == RemediationAction.SHARPE_POLISH:
                ppo_steps = max(1000, polish_timesteps // max(1, attempt))
            elif len(self._host.buffer) < 80:
                ppo_steps = min(ppo_steps, 2000)

            if len(self._host.buffer) >= 80:
                self._host.current_policy = self._host.ppo_trainer.update_from_buffer(
                    buffer=self._host.buffer,
                    timesteps=ppo_steps,
                    birth_phase=True,
                )
                self._host.ppo_steps += ppo_steps
                self._host._persist_checkpoint(
                    training_mode=training_mode,
                    curriculum_stage=CurriculumStage.STAGE4_POLISH.value,
                    phase="certificate_remediation",
                )

            current_eval = evaluate_holdout_certificate(
                runtime=self._host.runtime,
                holdout_data=holdout_data,
                policy=self._host.current_policy,
                real_data_pct=self._host._real_data_pct,
                holdout_days=split.holdout_days,
                constitution_violations=self._host._constitution_guard.violations,
                workspace_root=self._host.workspace_root,
                thresholds=self._host.birth_config.certificate_thresholds,
            )
            if current_eval.get("certificate_passed"):
                return current_eval

        write_birth_progress(
            self._host.workspace_root,
            stage="failed",
            phase="certificate_failed",
            message="Birth Certificate v2 thresholds not met after remediation.",
            progress_pct=100.0,
            cumulative_trades=self._host.cumulative_trades,
            target_trades=trade_budget_cap,
            birth_start_time=self._host.birth_start_time,
            oos_metrics=current_eval,
            failure_reasons=list(current_eval.get("failure_reasons") or []),
            remediation_attempt=self._host._remediation_attempt,
            stages_passed=list(self._host._stages_passed),
            data_manifest=dict(self._host._data_manifest),
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
                workspace_root=self._host.workspace_root,
            )
        except Exception as exc:
            logger.warning("birth.cert_attention_failed: %s", exc)
        self._host._persist_checkpoint(
            training_mode=training_mode,
            curriculum_stage=CurriculumStage.STAGE4_POLISH.value,
            phase="certificate_failed",
            oos_metrics=dict(current_eval),
        )
        return current_eval

    def resolve_birth_exit_winrate(self) -> float:
        receipt = receipt_for_stage(self._host._stage_pass_receipts, CurriculumStage.STAGE3_MIXED.value)
        if receipt is not None:
            return float(receipt.winrate)
        progress = read_birth_progress(self._host.workspace_root)
        raw = progress.get("birth_exit_winrate")
        if isinstance(raw, (int, float)):
            return float(raw)
        return 0.0

    def resolve_baseline_oos_winrate(self, *, checkpoint_state: dict[str, Any] | None = None) -> float:
        ckpt = checkpoint_state or {}
        ckpt_oos = ckpt.get("oos_metrics")
        if isinstance(ckpt_oos, dict):
            wr = ckpt_oos.get("oos_winrate")
            if isinstance(wr, (int, float)):
                return float(wr)
        progress = read_birth_progress(self._host.workspace_root)
        prog_oos = progress.get("oos_metrics")
        if isinstance(prog_oos, dict):
            wr = prog_oos.get("oos_winrate")
            if isinstance(wr, (int, float)):
                return float(wr)
        return 0.0

    def bootstrap_runway_stage5(self, *, train_ticks: list[dict[str, Any]]) -> None:
        """S5: optional rollback to best S3 snapshot + oracle distill from S1 trend."""
        cur_cfg = self._host.birth_config.curriculum
        snap = self._host.workspace_root / "lumina_agents" / "ppo" / "birth_best_stage3_mixed.zip"
        if snap.is_file():
            load_fn = getattr(self._host.ppo_trainer, "load_policy", None)
            if callable(load_fn):
                try:
                    load_fn(str(snap))
                    logger.info("birth.runway.s5_policy_rollback path=%s", snap)
                except Exception as exc:
                    logger.warning("birth.runway.s5_policy_rollback_failed: %s", exc)
        s1_ticks = filter_ticks_for_stage(CurriculumStage.STAGE1_TREND, train_ticks)
        if not s1_ticks:
            return
        max_patterns, scan_stride = self._host._resolve_oracle_mining_params(cur_cfg, aggressive=True)
        mine_result = mine_winning_patterns(
            ticks=s1_ticks[: min(len(s1_ticks), 50_000)],
            stage=CurriculumStage.STAGE5_PROFIT_VAL,
            runtime=self._host.runtime,
            workspace_root=self._host.workspace_root,
            max_patterns=max_patterns,
            scan_stride=scan_stride,
            max_hold_bars=cur_cfg.oracle_max_hold_bars,
        )
        for pattern in mine_result.patterns:
            self._host.buffer.add(
                pattern,
                priority=3.0 + min(10.0, abs(float(pattern.get("reward", 0.0)))),
            )
        logger.info(
            "birth.runway.s5_oracle_seed patterns=%s wins=%s",
            len(mine_result.patterns),
            mine_result.wins,
        )

    def run_certificate_runway_stages(
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
        """MVR runway S5→S6→S7 with micro-OOS gates (post-S6 sanity, post-S7 EP)."""
        cur_cfg = self._host.birth_config.curriculum
        holdout_ticks = list(split.holdout)
        runway_stages = ordered_runway_stages()
        max_micro_trades = int(getattr(cur_cfg, "runway_micro_oos_max_trades", 800))

        write_birth_progress(
            self._host.workspace_root,
            stage="training_running",
            phase="runway_stage",
            message="Certificate runway: profit → risk → generalize",
            progress_pct=80.0,
            cumulative_trades=self._host.cumulative_trades,
            target_trades=trade_budget_cap,
            ppo_steps=self._host.ppo_steps,
            birth_start_time=self._host.birth_start_time,
            runway_phase="S5",
            birth_exit_winrate=birth_exit_winrate,
        )

        for runway_index, stage in enumerate(runway_stages):
            if self._host._stop_requested():
                self._host._persist_checkpoint(
                    training_mode=training_mode,
                    curriculum_stage=stage.value,
                    phase="paused",
                )
                return self._host._paused_result()

            if stage.value in self._host._stages_passed:
                if self._host._verify_stage_pass_receipt_for_skip(stage, training_mode=training_mode):
                    continue

            if stage == CurriculumStage.STAGE5_PROFIT_VAL:
                self.bootstrap_runway_stage5(train_ticks=train_core_ticks)

            stage_ticks = ticks_for_runway_stage(
                stage,
                train_ticks=train_core_ticks,
                holdout_ticks=holdout_ticks,
                validation_ticks=validation_ticks,
            )
            if not stage_ticks:
                stage_ticks = list(validation_ticks) or list(train_core_ticks)
            target = stage_trade_target(stage, cur_cfg)
            self._host._accumulate_constitution_violations_before_stage_reset()

            stage_progress_pct = 80.0 + (runway_index / max(1, len(runway_stages))) * 8.0
            write_birth_progress(
                self._host.workspace_root,
                stage="training_running",
                phase="runway_stage",
                message=f"Runway {stage.value}: training…",
                progress_pct=stage_progress_pct,
                cumulative_trades=self._host.cumulative_trades,
                target_trades=trade_budget_cap,
                ppo_steps=self._host.ppo_steps,
                birth_start_time=self._host.birth_start_time,
                curriculum_stage=stage.value,
                runway_phase=f"S{runway_stage_index(stage)}",
                birth_exit_winrate=birth_exit_winrate,
            )

            micro_probe: dict[str, Any] | None = None
            while True:
                stage_error = self._host._run_stage_research_loop(
                    stage=stage,
                    stage_index=runway_index + 4,
                    stage_ticks=stage_ticks,
                    train_ticks=list(train_core_ticks),
                    holdout_ticks=holdout_ticks,
                    target=target,
                    stage_progress_pct=stage_progress_pct,
                    training_mode=training_mode,
                    ppo_steps_per_update=ppo_steps_per_update,
                    polish_ppo_timesteps=max(1000, int(cur_cfg.polish_ppo_timesteps)),
                    trade_budget_cap=trade_budget_cap,
                    prefer_real=prefer_real,
                    start_price=start_price,
                )
                if stage_error is not None:
                    return stage_error

                if stage == CurriculumStage.STAGE6_RISK_DISCIPLINE:
                    micro_probe = micro_oos_probe(
                        runtime=self._host.runtime,
                        holdout_data=holdout_ticks,
                        policy=self._host.current_policy,
                        real_data_pct=self._host._real_data_pct,
                        holdout_days=split.holdout_days,
                        constitution_violations=self._host._constitution_guard.violations,
                        workspace_root=self._host.workspace_root,
                        thresholds=self._host.birth_config.certificate_thresholds,
                        max_trades=max_micro_trades,
                    )
                    ok, probe_msg = micro_oos_sanity_passed(
                        micro_probe,
                        cfg=cur_cfg,
                        baseline_oos_winrate=baseline_oos_winrate,
                    )
                    write_birth_progress(
                        self._host.workspace_root,
                        stage="training_running",
                        phase="runway_micro_oos",
                        message=f"Post-S6 micro-OOS: {probe_msg}",
                        progress_pct=stage_progress_pct + 1.0,
                        cumulative_trades=self._host.cumulative_trades,
                        target_trades=trade_budget_cap,
                        micro_oos_probe=micro_probe,
                        runway_phase="S6_probe",
                    )
                    if not ok:
                        logger.info("birth.runway.s6_sanity_retry reason=%s", probe_msg)
                        continue

                if stage == CurriculumStage.STAGE7_HOLDOUT_PROFILE:
                    micro_probe = micro_oos_probe(
                        runtime=self._host.runtime,
                        holdout_data=holdout_ticks,
                        policy=self._host.current_policy,
                        real_data_pct=self._host._real_data_pct,
                        holdout_days=split.holdout_days,
                        constitution_violations=self._host._constitution_guard.violations,
                        workspace_root=self._host.workspace_root,
                        thresholds=self._host.birth_config.certificate_thresholds,
                        max_trades=max_micro_trades,
                    )
                    ok, probe_msg = micro_oos_evolution_proof_passed(
                        micro_probe,
                        birth_exit_winrate=birth_exit_winrate,
                        cfg=cur_cfg,
                    )
                    write_birth_progress(
                        self._host.workspace_root,
                        stage="training_running",
                        phase="runway_micro_oos",
                        message=f"Post-S7 EP probe: {probe_msg}",
                        progress_pct=stage_progress_pct + 1.5,
                        cumulative_trades=self._host.cumulative_trades,
                        target_trades=trade_budget_cap,
                        micro_oos_probe=micro_probe,
                        runway_phase="S7_ep_probe",
                    )
                    if not ok:
                        logger.info("birth.runway.s7_ep_retry reason=%s", probe_msg)
                        continue

                break

            self._host._commit_stage_graduation(
                stage,
                training_mode=training_mode,
                curriculum_stage=stage.value,
                policy_path=str(self._host.final_policy_path),
                phase="runway_stage_complete",
            )

        return None

    def fail_certificate_with_runway_checkpoint(
        self,
        *,
        eval_result: dict[str, Any],
        training_mode: str,
        trade_budget_cap: int,
    ) -> dict[str, Any]:
        """Persist cert failure for runway resume (skip generic remediation when MVR enabled)."""
        current_eval = dict(eval_result)
        write_birth_progress(
            self._host.workspace_root,
            stage="failed",
            phase="certificate_failed",
            message="Birth Certificate v2 thresholds not met — resume enters runway S5.",
            progress_pct=100.0,
            cumulative_trades=self._host.cumulative_trades,
            target_trades=trade_budget_cap,
            birth_start_time=self._host.birth_start_time,
            oos_metrics=current_eval,
            failure_reasons=list(current_eval.get("failure_reasons") or []),
            stages_passed=list(self._host._stages_passed),
            data_manifest=dict(self._host._data_manifest),
            needs_attention=True,
            retryable=True,
            birth_exit_winrate=self.resolve_birth_exit_winrate(),
        )
        try:
            from lumina_core.notifications.attention_events import birth_certificate_failed_event
            from lumina_core.notifications.attention_notifier import notify_attention

            notify_attention(
                birth_certificate_failed_event(
                    failure_reasons=list(current_eval.get("failure_reasons") or []),
                ),
                workspace_root=self._host.workspace_root,
            )
        except Exception as exc:
            logger.warning("birth.cert_attention_failed: %s", exc)
        self._host._persist_checkpoint(
            training_mode=training_mode,
            curriculum_stage=CurriculumStage.STAGE5_PROFIT_VAL.value,
            phase="certificate_failed",
            oos_metrics=dict(current_eval),
        )
        return {
            "status": "certificate_failed",
            "total_trades": self._host.cumulative_trades,
            "ppo_steps": self._host.ppo_steps,
            "real_data_pct": self._host._real_data_pct,
            "eval": current_eval,
            "training_mode": "certified",
        }

    def run_stage8_polish_and_certificate(
        self,
        *,
        split: Any,
        training_mode: str,
        ppo_steps_per_update: int,
        trade_budget_cap: int,
        prefer_real: bool,
        start_price: float,
    ) -> dict[str, Any]:
        """S8: PPO polish + unified holdout certificate eval (+ EP record on pass)."""
        _ = (ppo_steps_per_update, prefer_real, start_price)
        cfg = self._host.birth_config
        cur_cfg = cfg.curriculum

        polish_scorecard = build_scorecard_payload(
            stage=CurriculumStage.STAGE4_POLISH,
            curriculum_index=8,
            stages_passed=list(self._host._stages_passed),
            stage_trades=0,
            stage_wins=0,
            stage_hold_signals=0,
            stage_total_signals=0,
            constitution_violations=self._host._constitution_guard.violations,
            target_trades=0,
            phase="ppo_polish",
            patterns_mined=0,
            learning_attempt=0,
            cfg=cur_cfg,
        )
        write_birth_progress(
            self._host.workspace_root,
            stage="ppo_training",
            phase="ppo_polish",
            message="Final PPO polish (stage8).",
            progress_pct=88.0,
            cumulative_trades=self._host.cumulative_trades,
            target_trades=trade_budget_cap,
            ppo_steps=self._host.ppo_steps,
            birth_start_time=self._host.birth_start_time,
            curriculum_stage=CurriculumStage.STAGE4_POLISH.value,
            runway_phase="S8",
            **polish_scorecard,
        )

        from lumina_core.notifications.milestone_events import (
            curriculum_stage4_polish_passed_event,
            refinement_started_event,
        )

        self._host._notify_milestone(
            curriculum_stage4_polish_passed_event(
                stages_passed=list(self._host._stages_passed),
                cumulative_trades=self._host.cumulative_trades,
            )
        )
        self._host._notify_milestone(
            refinement_started_event(
                cumulative_trades=self._host.cumulative_trades,
                ppo_steps=self._host.ppo_steps,
            )
        )

        polish_steps = cur_cfg.polish_ppo_timesteps
        if len(self._host.buffer) >= 256:
            self._host.ppo_trainer.final_birth_polish(self._host.buffer)
            self._host.ppo_steps += polish_steps
        else:
            polish_batch = min(polish_steps, 10_000)
            self._host.ppo_trainer.update_from_buffer(
                buffer=self._host.buffer,
                timesteps=polish_batch,
                birth_phase=True,
            )
            self._host.ppo_steps += polish_batch
        self._host._persist_checkpoint(
            training_mode=training_mode,
            curriculum_stage=CurriculumStage.STAGE4_POLISH.value,
            policy_path=str(self._host.final_policy_path),
            phase="ppo_polish",
        )
        self._host.ppo_trainer.save_final_birth_policy(str(self._host.final_policy_path))

        oos_scorecard = build_scorecard_payload(
            stage=CurriculumStage.STAGE4_POLISH,
            curriculum_index=8,
            stages_passed=list(self._host._stages_passed),
            stage_trades=0,
            stage_wins=0,
            stage_hold_signals=0,
            stage_total_signals=0,
            constitution_violations=self._host._constitution_guard.violations,
            target_trades=0,
            phase="oos_evaluation",
            patterns_mined=0,
            learning_attempt=0,
            cfg=cur_cfg,
        )
        write_birth_progress(
            self._host.workspace_root,
            stage="training_running",
            phase="oos_evaluation",
            message="OOS certificate evaluatie (unified S8)…",
            progress_pct=94.0,
            cumulative_trades=self._host.cumulative_trades,
            target_trades=trade_budget_cap,
            birth_start_time=self._host.birth_start_time,
            runway_phase="S8_cert",
            **oos_scorecard,
        )

        eval_result = evaluate_holdout_certificate(
            runtime=self._host.runtime,
            holdout_data=split.holdout,
            policy=self._host.current_policy,
            real_data_pct=self._host._real_data_pct,
            holdout_days=split.holdout_days,
            constitution_violations=self._host._constitution_guard.violations,
            workspace_root=self._host.workspace_root,
            thresholds=cfg.certificate_thresholds,
        )

        if not eval_result.get("certificate_passed"):
            if cur_cfg.certificate_runway_enabled:
                return self.fail_certificate_with_runway_checkpoint(
                    eval_result=eval_result,
                    training_mode=training_mode,
                    trade_budget_cap=trade_budget_cap,
                )
            eval_result = self.run_certificate_remediation(
                split=split,
                eval_result=eval_result,
                training_mode=training_mode,
                ppo_steps_per_update=ppo_steps_per_update,
                trade_budget_cap=trade_budget_cap,
                prefer_real=prefer_real,
                start_price=start_price,
            )
            if isinstance(eval_result, dict) and eval_result.get("status") == "paused":
                return eval_result
            if not eval_result.get("certificate_passed"):
                return {
                    "status": "certificate_failed",
                    "total_trades": self._host.cumulative_trades,
                    "ppo_steps": self._host.ppo_steps,
                    "real_data_pct": self._host._real_data_pct,
                    "eval": eval_result,
                    "training_mode": "certified",
                }

        from lumina_core.notifications.milestone_events import oos_evaluation_passed_event

        self._host._notify_milestone(oos_evaluation_passed_event(eval_result=eval_result))

        return self.complete_certified_birth(
            split=split,
            eval_result=eval_result,
            training_mode=training_mode,
            trade_budget_cap=trade_budget_cap,
        )

    def complete_certified_birth(
        self,
        *,
        split: Any,
        eval_result: dict[str, Any],
        training_mode: str,
        trade_budget_cap: int,
    ) -> dict[str, Any]:
        self._host._stages_passed.append(CurriculumStage.STAGE4_POLISH.value)
        certificate = build_certificate_from_eval(
            workspace_root=self._host.workspace_root,
            eval_result=eval_result,
            curriculum_stages_passed=self._host._stages_passed,
            training_trades=self._host.cumulative_trades,
            ppo_steps=self._host.ppo_steps,
        )
        write_certificate(self._host.workspace_root, certificate)
        clear_checkpoint(self._host.workspace_root)
        clear_buffer(self._host.workspace_root)
        stamp = datetime.now(timezone.utc).isoformat()
        for path in (self._host.completion_flag_path, self._host.legacy_completion_flag_path):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(stamp, encoding="utf-8")

        register_birth_gen0_dna(self._host.workspace_root, certificate)
        try:
            from lumina_core.evolution.meta_milestones import propose_next_milestone

            propose_next_milestone(
                self._host.workspace_root,
                generation=0,
                current_winrate=float(eval_result.get("oos_winrate", eval_result.get("winrate", 0.0)) or 0.0),
                current_sharpe=float(eval_result.get("oos_sharpe", eval_result.get("sharpe", 0.0)) or 0.0),
                regime_coverage=int(eval_result.get("regimes_covered", 0) or 0),
            )
        except Exception as exc:
            logger.warning("birth.meta_milestone.gen0_failed: %s", exc)
        update_bible_after_birth(self._host.workspace_root, certificate, eval_result)

        from lumina_core.birth.evolution_proof_gate import (
            EvolutionProofConfig,
            record_and_evaluate_at_certificate,
        )
        from lumina_core.notifications.milestone_events import (
            birth_certificate_issued_event,
            evolution_proof_failed_event,
            evolution_proof_passed_event,
        )

        birth_exit_wr = self.resolve_birth_exit_winrate()
        if birth_exit_wr <= 0.0:
            birth_exit_wr = float(
                eval_result.get("training_winrate", eval_result.get("winrate", 0.0)) or 0.0
            )
        curriculum_cfg = self._host.birth_config.curriculum
        proof_cfg = EvolutionProofConfig(
            min_trades=int(curriculum_cfg.evolution_proof_min_trades),
            min_winrate_lift=float(curriculum_cfg.evolution_proof_min_winrate_lift),
            polish_oos_winrate_min=float(curriculum_cfg.evolution_proof_polish_oos_winrate_min),
        )
        proof_result = record_and_evaluate_at_certificate(
            self._host.workspace_root,
            eval_result=eval_result,
            birth_exit_winrate=birth_exit_wr,
            cfg=proof_cfg,
        )
        if proof_result.passed:
            self._host._notify_milestone(
                evolution_proof_passed_event(
                    oos_winrate=float(proof_result.polish_oos_winrate or 0.0),
                    lift=proof_result.winrate_lift,
                )
            )
            from lumina_core.maturity.milestone_hooks import hook_evolution_proof_passed

            hook_evolution_proof_passed(
                self._host.workspace_root,
                oos_winrate=float(proof_result.polish_oos_winrate or 0.0),
                lift=proof_result.winrate_lift,
            )
        else:
            self._host._notify_milestone(
                evolution_proof_failed_event(reasons=list(proof_result.reasons))
            )
            from lumina_core.notifications.attention_events import evolution_proof_failed_attention_event

            self._host._notify_attention(
                evolution_proof_failed_attention_event(reasons=list(proof_result.reasons))
            )

        self._host._notify_milestone(
            birth_certificate_issued_event(
                eval_result=eval_result,
                stages_passed=list(self._host._stages_passed),
                cumulative_trades=self._host.cumulative_trades,
                ppo_steps=self._host.ppo_steps,
            )
        )
        from lumina_core.maturity.milestone_hooks import hook_birth_certificate_issued

        hook_birth_certificate_issued(
            self._host.workspace_root,
            cumulative_trades=self._host.cumulative_trades,
            stages_passed=list(self._host._stages_passed),
        )

        write_birth_progress(
            self._host.workspace_root,
            stage="completed",
            phase="certificate_issued",
            message="Birth Certificate v2 issued.",
            progress_pct=100.0,
            cumulative_trades=self._host.cumulative_trades,
            target_trades=trade_budget_cap,
            ppo_steps=self._host.ppo_steps,
            birth_start_time=self._host.birth_start_time,
            certificate_ok=True,
            oos_metrics=eval_result,
            curriculum_stages_passed=self._host._stages_passed,
        )

        target_policy = self._host.final_policy_path
        return {
            "status": "completed",
            "total_trades": self._host.cumulative_trades,
            "ppo_steps": self._host.ppo_steps,
            "real_data_pct": self._host._real_data_pct,
            "policy_path": str(target_policy),
            "certificate_path": str(certificate_path(self._host.workspace_root)),
            "eval": eval_result,
            "training_mode": training_mode,
        }

