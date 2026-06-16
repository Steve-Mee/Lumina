from __future__ import annotations

import pytest

from tests.birth.preflight_helpers import patch_holdout_preflight_ok


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
