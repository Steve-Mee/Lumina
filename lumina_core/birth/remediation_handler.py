"""RemediationHandler — single responsibility for stall remediation and human-gate paths.

Core logic in stall_remediation.py and remediation.py.
In evented flow this handler reacts to terminal stall signals and
publishes remediation start/complete or escalates to phoenix.
"""

from __future__ import annotations

from lumina_core.birth.remediation import (
    RemediationAction,
    RemediationPlan,
    parse_failure_reason_keys,
    select_remediation_plan,
)
from lumina_core.birth.stall_remediation import (
    HUMAN_GATE_REASON,
    StallRemediationAction,
    StallRemediationState,
    begin_remediation_cycle,
    begin_remediation_step,
    can_start_remediation,
    should_advance_remediation_step,
)

__all__ = [
    "RemediationAction",
    "RemediationPlan",
    "HUMAN_GATE_REASON",
    "StallRemediationAction",
    "StallRemediationState",
    "begin_remediation_cycle",
    "begin_remediation_step",
    "can_start_remediation",
    "should_advance_remediation_step",
    "parse_failure_reason_keys",
    "select_remediation_plan",
]
