"""Import boundary guards for birth handler decoupling."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
def test_meta_controller_does_not_import_plateau_escalator() -> None:
    source = (_ROOT / "lumina_core" / "birth" / "meta_controller.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
        for alias in node.names
    }
    modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "lumina_core.birth.plateau_escalator" not in modules
    assert "detect_over_trading_trap" not in imports


@pytest.mark.unit
def test_organism_autonomy_does_not_import_phoenix_loop_orchestration() -> None:
    source = (_ROOT / "lumina_core" / "birth" / "organism_autonomy.py").read_text(encoding="utf-8")
    assert "begin_phoenix_cycle" not in source
    assert "build_phoenix_checkpoint_patch" not in source
    assert "can_start_phoenix" not in source


@pytest.mark.unit
def test_curriculum_stage_handler_is_thin_adapter() -> None:
    path = _ROOT / "lumina_core" / "birth" / "curriculum_stage_handler.py"
    text = path.read_text(encoding="utf-8")
    assert len(text.splitlines()) < 150
    assert "run_stage_research_loop" in text
    assert "BirthMetaController" not in text
    assert "plateau_escalator" not in text
