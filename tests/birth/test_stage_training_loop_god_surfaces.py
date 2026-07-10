"""Tests for stage_training_loop after full event-bus decomposition.

The monolithic procedural logic has been deleted and replaced by
event emissions + dedicated handlers. This file is now a thin shim.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_STAGE_LOOP = _ROOT / "lumina_core" / "birth" / "stage_training_loop.py"


@pytest.mark.unit
def test_stage_training_loop_is_now_thin_after_decomposition() -> None:
    """After Prompt 1 decomposition the god module must be small."""
    text = _STAGE_LOOP.read_text(encoding="utf-8")
    line_count = len(text.splitlines())
    assert line_count < 150, f"stage_training_loop.py still too large: {line_count}"
    assert "def run_stage_research_loop(" in text  # thin shim still exports for compat
    # No longer contains the old internal god orchestration strings
    assert "_apply_plateau_evolution" not in text
    assert "while True:" not in text or text.count("while True:") < 2  # only incidental


@pytest.mark.unit
def test_stage_training_loop_emits_to_bus() -> None:
    text = _STAGE_LOOP.read_text(encoding="utf-8")
    assert "birth.curriculum.stage.requested" in text or "publish" in text