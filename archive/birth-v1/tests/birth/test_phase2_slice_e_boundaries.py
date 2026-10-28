"""Slice E / Track C: package boundaries, single wall engine, no stage_loop spine."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.phase2_autonomy.contracts import Phase2InstanceAdaptProposal
from lumina_core.birth.phase2_autonomy.handler_hooks import (
    cfg_with_wall_thresholds,
    merge_instance_spawn_flags,
    phase2_wall_closed_loop,
)
from lumina_core.birth.phase2_autonomy.instance_adapter import (
    materialize_instance_adapt_payload,
    validate_instance_proposal,
)
from lumina_core.birth.starship_swarm_gates import (
    CANONICAL_SWARM_NO_LIFT_REASON,
    LEGACY_SWARM_NO_LIFT_REASON,
    dual_write_tournament_lift_keys,
    normalize_swarm_attention_reason,
    prefer_tournament_progress_keys,
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
def test_closed_loop_lives_in_handler_hooks_not_handler_god() -> None:
    """Closed-loop implementation lives in handler_hooks; mixins only import hooks."""
    handler = Path("lumina_core/birth/wall_adaptation_handler.py").read_text(encoding="utf-8")
    assert "def phase2_wall_closed_loop" not in handler
    assert "def phase2_recovery_closed_loop" not in handler
    assert "evaluate_dynamic_wall" not in handler

    triggers = Path("lumina_core/birth/wall_adaptation_triggers.py").read_text(encoding="utf-8")
    recovery = Path("lumina_core/birth/wall_adaptation_recovery.py").read_text(encoding="utf-8")
    assert "handler_hooks" in triggers
    assert "handler_hooks" in recovery
    # Single wall engine: still evaluate_wall_trigger only (no second ML wall).
    assert "evaluate_wall_trigger" in triggers
    assert "ml_wall" not in triggers.lower()
    assert "second_wall" not in triggers.lower()


@pytest.mark.unit
def test_phase2_package_has_no_stage_loop_imports() -> None:
    """Code imports of stage_loop are forbidden; docstrings may mention the boundary."""
    root = Path("lumina_core/birth/phase2_autonomy")
    offenders: list[str] = []
    for path in root.glob("*.py"):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'"):
                continue
            if "import" in stripped and "stage_loop" in stripped:
                offenders.append(f"{path.name}:{i}")
            if "from lumina_core.birth.stage_loop" in stripped:
                offenders.append(f"{path.name}:{i}")
    assert offenders == [], f"phase2 must not import stage_loop: {offenders}"


@pytest.mark.unit
def test_instance_validation_ssot_rejects_os_and_broker() -> None:
    bad = Phase2InstanceAdaptProposal(action="os_spawn_broker", risk_touching=False)
    viol = validate_instance_proposal(bad)
    assert viol
    assert any("not_allowed" in v or "forbidden" in v for v in viol)

    ok = Phase2InstanceAdaptProposal(
        action="spawn_plateau",
        spawn_plateau=True,
        refresh_handler_cfg=True,
    )
    assert validate_instance_proposal(ok) == []
    payload = materialize_instance_adapt_payload(ok)
    assert payload["os_spawn"] is False
    assert payload["process_restart_required"] is False


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


@pytest.mark.unit
def test_tournament_vanity_naming_normalized() -> None:
    assert (
        normalize_swarm_attention_reason(LEGACY_SWARM_NO_LIFT_REASON)
        == CANONICAL_SWARM_NO_LIFT_REASON
    )
    payload: dict = {}
    dual_write_tournament_lift_keys(payload, lift_ok=True, at_start=0.42)
    assert payload["swarm_tournament_lift_ok"] is True
    assert payload["swarm_edgescore_lift_ok"] is True  # legacy alias only
    assert payload["swarm_tournament_at_start"] == 0.42

    preferred = prefer_tournament_progress_keys(
        {
            "swarm_edgescore_lift_ok": True,
            "swarm_edgescore_at_start": 0.5,
            "attention_reason_code": LEGACY_SWARM_NO_LIFT_REASON,
        }
    )
    assert preferred["swarm_tournament_lift_ok"] is True
    assert preferred["swarm_tournament_at_start"] == 0.5
    assert preferred["attention_reason_code"] == CANONICAL_SWARM_NO_LIFT_REASON
