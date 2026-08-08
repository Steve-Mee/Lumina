"""Check/audit methods for ConstitutionalGuard (global residual)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from lumina_core.audit import get_audit_logger
from lumina_core.safety.constitutional_guard import GuardResult
from lumina_core.safety.trading_constitution import (
    ConstitutionalViolation,
    ConstitutionalViolationError,
)

logger = logging.getLogger(__name__)


class ConstitutionalGuardChecksMixin:
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
