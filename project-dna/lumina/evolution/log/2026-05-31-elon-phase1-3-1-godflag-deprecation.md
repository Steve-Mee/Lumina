# 2026-05-31 — Phase 1.3.1: God-Flag Deprecation & State Cleanup (First Sub-Slice of Phase 1.3)

**Parent**: Approved Phase 1.3 Plan (2026-05-31)  
**Recommended Starting Slice**: 1.3.1 — God-Flag Deprecation & State Cleanup (highest priority per the plan).

**Protocol Status**: This entry is the mandatory formal hypothesis record for the first concrete sub-slice of Phase 1.3, written before any detailed design or implementation work begins.

---

## Hypothesis

Now that the structural removal work of Phase 1.2 is complete, the `admission_chain_final_arbitration_approved` god-flag has become dead or near-dead code in the capital execution path:

- It is no longer read for decision-making in any hot path (reasoning_service and operations_service removed in 1.2.1/1.2.2).
- It is still being written in `order_gatekeeper.py` after every successful early admission.
- It remains defined in `runtime_state.py` and exposed via the state facade.

By executing a dedicated deprecation and cleanup sub-slice (1.3.1), we will:

- Stop writing the god-flag in the early gate (or clearly mark it as deprecated/observability-only).
- Remove or convert the field from `runtime_state.py`.
- Update or remove the mapping in the state facade.
- Clean up all references, comments, and the one remaining direct test assertion.
- Reduce the visible surface of the old trusted-path architecture.

This is the highest-ROI first sub-slice of Phase 1.3 because the god-flag is one of the most visible remnants of the pre-1.2 "trusted path" design.

**Falsifiable Predictions**:
- After this slice, the god-flag will no longer be written during normal order flow in strict modes (or will be accompanied by a clear deprecation warning).
- A search for `admission_chain_final_arbitration_approved` in production code will return only state definition, facade (if kept for backward compat), and deprecation comments.
- The direct assertion in `test_admission_chain_canonical.py` will be removed or heavily updated.
- No production or test breakage occurs from this cleanup.

---

## Scope of 1.3.1 (Focused)

This slice is deliberately narrow:

- **Primary target**: The god-flag itself and its immediate infrastructure.
- **In scope**:
  - `order_gatekeeper.py` — stop writing or add deprecation around the setattr.
  - `runtime_state.py` — remove the field or mark it deprecated.
  - `engine_state_facade.py` — remove or deprecate the mapping.
  - `test_admission_chain_canonical.py` — update/remove the assertion.
  - Comments and docstrings across the touched files.
- **Out of scope for this slice**:
  - Final resolution of B-001 (that is 1.3.2).
  - Broad documentation overhaul (that is 1.3.4).
  - Test hygiene beyond the direct god-flag assertion.

---

## Design Approach (High Level)

**Recommended path (controlled deprecation)**:

1. In `order_gatekeeper.py`:
   - Add a clear deprecation warning (via logger + possibly a one-time ConstitutionViolation-style event) the first time the flag would be set in strict modes.
   - Consider stopping the write entirely in strict modes after a short transition, or keep writing it as pure observability with a comment.

2. In `runtime_state.py`:
   - Remove the field, or keep it with a deprecation comment and default=False.

3. In `engine_state_facade.py`:
   - Remove the mapping or mark it as deprecated/read-only.

4. In the single test:
   - Remove or update the assertion that expects the flag to be True after a successful early gate.

All changes should be accompanied by comments referencing this 1.3.1 entry and the broader 2026-05-31 Elon aperture work.

---

## Risks & Mitigations

- **Some obscure code path still reads the god-flag**: Low risk after 1.2.1/1.2.2, but possible in internal tools or future code.
  - Mitigation: Add a deprecation warning on write (and optionally on read if we keep the field temporarily). Telemetry will surface usage quickly.

- **Test that hard-asserts on the flag breaks**: Expected and easy to fix.
  - Mitigation: Update the test as part of this slice.

- **State persistence / migration concerns**: The flag was being persisted via the facade. Removing it may affect old state snapshots.
  - Mitigation: Since we are in a cleanup phase after major architectural change, we accept that old persisted state may lose this field. Document it.

---

## Success Criteria for 1.3.1

- The god-flag is no longer written during normal operation in strict modes (or is written with explicit deprecation signaling).
- The field is removed from `runtime_state.py` (or clearly marked deprecated).
- The mapping is removed from the state facade.
- The direct test assertion is updated/removed.
- All changes are documented with references to this entry.
- A public 1.3.1 completion entry is published.
- No unexpected breakage in SIM or paper-guard validation.

---

## Relationship to Later 1.3 Sub-Slices

This slice is intentionally sequenced first because:
- It has relatively low blast radius now that no hot paths read the flag for decisions.
- It gives a quick, visible "win" in cleaning up the old architecture.
- It reduces the number of moving parts before we tackle the more sensitive B-001 final resolution in 1.3.2.

---

## Immediate Next Actions

1. This hypothesis entry.
2. Enter dedicated Plan Mode for the detailed implementation design of 1.3.1.
3. After approval: execute the changes following the established discipline.
4. Validation + public completion entry.
5. Then proceed to 1.3.2 (B-001 final resolution) or another high-priority sub-slice.

---

*Phase 1.3 has begun. We start with the most visible piece of dead trusted-path state: the god-flag.*

**We continue with the same iron discipline. No steps skipped. Full protocol followed.**

**Focus remains absolute on making the post-1.2 narrow-aperture reality the clear, documented, and only truth in the system.**