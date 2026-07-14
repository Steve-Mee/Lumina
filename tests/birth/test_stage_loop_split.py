"""Guards for stage loop module split."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_EXECUTOR = _ROOT / "lumina_core" / "birth" / "stage_rollout_executor.py"
_ROLLOUT = _ROOT / "lumina_core" / "birth" / "stage_loop_rollout.py"
_RECOVERY = _ROOT / "lumina_core" / "birth" / "stage_loop_recovery.py"
_CONTEXT = _ROOT / "lumina_core" / "birth" / "stage_loop_context.py"


@pytest.mark.unit
def test_stage_rollout_executor_is_thin_wrapper() -> None:
    text = _EXECUTOR.read_text(encoding="utf-8")
    assert "stage_loop_rollout" in text
    assert len(text.splitlines()) < 80


@pytest.mark.unit
def test_stage_loop_rollout_hosts_main_loop() -> None:
    text = _ROLLOUT.read_text(encoding="utf-8")
    assert "def run_stage_research_loop" in text
    assert "while True:" in text
    assert "BirthBusClient" in text


@pytest.mark.unit
def test_stage_loop_recovery_exports_adaptation_helpers() -> None:
    text = _RECOVERY.read_text(encoding="utf-8")
    for symbol in (
        "try_adaptive_stall_recovery",
        "force_never_stop_recovery",
        "try_adaptation_stuck_escape",
        "adaptation_failure_key",
    ):
        assert symbol in text


@pytest.mark.unit
def test_stage_loop_context_dataclass_exists() -> None:
    tree = ast.parse(_CONTEXT.read_text(encoding="utf-8"))
    classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    assert "StageLoopContext" in classes