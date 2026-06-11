# 2026-05-31 — Phase 1.2.1: First Structural Removal Slice — Eliminate God-Flag Usage in reasoning_service (Elon Aperture Hardening)

**Parent Plan**: Phase 1.2 Plan (approved 2026-05-31) — "Make the Authoritative Check the Only Check"  
**Parent Completion**: `2026-05-31-elon-phase1-1-complete.md`  
**Impact Class**: Medium (removal of cached approval usage in one specific caller path; safety net from Phase 1.1 remains fully active).

**Protocol Status**: This entry is the mandatory formal record *before* any removal code is written or further detailed design sessions begin.

---

## Hypothesis

By removing the god-flag read (`admission_chain_final_arbitration_approved`) and the associated skip logic from `reasoning_service.submit_order`, and forcing that path to always go through the full `policy_engine.execute_order` (which itself is now guarded by `aperture_guard`), we will:

- Eliminate one of the four FATAL bypass mechanisms (B-003) as a structural risk.
- Generate clean telemetry on the actual cost and frequency of the late authoritative check for reasoning-driven orders.
- Prove that the Phase 1.1 safety net (`aperture_guard`) works in practice during real removal work.
- Move the system one measurable step closer to having the late authoritative Admission Chain + Final Arbitration as the *only* path.

This is the smallest possible structural removal slice that delivers real progress while maintaining full reversibility and safety.

**Falsifiable Predictions**:
- Within 14 days of merge in SIM + paper-guard under load: Zero silent bypasses via the old reasoning path (enforced by `aperture_guard`).
- Guardian Aperture Integrity Score improves by at least +1.0–1.5 points attributable to this removal (combined with P1.1 enforcement).
- Performance impact in the supervisor loop for reasoning-driven orders is measured and acceptable (or triggers the parallel optimization track).
- The removal is fully rolled back within one commit if any unexpected issues appear.

**Measurement**:
- Guardian (aperture scoring + violation events).
- Structured error logs containing `APERTURE_BYPASS_*`.
- Explicit timing instrumentation around the late check for reasoning orders.
- Updated bypass inventory.

---

## Why Start with reasoning_service?

From the approved Phase 1.2 plan and exploration:
- It is one of the three god-flag readers.
- The reasoning path is often used for more deliberate (less high-frequency) decisions compared to the pure supervisor hot loop in operations_service.
- Removing it first gives us lower-risk data on the cost of always running the late check.
- It is a clean, contained caller.

The harder hot-loop paths (`operations_service` + direct broker paths in runtime_workers) are intentionally left for later slices (1.2.2 / 1.2.3).

---

## Design for This Slice (High Level)

1. **Remove the god-flag read and skip logic** in `reasoning_service.py` (around the current Phase 1.1 instrumentation).
2. **Ensure the call always goes through** `policy_engine.execute_order(...)` without the skip parameter (or with it forced to False).
3. **Update `aperture_guard`** if needed to cover any new/remaining surface (unlikely).
4. **Add / update tests** that prove:
   - The old skip path no longer exists for this caller.
   - `aperture_guard` still catches any attempt to re-introduce similar logic.
5. **Add lightweight measurement** (timing + counters) around the late check for this path.
6. **Update documentation** (bypass inventory, state facade comments if relevant).

The Phase 1.1 `aperture_guard` calls remain in place as the permanent safety net.

---

## Evolvability Impact

Positive. We are removing a piece of mutable shared god-state and a trusted-path optimization. This makes the risk layer easier to reason about and evolve in the future.

Estimated delta: +0.5 to +0.8 on the risk/aperture evolvability dimension.

---

## Reversibility & Rollback

Extremely high:
- The change is localized to one file (reasoning_service.py) + test updates.
- The old god-flag read + skip logic can be restored in a single revert.
- `aperture_guard` will continue to protect the system even if the removal is rolled back.
- No persistent state migration is required for this slice.

Rollback trigger examples: unacceptable latency in reasoning-driven orders, unexpected test failures in paper-guard, or any REAL-mode incident during validation.

---

## Risk Analysis (Specific to This Slice)

- **Performance**: Reasoning-driven orders may now always pay the full late check cost. Mitigation: We measure it explicitly. If bad, we pause and prioritize the parallel gate optimization track before touching the hotter operations path.
- **Behavioral change**: Some reasoning orders that previously relied on the cached approval may now get rejected by fresher checks. This is *desired* (correctness over optimization). The safety net catches any real breakage.
- **Test coverage**: The existing Phase 1.1 tests + contract tests provide a strong base. We will add specific assertions that the skip path is gone for this caller.

---

## Success Criteria for Phase 1.2.1

- The god-flag read and skip logic is completely removed from `reasoning_service.py`.
- All relevant tests pass in SIM and paper-guard.
- At least one clean, load-bearing campaign (aggressive agent activity) completes with zero silent bypasses on the reasoning path.
- Updated bypass inventory published marking B-003 as "structurally removed (enforcement layer remains)".
- Public completion entry for 1.2.1 with before/after metrics.
- Clear data/decision point for whether to proceed to 1.2.2 or first invest in gate optimization.

---

## Next Immediate Actions (After This Entry)

1. Enter a new (or continued) Plan Mode session specifically for the detailed implementation design of this 1.2.1 slice (if the removal work itself qualifies as requiring it).
2. Implement the removal in reasoning_service + tests + measurement.
3. Run validation campaigns.
4. Publish telemetry + updated inventory + 1.2.1 completion entry.
5. Decide (publicly) on 1.2.2 vs parallel optimization work.

---

*This slice is deliberately small, telemetry-driven, and fully protected by the Phase 1.1 safety net. It is the first real step toward making the authoritative late check the only check.*

**Focus remains absolute**: A narrow, trustworthy, un-bypassable capital aperture that enables safe high-velocity self-evolution.

**Phase 1.2.1 hypothesis locked. Ready for detailed planning and execution.**