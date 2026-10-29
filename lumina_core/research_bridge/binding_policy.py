"""S2 encoding of D8–D11 / fail-closed law. Proposal-only: never places an order.

S3 will execute through Risk Core / Position Manager. This module only maps
severity → size, SLA miss → retry/escalate, and independence → bool.
"""

from __future__ import annotations

import math
from typing import Literal

SUSPEND_REDUCE_FRACTION: float = 0.5
DISABLE_FLATTEN_FRACTION: float = 1.0
SLA_RETRY_LIMIT: int = 1
SLA_ESCALATE_AFTER_SECONDS: int = 600
INDEPENDENCE_CORR_MAX: float = 0.5
D7_DEFAULT_SLA_SECONDS: int = 300
D7_CRITICAL_SLA_SECONDS: int = 60

ReduceStage = Literal["deweighted", "suspended", "retired", "disabled", "critical", "hard_limit"]
SlaDecision = Literal["retry", "escalate"]


class BindingPolicyRefused(ValueError):
    """Binding mapping cannot be applied without inventing a size or a retry."""


_REDUCE_STAGES: frozenset[str] = frozenset({"deweighted", "suspended"})
_FLATTEN_STAGES: frozenset[str] = frozenset(
    {"retired", "disabled", "disable", "critical", "hard_limit", "hard_dd", "prolonged_disconnect"}
)


def reduce_fraction_for_stage(stage: str) -> float:
    """D9: suspend/de-weight → 50%; disable/critical/retired/hard limit → flatten 100%."""
    key = str(stage or "").strip().lower()
    if key in _REDUCE_STAGES:
        return SUSPEND_REDUCE_FRACTION
    if key in _FLATTEN_STAGES:
        return DISABLE_FLATTEN_FRACTION
    raise BindingPolicyRefused(f"unknown_alarm_stage:{stage}")


def reduce_qty(stage: str, open_qty: int) -> int:
    """Contracts to reduce (positive). Flatten of qty 2 is 2; 50% of 2 is 1."""
    if isinstance(open_qty, bool) or not isinstance(open_qty, int) or open_qty < 1:
        raise BindingPolicyRefused("open_qty_invalid")
    fraction = reduce_fraction_for_stage(stage)
    if fraction == DISABLE_FLATTEN_FRACTION:
        return int(open_qty)
    reduced = int(open_qty * fraction)
    if reduced < 1:
        raise BindingPolicyRefused("reduce_qty_rounds_to_zero")
    if reduced >= open_qty:
        raise BindingPolicyRefused("reduce_qty_not_partial")
    return int(reduced)


def sla_decision(miss_count: int, elapsed_seconds: float) -> SlaDecision:
    """D10: first miss → retry; second miss or wall > 10 min → escalate. No silent loop."""
    if isinstance(miss_count, bool) or not isinstance(miss_count, int) or miss_count < 1:
        raise BindingPolicyRefused("miss_count_invalid")
    if not _finite_non_negative(elapsed_seconds):
        raise BindingPolicyRefused("elapsed_invalid")
    if elapsed_seconds > float(SLA_ESCALATE_AFTER_SECONDS):
        return "escalate"
    if miss_count > SLA_RETRY_LIMIT:
        return "escalate"
    return "retry"


def independent(
    *,
    hypothesis_id: str,
    family: str,
    other_hypothesis_id: str,
    other_family: str,
    config_id: str,
    other_config_id: str,
    correlation: float | None,
) -> tuple[bool, str]:
    """D11: different hypothesis **and** family, **and** corr strictly < 0.5."""
    left_h = str(hypothesis_id or "").strip()
    right_h = str(other_hypothesis_id or "").strip()
    left_f = str(family or "").strip()
    right_f = str(other_family or "").strip()
    left_c = str(config_id or "").strip()
    right_c = str(other_config_id or "").strip()
    if not left_h or not right_h or not left_f or not right_f:
        return False, "survivors_identity_missing"
    if left_h == right_h:
        return False, "survivors_same_hypothesis"
    if left_c and right_c and left_c == right_c:
        return False, "survivors_same_config"
    if left_f == right_f:
        return False, "survivors_same_family"
    if correlation is None:
        return False, "survivors_corr_unavailable"
    if not _finite_correlation(correlation):
        return False, "survivors_corr_unavailable"
    if float(correlation) >= INDEPENDENCE_CORR_MAX:
        return False, "survivors_corr_not_independent"
    return True, "independent"


def _finite_non_negative(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    number = float(value)
    return math.isfinite(number) and number >= 0.0


def _finite_correlation(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    number = float(value)
    if not math.isfinite(number):
        return False
    return -1.0 <= number <= 1.0
