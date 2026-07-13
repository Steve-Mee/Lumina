"""
AST/grep guards for launcher birth module god-surface baselines (phase 2B).

Locks submodule sizes after birth_service / birth_runner modularization.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_LAUNCHER_BIRTH = _ROOT / "lumina_launcher" / "services"

# Baselines captured 2026-07-04 after phase 2A/2B splits; birth_runner facade removed 2026-07-13.
_LINE_BASELINES: dict[str, int] = {
    "birth_service.py": 520,
    "birth_status_mapper.py": 351,
    "birth_status_enricher.py": 149,
    "birth_status_plateau_risk.py": 60,
    "birth_runner_lock.py": 181,
    "birth_runner_start.py": 304,
    "birth_runner_wipe.py": 115,
    "birth_runner_recovery.py": 183,
}

_METHOD_CEILINGS: dict[str, dict[str, int]] = {
    "birth_runner_start.py": {"start_birth": 170},
}


def _source(name: str) -> str:
    return (_LAUNCHER_BIRTH / name).read_text(encoding="utf-8")


def _top_level_functions(tree: ast.Module) -> list[ast.FunctionDef]:
    return [node for node in tree.body if isinstance(node, ast.FunctionDef)]


@pytest.mark.unit
@pytest.mark.parametrize("filename,baseline", list(_LINE_BASELINES.items()))
def test_launcher_birth_module_loc_at_or_below_baseline(filename: str, baseline: int) -> None:
    line_count = len(_source(filename).splitlines())
    assert line_count <= baseline, (
        f"{filename} has {line_count} lines (baseline <= {baseline}); "
        "extract to bounded modules instead of growing the god file"
    )


@pytest.mark.unit
@pytest.mark.parametrize("filename,ceilings", list(_METHOD_CEILINGS.items()))
def test_launcher_birth_method_ceilings(filename: str, ceilings: dict[str, int]) -> None:
    source = _source(filename)
    tree = ast.parse(source)
    lines = source.splitlines()
    for name, ceiling in ceilings.items():
        for node in _top_level_functions(tree):
            if node.name != name:
                continue
            start = node.lineno - 1
            end = node.end_lineno or start + 1
            body_lines = len(lines[start:end])
            assert body_lines <= ceiling, (
                f"{filename}::{name} has {body_lines} lines (ceiling {ceiling})"
            )
            break
        else:
            raise AssertionError(f"function {name!r} not found in {filename}")