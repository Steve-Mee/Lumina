# 2026-05-31 — Phase 1.3.3: Setter & Metadata Cleanup (Legacy Bypass Flags)

**Parent**: Approved Phase 1.3 Plan  
**Previous**: 1.3.2 (B-001 hard removal) completed under simulation.

**Protocol Status**: This is the formal hypothesis entry that opens 1.3.3. No implementation work will begin until this entry exists and a dedicated Plan Mode has been completed for the slice.

---

## Context

After the completion of Phase 1.2 (structural removal of all four FATAL bypass mechanisms) and 1.3.1 + 1.3.2 (god-flag + B-001 cleanup):

- The architectural reality has changed dramatically.
- However, **legacy metadata flags and setters** from the old trusted-path era are still scattered throughout the codebase.
- The most prominent remaining one is `skip_admission_chain_recheck` (the B-004 short-circuit metadata flag).

These flags are no longer honored in strict modes (thanks to Phase 1.2.3), but the code that sets them and the checks that look for them still exist. This creates:
- Technical debt
- Cognitive load
- Risk of future developers re-activating old behavior by accident
- Inconsistent "truth" in the system

---

## Hypothesis

By executing a dedicated "Setter & Metadata Cleanup" phase (1.3.3), we will:

- Remove or neutralize all remaining production code that sets legacy bypass metadata flags (`skip_admission_chain_recheck` and any similar remnants).
- Clean up the now-dead checks in the broker layer where possible.
- Update or mark as explicitly legacy the test code that still relies on these flags.
- Make the post-1.2/1.3 reality the *only* reality in the code: the late authoritative gate is always the single source of truth in strict modes.

This will reduce attack surface, lower maintenance cost, and prevent accidental re-introduction of old bypass patterns.

**Falsifiable Predictions**:
- After 1.3.3, a search for `skip_admission_chain_recheck` in production `.py` files under `lumina_core/` will return only pops/cleanups or deprecation comments (no active setters that can create a bypass).
- The number of places that still write these legacy flags drops to zero in normal trading paths.
- Future code reviews will have far fewer "what does this old flag do?" discussions.

---

## Scope of 1.3.3

**Primary targets**:
- Remaining setters of `skip_admission_chain_recheck = True` in production code (mainly emergency/API paths and certain worker paths).
- The check in `broker_bridge.py:_run_final_arbitration` (can it be simplified now that the main paths no longer set it?).
- Any direct `Order(..., metadata={... "skip_admission_chain_recheck": True})` constructions in production flows.
- Test code that still uses these flags (mark as legacy or migrate where reasonable).

**Out of scope for this slice** (to keep it focused):
- Large-scale documentation overhaul (that's more 1.3.4).
- Removal of the entire metadata concept (some metadata is still useful).
- Changes to EOD force-close or emergency logic beyond cleaning the flag (those are special paths that need separate review).

---

## Risks & Mitigations

- **Emergency / force-close paths still need to work reliably**: These paths deliberately used the old skips for speed/reliability during crises.
  - Mitigation: Do not blindly remove the ability for emergency paths to bypass. Instead, make the bypass explicit, logged, and limited (or route them through a controlled emergency gate). Document clearly.

- **Test breakage**: Many golden-ledger and broker tests use the flag for convenience.
  - Mitigation: Migrate tests to go through proper gates where possible, or explicitly mark them as testing legacy behavior.

- **Over-cleaning**: Removing the flag everywhere might hide real operational needs.
  - Mitigation: Be surgical. Focus on normal trading paths first. Keep explicit, well-documented bypasses only for true emergency scenarios.

---

## Success Criteria for 1.3.3

- Zero active setters of legacy bypass metadata in normal (non-emergency) production code paths.
- The broker re-check layer is simplified where possible.
- All remaining usage of these flags is either removed, explicitly marked as legacy/emergency-only, or migrated.
- Updated bypass inventory and relevant docs reflect the new cleaner state.
- Public 1.3.3 completion entry published.

---

## Immediate Next Actions (Strict Sequence)

1. This hypothesis entry (done).
2. Enter dedicated Plan Mode for the detailed design and implementation plan of 1.3.3.
3. After approval: execute the cleanup following the same discipline as previous slices (small steps, tests, skill reviews where relevant, public entries).
4. Publish completion entry for 1.3.3.

---

*We continue the track with the same iron discipline. No steps skipped.*

**Focus remains absolute**: Make the post-1.2/1.3 reality (the narrow, authoritative late gate) the *only* reality in code and documentation.