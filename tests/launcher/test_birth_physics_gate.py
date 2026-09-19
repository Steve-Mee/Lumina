"""Launcher T=0 physics gate: missing SB3 never returns started."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lumina_core.birth.physics_preflight import PHYSICS_UNAVAILABLE, BirthPhysicsProbe

pytestmark = pytest.mark.unit


def test_start_rejects_when_physics_probe_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from lumina_launcher.services import birth_runner_start as start_mod

    (tmp_path / "config.yaml").write_text(
        "broker:\n  live_provider: ninjatrader\nfirst_boot:\n  training_trades: 25000\n  max_real_days: 365\n",
        encoding="utf-8",
    )
    (tmp_path / "state").mkdir(parents=True)

    def _fail_physics(
        svc: object,
        *,
        target_trades: int,
        start_time: float,
        training_mode: str,
        probe: BirthPhysicsProbe | None = None,
    ) -> dict[str, object]:
        del svc, start_time, probe
        return {
            "status": PHYSICS_UNAVAILABLE,
            "message": "Leermotor ontbreekt (stable_baselines3).",
            "retryable": False,
            "target_trades": int(target_trades),
            "practice_mode": training_mode == "practice",
            "recommended_actions": ["install_birth_physics_stack", "retry_birth"],
        }

    monkeypatch.setattr(
        "lumina_core.birth.physics_preflight.enforce_birth_physics",
        _fail_physics,
    )
    monkeypatch.setattr(start_mod, "preflight_historical_data", lambda *_a, **_k: (True, ""))
    monkeypatch.setattr(start_mod, "launcher_setup_status", lambda _svc: {"ok": True})
    monkeypatch.setattr(start_mod, "adaptive_intelligence_status", lambda _svc: {"tier": "light"})

    thread_started = {"n": 0}

    class _FakeThread:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def start(self) -> None:
            thread_started["n"] += 1

    monkeypatch.setattr(start_mod.threading, "Thread", _FakeThread)

    svc = SimpleNamespace(
        workspace_root=tmp_path,
        is_running=lambda: False,
        is_completed=lambda: False,
        pause_flag_path=tmp_path / "state" / "pause.flag",
        _stop_requested=MagicMock(),
        _result=None,
        _error=None,
        _start_time=None,
        _stalled_auto_resume_attempted=False,
        _thread=None,
    )
    svc._stop_requested.clear = MagicMock()

    result = start_mod.start_birth(
        svc,
        target_trades=25000,
        force=True,
        practice_mode=False,
        explicit_user_start=True,
        continue_training=False,
        reuse_data=False,
    )
    assert result["status"] == PHYSICS_UNAVAILABLE
    assert result.get("retryable") is False
    assert thread_started["n"] == 0
    assert svc._thread is None


def test_start_birth_source_gates_physics_before_thread() -> None:
    source = Path("lumina_launcher/services/birth_runner_start.py").read_text(encoding="utf-8")
    assert "enforce_birth_physics" in source
    assert source.index("enforce_birth_physics") < source.index('name="LuminaBirthThread"')
    assert source.index("enforce_birth_physics") < source.index("History preflight OK")
    assert "wipe_and_retry" not in source[source.index("enforce_birth_physics") : source.index("skip_history_preflight")]


def test_orchestrator_source_gates_physics_before_bootstrap() -> None:
    source = Path("lumina_core/birth/birth_phase_orchestrator.py").read_text(encoding="utf-8")
    assert "reject_birth_if_physics_missing" in source
    assert source.index("reject_birth_if_physics_missing") < source.index("bootstrap_birth_phase(")


def test_start_practice_also_requires_physics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from lumina_launcher.services import birth_runner_start as start_mod

    (tmp_path / "config.yaml").write_text("first_boot:\n  training_trades: 1000\n", encoding="utf-8")
    (tmp_path / "state").mkdir(parents=True)

    seen: dict[str, str] = {}

    def _fail_physics(
        svc: object,
        *,
        target_trades: int,
        start_time: float,
        training_mode: str,
        probe: BirthPhysicsProbe | None = None,
    ) -> dict[str, object]:
        del svc, target_trades, start_time, probe
        seen["mode"] = training_mode
        return {
            "status": PHYSICS_UNAVAILABLE,
            "message": "Leermotor ontbreekt (stable_baselines3).",
            "retryable": False,
        }

    monkeypatch.setattr(
        "lumina_core.birth.physics_preflight.enforce_birth_physics",
        _fail_physics,
    )
    svc = SimpleNamespace(
        workspace_root=tmp_path,
        is_running=lambda: False,
        is_completed=lambda: False,
        pause_flag_path=tmp_path / "state" / "pause.flag",
        _stop_requested=MagicMock(),
        _result=None,
        _error=None,
        _start_time=None,
        _stalled_auto_resume_attempted=False,
        _thread=None,
    )
    svc._stop_requested.clear = MagicMock()
    result = start_mod.start_birth(
        svc,
        target_trades=1000,
        force=False,
        practice_mode=True,
        explicit_user_start=True,
    )
    assert result["status"] == PHYSICS_UNAVAILABLE
    assert seen["mode"] == "practice"


def test_progress_payload_roundtrip_not_json_broken() -> None:
    payload = {
        "status": PHYSICS_UNAVAILABLE,
        "retryable": False,
        "recommended_actions": ["install_birth_physics_stack", "retry_birth"],
    }
    encoded = json.dumps(payload)
    assert "wipe" not in encoded
