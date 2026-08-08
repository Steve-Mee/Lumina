"""AST guards for birth_phase_orchestrator god-surface baseline (phase 1E)."""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_ORCHESTRATOR = _ROOT / "lumina_core" / "birth" / "birth_phase_orchestrator.py"

# Wave D thin coordinator after phase-module extract (bootstrap/data/cert/train).
_ORCHESTRATOR_LINE_BASELINE = 120

_PHASE_MODULES = (
    "birth_phase_bootstrap.py",
    "birth_phase_data_policy.py",
    "birth_phase_certificate_resume.py",
    "birth_phase_train_complete.py",
    "birth_phase_certificate_gate.py",
)


@pytest.mark.unit
def test_birth_phase_orchestrator_loc_at_or_below_baseline() -> None:
    line_count = len(_ORCHESTRATOR.read_text(encoding="utf-8").splitlines())
    assert line_count <= _ORCHESTRATOR_LINE_BASELINE, (
        f"birth_phase_orchestrator.py has {line_count} lines "
        f"(baseline <= {_ORCHESTRATOR_LINE_BASELINE})"
    )


@pytest.mark.unit
def test_birth_phase_modules_exist_and_stay_bounded() -> None:
    for name in _PHASE_MODULES:
        path = _ROOT / "lumina_core" / "birth" / name
        assert path.is_file(), f"missing phase module {name}"
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        assert line_count <= 350, f"{name} has {line_count} lines (cap 350)"


@pytest.mark.unit
def test_birth_phase_orchestrator_exports_run_birth_phase() -> None:
    text = _ORCHESTRATOR.read_text(encoding="utf-8")
    assert "def run_birth_phase(" in text
    assert "bootstrap_birth_phase" in text
    assert "prepare_birth_data_and_policy" in text
    assert "try_certificate_fast_path_resume" in text
    assert "run_curriculum_and_complete" in text