"""Tick cache preservation on birth reset (operator T1/T2 path)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_launcher.core.birth_reset import clear_birth_training_state


def _touch(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    state = tmp_path / "state"
    state.mkdir()
    _touch(state / "lumina_birth_progress.json", "{}")
    _touch(state / "lumina_birth_checkpoint.json", "{}")
    _touch(state / "lumina_birth_ticks_cache.jsonl", "{}\n")
    _touch(state / "lumina_birth_split_cache.json", "{}")
    _touch(state / "lumina_birth_cache_manifest.json", "{}")
    _touch(state / "lumina_setup_complete.json", "{}")
    _touch(state / "lumina_daytrading_bible.json", "{}")
    cache = state / "birth_enrichment_cache"
    cache.mkdir()
    _touch(cache / "sample.meta.json", "{}")
    return tmp_path


@pytest.mark.unit
def test_preserve_tick_cache_keeps_ticks_and_enrichment(workspace: Path) -> None:
    result = clear_birth_training_state(
        workspace,
        wipe_genesis=True,
        preserve_tick_cache=True,
    )
    assert result.success is True
    assert not (workspace / "state" / "lumina_birth_progress.json").exists()
    assert not (workspace / "state" / "lumina_setup_complete.json").exists()
    assert (workspace / "state" / "lumina_birth_ticks_cache.jsonl").exists()
    assert (workspace / "state" / "lumina_birth_split_cache.json").exists()
    assert (workspace / "state" / "birth_enrichment_cache" / "sample.meta.json").exists()
    assert "tick cache preserved" in result.message.lower()


@pytest.mark.unit
def test_full_wipe_removes_tick_cache(workspace: Path) -> None:
    result = clear_birth_training_state(
        workspace,
        wipe_genesis=True,
        preserve_tick_cache=False,
    )
    assert result.success is True
    assert not (workspace / "state" / "lumina_birth_ticks_cache.jsonl").exists()
    assert not (workspace / "state" / "birth_enrichment_cache").exists()
