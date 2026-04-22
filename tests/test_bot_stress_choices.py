from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from lumina_core.evolution.bot_stress_choices import (
    BOT_STRESS_CHOICES_FILE,
    ENV_NEURO_OHLC_ROLLOUTS,
    ENV_OHLC_DNA_STRESS,
    apply_env_stress_flags,
    resolve_neuro_ohlc_stress_rollouts,
    resolve_ohlc_reality_stress_enabled,
    save_bot_stress_choices,
)


def test_save_and_resolve_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "b.json"
    monkeypatch.setattr("lumina_core.evolution.bot_stress_choices.BOT_STRESS_CHOICES_FILE", p, raising=False)
    monkeypatch.delenv(ENV_OHLC_DNA_STRESS, raising=False)
    monkeypatch.delenv(ENV_NEURO_OHLC_ROLLOUTS, raising=False)
    save_bot_stress_choices(ohlc_reality_stress_enabled=True, use_ohlc_stress_rollouts=False)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["ohlc_reality_stress_enabled"] is True
    assert data["use_ohlc_stress_rollouts"] is False
    assert resolve_ohlc_reality_stress_enabled() is True
    assert resolve_neuro_ohlc_stress_rollouts() is False


def test_env_overrides_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "b.json"
    monkeypatch.setattr("lumina_core.evolution.bot_stress_choices.BOT_STRESS_CHOICES_FILE", p, raising=False)
    p.write_text(
        json.dumps({"ohlc_reality_stress_enabled": True, "use_ohlc_stress_rollouts": True}),
        encoding="utf-8",
    )
    monkeypatch.setenv(ENV_OHLC_DNA_STRESS, "0")
    monkeypatch.setenv(ENV_NEURO_OHLC_ROLLOUTS, "0")
    assert resolve_ohlc_reality_stress_enabled() is False
    assert resolve_neuro_ohlc_stress_rollouts() is False


def test_apply_env_stress_flags_partial(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_OHLC_DNA_STRESS, raising=False)
    monkeypatch.delenv(ENV_NEURO_OHLC_ROLLOUTS, raising=False)
    apply_env_stress_flags(1, None)
    assert os.environ.get(ENV_OHLC_DNA_STRESS) == "1"
    assert ENV_NEURO_OHLC_ROLLOUTS not in os.environ
    monkeypatch.delenv(ENV_OHLC_DNA_STRESS, raising=False)
