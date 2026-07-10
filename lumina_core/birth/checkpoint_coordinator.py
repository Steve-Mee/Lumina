"""Birth checkpoint persistence and trajectory buffer restore."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Protocol

from lumina_core.birth.buffer_persist import load_buffer, save_buffer
from lumina_core.birth.checkpoint import save_checkpoint


class BirthCheckpointHost(Protocol):
    workspace_root: Path
    cumulative_trades: int
    ppo_steps: int
    _stages_passed: list[str]
    _stage_pass_receipts: list[Any]
    _active_stage_metrics: dict[str, Any]
    _data_manifest: dict[str, Any]
    _remediation_attempt: int
    final_policy_path: Path
    _last_checkpoint_at: float
    buffer: Any

    def _stage_metrics_snapshot(self, **kwargs: Any) -> dict[str, Any]: ...


class BirthCheckpointCoordinator:
    def __init__(self, host: BirthCheckpointHost) -> None:
        self._host = host

    def restore_buffer_from_checkpoint(self, state: dict[str, Any]) -> None:
        host = self._host
        buffer_file = str(state.get("buffer_path", "") or "").strip()
        if buffer_file and Path(buffer_file).is_file():
            for traj in load_buffer(host.workspace_root):
                host.buffer.add(traj)
            return
        if int(state.get("version", 2) or 2) >= 3:
            for traj in load_buffer(host.workspace_root):
                host.buffer.add(traj)

    def persist_checkpoint(
        self,
        *,
        training_mode: str,
        curriculum_stage: str,
        policy_path: str | None = None,
        phase: str = "",
        stage_metrics: dict[str, Any] | None = None,
        oos_metrics: dict[str, Any] | None = None,
    ) -> None:
        host = self._host
        if stage_metrics:
            merged = dict(host._active_stage_metrics)
            merged.update(stage_metrics)
            host._active_stage_metrics = merged
        metrics = (
            dict(host._active_stage_metrics)
            if host._active_stage_metrics
            else host._stage_metrics_snapshot()
        )
        saved_buffer = save_buffer(host.workspace_root, host.buffer.trajectories)
        save_checkpoint(
            host.workspace_root,
            cumulative_trades=host.cumulative_trades,
            ppo_steps=host.ppo_steps,
            training_mode=training_mode,
            stages_passed=host._stages_passed,
            curriculum_stage=curriculum_stage,
            policy_path=str(policy_path or host.final_policy_path),
            stage_metrics=metrics,
            buffer_path=saved_buffer,
            data_manifest=host._data_manifest,
            phase=phase,
            remediation_attempt=host._remediation_attempt,
            stage_pass_receipts=[r.to_dict() for r in host._stage_pass_receipts],
            oos_metrics=oos_metrics,
        )
        host._last_checkpoint_at = time.time()