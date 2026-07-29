"""Birth engine lifecycle: wiring helpers, progress, checkpoint, certificate delegates."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.certificate_pipeline import BirthCertificatePipeline
from lumina_core.birth.checkpoint_coordinator import BirthCheckpointCoordinator
from lumina_core.birth.config import load_birth_v2_config
from lumina_core.birth.curriculum_orchestrator import CurriculumOrchestrator
from lumina_core.birth.data_pipeline import (
    BirthDataPipeline,
    generate_synthetic_ticks,
    train_hash,
)
from lumina_core.birth.progress_reporter import BirthProgressReporter
from lumina_core.birth.progress import (
    read_birth_progress,
    write_birth_progress,
)
from lumina_core.hardware_intelligence import HARDWARE_PROFILES
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.engine")


class EngineLifecycleMixin:
    def _resolve_approval_twin(self) -> Any | None:
        """Best-effort ApprovalTwin for birth auto-judgment (ADR-0031/0032).

        Prefer engine-attached twin; fall back to EvolutionOrchestrator singleton.
        Fail-closed: missing twin is OK (autonomy falls back to human notify paths).
        """
        for attr in ("approval_twin", "_approval_twin"):
            twin = getattr(self, attr, None)
            if twin is not None:
                return twin
        try:
            from lumina_core.evolution.evolution_orchestrator import EvolutionOrchestrator

            return getattr(EvolutionOrchestrator(), "_approval_twin", None)
        except Exception:
            return None

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
        # Hard only — soft entry blocks must not poison stage pass / HUD graduation gate.
        session = int(self._constitution_guard.violations)
        cumulative = int(self._constitution_violations_cumulative) + session
        soft = int(getattr(self._constitution_guard, "soft_blocks", 0) or 0)
        return {
            "constitution_violations": cumulative,
            "constitution_violations_session": session,
            "constitution_violations_cumulative": cumulative,
            "constitution_soft_blocks": soft,
            "constitution_soft_blocks_session": soft,
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

    def _on_curriculum_aborted(self, abort: dict[str, Any]) -> None:
        """Honor fail-closed abort: set stop signals so the stage loop exits."""
        reason = str((abort or {}).get("reason") or "curriculum_aborted")
        self._force_stop_reason = reason
        if self.stop_event is not None:
            self.stop_event.set()
        try:
            self.pause_flag_path.parent.mkdir(parents=True, exist_ok=True)
            self.pause_flag_path.write_text(
                f"abort:{reason}",
                encoding="utf-8",
            )
        except Exception:
            logger.debug("birth.abort_pause_flag_write_failed", exc_info=True)
        logger.critical(
            "birth.fail_closed.host_stop reason=%s — stage loop will exit",
            reason,
        )

    def _stop_requested(self) -> bool:
        if self._force_stop_reason:
            return True
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

    def _resolve_ppo_trainer(self) -> Any:
        """Bound PPO trainer used for birth policy minting (fail-closed if unbound)."""
        trainer = self.ppo_trainer
        if trainer is None:
            trainer = getattr(self.runtime, "ppo_trainer", None)
            if trainer is not None:
                self.ppo_trainer = trainer
        return trainer

    def _create_birth_policy(
        self,
        *,
        allow_load_existing: bool,
        policy_path: str | None = None,
        force_reinit: bool = False,
    ) -> Any:
        trainer = self._resolve_ppo_trainer()
        create = getattr(trainer, "create_fresh_birth_policy", None)
        if not callable(create):
            raise RuntimeError(
                "PPO trainer unbound or incompatible (missing create_fresh_birth_policy); "
                "birth cannot mint a policy."
            )
        resolved_path = str(policy_path or "").strip()
        if resolved_path:
            candidate = Path(resolved_path)
            if candidate.is_file():
                load_policy = getattr(trainer, "load_policy", None)
                if callable(load_policy):
                    load_policy(resolved_path)
                active = getattr(trainer, "_resolve_active_model", None)
                if callable(active):
                    loaded = active()
                    if loaded is not None:
                        return loaded
                load_weights = getattr(trainer, "load_weights", None)
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

    def _paused_result(self) -> dict[str, Any]:
        from lumina_core.birth.progress import read_birth_progress
        from lumina_core.birth.starship_birth import build_pause_ssot_payload, write_pause_ssot

        write_birth_progress(
            self.workspace_root,
            stage="paused",
            phase="paused",
            message="Birth Phase gepauzeerd door gebruiker.",
            progress_pct=min(
                99.0,
                float(self.cumulative_trades) / max(1.0, float(self.birth_config.trade_budget_cap)) * 100.0,
            ),
            cumulative_trades=self.cumulative_trades,
            target_trades=self.birth_config.trade_budget_cap,
            birth_start_time=self.birth_start_time,
            ppo_steps=self.ppo_steps,
            user_initiated_stop=True,
        )
        # Starship A5: keep lumina_birth_progress + first_boot_progress identical.
        current = read_birth_progress(self.workspace_root)
        write_pause_ssot(
            self.workspace_root,
            build_pause_ssot_payload(
                progress=current,
                message="Birth Phase gepauzeerd door gebruiker.",
            ),
        )
        return {"status": "paused", "total_trades": self.cumulative_trades, "ppo_steps": self.ppo_steps}

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
