"""
Aperture Guard — Permanent Regression Detector for Capital Aperture Erosion.

Post Phase 1.3.4 (2026-05-31): All four known structural bypass mechanisms
(B-001 through B-004) have been eliminated. The late authoritative Admission
Chain + Final Arbitration is now the only effective path to the broker in
strict modes (real, sim_real_guard).

This module is retained as a **permanent tripwire**. Any future code that
attempts to introduce a new bypass or shortcut around the authoritative gate
and calls this function will be made immediately and loudly impossible to
ignore:

- In strict modes: LuminaError(FATAL_MODE_VIOLATION) + ConstitutionViolation event.
- In non-strict modes: extremely loud warning with explicit guidance.

The existence of this detector, combined with the absence of any functional
bypass paths, makes re-introduction of trusted-path erosion a first-class,
observable failure that cannot be done silently.

See:
- evolution/log/2026-05-31-elon-phase1-3-4-zero-trace-hygiene-complete.md
- project-dna/lumina/operating-system/rules/aperture.yaml
"""

from __future__ import annotations

import logging
from typing import Any

from lumina_core.agent_orchestration.schemas import ConstitutionViolation
from lumina_core.engine.errors import ErrorSeverity, LuminaError, log_structured

logger = logging.getLogger("lumina.risk.aperture_guard")

# Track E: align with capital_aperture_lineage strict capital surfaces.
STRICT_MODES = frozenset({"real", "sim_real_guard", "live", "production", "prod"})

__all__ = [
    "STRICT_MODES",
    "enforce_no_bypass_in_strict_mode",
]


def _resolve_mode(engine: Any | None) -> str:
    """Best-effort mode resolution. Mirrors patterns used in broker_bridge and order_gatekeeper."""
    if engine is None:
        return "unknown"
    config = getattr(engine, "config", None)
    mode = str(getattr(config, "trade_mode", "paper") or "paper").strip().lower()
    return mode or "paper"


def _emit_constitution_violation(
    *,
    event_bus: Any | None,
    bypass_id: str,
    mode: str,
    caller: str,
    reason: str,
) -> None:
    """
    Best-effort publish of a ConstitutionViolation on the typed Event Bus.

    Never allowed to block or raise. The hard fail-closed behavior comes from
    the LuminaError raise in the caller, not from this emission.
    """
    if event_bus is None:
        return

    try:
        payload = ConstitutionViolation(
            principle_name="capital_aperture_regression_detector",
            severity="fatal",
            description="Attempt to use bypass/shortcut path around authoritative gate in strict mode",
            detail=f"bypass_id={bypass_id};caller={caller};reason={reason}",
            mode=mode,
        ).model_dump(mode="json")

        event_bus.publish_validated(
            topic="safety.constitution.violation",
            producer="risk.aperture_guard",
            payload=payload,
            metadata={
                "bypass_id": bypass_id,
                "caller": caller,
                "mode": mode,
            },
        )
    except Exception:
        # Best effort only. Do not let telemetry prevent the hard fail-closed path.
        logger.exception("Failed to publish aperture regression ConstitutionViolation (non-fatal)")


def enforce_no_bypass_in_strict_mode(
    *,
    engine: Any | None,
    bypass_id: str,
    caller: str,
    reason: str = "",
) -> None:
    """
    Permanent regression / erosion detector for the capital aperture.

    After Phase 1.3.4 zero-trace hygiene, there are no known or tolerated
    bypass mechanisms. Any code path that feels the need to call this
    function is, by definition, attempting to introduce (or has already
    introduced) a new shortcut around the authoritative Admission Chain +
    Final Arbitration.

    Contract (post 1.3.4):
    - In REAL or sim_real_guard: always raises LuminaError(FATAL) after
      structured logging and best-effort ConstitutionViolation.
    - In all other modes: emits an extremely loud warning so the attempt
      is visible during SIM / paper / research work. The warning explicitly
      directs the developer to the full authoritative gate path.

    This function is intentionally pure. Call it at the earliest possible
    point in any new suspicious shortcut you are tempted to add.
    """
    mode = _resolve_mode(engine)
    is_strict = mode in STRICT_MODES

    if is_strict:
        error = LuminaError(
            severity=ErrorSeverity.FATAL_MODE_VIOLATION,
            code="ATTEMPT_TO_BYPASS_AUTHORITATIVE_GATE_IN_STRICT_MODE",
            message=f"Capital aperture regression: bypass/shortcut attempt detected in strict mode ({mode})",
            context={
                "bypass_id": bypass_id,
                "caller": caller,
                "mode": mode,
                "reason": reason,
            },
        )
        log_structured(error)

        _emit_constitution_violation(
            event_bus=getattr(engine, "event_bus", None),
            bypass_id=bypass_id,
            mode=mode,
            caller=caller,
            reason=reason or "new_bypass_or_shortcut_attempt",
        )

        # Hard fail-closed. This is the permanent invariant.
        raise error

    else:
        # Non-strict modes: make the attempt impossible to ignore during development/SIM.
        logger.warning(
            "APERTURE_REGRESSION_DETECTED: bypass_id=%s caller=%s mode=%s reason=%s — "
            "This path bypasses or shortcuts the authoritative Admission Chain + Final Arbitration. "
            "Use the full gate. See 2026-05-31 Elon aperture hardening (Phase 1.3.4 zero-trace).",
            bypass_id,
            caller,
            mode,
            reason,
        )


# === Historical Note (Post 1.3.4 Zero-Trace Hygiene) ===
# All B-00x constants (BYPASS_OPERATIONS_GOD_FLAG, BYPASS_REASONING_GOD_FLAG,
# BYPASS_BROKER_RECHECK_SKIP / B-004, and the B-001 skip_final_arbitration
# enforcement) were removed during the 1.2.x structural removal + 1.3.x
# deprecation + 1.3.4 hygiene passes.
#
# The guard now enforces a single, simple, permanent rule:
# "There shall be no bypass paths around the late authoritative gate in
# strict modes. Any attempt will be fatal and observable."
#
# This is the lasting output of the 2026-05-31 Elon first-principles
# capital aperture hardening track.