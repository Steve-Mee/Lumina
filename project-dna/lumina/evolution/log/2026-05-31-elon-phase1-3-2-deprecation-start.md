# 2026-05-31 — Phase 1.3.2: Deprecation Window Started for B-001

**Parent**: `2026-05-31-elon-phase1-3-2-b001-final-resolution.md` + approved 1.3.2 implementation plan.

**Status**: **Deprecation phase active** (hard removal to follow after telemetry window).

---

## What Was Delivered (Deprecation Phase)

- Added strong, observable deprecation signaling in `policy_engine.execute_order` when `skip_final_arbitration=True` is received:
  - Loud logger warning.
  - Best-effort `ConstitutionViolation` event on the bus with `deprecated: true` metadata.
- Updated call sites in `operations_service.py` and `reasoning_service.py` with clear comments.
- Updated `aperture_guard.py` documentation to reflect the new status of B-001.
- Updated the bypass inventory.

**Safety net**: The existing Phase 1.1 fatal behavior in strict modes (via `enforce_no_bypass_in_strict_mode`) remains fully active and unchanged during the deprecation window.

---

## Current State

B-001 is now in a **controlled, observable final deprecation window**.

Any code (internal, test, or future) that still attempts to use the old skip will:
- Be loudly warned in logs.
- Emit a ConstitutionViolation event (visible on the Event Bus).
- Still be fatally blocked in `real` and `sim_real_guard` modes (existing safety net).

This gives us clean telemetry to decide when it is safe to perform the final hard removal of the parameter.

---

## Next (Per Approved Plan)

- Run with deprecation active in SIM + paper-guard (and any internal environments).
- Monitor for usage via logs and `safety.constitution.violation` events with `deprecated: true`.
- Once telemetry shows near-zero usage for a sufficient period (recommended 30-45 days, or shorter if data is clean): proceed to the hard removal step of 1.3.2.
- Publish a follow-up completion entry when the hard removal is executed.

**Phase 1.3.2 deprecation phase has begun. The last active mechanism from the original diagnosis is now on a clear path to elimination.**

*Disciplined, professional, telemetry-driven final cleanup.*