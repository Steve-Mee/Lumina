"""Birth Phase v2 orchestrator (ADR-0012/0013/0014).

Composition root façade — lifecycle / trajectory / graduation helpers live in
``engine_lifecycle``, ``engine_trajectory``, ``engine_graduation``.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from lumina_core.birth.birth_constitution_guard import BirthConstitutionGuard
from lumina_core.birth.birth_bus_client import BirthBusClient
from lumina_core.birth.birth_handler_registry import BirthHandlerRegistry
from lumina_core.birth.config import (  # noqa: F401 — re-export for monkeypatch / public API
    BirthCurriculumConfig,
    load_birth_v2_config,
)
from lumina_core.birth.constitution_enforcer import ConstitutionEnforcer
from lumina_core.birth.curriculum_orchestrator import CurriculumOrchestrator
from lumina_core.birth.curriculum_stage_handler import create_and_attach_stage_handler
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.engine_graduation import EngineGraduationMixin
from lumina_core.birth.engine_lifecycle import EngineLifecycleMixin
from lumina_core.birth.engine_trajectory import (  # noqa: F401
    EngineTrajectoryMixin,
    ProvisionalPassDecision,
    TrajectoryBuffer,
)
from lumina_core.birth.stage_pass_receipt import StagePassReceipt
from lumina_core.logging_utils import get_logger

# Bounded-module markers kept on the composition root for god-surface import guards.
# (Delegates live in engine_lifecycle / engine_graduation / engine_trajectory.)
_BOUNDED_IMPORT_MARKERS = (
    "lumina_core.birth.checkpoint",
    "lumina_core.birth.curriculum",
    "lumina_core.birth.data_pipeline",
    "lumina_core.birth.progress_reporter",
    "lumina_core.birth.checkpoint_coordinator",
    "lumina_core.birth.stage_training_loop",
    "lumina_core.birth.certificate_pipeline",
    "lumina_core.birth.birth_handler_registry",
    "lumina_core.birth.birth_bus_client",
)

logger = get_logger("lumina.birth.engine")

__all__ = [
    "BirthCurriculumConfig",
    "BirthPhaseEngineV2",
    "ProvisionalPassDecision",
    "TrajectoryBuffer",
    "load_birth_v2_config",
]


class BirthPhaseEngineV2(
    EngineLifecycleMixin,
    EngineGraduationMixin,
    EngineTrajectoryMixin,
):
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
        # Prefer explicit inject; fall back to runtime-bound trainer (launcher/container paths).
        self.ppo_trainer = ppo_trainer if ppo_trainer is not None else getattr(runtime, "ppo_trainer", None)
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
        self._terminal_freeze: dict[str, Any] | None = None
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
        self._force_stop_reason: str | None = None
        try:
            self._curriculum_orchestrator = CurriculumOrchestrator(self.event_bus)
            self._constitution_enforcer = ConstitutionEnforcer(self.event_bus)
            self._constitution_enforcer.attach()
            # True fail-closed: abort event must stop the stage loop, not only log.
            self._curriculum_orchestrator.on_curriculum_aborted(self._on_curriculum_aborted)
            approval_twin = self._resolve_approval_twin()
            self._birth_handler_registry = BirthHandlerRegistry(
                self.event_bus,
                self.birth_config.curriculum,
                self.birth_config.reward,
                approval_twin=approval_twin,
            )
            self._birth_handler_registry.attach_all()
            self._birth_bus_client = BirthBusClient(
                self.event_bus,
                self.birth_config.curriculum,
                self.birth_config.reward,
                registry=self._birth_handler_registry,
                approval_twin=approval_twin,
            )
            # Twin EventBus subscriptions (shadow observe) when orchestrator twin is present
            if approval_twin is not None and hasattr(approval_twin, "bind_event_bus"):
                try:
                    approval_twin.bind_event_bus(self.event_bus)
                except Exception:
                    logger.debug("birth.twin_bind_event_bus_failed", exc_info=True)
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
        # Recovery (plateau / remediation / wall+adaptation / phoenix) is now in handlers via BirthBusClient.
        # run_stage_research_loop is thin orchestration.
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
