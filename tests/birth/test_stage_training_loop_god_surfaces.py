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
def test_stage_rollout_executor_loc_initial_ceiling() -> None:
    """Executor extracted from curriculum_stage_handler; bound growth during bus migration."""
    path = _ROOT / "lumina_core" / "birth" / "stage_rollout_executor.py"
    line_count = len(path.read_text(encoding="utf-8").splitlines())
    assert line_count <= 3400, f"stage_rollout_executor.py grew to {line_count} lines"