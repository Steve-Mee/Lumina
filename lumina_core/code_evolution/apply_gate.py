"""H5: Controlled apply of code-evolution proposals to sandbox store only.

Never mutates the live repo tree, risk, broker, or REAL capital paths.
Apply is fail-closed: default off; REAL-like capital always blocked.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.code_evolution.operators import (
    FORBIDDEN_PARAMETER_KEYS,
    PARAMETER_CATALOG,
    validate_parameter_tweak,
)
from lumina_core.code_evolution.proposal import (
    ALLOWED_TARGETS,
    CodeMutationOperator,
    CodeMutationProposal,
)

logger = logging.getLogger(__name__)

REAL_LIKE = frozenset({"real", "live", "prod", "production", "sim_real_guard"})

# Sandbox store relative paths under journal root / applied/
PARAMS_FILE = "params.json"
INDICATORS_DIR = "indicators"
SNIPPETS_DIR = "snippets"
APPLIED_LOG = "applied.jsonl"

_SAFE_ID = re.compile(r"^[\w.\-]{1,80}$")


def is_real_like_capital(mode: str | None) -> bool:
    return str(mode or "").strip().lower() in REAL_LIKE


@dataclass(slots=True)
class ApplyPolicy:
    """Operator-facing apply policy (config-driven, fail-closed defaults)."""

    apply_enabled: bool = False
    require_human_approve: bool = True
    forbid_apply_in_real_capital: bool = True
    require_sandbox_pass: bool = True
    require_constitution_pass: bool = True
    require_twin_recommendation: bool = True  # when human marker absent
    # Twin sole-apply only when human marker not required and twin says go
    allow_twin_judgment_apply: bool = False

    @classmethod
    def from_config(cls, cfg: dict[str, Any] | None) -> ApplyPolicy:
        c = dict(cfg or {})
        return cls(
            apply_enabled=bool(c.get("apply_to_sandbox_store", c.get("apply_enabled", False))),
            require_human_approve=bool(c.get("require_human_approve_for_apply", True)),
            forbid_apply_in_real_capital=bool(c.get("forbid_apply_in_real_capital", True)),
            require_sandbox_pass=bool(c.get("require_sandbox_pass", True)),
            require_constitution_pass=bool(c.get("require_constitution_pass", True)),
            require_twin_recommendation=bool(c.get("require_twin_recommendation", True)),
            allow_twin_judgment_apply=bool(c.get("allow_twin_judgment_apply", False)),
        )


@dataclass(slots=True)
class ApplyEvidence:
    """Evidence required for a controlled sandbox apply."""

    proposal: CodeMutationProposal
    capital_mode: str = "sim"
    constitution_passed: bool = False
    sandbox_passed: bool = False
    twin_recommendation: bool = False
    twin_effective: bool = False
    human_approved: bool = False
    human_approver: str = ""
    violations: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ApplyGateDecision:
    allowed: bool
    reason: str
    fail_reasons: list[str] = field(default_factory=list)
    policy: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "fail_reasons": list(self.fail_reasons),
            "policy": dict(self.policy),
        }


from lumina_core.code_evolution.apply_gate_ops import CodeEvolutionApplyOpsMixin

class CodeEvolutionApplyGate(CodeEvolutionApplyOpsMixin):
    """Fail-closed gate + sandbox-store writer for H5 controlled apply."""

    def __init__(
        self,
        *,
        journal_root: Path | str,
        policy: ApplyPolicy | None = None,
    ) -> None:
        self.root = Path(journal_root)
        self.pending_root = self.root / "pending"
        self.applied_root = self.root / "applied"
        self.policy = policy or ApplyPolicy()
        self.applied_root.mkdir(parents=True, exist_ok=True)
        self.pending_root.mkdir(parents=True, exist_ok=True)

    def is_human_approved(self, proposal_id: str) -> tuple[bool, str]:
        marker = self.pending_root / proposal_id / "APPROVED"
        if not marker.exists():
            return False, ""
        try:
            text = marker.read_text(encoding="utf-8", errors="ignore").strip()
        except OSError:
            return False, ""
        return True, text or "approved"

    def evaluate(self, evidence: ApplyEvidence) -> ApplyGateDecision:
        """Check whether sandbox apply is permitted (does not write)."""
        policy = self.policy
        fails: list[str] = []
        pol = {
            "apply_enabled": policy.apply_enabled,
            "require_human_approve": policy.require_human_approve,
            "forbid_apply_in_real_capital": policy.forbid_apply_in_real_capital,
            "allow_twin_judgment_apply": policy.allow_twin_judgment_apply,
        }

        if not policy.apply_enabled:
            return ApplyGateDecision(
                allowed=False,
                reason="apply_disabled",
                fail_reasons=["apply_disabled"],
                policy=pol,
            )

        if policy.forbid_apply_in_real_capital and is_real_like_capital(evidence.capital_mode):
            fails.append("capital_mode_real")

        prop = evidence.proposal
        target = str(prop.target or "")
        if target not in ALLOWED_TARGETS:
            fails.append("target_not_sandbox")

        if policy.require_constitution_pass and not evidence.constitution_passed:
            fails.append("constitution_not_passed")
        if policy.require_sandbox_pass and not evidence.sandbox_passed:
            fails.append("sandbox_not_passed")

        human_ok = bool(evidence.human_approved)
        if not human_ok:
            ok_m, _ = self.is_human_approved(prop.proposal_id)
            human_ok = ok_m

        twin_ok = bool(evidence.twin_recommendation)
        if policy.require_human_approve and not human_ok:
            # Twin sole path only if explicitly allowed
            if not (
                policy.allow_twin_judgment_apply
                and twin_ok
                and (evidence.twin_effective or twin_ok)
            ):
                fails.append("human_approval_required")
        elif policy.require_twin_recommendation and not twin_ok and not human_ok:
            fails.append("twin_or_human_required")

        # Operator re-validation for param tweaks
        op = prop.operator
        if isinstance(op, str):
            try:
                op = CodeMutationOperator(op)
            except ValueError:
                fails.append("unknown_operator")
                op = None
        if op == CodeMutationOperator.PARAMETER_TWEAK:
            payload = prop.payload or {}
            key = str(payload.get("key") or "")
            if key in FORBIDDEN_PARAMETER_KEYS or key not in PARAMETER_CATALOG:
                fails.append("parameter_not_allowed")
            else:
                try:
                    old_v = float(payload.get("old_value"))
                    new_v = float(payload.get("new_value"))
                except (TypeError, ValueError):
                    fails.append("parameter_non_numeric")
                else:
                    for name in validate_parameter_tweak(key, old_v, new_v):
                        fails.append(name)

        if fails:
            return ApplyGateDecision(
                allowed=False,
                reason="apply_gate_blocked",
                fail_reasons=fails,
                policy=pol,
            )
        return ApplyGateDecision(
            allowed=True,
            reason="apply_gate_ok",
            fail_reasons=[],
            policy=pol,
        )

__all__ = [
    "ApplyEvidence",
    "ApplyGateDecision",
    "ApplyPolicy",
    "CodeEvolutionApplyGate",
    "is_real_like_capital",
]
