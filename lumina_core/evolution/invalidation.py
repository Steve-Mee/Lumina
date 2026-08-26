"""Invalidation classifier — not the mutating operator (K8)."""

from __future__ import annotations

from typing import Any

from lumina_core.code_evolution.proposal import CodeMutationOperator, CodeMutationProposal

BEHAVIOR_TWEAK = "behavior_tweak"
POLICY_INCOMPATIBLE = "policy_incompatible"
CORE_CRITICAL = "core_critical"

_LOOKBACK_KEYS = frozenset(
    {"ema_fast_window", "ema_slow_window", "rsi_period", "lookback", "window"}
)
_CORE_PREFIXES = (
    "lumina_core/risk/",
    "lumina_core/broker/",
    "lumina_core/safety/",
    "ALTER TABLE",
)


def classify_code_proposal(proposal: CodeMutationProposal | dict[str, Any]) -> str:
    """Fail-closed: doubt and snippets/indicators/lookbacks → policy_incompatible."""
    if isinstance(proposal, CodeMutationProposal):
        operator = proposal.operator
        payload = dict(proposal.payload or {})
        target = str(proposal.target or "")
        code = str(payload.get("code") or "")
    else:
        operator = proposal.get("operator")
        payload = dict(proposal.get("payload") or {})
        target = str(proposal.get("target") or "")
        code = str(payload.get("code") or "")

    blob = f"{target} {code}".lower()
    if any(p.lower() in blob for p in _CORE_PREFIXES):
        return CORE_CRITICAL

    op = operator.value if isinstance(operator, CodeMutationOperator) else str(operator or "")
    op_l = op.strip().lower()
    if op_l in {
        CodeMutationOperator.ADD_SIMPLE_INDICATOR.value,
        CodeMutationOperator.STRATEGY_SNIPPET_ADJUST.value,
        "add_simple_indicator",
        "strategy_snippet_adjust",
    }:
        return POLICY_INCOMPATIBLE

    if op_l in {CodeMutationOperator.PARAMETER_TWEAK.value, "parameter_tweak"}:
        key = str(payload.get("key") or "").strip().lower()
        if key in _LOOKBACK_KEYS:
            return POLICY_INCOMPATIBLE
        if key == "confluence_threshold":
            return BEHAVIOR_TWEAK
        return POLICY_INCOMPATIBLE

    return POLICY_INCOMPATIBLE
