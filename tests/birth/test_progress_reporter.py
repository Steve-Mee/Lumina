"""Unit tests for birth progress_reporter module."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.birth.progress import read_birth_progress
from lumina_core.birth.progress_reporter import BirthProgressReporter


@pytest.mark.unit
def test_emit_birth_progress_writes_state(tmp_path: Path) -> None:
    BirthProgressReporter(tmp_path).emit_birth_progress(
        stage="loading_data",
        phase="enriching_news",
        message="test message",
        progress_pct=20.5,
        cumulative_trades=0,
        target_trades=100,
        ppo_steps=0,
        birth_start_time=1.0,
        training_mode="certified",
    )
    snap = read_birth_progress(tmp_path)
    assert snap.get("phase") == "enriching_news"
    assert snap.get("message") == "test message"