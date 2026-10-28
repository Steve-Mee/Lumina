"""AST scan: every production place/submit/try_open is behind the S0 freeze or a listed transport."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = (ROOT / "lumina_core", ROOT / "lumina_os")
PLACE_NAMES = frozenset(
    {
        "place_order",
        "execute_order",
        "submit_order",
        "try_open",
        "submit_paper_order",
        "submit_order_with_risk_check",
    }
)
EXCLUDED_CALL_NAMES = frozenset({"place_order_sync"})
GATE_NAMES = frozenset({"assert_validation_gate_or_block", "gate_order"})
TRANSPORT_ALLOW = frozenset(
    {
        "lumina_core/broker/broker_bridge/base.py",
        "lumina_core/broker/broker_bridge/paper_broker.py",
        "lumina_core/broker/broker_bridge/cross_trade_broker.py",
        "lumina_core/broker/ninjatrader/broker.py",
        "lumina_core/broker/ninjatrader/bridge_command_sync.py",
        "lumina_core/broker/ninjatrader/fabric_client_ops.py",
        "lumina_core/ports/broker.py",
    }
)


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _enclosing_function(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    current: ast.AST | None = node
    while current is not None:
        current = parents.get(current)
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current
    return None


def _function_calls_gate(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for child in ast.walk(fn):
        if isinstance(child, ast.Call) and _call_name(child) in GATE_NAMES:
            return True
    return False


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    mapping: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            mapping[child] = node
    return mapping


@pytest.mark.unit
def test_every_place_call_is_gated_or_listed_transport() -> None:
    failures: list[str] = []
    for root in SCAN_ROOTS:
        for path in root.rglob("*.py"):
            rel = path.relative_to(ROOT).as_posix()
            if "/generated/" in rel or rel.endswith("_pb2.py") or rel.endswith("_pb2_grpc.py"):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            parents = _parents(tree)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = _call_name(node)
                if name is None or name in EXCLUDED_CALL_NAMES or name not in PLACE_NAMES:
                    continue
                if rel in TRANSPORT_ALLOW:
                    continue
                fn = _enclosing_function(node, parents)
                if fn is None or not _function_calls_gate(fn):
                    lineno = getattr(node, "lineno", 0)
                    owner = fn.name if fn is not None else "<module>"
                    failures.append(f"{rel}:{lineno}:{owner} calls {name} without S0 gate")
    assert failures == [], "Ungated place path(s):\n" + "\n".join(failures)


@pytest.mark.unit
def test_assert_validation_gate_or_block_does_not_read_yaml_or_env() -> None:
    path = ROOT / "lumina_core" / "order_gatekeeper" / "ungated_place_block.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    freeze_fn = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "assert_validation_gate_or_block"
    )
    called: set[str] = set()
    for child in ast.walk(freeze_fn):
        if isinstance(child, ast.Call):
            name = _call_name(child)
            if name is not None:
                called.add(name)
    assert "research_execution_mode_from_mapping" not in called
    assert "getenv" not in called
    assert "safe_load" not in called
    source = ast.unparse(freeze_fn)
    assert "S0_PLACE_SOURCE_ALLOWLIST" not in source
