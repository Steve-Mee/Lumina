# 2026-05-31 — Phase 1.2.2: Second Structural Removal Slice — Eliminate God-Flag Usage in operations_service (Hot Supervisor Path)

**Parent Plan**: Phase 1.2 Plan (approved) — "Make the Authoritative Check the Only Check"  
**Previous Slice**: 1.2.1 completed (reasoning_service god-flag removed)  
**Impact Class**: Medium-to-Large (removal from the hotter supervisor path in operations_service; higher performance sensitivity).

**Protocol**: This entry is the mandatory formal hypothesis record *before* any 1.2.2 code changes or detailed planning.

---

## Hypothesis

Following the successful removal in reasoning_service (1.2.1), we now remove the god-flag read and skip logic from `operations_service.place_order` (the primary path used by the supervisor loop).

By doing so:
- We eliminate the second FATAL bypass mechanism (B-002) as a structural risk.
- We force the full authoritative late check for the majority of trading decisions in the 1s supervisor loop.
- We generate critical real-world data on the performance cost of always running the late check in the hottest path.
- We validate that the Phase 1.1 `aperture_guard` safety net + early gates are sufficient during removal of high-frequency paths.

This is the next logical, telemetry-driven slice in the approved 1.2 sequence.

**Falsifiable Predictions**:
- Within 14-21 days after merge (heavy SIM + paper-guard load with realistic agent activity): Zero silent B-002 bypasses.
- Measurable performance delta in the supervisor loop is captured and used to decide whether to proceed to 1.2.3 or first invest in gate optimization.
- Guardian Aperture Integrity Score continues to improve (target cumulative +2.0–2.5 from start of 1.2 series after this slice).
- No production-like incidents in guarded modes attributable to this removal.

**Measurement**:
- Guardian aperture scoring + violation events.
- Explicit timing around the late check in the supervisor path.
- Updated bypass inventory (B-002 marked removed).
- Supervisor loop latency / iteration time under load.

---

## Why This Order (1.2.2 after 1.2.1)

- reasoning_service was the lower-risk, lower-frequency path → good first data point.
- operations_service is the primary hot path in the supervisor. Removing it next maximizes the impact on the "trusted path" surface while we still have the safety net.
- The approved Phase 1.2 plan explicitly sequences operations_service as 1.2.2.

---

## Design Approach (High Level, to be detailed in next Plan Mode)

- Remove the god-flag read + Phase 1.1 enforcement block in `operations_service.py`.
- Force `policy_engine.execute_order(..., skip_final_arbitration=False)`.
- Keep all other Phase 1.1 guards (especially B-001 in policy_engine and B-004 in broker_bridge).
- Add strong measurement (latency, call counts) for this specific path.
- Heavy validation in SIM/paper-guard before any consideration of REAL.

The removal will be protected by the existing `aperture_guard` on the remaining bypasses and the fact that the early gate is still performed.

---

## Risks Specific to This Hotter Slice

- Higher potential performance impact on the 1s supervisor loop.
- Higher volume of orders affected → any behavioral change (fresher rejections) will be more visible.
- Greater need for precise measurement and rollback readiness.

**Mitigations** (will be detailed in the implementation plan):
- Start with very aggressive instrumentation.
- Use paper-guard heavily.
- Keep the aperture_guard safety net active.
- Have a fast rollback plan (single file revert + re-enabling the guard block if needed).

---

## Success Criteria for Phase 1.2.2

- God-flag usage completely removed from operations_service.
- All tests + contract tests green.
- At least one high-load validation campaign in SIM + paper-guard with zero silent B-002 bypasses and acceptable performance characteristics.
- Updated bypass inventory (only B-001 and B-004 remaining as FATAL structural mechanisms).
- Public 1.2.2 completion entry with before/after data.
- Clear, evidence-based decision for 1.2.3 vs pausing for gate optimization.

---

## Next Actions (Strict Sequence)

1. This entry (hypothesis locked).
2. Enter dedicated Plan Mode for the detailed 1.2.2 implementation design (following the exact successful pattern of 1.2.1).
3. After approval: implement the removal.
4. Validation campaigns.
5. Publish telemetry + completion entry.
6. Team decision point before 1.2.3.

---

*We continue the disciplined, slice-by-slice elimination of the trusted path mechanisms exactly as defined in the approved Phase 1.2 plan. No steps skipped. Safety net (Phase 1.1) remains the foundation.*

**Focus locked on the end goal: the late authoritative check as the single narrow aperture.**