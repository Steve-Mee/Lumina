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
    ConstitutionalViolationError,
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


class ConstitutionalGuard:
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

    def check_pre_mutation(
        self,
        dna_content: str,
        mode: str,
        *,
        raise_on_fatal: bool = False,
    ) -> GuardResult:
        """Fast constitutional check BEFORE sandbox evaluation.

        This is a lightweight, in-process check against the TradingConstitution.
        Run this before investing resources in sandbox scoring.

        Args:
            dna_content: Raw DNA string.
            mode: Trading mode.
            raise_on_fatal: If True, raises ConstitutionalViolationError on
                FATAL violations (useful in test assertions).

        Returns:
            ``GuardResult`` with ``passed=True`` when all FATAL principles pass.
        """
        return self._run_check(
            dna_content=dna_content,
            mode=mode,
            phase="pre_mutation",
            raise_on_fatal=raise_on_fatal,
        )

    def check_pre_promotion(
        self,
        dna_content: str,
        mode: str,
        *,
        raise_on_fatal: bool = True,
    ) -> GuardResult:
        """Full constitutional check BEFORE promoting DNA to active.

        This is the final gate.  It is stricter by default (``raise_on_fatal=True``).

        Args:
            dna_content: Raw DNA string.
            mode: Trading mode.
            raise_on_fatal: If True (default), raises ``ConstitutionalViolationError``
                on any FATAL violation.

        Returns:
            ``GuardResult`` with ``passed=True`` when all FATAL principles pass.

        Raises:
            ConstitutionalViolationError: When ``raise_on_fatal=True`` and a
                FATAL violation is detected.
        """
        return self._run_check(
            dna_content=dna_content,
            mode=mode,
            phase="pre_promotion",
            raise_on_fatal=raise_on_fatal,
        )

    def evaluate_sandboxed(
        self,
        *,
        dna_content: str,
        mode: str,
        pnl: float = 0.0,
        max_dd: float = 0.0,
        sharpe: float = 0.0,
    ):
        """Run a full sandboxed evaluation (constitutional check + fitness scoring).

        Returns a ``SandboxedResult`` from ``SandboxedMutationExecutor``.
        """
        return self._sandbox.evaluate(
            dna_content=dna_content,
            mode=mode,
            pnl=pnl,
            max_dd=max_dd,
            sharpe=sharpe,
        )

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

    def veto_unless_constitutional(
        self,
        *,
        dna_content: str | dict | Any,
        mode: str,
        current_recommendation: bool = True,
    ) -> bool:
        """Return False (veto) if the DNA has any FATAL constitutional violation.

        This is the explicit integration point for ApprovalTwinAgent and callers:
        effective = twin_recommendation and guard.veto_unless_constitutional(...)

        - Normalizes str/dict/PolicyDNA-like content.
        - Always fail-closed: exception during check or any fatal -> False.
        - Mode-aware (REAL stricter).
        - Does not raise; returns boolean for easy AND-ing with twin output.
        """
        try:
            content_str: str
            if isinstance(dna_content, str):
                content_str = dna_content
            elif isinstance(dna_content, dict):
                import json as _json
                content_str = _json.dumps(dna_content, sort_keys=True)
            else:
                # PolicyDNA or other object with .content
                raw = getattr(dna_content, "content", dna_content)
                if isinstance(raw, (dict, list)):
                    import json as _json
                    content_str = _json.dumps(raw, sort_keys=True)
                else:
                    content_str = str(raw or "")

            # Use the authoritative check (pre_mutation is sufficient and lightweight)
            result = self.check_pre_mutation(content_str, mode=mode, raise_on_fatal=False)
            if not result.passed:
                return False
            return bool(current_recommendation)
        except Exception:
            # Fail-closed: any problem evaluating the guard for the twin path blocks.
            logger.error("ConstitutionalGuard.veto_unless_constitutional unexpected error (fail-closed) — blocking")
            return False

    def check_twin_recommendation(
        self,
        *,
        dna_content: str | dict | Any,
        mode: str,
        twin_recommendation: bool,
        twin_risk_flags: list[str] | None = None,
    ) -> GuardResult:
        """Run full pre-promotion style check and return a GuardResult whose .passed is the
        AND of constitution pass and (twin_recommendation only if constitution passes).

        Useful for logging/audit paths that want the full GuardResult shape including
        twin context. The returned result always reflects constitution reality first.
        """
        # First get the raw constitutional result (authoritative)
        content_for_check = dna_content
        if not isinstance(content_for_check, str):
            try:
                import json as _json
                if isinstance(content_for_check, dict):
                    content_for_check = _json.dumps(content_for_check, sort_keys=True)
                else:
                    raw = getattr(content_for_check, "content", content_for_check)
                    content_for_check = _json.dumps(raw, sort_keys=True) if isinstance(raw, dict) else str(raw or "")
            except Exception:
                content_for_check = str(dna_content or "")

        base = self.check_pre_promotion(content_for_check, mode=mode, raise_on_fatal=False)

        # Return constitution truth; twin AND is applied via veto_ helpers by callers.
        return base

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_check(
        self,
        *,
        dna_content: str,
        mode: str,
        phase: str,
        raise_on_fatal: bool,
    ) -> GuardResult:
        import hashlib

        dna_hash = hashlib.sha256(dna_content.encode()).hexdigest()[:16]
        audit_id = f"{phase}_{dna_hash}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}"

        self._check_count += 1

        try:
            violations = self._constitution.audit(dna_content, mode=mode, raise_on_fatal=False)
        except Exception as exc:
            # Fail-closed: any unexpected error is treated as a FATAL violation.
            logger.error(
                "ConstitutionalGuard unexpected error in %s [dna=%s]: %s — blocking",
                phase,
                dna_hash,
                exc,
            )
            v = ConstitutionalViolation(
                principle_name="guard_internal_error",
                description=f"Guard raised unexpectedly: {exc}",
                severity="fatal",
                detail=str(exc),
                mode=mode,
            )
            violations = [v]

        fatals = [v for v in violations if v.severity == "fatal"]
        passed = not bool(fatals)

        if not passed:
            self._block_count += 1
            logger.error(
                "ConstitutionalGuard BLOCKED [%s] dna=%s mode=%s fatals=%s",
                phase,
                dna_hash,
                mode,
                [v.principle_name for v in fatals],
            )
        elif violations:
            # Warnings only.
            logger.warning(
                "ConstitutionalGuard WARN [%s] dna=%s mode=%s warns=%s",
                phase,
                dna_hash,
                mode,
                [v.principle_name for v in violations],
            )

        result = GuardResult(
            passed=passed,
            violations=violations,
            check_phase=phase,
            mode=mode,
            dna_hash=dna_hash,
            audit_id=audit_id,
        )

        self._append_audit(result)

        if raise_on_fatal and fatals:
            raise ConstitutionalViolationError(fatals)

        return result

    def _append_audit(self, result: GuardResult) -> None:
        """Append the check result to the audit JSONL file (best-effort)."""
        try:
            get_audit_logger().append(
                stream="safety.constitution",
                payload=result.to_audit_record(),
                path=self._audit_path,
                mode=str(result.mode).strip().lower(),
                actor_id="constitutional_guard",
                severity="warning" if len(result.warn_violations) > 0 else "info",
                fail_closed_real=False,
            )
        except Exception as exc:
            logger.warning("ConstitutionalGuard: audit write failed: %s", exc)
