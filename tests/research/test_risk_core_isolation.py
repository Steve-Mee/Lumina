"""AST contract: lumina_research.risk_core imports only stdlib + itself."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RISK_CORE = ROOT / "lumina_research" / "risk_core"
ALLOWED_PREFIXES = frozenset({"lumina_research.risk_core"})
BANNED_PREFIXES = (
    "lumina_core",
    "lumina_research.validation",
    "lumina_research.fitness",
    "lumina_agents",
    "numpy",
    "pandas",
    "scipy",
)


def _module_from_import(node: ast.AST) -> str:
    if isinstance(node, ast.ImportFrom):
        if node.level:
            return "lumina_research.risk_core"
        return node.module or ""
    if isinstance(node, ast.Import):
        return node.names[0].name
    return ""


@pytest.mark.unit
def test_risk_core_import_allowlist() -> None:
    stdlib = set(sys.stdlib_module_names)
    stdlib.add("__future__")
    hits: list[str] = []
    for path in RISK_CORE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            module = _module_from_import(node)
            if not module:
                continue
            root = module.split(".", 1)[0]
            allowed = root in stdlib or any(
                module == prefix or module.startswith(prefix + ".") for prefix in ALLOWED_PREFIXES
            )
            if not allowed:
                rel = path.relative_to(ROOT).as_posix()
                hits.append(f"{rel}:{node.lineno}:{module}")
    assert hits == [], "risk_core imported a forbidden module:\n" + "\n".join(hits)


@pytest.mark.unit
def test_risk_core_does_not_import_live_risk_or_evolution() -> None:
    for path in RISK_CORE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            module = _module_from_import(node)
            for banned in BANNED_PREFIXES:
                assert module != banned
                assert not module.startswith(banned + ".")
