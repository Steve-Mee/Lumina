from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.birth.birth_handler_registry import BirthHandlerRegistry
from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig
from lumina_core.config.atomic_yaml import atomic_write_yaml, read_yaml_stable
from lumina_core.config_loader import ConfigLoader
from lumina_core.container import ApplicationContainer, ConfigService
from lumina_core.runtime_config_reloader import (
    RuntimeConfigReloader,
    _immutable_field_changes,
)


def _valid_base_cfg() -> dict[str, Any]:
    return {
        "mode": "sim",
        "broker": {"backend": "live"},
        "sim": {"kelly_fraction": 1.0, "max_total_open_risk": 3000.0},
        "real": {"kelly_fraction": 0.25, "max_total_open_risk": 150.0},
        "runtime_config": {"hot_reload": {"enabled": True, "debounce_ms": 50}},
    }


def _write_cfg(tmp_path: Path, payload: dict[str, Any]) -> Path:
    path = tmp_path / "config.yaml"
    atomic_write_yaml(path, payload)
    return path


@dataclass
class _LiveConfigStub:
    trade_mode: str = "sim"
    broker_backend: str = "live"
    instrument: str = "MES JUN26"
    swarm_symbols: list[str] = field(default_factory=lambda: ["MES JUN26"])


def _minimal_reload_container(*, config: Any) -> ApplicationContainer:
    container = object.__new__(ApplicationContainer)
    container.config = config
    container.engine = MagicMock()
    container.engine.config = config
    container.config_service = ConfigService()
    container.logger = MagicMock()
    container.event_bus = EventBus()
    container._birth_reload_host = None
    container._config_reloader = None
    return container


@pytest.mark.unit
def test_read_yaml_stable_waits_for_tmp_to_clear(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("mode: sim\nbroker:\n  backend: live\n", encoding="utf-8")
    tmp_file = tmp_path / "config.yaml.tmp"
    tmp_file.write_text("mode: real\n", encoding="utf-8")

    result = read_yaml_stable(cfg_path, settle_ms=20, max_attempts=2)
    assert result == {}


@pytest.mark.unit
def test_atomic_write_yaml_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    payload = _valid_base_cfg()
    atomic_write_yaml(path, payload)
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert loaded["mode"] == "sim"
    assert not (tmp_path / "config.yaml.tmp").exists()


@pytest.mark.unit
def test_immutable_field_changes_detects_trade_mode() -> None:
    live = _LiveConfigStub(trade_mode="sim")
    cfg = {"mode": "real", "broker": {"backend": "live"}}
    assert "trade_mode" in _immutable_field_changes(cfg, live)


@pytest.mark.unit
def test_immutable_field_changes_ignores_absent_keys() -> None:
    live = _LiveConfigStub()
    cfg = {"sim": {"kelly_fraction": 0.5}}
    assert _immutable_field_changes(cfg, live) == []


@pytest.mark.unit
def test_apply_config_reload_rejects_immutable_change(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_cfg(tmp_path, _valid_base_cfg())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LUMINA_CONFIG", str(tmp_path / "config.yaml"))
    monkeypatch.setenv("LUMINA_MODE", "sim")
    monkeypatch.setenv("TRADE_MODE", "sim")
    monkeypatch.setenv("BROKER_BACKEND", "live")
    ConfigLoader.invalidate()

    container = _minimal_reload_container(config=_LiveConfigStub())

    mutated = _valid_base_cfg()
    mutated["instrument"] = "NQ JUN26"
    atomic_write_yaml(tmp_path / "config.yaml", mutated)

    result = container.apply_config_reload(source="test")
    assert result.applied is False
    assert "instrument" in result.immutable_fields


@pytest.mark.unit
def test_apply_config_reload_applies_safe_sim_overlay(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_cfg(tmp_path, _valid_base_cfg())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LUMINA_CONFIG", str(tmp_path / "config.yaml"))
    monkeypatch.setenv("LUMINA_MODE", "sim")
    monkeypatch.setenv("TRADE_MODE", "sim")
    monkeypatch.setenv("BROKER_BACKEND", "live")
    ConfigLoader.invalidate()

    prior = ConfigService().load()
    container = _minimal_reload_container(config=prior)

    mutated = _valid_base_cfg()
    mutated["sim"] = {**mutated["sim"], "kelly_fraction": 0.42}
    atomic_write_yaml(tmp_path / "config.yaml", mutated)

    result = container.apply_config_reload(source="test")
    assert result.applied is True
    ConfigLoader.invalidate()
    assert ConfigLoader.section("sim", "kelly_fraction") == pytest.approx(0.42)


@pytest.mark.unit
def test_birth_handler_registry_sync_birth_cfg() -> None:
    bus = EventBus()
    curriculum = BirthCurriculumConfig(stage1_trend_trades=1111)
    reward = BirthRewardConfig(expectancy_coeff=0.33)
    registry = BirthHandlerRegistry(bus, BirthCurriculumConfig(), BirthRewardConfig())
    registry.sync_birth_cfg(curriculum, reward)
    assert registry.curriculum_cfg.stage1_trend_trades == 1111
    assert registry.reward_cfg.expectancy_coeff == pytest.approx(0.33)
    assert registry.meta.controller.baseline_reward.expectancy_coeff == pytest.approx(0.33)


@pytest.mark.unit
def test_reloader_publishes_events_on_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_cfg(tmp_path, _valid_base_cfg())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LUMINA_CONFIG", str(tmp_path / "config.yaml"))
    monkeypatch.setenv("LUMINA_CONFIG_HOT_RELOAD", "true")
    monkeypatch.setenv("LUMINA_MODE", "sim")
    monkeypatch.setenv("TRADE_MODE", "sim")
    monkeypatch.setenv("BROKER_BACKEND", "live")
    ConfigLoader.invalidate()

    prior = ConfigService().load()
    container = _minimal_reload_container(config=prior)

    events: list[str] = []

    def _capture(event: Any) -> None:
        events.append(str(event.topic))

    container.event_bus.subscribe("runtime.config.reloaded", _capture)
    container.event_bus.subscribe("runtime.config.reload_failed", _capture)

    mutated = _valid_base_cfg()
    mutated["sim"] = {**mutated["sim"], "max_total_open_risk": 2500.0}
    atomic_write_yaml(tmp_path / "config.yaml", mutated)

    reloader = RuntimeConfigReloader(container)
    result = reloader.reload_now(source="test")
    assert result.applied is True
    assert "runtime.config.reloaded" in events


@pytest.mark.unit
def test_validate_dict_rejects_invalid_mode_matrix() -> None:
    cfg = {"mode": "paper", "broker": {"backend": "live"}}
    assert ConfigLoader.validate_dict(cfg, raise_on_error=False) is False
