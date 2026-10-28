from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.birth.engine import BirthPhaseEngineV2
from lumina_core.hardware_intelligence import HARDWARE_PROFILES


def _engine(tmp_path: Path) -> BirthPhaseEngineV2:
    return BirthPhaseEngineV2(
        runtime=SimpleNamespace(),
        ppo_trainer=SimpleNamespace(),
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )


@pytest.mark.unit
def test_apply_hardware_profile_cpu_efficient(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine._hardware_profile_payload = {
        "profile": "cpu_efficient",
        "tuning": HARDWARE_PROFILES["cpu_efficient"].to_dict(),
        "detection": {"recommended_profile": "cpu_efficient"},
    }

    engine._apply_hardware_profile()
    cur = engine.birth_config.curriculum

    assert cur.rollout_chunk_trades == 50
    assert cur.curriculum_ppo_timesteps == 1_500
    assert cur.max_escalation_level == 2
    assert cur.oracle_scan_stride == 10
    assert engine.birth_config.ppo_update_timesteps == 10_000


@pytest.mark.unit
def test_apply_hardware_profile_gpu_accelerated(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine._hardware_profile_payload = {
        "profile": "gpu_accelerated",
        "tuning": HARDWARE_PROFILES["gpu_accelerated"].to_dict(),
        "detection": {"recommended_profile": "gpu_accelerated"},
    }

    engine._apply_hardware_profile()
    cur = engine.birth_config.curriculum

    assert cur.rollout_chunk_trades == 250
    assert cur.curriculum_ppo_timesteps == 3_000
    assert cur.max_escalation_level == 5
    assert cur.oracle_scan_stride == 5
    assert engine.birth_config.ppo_update_timesteps == 25_000


@pytest.mark.unit
def test_apply_hardware_profile_leaves_certificate_thresholds_unchanged(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    before = engine.birth_config.certificate_thresholds.model_dump()
    engine._hardware_profile_payload = {
        "profile": "cpu_efficient",
        "tuning": HARDWARE_PROFILES["cpu_efficient"].to_dict(),
        "detection": {"recommended_profile": "cpu_efficient"},
    }

    engine._apply_hardware_profile()

    assert engine.birth_config.certificate_thresholds.model_dump() == before


@pytest.mark.unit
def test_run_birth_phase_loads_and_applies_hardware_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _engine(tmp_path)
    calls: list[str] = []
    payload = {
        "profile": "cpu_efficient",
        "tuning": HARDWARE_PROFILES["cpu_efficient"].to_dict(),
        "detection": {"recommended_profile": "cpu_efficient"},
    }

    monkeypatch.setattr(
        "lumina_core.birth.birth_phase_orchestrator.ensure_first_boot_hardware_profile",
        lambda workspace_root: calls.append("ensure") or payload,
    )
    monkeypatch.setattr(
        engine,
        "_apply_hardware_profile",
        lambda: calls.append("apply"),
    )

    def _stop_after_hardware(*_args: object, **_kwargs: object) -> dict[str, str]:
        raise RuntimeError("stop_after_hardware")

    monkeypatch.setattr(
        "lumina_core.birth.birth_phase_orchestrator.read_birth_progress",
        _stop_after_hardware,
    )

    with pytest.raises(RuntimeError, match="stop_after_hardware"):
        engine.run_birth_phase(force=True)

    assert calls == ["ensure", "apply"]
