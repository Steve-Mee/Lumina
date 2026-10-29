"""AST: lumina_research/monitoring still has no broker or place_order import."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MONITOR = ROOT / "lumina_research" / "monitoring"
BANNED = (
    "lumina_core.broker",
    "lumina_core.order_gatekeeper",
    "lumina_core.risk.alarm_executor",
    "place_order",
)


def _module(node: ast.AST) -> str:
    if isinstance(node, ast.ImportFrom):
        return node.module or ""
    if isinstance(node, ast.Import):
        return node.names[0].name
    return ""


@pytest.mark.unit
def test_monitoring_has_no_broker_or_place_order() -> None:
    hits: list[str] = []
    for path in MONITOR.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "place_order" in text:
            hits.append(f"{path.relative_to(ROOT)}:place_order")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            module = _module(node)
            for banned in BANNED:
                if banned == "place_order":
                    continue
                if module == banned or module.startswith(banned + "."):
                    hits.append(f"{path.relative_to(ROOT)}:{node.lineno}:{module}")
    assert hits == []
