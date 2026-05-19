from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lumina_launcher.core.setup_config import SetupConfig
from lumina_launcher.core.setup_gate import resolve_launcher_setup_state


@pytest.mark.unit
def test_resolve_launcher_setup_state_needs_smart_setup() -> None:
    setup = MagicMock()
    setup.is_setup_complete.return_value = False
    smart = MagicMock()
    smart.is_intelligence_stack_ready.return_value = False

    state = resolve_launcher_setup_state(
        Path("."),
        setup_service=setup,
        smart_setup_service=smart,
    )
    assert state.setup_complete is False
    assert state.intelligence_stack_ready is False
    assert state.needs_smart_setup is True
    assert state.needs_guided_setup is False
    assert state.launcher_ready is False


@pytest.mark.unit
def test_resolve_launcher_setup_state_needs_guided_setup() -> None:
    setup = MagicMock()
    setup.is_setup_complete.return_value = False
    smart = MagicMock()
    smart.is_intelligence_stack_ready.return_value = True

    state = resolve_launcher_setup_state(Path("."), setup_service=setup, smart_setup_service=smart)
    assert state.needs_smart_setup is False
    assert state.needs_guided_setup is True
    assert state.launcher_ready is False


@pytest.mark.unit
def test_resolve_launcher_setup_state_launcher_ready() -> None:
    setup = MagicMock()
    setup.is_setup_complete.return_value = True
    smart = MagicMock()
    smart.is_intelligence_stack_ready.return_value = True

    state = resolve_launcher_setup_state(Path("."), setup_service=setup, smart_setup_service=smart)
    assert state.setup_complete is True
    assert state.needs_smart_setup is False
    assert state.needs_guided_setup is False
    assert state.launcher_ready is True


@pytest.mark.unit
def test_resolve_launcher_setup_state_classic_skips_smart_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = MagicMock()
    setup.is_setup_complete.return_value = False
    smart = MagicMock()
    smart.is_intelligence_stack_ready.return_value = False

    monkeypatch.setattr(
        "lumina_launcher.core.setup_gate.SetupConfig.from_workspace",
        lambda _root: SetupConfig(mode="classic"),
    )

    state = resolve_launcher_setup_state(Path("."), setup_service=setup, smart_setup_service=smart)
    assert state.needs_smart_setup is False
    assert state.needs_guided_setup is True
