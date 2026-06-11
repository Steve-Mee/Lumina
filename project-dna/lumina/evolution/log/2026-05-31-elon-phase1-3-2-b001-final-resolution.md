# 2026-05-31 — Phase 1.3.2: B-001 Final Resolution (Last Active Structural Mechanism)

**Parent**: Approved Phase 1.3 Plan (2026-05-31)  
**Previous Sub-Slice**: 1.3.1 (God-Flag Deprecation) successfully completed.  
**Focus of this sub-slice**: Final resolution of the last remaining active FATAL structural bypass mechanism: **B-001** (the `skip_final_arbitration` parameter in `policy_engine.execute_order`).

**Protocol Status**: This entry is the mandatory formal hypothesis record for 1.3.2, written before any detailed design or implementation work on this sub-slice begins.

---

## Context

After the completion of Phase 1.2 and 1.3.1:

- B-002, B-003, and B-004 have been structurally removed or made ineffective.
- The god-flag has been deprecated and cleaned up.
- **Only B-001 remains** as an active, callable mechanism that can still cause a bypass of the full Admission Chain + Final Arbitration in `policy_engine.execute_order`.

This parameter is still protected by the Phase 1.1 `aperture_guard` (fatal in strict modes), but the mechanism itself has not yet been removed or permanently hardened. It is the last piece of the original "trusted path optimization" architecture that was diagnosed as a critical single point of failure in the 2026-05-31 Elon first-principles analysis.

---

## Hypothesis

By executing a dedicated final resolution sub-slice for B-001 (1.3.2), we will:

- Bring the last active structural bypass mechanism to a clean, intentional, and permanent state (either removed or placed under strict, observable, time-boxed deprecation).
- Eliminate the final remaining way for code to request skipping the authoritative late check in the capital execution path.
- Complete the core structural goal of the entire 1.2 + 1.3 series: there are no longer any functional trusted-path bypass mechanisms in the system.
- Create maximum clarity and safety for all future work (including any gate optimization efforts).

**Falsifiable Predictions**:
- After this sub-slice, there will be zero remaining code paths that can request a bypass of the full late authoritative check via the old B-001 mechanism.
- The `skip_final_arbitration` parameter will either no longer exist or will be non-functional / always fatal in strict modes with clear deprecation signaling.
- Guardian Aperture Integrity Score will reflect the final major improvement from this long-running aperture hardening track.
- Future attempts to re-introduce similar "skip the authoritative check" logic will be structurally much harder and more visible.

---

## Option Evaluation (from the approved parent Phase 1.3 plan)

### Option A — Recommended: Controlled Deprecation Window + Final Removal
- Keep the parameter temporarily for backward compatibility.
- Make any use of `skip_final_arbitration=True` trigger loud deprecation warnings + ConstitutionViolation events (even in non-strict modes).
- In strict modes: it remains fatal (current behavior via aperture_guard).
- After a defined, documented deprecation period (e.g. 45–60 days), remove the parameter entirely or make it a hard no-op that always forces the full check.

**Pros**: Lowest risk of breaking obscure call sites or internal tools. Provides clear telemetry on any remaining usage. Graceful and professional.

**Cons**: Slightly more work and calendar time than immediate deletion.

### Option B — Immediate Hard Removal
- Delete the parameter from the function signature and all call sites.
- Always run the full gate.

**Pros**: Fastest possible cleanup. Cleanest final code.

**Cons**: Higher risk of discovering hidden usage only after the fact. Less professional than a proper deprecation for a mechanism that has existed for a long time.

**Decision**: Execute **Option A** (controlled deprecation + final removal). This is the safer, more disciplined choice and is fully consistent with how we handled similar situations earlier in the track.

---

## Scope of 1.3.2

**In scope**:
- Final resolution of the `skip_final_arbitration` parameter in `policy_engine.py`.
- Updating the two remaining call sites (`operations_service` and `reasoning_service` — already passing `False` after 1.2.x, but the parameter itself still exists).
- Updating `aperture_guard.py` (B-001 enforcement can be adjusted or removed once the mechanism is gone).
- Adding proper deprecation signaling and telemetry.
- Updating relevant tests.
- Clear documentation of the deprecation timeline and final removal date.

**Out of scope for this sub-slice**:
- Broader documentation overhaul (1.3.4).
- Large-scale test hygiene beyond what is directly related to B-001.
- Any changes to the remaining aperture_guard enforcement logic for other (already removed) mechanisms.

---

## Design Approach (High Level)

1. In `policy_engine.py`:
   - Add deprecation logic when `skip_final_arbitration=True` is received.
   - In strict modes: keep the existing fatal behavior via aperture_guard (or strengthen it).
   - In non-strict modes: emit strong deprecation warnings + ConstitutionViolation events.

2. Update call sites:
   - Ensure `operations_service` and `reasoning_service` continue to (or explicitly) pass `False`.
   - Remove any remaining conditional logic that could still pass `True`.

3. In `aperture_guard.py`:
   - Once the deprecation period ends and the parameter is removed, B-001 can be taken out of the active bypass list.

4. Documentation:
   - Add clear comments and references to this entry.
   - Update the bypass inventory to reflect that B-001 is now in final deprecation.

5. Telemetry:
   - Ensure any use of the old path is loudly visible in logs and on the Event Bus.

---

## Risks & Mitigations

- **Undiscovered call sites** that still pass `skip_final_arbitration=True`:
  - Mitigation: Strong deprecation warnings + ConstitutionViolation events will surface them quickly. We keep the fatal behavior in strict modes as a safety net.

- **Test breakage**:
  - Mitigation: Expected and manageable. Update tests as part of the slice.

- **Desire to move faster**:
  - Mitigation: The controlled deprecation path gives us data and safety. If telemetry shows zero usage after a short period, we can accelerate the final removal.

---

## Success Criteria for 1.3.2

- The `skip_final_arbitration` parameter is either removed or placed under strict, observable, time-boxed deprecation with clear signaling.
- No remaining production paths can silently request a bypass via this old mechanism.
- The bypass inventory is updated to reflect that B-001 is in its final resolved state.
- A public 1.3.2 completion entry is published.
- All relevant tests pass.
- Clear handoff to the remaining 1.3 sub-slices (especially documentation alignment).

---

## Relationship to the Rest of Phase 1.3

This sub-slice is the natural and highest-priority follow-up to 1.3.1 because:
- It resolves the last *active* structural mechanism (not just dead state).
- It provides the final major improvement to the Aperture Integrity Score from the entire 1.2 + 1.3 series.
- Once B-001 is resolved, the rest of Phase 1.3 becomes mostly documentation, test hygiene, and architectural alignment work.

---

## Immediate Next Actions

1. This hypothesis entry.
2. Enter dedicated Plan Mode for the detailed implementation design of 1.3.2 (following the exact same successful pattern as 1.3.1).
3. After approval: execute the deprecation + final removal work.
4. Validation + public completion entry.
5. Proceed to the remaining 1.3 sub-slices (particularly 1.3.4 — documentation and architecture alignment).

---

*Phase 1.3 continues with the same iron discipline.*

**We are now resolving the very last active piece of the original trusted-path architecture diagnosed in the 2026-05-31 Elon first-principles analysis.**

**Focus remains absolute on completing the narrow, typed, un-bypassable capital aperture.**