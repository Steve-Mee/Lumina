from __future__ import annotations

import pytest

from tests.birth.preflight_helpers import patch_holdout_preflight_ok


def _requests_meta_controller_tests(request: pytest.FixtureRequest) -> bool:
    if request.node.get_closest_marker("meta_controller") is not None:
        return True
    module_name = getattr(request.module, "__name__", "")
    return module_name.endswith(("test_meta_controller", "test_meta_self_eval"))


@pytest.fixture(autouse=True)
def _disable_birth_meta_controller_for_unit_tests(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Meta-controller self-eval loops exceed the 15s unit-test timeout budget."""
    if _requests_meta_controller_tests(request):
        return

    import lumina_core.birth.config as birth_config

    _orig_curriculum = birth_config.BirthCurriculumConfig
    _orig_load = birth_config.load_birth_v2_config

    def _curriculum_with_meta_off(*args, **kwargs):
        kwargs.setdefault("meta_controller_enabled", False)
        kwargs.setdefault("adaptation_enabled", False)
        kwargs.setdefault("wall_behavior", "strict")
        return _orig_curriculum(*args, **kwargs)

    def _load_without_meta(workspace_root=None):
        cfg = _orig_load(workspace_root)
        cfg.curriculum.meta_controller_enabled = False
        cfg.curriculum.adaptation_enabled = False
        cfg.curriculum.wall_behavior = "strict"
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
    monkeypatch.setattr(
        "lumina_core.birth.buffer_persist.save_buffer",
        lambda *_args, **_kwargs: "",
    )
    monkeypatch.setattr(
        "lumina_core.birth.engine.save_buffer",
        lambda *_args, **_kwargs: "",
    )
    monkeypatch.setattr(
        "lumina_core.birth.engine.enrich_ticks_for_sim",
        lambda ticks: ticks,
    )
    monkeypatch.setattr(
        "lumina_core.birth.data_expansion.enrich_ticks_for_sim",
        lambda ticks: ticks,
    )


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
