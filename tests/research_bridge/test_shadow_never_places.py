"""ResearchBridge never places: no broker import, no PlaceOrderCommand, no submit."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas_research import RESEARCH_PROMOTION_TOPIC
from lumina_core.research_bridge.install import attach_shadow_runtime
from lumina_core.research_bridge.shadow_runtime import ShadowRuntime
from lumina_research.agents.provenance import ProvenanceAuthority
from tests.research_bridge.helpers import make_runtime, sealed_candidate

ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "lumina_core" / "research_bridge"
S3_ALLOWED_IMPORTS = frozenset(
    {
        ("lumina_core/research_bridge/sim_runtime.py", "lumina_core.broker.broker_bridge.schemas"),
        ("lumina_core/research_bridge/protective_stop.py", "lumina_core.broker.broker_bridge.schemas"),
        ("lumina_core/research_bridge/protective_attach.py", "lumina_core.broker.broker_bridge.schemas"),
        ("lumina_core/research_bridge/sim_protected.py", "lumina_core.broker.broker_bridge.schemas"),
        ("lumina_core/research_bridge/sim_gate.py", "lumina_core.broker.ninjatrader.account_names"),
    }
)
S3_ALLOWED_CALLS = frozenset(
    {
        ("lumina_core/research_bridge/sim_runtime.py", "submit_order"),
        ("lumina_core/research_bridge/sim_protected.py", "submit_order"),
    }
)
BANNED_IMPORT_PREFIXES = (
    "lumina_core.broker",
    "lumina_core.broker.ninjatrader",
    "lumina_os.backend.emergency_order_endpoints",
)
BANNED_CALLS = frozenset(
    {
        "place_order",
        "place_order_sync",
        "submit_order",
        "submit_paper_order",
        "submit_order_with_risk_check",
        "try_open",
        "execute_order",
        "PlaceOrderCommand",
    }
)


def _imported_module(node: ast.AST) -> str:
    if isinstance(node, ast.ImportFrom):
        return node.module or ""
    if isinstance(node, ast.Import):
        return node.names[0].name
    return ""


@pytest.mark.unit
def test_research_bridge_tree_has_no_broker_or_place_imports() -> None:
    hits: list[str] = []
    for path in BRIDGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rel = path.relative_to(ROOT).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = _imported_module(node)
                for banned in BANNED_IMPORT_PREFIXES:
                    if module == banned or module.startswith(banned + "."):
                        if (rel, module) not in S3_ALLOWED_IMPORTS:
                            hits.append(f"{rel}:{node.lineno}:import {module}")
            if isinstance(node, ast.Call):
                func = node.func
                name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
                if name in BANNED_CALLS and (rel, name) not in S3_ALLOWED_CALLS:
                    hits.append(f"{rel}:{node.lineno}:call {name}")
            if isinstance(node, ast.Name) and node.id == "PlaceOrderCommand":
                hits.append(f"{rel}:{node.lineno}:name PlaceOrderCommand")
    assert hits == [], "ResearchBridge must not place:\n" + "\n".join(hits)


@pytest.mark.unit
def test_sealed_candidate_does_not_submit(tmp_path: Path) -> None:
    _bus, authority, runtime, _alerts, observe = make_runtime(tmp_path, healthy=True)
    candidate = sealed_candidate(authority)
    intent = runtime.on_candidate(candidate)
    assert intent is not None
    runtime.assert_no_broker_submit()
    assert len(runtime.issued_intents()) == 1
    assert len(runtime.issued_fills()) == 1
    assert len(observe.calls) == 1


@pytest.mark.unit
def test_shadow_runtime_is_the_port_shape() -> None:
    assert hasattr(ShadowRuntime, "on_candidate")
    assert hasattr(ShadowRuntime, "shadow_fill")
    assert hasattr(ShadowRuntime, "assert_no_broker_submit")


@pytest.mark.unit
def test_attach_shadow_runtime_defaults_unhealthy(tmp_path: Path) -> None:
    bus = EventBus()
    authority = ProvenanceAuthority()
    runtime = attach_shadow_runtime(bus, authority=authority, jsonl_path=tmp_path / "shadow.jsonl")
    intent = runtime.on_candidate(sealed_candidate(authority))
    assert intent is None
    assert runtime.issued_intents() == ()
    runtime.assert_no_broker_submit()


@pytest.mark.unit
def test_event_bus_candidate_becomes_logged_intent(tmp_path: Path) -> None:
    bus, authority, runtime, _alerts, observe = make_runtime(tmp_path, healthy=True)
    bus.register_topic_guard(RESEARCH_PROMOTION_TOPIC, authority.guard_promotion)
    candidate = sealed_candidate(authority)
    bus.publish(
        topic=RESEARCH_PROMOTION_TOPIC,
        producer="promotion_agent",
        payload=candidate.model_dump(mode="json"),
    )
    assert len(runtime.issued_intents()) == 1
    assert len(runtime.issued_fills()) == 1
    assert len(observe.calls) == 1
    runtime.assert_no_broker_submit()
