from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "lumina_research"
NEEDLES = (
    "LUMINA_LIVE_RELEASE_SECRET",
    "lumina_core.risk.live_release",
    "lumina_core.risk.sim_account_guard",
    "live_release.py",
    "sim_account_guard.py",
)


def _python_files() -> tuple[Path, ...]:
    return tuple(sorted(RESEARCH.rglob("*.py")))


@pytest.mark.unit
@pytest.mark.safety_gate
def test_research_tree_cannot_see_live_release_secret_or_core_modules() -> None:
    hits: list[str] = []
    for path in _python_files():
        source = path.read_text(encoding="utf-8")
        for needle in NEEDLES:
            if needle in source:
                hits.append(f"{path.relative_to(ROOT)}:{needle}")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("lumina_core.risk"):
                hits.append(f"{path.relative_to(ROOT)}:import {node.module}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("lumina_core.risk"):
                        hits.append(f"{path.relative_to(ROOT)}:import {alias.name}")
    assert hits == [], "research isolation broken:\n" + "\n".join(hits)
