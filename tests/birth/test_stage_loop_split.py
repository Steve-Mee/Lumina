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
_SESSION_RUNNER = _BIRTH / "stage_loop_session_runner.py"
_DATA_OPS = _BIRTH / "stage_loop_data_ops.py"
_DATA_CACHE = _BIRTH / "stage_loop_data_cache.py"
_DATA_ENRICH = _BIRTH / "stage_loop_data_enrich.py"
_RECOVERY = _BIRTH / "stage_loop_recovery.py"
_RECOVERY_MIXIN = _BIRTH / "stage_loop_recovery_mixin.py"
_RECOVERY_TERMINAL = _BIRTH / "stage_loop_recovery_terminal.py"
_RECOVERY_REMEDIATION = _BIRTH / "stage_loop_recovery_remediation.py"
_RECOVERY_ADAPTATION = _BIRTH / "stage_loop_recovery_adaptation.py"
_ROLLOUT_CYCLE = _BIRTH / "stage_loop_rollout_cycle.py"
_ROLLOUT_PRE = _BIRTH / "stage_loop_rollout_pre.py"
_ROLLOUT_POST = _BIRTH / "stage_loop_rollout_post.py"
_ROLLOUT_TAIL = _BIRTH / "stage_loop_rollout_tail.py"
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
    assert "StageLoopSessionRunnerMixin" in text
    assert "def run_stage_research_loop" in text
    # Heavy run() body lives in runner; composition root stays thin.
    assert _SESSION.stat().st_size / 1024 < 15, "stage_loop_session.py too large"
    runner = _SESSION_RUNNER.read_text(encoding="utf-8")
    assert "class StageLoopSessionRunnerMixin" in runner
    assert "def run(" in runner
    assert "BirthBusClient" in runner


@pytest.mark.unit
def test_stage_loop_data_ops_is_composite_facade() -> None:
    text = _DATA_OPS.read_text(encoding="utf-8")
    assert "class StageLoopDataOpsMixin" in text
    assert "StageLoopDataCacheMixin" in text
    assert "StageLoopDataEnrichMixin" in text
    assert _DATA_OPS.stat().st_size / 1024 < 5, "stage_loop_data_ops.py too large"
    assert "class StageLoopDataCacheMixin" in _DATA_CACHE.read_text(encoding="utf-8")
    assert "class StageLoopDataEnrichMixin" in _DATA_ENRICH.read_text(encoding="utf-8")


@pytest.mark.unit
def test_stage_loop_recovery_exports_adaptation_helpers() -> None:
    """Compat façade keeps historical names; mixins own live recovery."""
    text = _RECOVERY.read_text(encoding="utf-8")
    assert "thin compatibility" in text.lower() or "compat" in text.lower()
    for symbol in (
        "try_adaptive_stall_recovery",
        "force_never_stop_recovery",
        "try_adaptation_stuck_escape",
        "adaptation_failure_key",
    ):
        assert symbol in text
    # Live ownership: adaptation mixin methods
    adapt = _RECOVERY_ADAPTATION.read_text(encoding="utf-8")
    assert "_try_adaptive_stall_recovery" in adapt
    assert "_force_never_stop_recovery" in adapt


@pytest.mark.unit
def test_recovery_and_plateau_mixins_exist() -> None:
    assert "class StageLoopRecoveryMixin" in _RECOVERY_MIXIN.read_text(encoding="utf-8")
    assert "class PlateauEvolutionMixin" in _PLATEAU.read_text(encoding="utf-8")
    for path, cls in (
        (_RECOVERY_TERMINAL, "StageLoopRecoveryTerminalMixin"),
        (_RECOVERY_REMEDIATION, "StageLoopRecoveryRemediationMixin"),
        (_RECOVERY_ADAPTATION, "StageLoopRecoveryAdaptationMixin"),
    ):
        assert path.is_file(), path.name
        assert f"class {cls}" in path.read_text(encoding="utf-8")


@pytest.mark.unit
def test_rollout_cycle_phase_mixins_exist() -> None:
    assert "class StageLoopRolloutCycleMixin" in _ROLLOUT_CYCLE.read_text(encoding="utf-8")
    for path, cls in (
        (_ROLLOUT_PRE, "StageLoopRolloutPreMixin"),
        (_ROLLOUT_POST, "StageLoopRolloutPostMixin"),
        (_ROLLOUT_TAIL, "StageLoopRolloutTailMixin"),
    ):
        assert path.is_file(), path.name
        assert f"class {cls}" in path.read_text(encoding="utf-8")
    # Cycle façade should stay thin orchestrator (not the 749-line method god)
    cycle_kb = _ROLLOUT_CYCLE.stat().st_size / 1024
    assert cycle_kb < 20, f"stage_loop_rollout_cycle.py too large: {cycle_kb:.1f} KB"


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
