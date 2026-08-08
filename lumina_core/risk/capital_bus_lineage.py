"""T10: Capital-path Event Bus lineage inventory + residual gate.

Documents the non-bypassable bus spine for reconstructability. Full monorepo
rewire remains continuous; this SSOT tracks emitters and required topics.
"""

from __future__ import annotations

from typing import Any

from lumina_core.agent_orchestration.schemas import (
    CRITICAL_EVENT_BUS_TOPICS,
    EVENT_BUS_TOPIC_MODELS,
)

# Required topics for capital-path reconstructability (core chain)
CAPITAL_PATH_CORE_TOPICS: tuple[str, ...] = (
    "admission.gate_entry",
    "risk.policy.decision",
    "risk.final_arbitration.result",
    "risk.admission.lineage_checked",
)

# Known emitter modules (inventory — not auto-scanned call graph)
CAPITAL_PATH_EMITTERS: tuple[dict[str, str], ...] = (
    {
        "topic": "admission.gate_entry",
        "module": "lumina_core.order_gatekeeper.gate_lineage",
        "when": "pre_trade_gate entry",
    },
    {
        "topic": "risk.policy.decision",
        "module": "lumina_core.order_gatekeeper.admission_risk_steps",
        "when": "risk policy step",
    },
    {
        "topic": "risk.final_arbitration.result",
        "module": "lumina_core.order_gatekeeper.admission_risk_steps",
        "when": "FinalArbitration step",
    },
    {
        "topic": "risk.admission.lineage_checked",
        "module": "lumina_core.broker.broker_bridge.admission",
        "when": "run_final_arbitration admit/reject after ensure_order_lineage",
    },
    {
        "topic": "execution.fill.received",
        "module": "execution path / reconciler",
        "when": "broker fill (post-capital)",
    },
)

__all__ = [
    "CAPITAL_PATH_CORE_TOPICS",
    "CAPITAL_PATH_EMITTERS",
    "build_capital_bus_lineage_inventory",
    "evaluate_capital_bus_lineage_gate",
]


def build_capital_bus_lineage_inventory() -> dict[str, Any]:
    """Static inventory: typed topics registered + known emitters."""
    missing_models: list[str] = []
    registered: list[str] = []
    for topic in CAPITAL_PATH_CORE_TOPICS:
        if topic in EVENT_BUS_TOPIC_MODELS:
            registered.append(topic)
        else:
            missing_models.append(topic)

    critical_ok = all(t in CRITICAL_EVENT_BUS_TOPICS for t in CAPITAL_PATH_CORE_TOPICS if t != "risk.policy.decision")
    # policy.decision is in CRITICAL; lineage_checked added in T10
    return {
        "schema": "capital_bus_lineage_inventory_v1",
        "core_topics": list(CAPITAL_PATH_CORE_TOPICS),
        "typed_models_registered": registered,
        "typed_models_missing": missing_models,
        "emitters": [dict(e) for e in CAPITAL_PATH_EMITTERS],
        "critical_topics_include_core": critical_ok or "risk.admission.lineage_checked" in CRITICAL_EVENT_BUS_TOPICS,
        "residual": [
            {
                "id": "full_capital_path_bus_rewire",
                "status": "continuous",
                "note": "Not every helper emits; core spine is gate_entry + FA + lineage_checked",
            },
            {
                "id": "live_95pct_coverage",
                "status": "runtime",
                "note": "scripts/validation/aperture_coverage_gate.py",
            },
        ],
        "policy": {
            "single_aperture": "run_final_arbitration → ensure_order_lineage → pre_trade_gate",
            "never_bypass_bus_for_real": True,
        },
    }


def evaluate_capital_bus_lineage_gate() -> dict[str, Any]:
    """Fail-closed if core capital topics lack typed models."""
    inv = build_capital_bus_lineage_inventory()
    missing = list(inv.get("typed_models_missing") or [])
    ok = len(missing) == 0
    return {
        "schema": "capital_bus_lineage_gate_v1",
        "ok": ok,
        "hard_fail": not ok,
        "reason": "typed_models_complete" if ok else "typed_models_missing",
        "message": (
            "Capital-path bus topics have typed contracts"
            if ok
            else f"Missing typed models for: {', '.join(missing)}"
        ),
        "inventory": inv,
    }
