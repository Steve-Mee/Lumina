"""Unit tests for birth checkpoint_coordinator module."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from lumina_core.birth.checkpoint import load_checkpoint_state
from lumina_core.birth.checkpoint_coordinator import BirthCheckpointCoordinator


@dataclass
class _FakeBuffer:
    trajectories: list[dict[str, Any]] = field(default_factory=list)

    def add(self, traj: dict[str, Any]) -> None:
        self.trajectories.append(traj)


@dataclass
class _FakeHost:
    workspace_root: Path
    cumulative_trades: int = 5
    ppo_steps: int = 100
    _stages_passed: list[str] = field(default_factory=lambda: ["stage1"])
    _stage_pass_receipts: list[Any] = field(default_factory=list)
    _active_stage_metrics: dict[str, Any] = field(default_factory=dict)
    _data_manifest: dict[str, Any] = field(default_factory=dict)
    _remediation_attempt: int = 0
    final_policy_path: Path = field(default_factory=lambda: Path("policy.zip"))
    _last_checkpoint_at: float = 0.0
    buffer: _FakeBuffer = field(default_factory=_FakeBuffer)

    def _stage_metrics_snapshot(self, **kwargs: Any) -> dict[str, Any]:
        return {"stage_trades": 1, **kwargs}


@pytest.mark.unit
def test_persist_checkpoint_writes_state(tmp_path: Path) -> None:
    host = _FakeHost(workspace_root=tmp_path)
    BirthCheckpointCoordinator(host).persist_checkpoint(
        training_mode="certified",
        curriculum_stage="stage2",
        policy_path=str(tmp_path / "policy.zip"),
        phase="curriculum_learning",
    )
    state = load_checkpoint_state(tmp_path)
    assert state.get("cumulative_trades") == 5
    assert state.get("ppo_steps") == 100
    assert state.get("curriculum_stage") == "stage2"
    assert host._last_checkpoint_at > 0