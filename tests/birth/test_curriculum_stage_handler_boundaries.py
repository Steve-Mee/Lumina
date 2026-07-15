"""AST guards for stage rollout executor orchestration imports."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_EXECUTOR = _ROOT / "lumina_core" / "birth" / "stage_rollout_executor.py"
_ROLLOUT = _ROOT / "lumina_core" / "birth" / "stage_loop_rollout.py"
_RECOVERY_MIXIN = _ROOT / "lumina_core" / "birth" / "stage_loop_recovery_mixin.py"

_FORBIDDEN_MODULES: set[str] = set()

_ALLOWED_PLATEAU_SYMBOLS = {
    "TERMINAL_STALL_REASON",
    "EvolutionAction",
    "PlateauEnterContext",
    "build_plateau_audit",
    "remediation_is_exhausted",
    "reset_plateau_for_new_cycle",
    "rolling_winrate_last_n_trades",
    "sanitize_plateau_best_snapshot",
    "should_trigger_plateau_evolution_step",
    "begin_evolution_step",
}


@pytest.mark.unit
def test_stage_rollout_executor_avoids_forbidden_orchestration_imports() -> None:
    tree = ast.parse(_EXECUTOR.read_text(encoding="utf-8"))
    modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    for forbidden in _FORBIDDEN_MODULES:
        assert forbidden not in modules


@pytest.mark.unit
def test_stage_rollout_executor_uses_bus_client() -> None:
    wrapper = _EXECUTOR.read_text(encoding="utf-8")
    assert "stage_loop_rollout" in wrapper
    rollout = _ROLLOUT.read_text(encoding="utf-8")
    recovery = _RECOVERY_MIXIN.read_text(encoding="utf-8")
    assert "run_stage_research_loop" in rollout
    assert "wall_evaluate_trigger" in recovery
    assert "adaptation_try_recovery" in recovery
    assert "from lumina_core.birth.organism_autonomy import evaluate_terminal_stall" not in recovery
    assert "get_adaptation_decision" not in recovery
    assert "begin_remediation_cycle" not in recovery
