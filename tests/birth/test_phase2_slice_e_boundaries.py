"""Slice E: package boundaries + no stage_loop god-surface for Phase 2."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.phase2_autonomy.handler_hooks import (
    cfg_with_wall_thresholds,
    merge_instance_spawn_flags,
    phase2_wall_closed_loop,
)


@pytest.mark.unit
def test_stage_loop_modules_do_not_import_phase2() -> None:
    """Phase 2 must not leak into stage_loop (handler-only wiring)."""
    root = Path("lumina_core/birth")
    offenders: list[str] = []
    for path in root.glob("stage_loop*.py"):
        text = path.read_text(encoding="utf-8")
        if "phase2_autonomy" in text or "Phase2Autonomy" in text:
            offenders.append(path.name)
    assert offenders == [], f"stage_loop must not import phase2: {offenders}"


@pytest.mark.unit
def test_wall_handler_does_not_inline_closed_loop_body() -> None:
    """Closed-loop implementation lives in handler_hooks (thin handler)."""
    text = Path("lumina_core/birth/wall_adaptation_handler.py").read_text(encoding="utf-8")
    assert "def _phase2_wall_closed_loop" not in text
    assert "def _phase2_recovery_closed_loop" not in text
    assert "handler_hooks" in text


@pytest.mark.unit
def test_cfg_with_wall_thresholds_pure() -> None:
    cfg = BirthCurriculumConfig(
        certified_stage_stall_wall_sec=600,
        stage1_winrate_stagnation_rollouts=2,
        stage2_hold_stagnation_rollouts=2,
    )
    out = cfg_with_wall_thresholds(
        cfg,
        {
            "effective_stall_wall_sec": 900,
            "effective_winrate_stagnation_rollouts": 4,
            "effective_hold_stagnation_rollouts": 3,
        },
    )
    assert out.certified_stage_stall_wall_sec == 900
    assert cfg.certified_stage_stall_wall_sec == 600  # original untouched


@pytest.mark.unit
def test_inactive_orch_wall_hook_is_noop() -> None:
    cfg = BirthCurriculumConfig()
    meta, eval_cfg = phase2_wall_closed_loop(
        None,
        cfg=cfg,
        registry=None,
        correlation_id="x",
        stage_name="STAGE1_TREND",
        ctx={},
    )
    assert meta is None
    assert eval_cfg is cfg


@pytest.mark.unit
def test_merge_instance_spawn_flags() -> None:
    plateau, phoenix = merge_instance_spawn_flags(
        plan_spawn_plateau=False,
        plan_spawn_phoenix=False,
        phase2_extra={
            "instance": {
                "applied": True,
                "apply_payload": {"spawn_plateau": True, "spawn_phoenix_reset": False},
            }
        },
    )
    assert plateau is True
    assert phoenix is False
