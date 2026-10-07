"""Long rollouts must yield the interpreter so the desktop API stays reachable."""

from __future__ import annotations

from lumina_core.birth.control_plane_yield import (
    _CONTROL_PLANE_YIELD_STEPS,
    release_control_plane,
)


def test_release_control_plane_sleeps_only_on_the_interval(monkeypatch) -> None:
    calls: list[float] = []
    monkeypatch.setattr(
        "lumina_core.birth.control_plane_yield.time.sleep",
        lambda seconds: calls.append(seconds),
    )
    release_control_plane(0)
    release_control_plane(_CONTROL_PLANE_YIELD_STEPS - 1)
    assert calls == []
    release_control_plane(_CONTROL_PLANE_YIELD_STEPS)
    release_control_plane(_CONTROL_PLANE_YIELD_STEPS * 2)
    assert calls == [0, 0]
