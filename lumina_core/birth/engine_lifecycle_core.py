"""Wiring / twin / hardware / policy create (M5 engine_lifecycle extract)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.certificate_pipeline import BirthCertificatePipeline
from lumina_core.birth.checkpoint_coordinator import BirthCheckpointCoordinator
from lumina_core.birth.data_pipeline import (
    BirthDataPipeline,
    generate_synthetic_ticks,
    train_hash,
)
from lumina_core.birth.progress_reporter import BirthProgressReporter
from lumina_core.hardware_intelligence import HARDWARE_PROFILES

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.engine")


class EngineLifecycleCoreMixin:
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

    def _constitution_progress_fields(self) -> dict[str, Any]:
        # Hard only for graduation keys — soft entry blocks are HUD/ops forensics.
        session = int(self._constitution_guard.violations)
        cumulative = int(self._constitution_violations_cumulative) + session
        soft = int(getattr(self._constitution_guard, "soft_blocks", 0) or 0)
        hist_fn = getattr(self._constitution_guard, "soft_block_histogram", None)
        hist = hist_fn() if callable(hist_fn) else {}
        fields: dict[str, Any] = {
            "constitution_violations": cumulative,
            "constitution_violations_session": session,
            "constitution_violations_cumulative": cumulative,
            "constitution_soft_blocks": soft,
            "constitution_soft_blocks_session": soft,
            "soft_block_reasons_hist": hist if isinstance(hist, dict) else {},
            "birth_risk_clips_applied": int(
                getattr(self._constitution_guard, "clips_applied", 0) or 0
            ),
        }
        return fields

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


