"""
AST/grep guards for birth engine god-surface baseline (phase 0).

Locks current size so engine.py cannot grow without an intentional guard update
during modularization. Lower *_BASELINE constants as logic moves to bounded modules.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_BIRTH_ENGINE = _ROOT / "lumina_core" / "birth" / "engine.py"

# Baseline captured 2026-07-04; decrease per extraction PR (phase 1 target <800).
# Phase 1A (data_pipeline extract): 6042 -> 5696.
# Phase 1B (progress + checkpoint extract): 5696 -> 5643.
# Phase 1C (stage_training_loop extract): 5643 -> 2473.
# Phase 1D (certificate_pipeline extract): 2473 -> 1625.
# Phase 1D cleanup (unused import prune): 1625 -> 1508.
# Phase 1E (birth_phase_orchestrator extract): 1508 -> 887.
_ENGINE_LINE_BASELINE = 883
_ENGINE_METHOD_BASELINE = 44

# Largest method bodies — must not grow without intentional guard update.
_METHOD_LINE_CEILINGS: dict[str, int] = {
    "run_birth_phase": 30,
}

# Submodules already own these concerns; engine should keep delegating via imports.
_BOUNDED_MODULE_MARKERS = [
    "lumina_core.birth.checkpoint",
    "lumina_core.birth.curriculum",
    "lumina_core.birth.data_pipeline",
    "lumina_core.birth.progress_reporter",
    "lumina_core.birth.checkpoint_coordinator",
    "lumina_core.birth.stage_training_loop",
    "lumina_core.birth.certificate_pipeline",
    "lumina_core.birth.birth_phase_orchestrator",
    "lumina_core.birth.meta_controller",
    "lumina_core.birth.plateau_escalator",
    "lumina_core.birth.organism_autonomy",
    "lumina_core.birth.phoenix_loop",
    "lumina_core.birth.stall_remediation",
    "lumina_core.birth.certificate_evaluator",
    "lumina_core.birth.tick_cache_persist",
]


def _engine_source() -> str:
    return _BIRTH_ENGINE.read_text(encoding="utf-8")


def _birth_engine_class(tree: ast.Module) -> ast.ClassDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "BirthPhaseEngineV2":
            return node
    msg = "BirthPhaseEngineV2 not found"
    raise AssertionError(msg)


def _method_body_lines(source: str, class_node: ast.ClassDef, name: str) -> str:
    lines = source.splitlines()
    for item in class_node.body:
        if isinstance(item, ast.FunctionDef) and item.name == name:
            start = item.lineno - 1
            end = item.end_lineno or start + 1
            return "\n".join(lines[start:end])
    msg = f"method {name!r} not found on BirthPhaseEngineV2"
    raise AssertionError(msg)


@pytest.mark.unit
def test_birth_engine_loc_at_or_below_baseline() -> None:
    line_count = len(_engine_source().splitlines())
    assert line_count <= _ENGINE_LINE_BASELINE, (
        f"birth/engine.py has {line_count} lines (baseline <= {_ENGINE_LINE_BASELINE}); "
        "extract to bounded modules instead of growing the god file"
    )


@pytest.mark.unit
def test_birth_engine_method_count_at_or_below_baseline() -> None:
    tree = ast.parse(_engine_source())
    cls = _birth_engine_class(tree)
    method_count = sum(1 for item in cls.body if isinstance(item, ast.FunctionDef))
    assert method_count <= _ENGINE_METHOD_BASELINE, (
        f"BirthPhaseEngineV2 has {method_count} methods (baseline <= {_ENGINE_METHOD_BASELINE})"
    )


@pytest.mark.unit
def test_birth_engine_largest_methods_do_not_grow() -> None:
    source = _engine_source()
    tree = ast.parse(source)
    cls = _birth_engine_class(tree)
    for name, ceiling in _METHOD_LINE_CEILINGS.items():
        body = _method_body_lines(source, cls, name)
        line_count = len(body.splitlines())
        assert line_count <= ceiling, (
            f"{name} has {line_count} lines (ceiling {ceiling}); extract before adding logic"
        )


@pytest.mark.unit
def test_birth_engine_imports_bounded_birth_modules() -> None:
    text = _engine_source()
    hits = sum(1 for marker in _BOUNDED_MODULE_MARKERS if marker in text)
    assert hits >= 6, "engine.py should import from bounded birth submodules"


@pytest.mark.unit
def test_birth_engine_extraction_targets_exist_as_imports() -> None:
    """Phase 1 modules are not yet extracted; guard documents intended split boundaries."""
    text = _engine_source()
    for symbol in (
        "_persist_checkpoint",
        "_data_pipeline",
        "_certificate_pipeline",
        "_emit_birth_progress",
        "birth_phase_orchestrator",
    ):
        assert symbol in text, f"expected {symbol!r} in engine as thin delegate/hub"