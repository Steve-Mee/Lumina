from __future__ import annotations

import pytest

from tests.birth.preflight_helpers import patch_holdout_preflight_ok

_ENGINE_SHIM_SKIP_SUFFIXES = (
    "test_meta_controller",
    "test_meta_self_eval",
    "test_stage1_stagnation",
    "test_plateau_escalator",
    "test_stall_remediation",
)


def _skip_birth_engine_shims(request: pytest.FixtureRequest) -> bool:
    if request.node.get_closest_marker("meta_controller") is not None:
        return True
    module_name = getattr(request.module, "__name__", "")
    return module_name.endswith(_ENGINE_SHIM_SKIP_SUFFIXES)


@pytest.fixture(autouse=True)
def _disable_birth_meta_controller_for_unit_tests(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Keep heavy birth engine paths bounded in unit tests."""
    if _skip_birth_engine_shims(request):
        return

    import lumina_core.birth.config as birth_config

    _orig_curriculum = birth_config.BirthCurriculumConfig
    _orig_load = birth_config.load_birth_v2_config

    def _curriculum_with_meta_off(*args, **kwargs):
        kwargs.setdefault("meta_controller_enabled", False)
        kwargs.setdefault("adaptation_enabled", False)
        kwargs.setdefault("wall_behavior", "strict")
        kwargs.setdefault("plateau_detection_enabled", False)
        kwargs.setdefault("stall_remediation_enabled", False)
        return _orig_curriculum(*args, **kwargs)

    def _load_without_meta(workspace_root=None):
        cfg = _orig_load(workspace_root)
        cfg.curriculum.meta_controller_enabled = False
        cfg.curriculum.adaptation_enabled = False
        cfg.curriculum.wall_behavior = "strict"
        cfg.curriculum.plateau_detection_enabled = False
        cfg.curriculum.stall_remediation_enabled = False
        return cfg

    monkeypatch.setattr(birth_config, "BirthCurriculumConfig", _curriculum_with_meta_off)
    monkeypatch.setattr(birth_config, "load_birth_v2_config", _load_without_meta)
    monkeypatch.setattr(
        "lumina_core.birth.engine.BirthCurriculumConfig",
        _curriculum_with_meta_off,
    )
    monkeypatch.setattr(
        "lumina_core.birth.engine.load_birth_v2_config",
        _load_without_meta,
    )
    # Wave B PR-B1: lifecycle mixin binds load_birth_v2_config at import time.
    monkeypatch.setattr(
        "lumina_core.birth.engine_lifecycle.load_birth_v2_config",
        _load_without_meta,
    )
    monkeypatch.setattr(
        "lumina_core.birth.engine_trajectory.BirthCurriculumConfig",
        _curriculum_with_meta_off,
    )
    monkeypatch.setattr(
        "lumina_core.birth.buffer_persist.save_buffer",
        lambda *_args, **_kwargs: "",
    )
    monkeypatch.setattr(
        "lumina_core.birth.checkpoint_coordinator.save_buffer",
        lambda *_args, **_kwargs: "",
    )
    monkeypatch.setattr(
        "lumina_core.birth.data_pipeline.enrich_ticks_for_sim",
        lambda ticks, **_kwargs: ticks,
    )
    monkeypatch.setattr(
        "lumina_core.birth.data_expansion.enrich_ticks_for_sim",
        lambda ticks, **_kwargs: ticks,
    )

    from lumina_core.birth.sim_runner import SimRolloutResult

    def _default_rollout(**_kwargs: object) -> SimRolloutResult:
        return SimRolloutResult(
            trades=10,
            wins=5,
            hold_signals=0,
            total_signals=10,
            total_pnl=5.0,
            trajectories=[
                {"reward": 1.0, "observation": {"vector": [5000.0 + i * 0.1]}} for i in range(100)
            ],
            pnl_series=[1.0] * 10,
            constitution_violations=0,
            regimes_seen={"TREND_UP", "TREND_DOWN", "NEUTRAL"},
            partial_complete=True,
            rollout_steps=200,
        )

    for rollout_site in (
        "lumina_core.birth.stage_training_loop.run_policy_rollout",
        "lumina_core.birth.curriculum_stage_handler.run_policy_rollout",
        "lumina_core.birth.sim_runner.run_policy_rollout",
        "lumina_core.birth.certificate_pipeline.run_policy_rollout",
        "lumina_core.birth.certificate_remediation.run_policy_rollout",
        "lumina_core.birth.certificate_evaluator.run_policy_rollout",
    ):
        monkeypatch.setattr(rollout_site, _default_rollout)


def _requests_no_preflight_bypass(request: pytest.FixtureRequest) -> bool:
    if request.node.get_closest_marker("no_preflight_bypass") is not None:
        return True
    module = request.module
    module_markers = getattr(module, "pytestmark", ())
    if not isinstance(module_markers, (list, tuple)):
        module_markers = (module_markers,)
    return any(getattr(mark, "name", "") == "no_preflight_bypass" for mark in module_markers)


@pytest.fixture(autouse=True)
def _bypass_holdout_preflight_for_engine_integration(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    module_name = getattr(request.module, "__name__", "")
    if module_name.endswith("test_preflight"):
        return
    if _requests_no_preflight_bypass(request):
        return
    patch_holdout_preflight_ok(monkeypatch)


@pytest.fixture
def birth_event_bus():
    from lumina_core.agent_orchestration.event_bus import EventBus

    return EventBus()


@pytest.fixture
def birth_bus_client(birth_event_bus):
    from lumina_core.birth.birth_bus_client import BirthBusClient
    from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig

    return BirthBusClient(
        birth_event_bus,
        BirthCurriculumConfig(),
        BirthRewardConfig(),
    )
