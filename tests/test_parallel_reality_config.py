from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from lumina_core.config_loader import ConfigLoader
from lumina_core.evolution.parallel_reality_config import (
    ENV_PARALLEL_REALITIES,
    SESSION_FILE,
    apply_env_parallel_realities,
    clamp_parallel,
    recommend_parallel_realities,
    resolve_parallel_realities,
    save_parallel_realities_session,
)
from lumina_core.evolution.meta_swarm import parallel_realities_from_config


def test_clamp_parallel_bounds() -> None:
    assert clamp_parallel(0) == 1
    assert clamp_parallel(1) == 1
    assert clamp_parallel(50) == 50
    assert clamp_parallel(99) == 50


def test_recommend_in_range() -> None:
    r = recommend_parallel_realities()
    assert 1 <= r <= 50


def test_apply_env_parallel_realities(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_PARALLEL_REALITIES, raising=False)
    v = apply_env_parallel_realities(7)
    assert v == 7
    assert os.environ.get(ENV_PARALLEL_REALITIES) == "7"
    assert apply_env_parallel_realities(99) == 50


def test_resolve_env_over_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "s.json"
    monkeypatch.setattr(
        "lumina_core.evolution.parallel_reality_config.SESSION_FILE",
        p,
        raising=False,
    )
    p.write_text(json.dumps({"parallel_realities": 3, "updated_at": "t"}), encoding="utf-8")
    monkeypatch.setenv(ENV_PARALLEL_REALITIES, "40")
    assert resolve_parallel_realities() == 40
    monkeypatch.delenv(ENV_PARALLEL_REALITIES, raising=False)
    assert resolve_parallel_realities() == 3


def test_save_and_resolve_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_PARALLEL_REALITIES, raising=False)
    p = tmp_path / "s.json"
    monkeypatch.setattr("lumina_core.evolution.parallel_reality_config.SESSION_FILE", p, raising=False)
    n = save_parallel_realities_session(9)
    assert n == 9
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["parallel_realities"] == 9
    assert resolve_parallel_realities() == 9


def test_parallel_realities_from_config_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_PARALLEL_REALITIES, raising=False)
    assert 1 <= parallel_realities_from_config() <= 50


def _patch_config_get(monkeypatch: pytest.MonkeyPatch, payload: dict) -> None:
    def _fake_get(_cls, *, reload: bool = False):
        del reload
        return dict(payload)

    monkeypatch.setattr(ConfigLoader, "get", classmethod(_fake_get))


def test_resolve_session_over_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Zonder env wint het sessiebestand boven config.yaml (parallel_realities)."""
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"parallel_realities": 11, "updated_at": "t"}), encoding="utf-8")
    monkeypatch.setattr("lumina_core.evolution.parallel_reality_config.SESSION_FILE", p, raising=False)
    monkeypatch.delenv(ENV_PARALLEL_REALITIES, raising=False)

    _patch_config_get(
        monkeypatch,
        {"evolution": {"multiweek_fitness": {"parallel_realities": 2}}},
    )
    ConfigLoader.invalidate()
    try:
        assert resolve_parallel_realities() == 11
    finally:
        ConfigLoader.invalidate()


def test_resolve_yaml_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Geen env en geen sessiebestand → waarde uit evolution.multiweek_fitness in config."""
    missing = tmp_path / "nope.json"
    monkeypatch.setattr("lumina_core.evolution.parallel_reality_config.SESSION_FILE", missing, raising=False)
    monkeypatch.delenv(ENV_PARALLEL_REALITIES, raising=False)

    _patch_config_get(
        monkeypatch,
        {"evolution": {"multiweek_fitness": {"parallel_realities": 17}}},
    )
    ConfigLoader.invalidate()
    try:
        assert resolve_parallel_realities() == 17
    finally:
        ConfigLoader.invalidate()


def test_invalid_env_uses_session_not_yaml(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"parallel_realities": 5, "updated_at": "t"}), encoding="utf-8")
    monkeypatch.setattr("lumina_core.evolution.parallel_reality_config.SESSION_FILE", p, raising=False)
    monkeypatch.setenv(ENV_PARALLEL_REALITIES, "not_a_number")

    _patch_config_get(monkeypatch, {"evolution": {"multiweek_fitness": {"parallel_realities": 40}}})
    ConfigLoader.invalidate()
    try:
        assert resolve_parallel_realities() == 5
    finally:
        monkeypatch.delenv(ENV_PARALLEL_REALITIES, raising=False)
        ConfigLoader.invalidate()


def test_full_priority_chain_env_session_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"parallel_realities": 6, "updated_at": "t"}), encoding="utf-8")
    monkeypatch.setattr("lumina_core.evolution.parallel_reality_config.SESSION_FILE", p, raising=False)

    _patch_config_get(monkeypatch, {"evolution": {"multiweek_fitness": {"parallel_realities": 99}}})
    ConfigLoader.invalidate()
    try:
        monkeypatch.setenv(ENV_PARALLEL_REALITIES, "22")
        assert resolve_parallel_realities() == 22

        monkeypatch.delenv(ENV_PARALLEL_REALITIES, raising=False)
        assert resolve_parallel_realities() == 6

        p.unlink()
        assert resolve_parallel_realities() == 50  # yaml 99 clamped
    finally:
        ConfigLoader.invalidate()
