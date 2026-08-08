"""ConstitutionalGuard — the single integration point for all AGI safety checks.

Every mutation path in the evolution loop MUST call one of the two guard
methods before acting on a DNA candidate:

    guard.check_pre_mutation(dna_content, mode)
        — called before sandbox evaluation; blocks instantly on fatal violations.

    guard.check_pre_promotion(dna_content, mode)
        — called after sandbox scoring; final gate before live promotion.

Both methods are synchronous and fail-closed: any unexpected error blocks
the mutation/promotion rather than allowing it through.

Architecture:
  - ConstitutionalGuard is instantiated once per EvolutionOrchestrator.
  - It owns a TradingConstitution reference and a SandboxedMutationExecutor.
  - Audit records are appended to ``state/constitutional_audit.jsonl`` for
    forensic review.

Usage::

    guard = ConstitutionalGuard()

    # Before generating mutations:
    result = guard.check_pre_mutation(dna_content, mode="real")
    if not result.passed:
        logger.error("Pre-mutation blocked: %s", result.violation_names)
        return

    # After sandbox scoring, before registering DNA:
    result = guard.check_pre_promotion(dna_content, mode="real")
    if not result.passed:
        raise ConstitutionalViolationError(result.fatal_violations)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

from lumina_core.audit import get_audit_logger
from lumina_core.safety.trading_constitution import (
    ConstitutionalViolation,
    TradingConstitution,
    TRADING_CONSTITUTION,
)
from lumina_core.safety.sandboxed_executor import SandboxedMutationExecutor

logger = logging.getLogger(__name__)

_DEFAULT_AUDIT_FILE: Final[str] = "state/constitutional_audit.jsonl"


# ---------------------------------------------------------------------------
# Guard result
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class GuardResult:
    """Result of a pre-mutation or pre-promotion constitutional check.

    Attributes:
        passed:           True when no FATAL violations were found.
        violations:       Full list of violations (FATAL + WARN).
        check_phase:      ``"pre_mutation"`` or ``"pre_promotion"``.
        mode:             Trading mode the check was run under.
        dna_hash:         First 16 chars of the SHA-256 of the DNA content.
        audit_id:         Unique ID for this check (timestamp-based).
    """

    passed: bool
    violations: list[ConstitutionalViolation]
    check_phase: str
    mode: str
    dna_hash: str = ""
    audit_id: str = ""

    @property
    def fatal_violations(self) -> list[ConstitutionalViolation]:
        return [v for v in self.violations if v.severity == "fatal"]

    @property
    def warn_violations(self) -> list[ConstitutionalViolation]:
        return [v for v in self.violations if v.severity == "warn"]

    @property
    def violation_names(self) -> list[str]:
        return [v.principle_name for v in self.violations]

    @property
    def fatal_count(self) -> int:
        return len(self.fatal_violations)

    def to_audit_record(self) -> dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "check_phase": self.check_phase,
            "mode": self.mode,
            "dna_hash": self.dna_hash,
            "passed": self.passed,
            "fatal_count": self.fatal_count,
            "warn_count": len(self.warn_violations),
            "violation_names": self.violation_names,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ---------------------------------------------------------------------------
# ConstitutionalGuard
# ---------------------------------------------------------------------------

from lumina_core.safety.constitutional_guard_checks import (  # noqa: E402
    ConstitutionalGuardChecksMixin,
)


class ConstitutionalGuard(ConstitutionalGuardChecksMixin):
    """Top-level AGI safety gate integrating constitution + sandbox evaluation.

    Parameters
    ----------
    constitution:
        ``TradingConstitution`` instance.  Defaults to the global singleton
        ``TRADING_CONSTITUTION`` which contains all 15 principles.
    sandbox:
        ``SandboxedMutationExecutor`` for subprocess isolation.  Created
        automatically if not provided.
    audit_path:
        Path to the JSONL audit file.  Defaults to
        ``$LUMINA_STATE_DIR/constitutional_audit.jsonl`` or
        ``state/constitutional_audit.jsonl``.
    """

    def __init__(
        self,
        constitution: TradingConstitution | None = None,
        sandbox: SandboxedMutationExecutor | None = None,
        audit_path: Path | str | None = None,
    ) -> None:
        self._constitution = constitution or TRADING_CONSTITUTION
        self._sandbox = sandbox or SandboxedMutationExecutor()

        if audit_path is not None:
            self._audit_path = Path(audit_path)
        else:
            state_dir = os.getenv("LUMINA_STATE_DIR", "state")
            self._audit_path = Path(state_dir) / "constitutional_audit.jsonl"
        get_audit_logger().register_stream("safety.constitution", self._audit_path)

        self._check_count = 0
        self._block_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------




    @property
    def stats(self) -> dict[str, int]:
        """Return running statistics: total checks and total blocks."""
        return {"checks": self._check_count, "blocks": self._block_count}

    @property
    def constitution(self) -> TradingConstitution:
        """Expose the underlying constitution (read-only)."""
        return self._constitution

    # ------------------------------------------------------------------
    # Twin subordination helpers (explicit fail-closed paths)
    # ------------------------------------------------------------------



    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------


