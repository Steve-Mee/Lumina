"""AST guards for birth_phase_orchestrator god-surface baseline (phase 1E)."""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_ORCHESTRATOR = _ROOT / "lumina_core" / "birth" / "birth_phase_orchestrator.py"

# Phase 1E extract from engine.py (~627 lines).
_ORCHESTRATOR_LINE_BASELINE = 699


@pytest.mark.unit
def test_birth_phase_orchestrator_loc_at_or_below_baseline() -> None:
    line_count = len(_ORCHESTRATOR.read_text(encoding="utf-8").splitlines())
    assert line_count <= _ORCHESTRATOR_LINE_BASELINE, (
        f"birth_phase_orchestrator.py has {line_count} lines "
        f"(baseline <= {_ORCHESTRATOR_LINE_BASELINE})"
    )


@pytest.mark.unit
def test_birth_phase_orchestrator_exports_run_birth_phase() -> None:
    text = _ORCHESTRATOR.read_text(encoding="utf-8")
    assert "def run_birth_phase(" in text
    assert "host._data_pipeline()" in text or "host._ensure_holdout_preflight" in text