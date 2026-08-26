"""M5: data_pipeline + plateau_evolution_loop modularization LOC guards."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.birth.data_pipeline import (
    BirthDataPipeline,
    generate_synthetic_ticks,
    train_hash,
)
from lumina_core.birth.plateau_evolution_handler import PlateauEvolutionMixin

_BIRTH = Path(__file__).resolve().parents[2] / "lumina_core" / "birth"
_LOC_LIMIT = 500

_DATA_MODS = [
    "data_pipeline.py",
    "data_pipeline_types.py",
    "data_pipeline_resume.py",
    "data_pipeline_load.py",
    "data_pipeline_enrich.py",
]
_PLATEAU_MODS = [
    "plateau_evolution_loop.py",
    "plateau_evolution_detect.py",
    "plateau_evolution_advance.py",
    "plateau_evolution_actions.py",
    "plateau_evolution_handler.py",
]
_WAVE2_MODS = [
    "perfect_birth_gate.py",
    "perfect_birth_types.py",
    "perfect_birth_gather.py",
    "wall_adaptation_handler.py",
    "wall_adaptation_triggers.py",
    "wall_adaptation_recovery.py",
    "stage_loop_progress_write.py",
    "stage_loop_progress_write_enrich.py",
    "stage_loop_progress_write_starship.py",
]
_WAVE3_MODS = [
    "config_coercion_curriculum.py",
    "config_coercion_curriculum_core.py",
    "config_coercion_curriculum_mid.py",
    "config_coercion_curriculum_tail.py",
    "engine_lifecycle.py",
    "engine_lifecycle_core.py",
    "engine_lifecycle_ops.py",
    "engine_lifecycle_certificate.py",
    "engine_lifecycle_event.py",
    "stage_loop_session_phase_prepare.py",
    "stage_loop_session_phase_prepare_restore.py",
    "stage_loop_session_phase_prepare_plateau.py",
    "stage_loop_session_phase_prepare_init.py",
    "stage_loop_rollout_pre.py",
    "stage_loop_rollout_pre_caps.py",
    "stage_loop_rollout_types.py",
]
_WAVE3_PHASE2 = [
    "phase2_autonomy/orchestrator.py",
    "phase2_autonomy/orchestrator_wall.py",
    "phase2_autonomy/orchestrator_param.py",
    "phase2_autonomy/orchestrator_instance.py",
    "phase2_autonomy/orchestrator_publish.py",
]


def _loc(path: Path) -> int:
    return sum(1 for _ in path.open(encoding="utf-8"))


@pytest.mark.unit
def test_data_pipeline_modules_under_loc_bar() -> None:
    for name in _DATA_MODS:
        path = _BIRTH / name
        assert path.is_file(), name
        n = _loc(path)
        assert n <= _LOC_LIMIT, f"{name} LOC {n} > {_LOC_LIMIT}"


@pytest.mark.unit
def test_plateau_evolution_modules_under_loc_bar() -> None:
    for name in _PLATEAU_MODS:
        path = _BIRTH / name
        assert path.is_file(), name
        n = _loc(path)
        assert n <= _LOC_LIMIT, f"{name} LOC {n} > {_LOC_LIMIT}"


@pytest.mark.unit
def test_m5_wave2_modules_under_loc_bar() -> None:
    for name in _WAVE2_MODS:
        path = _BIRTH / name
        assert path.is_file(), name
        n = _loc(path)
        limit = 700 if name == "stage_loop_progress_write_enrich.py" else _LOC_LIMIT
        assert n <= limit, f"{name} LOC {n} > {limit}"


@pytest.mark.unit
def test_m5_wave3_modules_under_loc_bar() -> None:
    for name in _WAVE3_MODS + _WAVE3_PHASE2:
        path = _BIRTH / name
        assert path.is_file(), name
        n = _loc(path)
        assert n <= _LOC_LIMIT, f"{name} LOC {n} > {_LOC_LIMIT}"


@pytest.mark.unit
def test_plateau_mixin_mro_includes_m5_branches() -> None:
    names = {c.__name__ for c in PlateauEvolutionMixin.__mro__}
    assert "PlateauEvolutionDetectMixin" in names
    assert "PlateauEvolutionAdvanceMixin" in names
    assert "PlateauEvolutionLoopMixin" in names
    assert "PlateauEvolutionActionsMixin" in names
    assert hasattr(PlateauEvolutionMixin, "_maybe_detect_plateau")
    assert hasattr(PlateauEvolutionMixin, "_try_plateau_evolution")
    assert hasattr(PlateauEvolutionMixin, "_finalize_plateau_evolution_step")


@pytest.mark.unit
def test_progress_write_and_wall_mro() -> None:
    from lumina_core.birth.stage_loop_progress_write import StageLoopProgressWriteMixin
    from lumina_core.birth.wall_adaptation_handler import WallAdaptationHandler

    pnames = {c.__name__ for c in StageLoopProgressWriteMixin.__mro__}
    assert "StageLoopProgressWriteEnrichMixin" in pnames
    assert hasattr(StageLoopProgressWriteMixin, "_enrich_progress_scorecard")
    wnames = {c.__name__ for c in WallAdaptationHandler.__mro__}
    assert "WallAdaptationTriggerMixin" in wnames
    assert "WallAdaptationRecoveryMixin" in wnames


@pytest.mark.unit
def test_wave3_mro_and_curriculum_merge() -> None:
    from lumina_core.birth.config_coercion_curriculum import build_curriculum_config
    from lumina_core.birth.engine_lifecycle import EngineLifecycleMixin
    from lumina_core.birth.phase2_autonomy.orchestrator import Phase2AutonomyOrchestrator
    from lumina_core.birth.stage_loop_session_phase_prepare import SessionPhasePrepareMixin

    cfg = build_curriculum_config({"stage1_trend_trades": 1111, "phoenix_max_cycles": 9})
    assert cfg.stage1_trend_trades == 1111
    assert cfg.phoenix_max_cycles == 9
    assert hasattr(EngineLifecycleMixin, "_emit_birth_progress")
    assert hasattr(EngineLifecycleMixin, "_complete_certified_birth")
    names = {c.__name__ for c in SessionPhasePrepareMixin.__mro__}
    assert "SessionPhasePrepareRestoreMixin" in names
    assert "SessionPhasePreparePlateauMixin" in names
    assert "SessionPhasePrepareInitMixin" in names
    onames = {c.__name__ for c in Phase2AutonomyOrchestrator.__mro__}
    assert "Phase2WallEvalMixin" in onames
    assert hasattr(Phase2AutonomyOrchestrator, "evaluate_dynamic_wall")


@pytest.mark.unit
def test_data_pipeline_public_api_stable() -> None:
    ticks = generate_synthetic_ticks(10, start_price=100.0)
    assert len(ticks) == 10
    assert train_hash(ticks)
    assert train_hash([]) == ""
    # Class is constructible with a simple host stub
    class _Host:
        workspace_root = Path(".")
        birth_config = type("C", (), {"trade_budget_cap": 1000})()
        market_data_service = None
        runtime = None
        birth_start_time = 0.0
        cumulative_trades = 0
        ppo_steps = 0
        _data_manifest = {}
        _last_raw_ticks_hash = ""
        _real_data_pct = 0.0

        def _stop_requested(self) -> bool:
            return False

        def _emit_birth_progress(self, **kwargs):  # noqa: ANN003
            del kwargs

        def _notify_history_unavailable(self, detail: str) -> None:
            del detail

    pipe = BirthDataPipeline(_Host())  # type: ignore[arg-type]
    assert hasattr(pipe, "prepare_ticks_and_split")
