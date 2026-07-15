"""Guards for stage loop module split."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_BIRTH = _ROOT / "lumina_core" / "birth"
_EXECUTOR = _BIRTH / "stage_rollout_executor.py"
_ROLLOUT = _BIRTH / "stage_loop_rollout.py"
_SESSION = _BIRTH / "stage_loop_session.py"
_RECOVERY = _BIRTH / "stage_loop_recovery.py"
_RECOVERY_MIXIN = _BIRTH / "stage_loop_recovery_mixin.py"
_PLATEAU = _BIRTH / "plateau_evolution_handler.py"
_CONTEXT = _BIRTH / "stage_loop_context.py"


@pytest.mark.unit
def test_stage_rollout_executor_is_thin_wrapper() -> None:
    text = _EXECUTOR.read_text(encoding="utf-8")
    assert "stage_loop_rollout" in text
    assert len(text.splitlines()) < 80


@pytest.mark.unit
def test_stage_loop_rollout_is_thin_entrypoint() -> None:
    text = _ROLLOUT.read_text(encoding="utf-8")
    assert "def run_stage_research_loop" in text or "run_stage_research_loop" in text
    assert "stage_loop_session" in text
    size_kb = _ROLLOUT.stat().st_size / 1024
    assert size_kb < 15, f"stage_loop_rollout.py too large: {size_kb:.1f} KB"


@pytest.mark.unit
def test_stage_loop_session_hosts_orchestration() -> None:
    text = _SESSION.read_text(encoding="utf-8")
    assert "class StageLoopSession" in text
    assert "BirthBusClient" in text
    assert "def run_stage_research_loop" in text


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
def test_recovery_and_plateau_mixins_exist() -> None:
    assert "class StageLoopRecoveryMixin" in _RECOVERY_MIXIN.read_text(encoding="utf-8")
    assert "class PlateauEvolutionMixin" in _PLATEAU.read_text(encoding="utf-8")


@pytest.mark.unit
def test_stage_loop_context_dataclass_exists() -> None:
    tree = ast.parse(_CONTEXT.read_text(encoding="utf-8"))
    classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    assert "StageLoopContext" in classes


@pytest.mark.unit
def test_birth_py_files_under_50kb() -> None:
    oversized = []
    for path in _BIRTH.glob("*.py"):
        if path.name.startswith("_"):
            continue
        kb = path.stat().st_size / 1024
        if kb >= 50:
            oversized.append((path.name, kb))
    assert not oversized, f"birth/ files >= 50 KB: {oversized}"
