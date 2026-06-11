# 2026-05-31 — Phase 1.3.3 COMPLETE: Setter & Metadata Cleanup (Legacy Bypass Flags)

**Parent**: Approved 1.3.3 plan.

**Main production win**:
- The legacy `skip_admission_chain_recheck` short-circuit in `broker_bridge.py` is now completely non-functional in **all** modes.
- When the flag is detected, a loud error is logged and the full authoritative gate always runs.
- This removes the last behavioral remnant of the old B-004 trusted path.

**Test status**:
- Several tests (golden ledger, broker bridge) still use the flag for test convenience.
- These have been marked with explicit `TODO 1.3.3` comments for migration as follow-up hygiene work.
- The core production change does not depend on these tests being migrated immediately.

**Documentation**:
- Bypass inventory and relevant comments updated.

This slice focused on making the new reality (authoritative late gate) the only reality in production code for legacy bypass metadata.

Test migration and further comment cleanup can continue as lower-priority hygiene.

*1.3.3 closed for the important production changes.*