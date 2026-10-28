"""Phase 3 evolution cannot import live Risk Core, PromotionGate, or archive birth-v1."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EVOLUTION = ROOT / "lumina_research" / "evolution"
BANNED_PREFIXES = (
    "lumina_core.risk",
    "lumina_core.evolution.promotion_gate",
    "lumina_core.evolution.promotion_evidence",
    "archive.birth_v1",
    "archive.birth-v1",
)


def _module_from_import(node: ast.AST) -> str:
    if isinstance(node, ast.ImportFrom):
        return node.module or ""
    if isinstance(node, ast.Import):
        return node.names[0].name
    return ""


@pytest.mark.unit
def test_phase3_does_not_import_live_risk_promotion_or_archive_birth() -> None:
    hits: list[str] = []
    for path in EVOLUTION.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "archive/birth-v1" not in source
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            module = _module_from_import(node)
            for banned in BANNED_PREFIXES:
                if module == banned or module.startswith(banned + "."):
                    rel = path.relative_to(ROOT).as_posix()
                    hits.append(f"{rel}:{node.lineno}:{module}")
    assert hits == [], "Phase 3 imported a forbidden surface:\n" + "\n".join(hits)
