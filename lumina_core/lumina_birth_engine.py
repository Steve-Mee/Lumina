"""Thin façade delegating to BirthPhaseEngineV2 (ADR-0012)."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.ppo_trainer import PPOTrainer

logger = get_logger("lumina.birth_engine")


class LuminaBirthEngine:
    def __init__(
        self,
        runtime: Any = None,
        ppo_trainer: PPOTrainer | None = None,
        market_data_service: Any = None,
        config: dict[str, Any] | None = None,
        workspace_root: str | Path = Path.cwd(),
        stop_event: threading.Event | None = None,
    ) -> None:
        self.runtime = runtime
        self.ppo_trainer = ppo_trainer or PPOTrainer(engine=runtime)
        self.market_data_service = market_data_service
        self.config = config or {}
        self.workspace_root = Path(workspace_root)
        self.stop_event = stop_event
        self.logger = logger

        self.checkpoint_path = self.workspace_root / "state" / "lumina_birth_checkpoint.json"
        self.legacy_checkpoint_path = self.workspace_root / "state" / "first_boot_checkpoint.json"
        self.progress_path = self.workspace_root / "state" / "lumina_birth_progress.json"
        self.final_policy_path = self.workspace_root / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
        self.practice_policy_path = self.workspace_root / "lumina_agents" / "ppo" / "lumina_ppo_policy_practice.zip"
        self.completion_flag_path = self.workspace_root / "state" / "lumina_birth_completed.flag"
        self.legacy_completion_flag_path = self.workspace_root / "state" / "first_boot_completed.flag"
        self.practice_completed_flag_path = self.workspace_root / "state" / "lumina_birth_practice_completed.flag"

        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self.final_policy_path.parent.mkdir(parents=True, exist_ok=True)
        self.practice_policy_path.parent.mkdir(parents=True, exist_ok=True)

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
    ) -> dict[str, Any]:
        from lumina_core.birth.engine import BirthPhaseEngineV2

        v2 = BirthPhaseEngineV2(
            runtime=self.runtime,
            ppo_trainer=self.ppo_trainer,
            market_data_service=self.market_data_service,
            config=self.config,
            workspace_root=self.workspace_root,
            stop_event=self.stop_event,
        )
        override_cfg = getattr(self, "birth_config", None)
        if override_cfg is not None:
            v2.birth_config = override_cfg
        return v2.run_birth_phase(
            target_trades=target_trades,
            max_real_days=max_real_days,
            prefer_real_data_only=prefer_real_data_only,
            chunk_size=chunk_size,
            ppo_update_timesteps=ppo_update_timesteps,
            force=force,
            practice_mode=practice_mode,
            reuse_existing_policy=reuse_existing_policy,
            reuse_data_manifest=reuse_data_manifest,
        )
