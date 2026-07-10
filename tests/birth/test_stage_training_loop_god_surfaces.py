"""AST guards for stage_training_loop god surface baseline (phase 1C)."""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_STAGE_LOOP = _ROOT / "lumina_core" / "birth" / "stage_training_loop.py"

# Baseline 2026-07-04 after phase 1C extract.
# +2: respect auto_expand_on_adaptation in plateau evolution + stuck escape.
_STAGE_LOOP_LINE_BASELINE = 3352


@pytest.mark.unit
def test_stage_training_loop_loc_at_or_below_baseline() -> None:
    line_count = len(_STAGE_LOOP.read_text(encoding="utf-8").splitlines())
    assert line_count <= _STAGE_LOOP_LINE_BASELINE, (
        f"stage_training_loop.py has {line_count} lines (baseline <= {_STAGE_LOOP_LINE_BASELINE})"
    )


@pytest.mark.unit
def test_stage_training_loop_exports_run_function() -> None:
    text = _STAGE_LOOP.read_text(encoding="utf-8")
    assert "def run_stage_research_loop(" in text
    assert "host._emit_birth_progress" in text or "host._write_progress" in text