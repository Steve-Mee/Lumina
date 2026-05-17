"""Regression: Save Settings must not start Birth Phase; start requires explicit gate."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lumina_launcher.core.first_boot import FirstBootManager
from lumina_launcher.services.birth_service import BirthService
from lumina_launcher.ui.tabs import first_boot as fb


@pytest.mark.unit
def test_save_settings_never_calls_start_birth(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(fb.st, "session_state", {})
    manager = FirstBootManager(tmp_path)
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    birth_service = MagicMock(spec=BirthService)
    birth_service.is_running.return_value = False

    fb._persist_first_boot_settings(
        manager,
        training_trades=25_000,
        prefer_real_data_only=True,
        max_real_days=365,
        allow_minimal_synthetic_fallback=False,
        require_real_simulator_data=True,
    )

    birth_service.start_birth.assert_not_called()


@pytest.mark.unit
def test_start_birth_requires_explicit_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    birth_service = MagicMock(spec=BirthService)
    birth_service.is_running.return_value = False
    monkeypatch.setattr(fb.st.session_state, "get", lambda key, default=None: default)
    monkeypatch.setattr(fb, "_explicit_start_requested", lambda: False)

    ok, msg = fb._start_birth_training(
        birth_service=birth_service,
        backend_client=None,
        workspace_root=tmp_path,
        target_trades=25_000,
    )

    assert ok is False
    assert "expliciete" in msg.lower()
    birth_service.start_birth.assert_not_called()


@pytest.mark.unit
def test_start_birth_with_explicit_flag_calls_service(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    birth_service = MagicMock(spec=BirthService)
    birth_service.start_birth.return_value = {"status": "started", "message": "ok"}
    monkeypatch.setattr(fb, "_explicit_start_requested", lambda: True)
    monkeypatch.setattr(fb, "_clear_start_request_flags", lambda: None)

    ok, msg = fb._start_birth_training(
        birth_service=birth_service,
        backend_client=None,
        workspace_root=tmp_path,
        target_trades=25_000,
    )

    assert ok is True
    birth_service.start_birth.assert_called_once()
    call_kwargs = birth_service.start_birth.call_args.kwargs
    assert call_kwargs.get("explicit_user_start") is True


@pytest.mark.unit
def test_birth_service_rejects_without_explicit_user_start(tmp_path: Path) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)

    result = svc.start_birth(target_trades=5000, explicit_user_start=False)

    assert result["status"] == "rejected"
    assert svc._thread is None  # type: ignore[attr-defined]
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_first_boot_tab_save_and_start_have_stable_keys() -> None:
    source = Path(fb.__file__).read_text(encoding="utf-8")
    assert 'key="first_boot_save_settings"' in source or "key=_SAVE_SETTINGS_KEY" in source
    assert 'key="first_boot_start_birth_phase"' in source or "key=_START_BIRTH_KEY" in source
    assert "on_click=_on_save_settings_click" in source
    assert "on_click=_on_start_birth_click" in source
    assert "_persist_first_boot_settings" in source
    assert "first_boot_pending_save" in source.lower() or "_FIRST_BOOT_PENDING_SAVE_KEY" in source
