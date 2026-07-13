"""AST guards for stage rollout executor orchestration imports."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_EXECUTOR = _ROOT / "lumina_core" / "birth" / "stage_rollout_executor.py"

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
    text = _EXECUTOR.read_text(encoding="utf-8")
    assert "BirthBusClient" in text
    assert "wall_evaluate_trigger" in text
    assert "adaptation_try_recovery" in text
    assert "from lumina_core.birth.organism_autonomy import evaluate_terminal_stall" not in text
    assert "get_adaptation_decision" not in text
    assert "begin_remediation_cycle" not in text
