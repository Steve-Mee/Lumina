"""Twin knowledge wipe: confirm token, no sacred Birth files."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.evolution.twin_knowledge_reset import (
    WIPE_CONFIRM_TOKEN,
    wipe_twin_knowledge,
)


def test_wipe_requires_exact_confirm(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="confirm"):
        wipe_twin_knowledge(state_dir=tmp_path, confirm="yes")


def test_wipe_deletes_twin_files_not_tick_cache(tmp_path: Path) -> None:
    (tmp_path / "twin_base_training.json").write_text("{}", encoding="utf-8")
    (tmp_path / "twin_birth_readiness.json").write_text("{}", encoding="utf-8")
    (tmp_path / "approval_twin_model.json").write_text("{}", encoding="utf-8")
    (tmp_path / "steve_values_registry.jsonl").write_text("{}\n", encoding="utf-8")
    sacred = tmp_path / "lumina_birth_ticks_cache.jsonl"
    sacred.write_text("ticks", encoding="utf-8")
    result = wipe_twin_knowledge(state_dir=tmp_path, confirm=WIPE_CONFIRM_TOKEN)
    assert result["ok"] is True
    assert result["birth_ready"] is False
    assert (tmp_path / "twin_base_training.json").exists() is False
    assert (tmp_path / "twin_birth_readiness.json").exists() is False
    assert (tmp_path / "approval_twin_model.json").exists() is False
    assert sacred.read_text(encoding="utf-8") == "ticks"
    assert "lumina_birth_ticks_cache.jsonl" not in result["removed"]


def test_wipe_refuses_sacred_extra_path(tmp_path: Path) -> None:
    sacred = tmp_path / "lumina_birth_ticks_cache.jsonl"
    sacred.write_text("ticks", encoding="utf-8")
    with pytest.raises(RuntimeError, match="sacred"):
        wipe_twin_knowledge(
            state_dir=tmp_path,
            confirm=WIPE_CONFIRM_TOKEN,
            extra_paths=(sacred,),
        )
    assert sacred.read_text(encoding="utf-8") == "ticks"
