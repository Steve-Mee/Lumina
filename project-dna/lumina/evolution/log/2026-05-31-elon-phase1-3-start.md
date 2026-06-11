# 2026-05-31 — Phase 1.3: Cleanup, Deprecation & Full Removal of Remaining Trusted-Path Mechanisms

**Parent**: Phase 1.2 completion (`2026-05-31-elon-phase1-2-3-complete.md`)  
**Decision**: User explicitly chose to proceed to Phase 1.3 (cleanup & deprecation) instead of the parallel gate optimization track.

**Protocol Status**: This entry formally opens Phase 1.3 and serves as the high-level hypothesis before any detailed sub-slice planning or implementation begins.

---

## Context & Current State

With the completion of Phase 1.2.3, the structural removal work is done:

- B-002, B-003, and B-004 have been eliminated or made ineffective.
- Only **B-001** (the `skip_final_arbitration` parameter in `policy_engine.execute_order`) remains as an active structural mechanism under `aperture_guard` enforcement.
- The god-flag (`admission_chain_final_arbitration_approved`) is no longer read in any hot path for skipping purposes.
- The `skip_admission_chain_recheck` metadata short-circuit is defused in strict modes.

The "trusted path" architecture has been dismantled. What remains is **dead or near-dead code**, outdated state, scattered references, and documentation that still reflects the old reality.

---

## Hypothesis for Phase 1.3

By executing a dedicated cleanup and deprecation phase (Phase 1.3), we will:

- Remove all remaining technical debt from the old trusted-path optimization (god-flag, related state, dead setters, dead enforcement code).
- Make the system accurately reflect the new architectural truth: **the late authoritative Admission Chain + Final Arbitration is the single narrow, un-bypassable aperture**.
- Reduce cognitive load and attack surface for future evolution.
- Update all documentation, tests, and external interfaces so the new reality is the default mental model.
- Create a clean foundation before (or in parallel with) the gate optimization track.

**Falsifiable Predictions**:
- After Phase 1.3, a new developer or agent reading the core risk/order-flow code will no longer encounter references to the old god-flag or trusted-path skips as active mechanisms.
- The god-flag field in `runtime_state.py` and the state facade can be safely removed or turned into pure observability.
- All references to the removed B-00x mechanisms are gone from production code and active tests.
- Guardian Aperture Integrity Score remains stable or improves slightly due to reduced complexity.
- Future 1.2-style bypass attempts become structurally much harder to introduce.

---

## Scope of Phase 1.3 (High Level)

Phase 1.3 is primarily **cleanup and truth-alignment**, not new enforcement or removal of still-active mechanisms.

Key work packages (to be broken into sub-slices with their own hypotheses):

1. **God-flag & State Cleanup**
   - Deprecate and eventually remove `admission_chain_final_arbitration_approved` from `runtime_state.py`, `engine_state_facade.py`, and all related code.
   - Remove or convert to pure observability the writing of this flag in `order_gatekeeper.py`.

2. **Final B-001 Handling**
   - Decide on and execute the removal (or permanent hardening) of the last remaining active mechanism (B-001 in policy_engine).
   - This may be the last "structural" action before full cleanup.

3. **Dead Code & Reference Removal**
   - Remove all Phase 1.1 enforcement blocks for B-002/B-003/B-004.
   - Clean up now-unused constants and code paths in `aperture_guard.py`.
   - Update or remove tests that were written specifically around the old bypasses.

4. **Documentation & Architecture Alignment**
   - Major updates to `current-reality/architecture.md`, `anti-patterns.md`, `evolutionary-debt.md`.
   - Update AGENTS.md and the DNA Guardian rules if needed.
   - Update the bypass inventory to its final "post-1.2 reality" state.
   - Possibly create a new ADR documenting the death of the trusted-path optimization.

5. **Test & Tooling Hygiene**
   - Remove or update tests that relied on the old skips.
   - Ensure Guardian and other meta-tools no longer need special cases for these mechanisms.

---

## Principles for This Phase

- **Small, documented sub-slices** — Each major cleanup area (god-flag, B-001 final removal, docs, tests) gets its own hypothesis entry + Plan Mode if it touches core risk code.
- **Safety net remains** — The Phase 1.1 `aperture_guard` (now primarily protecting B-001) stays active until we decide B-001 itself is permanently resolved.
- **Reversibility** — Deprecations are done with clear timelines and comments before hard deletion.
- **Truth-seeking** — The system and its documentation must no longer lie about the architecture.

---

## Success Criteria for Phase 1.3 (Overall)

- Zero references to the old trusted-path mechanisms (god-flag usage for skipping, B-002/B-003/B-004) as active, functional paths in production code.
- The god-flag is either removed or explicitly marked as deprecated/observability-only.
- All core documentation (architecture, debt, AGENTS.md, etc.) accurately describes the new narrow-aperture reality.
- A clean, low-surprise codebase for the next major work (gate optimization or further aperture hardening).
- Public closure entry for Phase 1.3 that confirms the post-1.2 architecture is now the documented default.

---

## Relationship to Other Work

Phase 1.3 can run in parallel with (or before) the gate optimization track. In fact, cleaning up the old mechanisms first will make optimization work cleaner and less confusing.

---

## Immediate Next Steps

1. This entry (Phase 1.3 opened).
2. Break Phase 1.3 into logical sub-slices (starting with god-flag deprecation + state cleanup, and/or final B-001 resolution).
3. For each sub-slice: formal hypothesis entry → Plan Mode → implementation (following the exact same discipline as the 1.2.x series).
4. Regular public updates via evolution entries.

---

*Phase 1.2 structural removal is complete. We now enter the necessary hygiene and truth-alignment phase before declaring the aperture hardening work "architecturally done" at this level.*

**We continue with the same iron discipline. No steps skipped.**

**Focus remains absolute on the end goal: a narrow, typed, un-bypassable, fully observable capital aperture that enables safe, high-velocity self-evolution.**