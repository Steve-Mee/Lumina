# 2026-05-31 — Phase 1.2.3: Final Structural Removal Slice — Eliminate the Last-Mile skip_admission_chain_recheck in broker_bridge

**Parent Plan**: Approved Phase 1.2 Plan — "Make the Authoritative Check the Only Check"  
**Previous Slices**: 1.2.1 (reasoning_service) and 1.2.2 (operations_service) completed.  
**Impact Class**: Medium-to-Large (removal of the final short-circuit in the broker layer; affects all order submission paths to the wire).

**Protocol**: This entry is the mandatory formal hypothesis record *before* any 1.2.3 code changes or detailed planning.

---

## Hypothesis

This is the final structural removal slice in the Phase 1.2 series.

By removing the `skip_admission_chain_recheck` metadata short-circuit inside `broker_bridge._run_final_arbitration` (B-004), we will:

- Eliminate the last remaining FATAL structural bypass mechanism.
- Make the authoritative re-check in the broker layer (the true last mile before the wire) unavoidable in strict modes.
- Render the god-flag (`admission_chain_final_arbitration_approved`) and all related skip logic largely dead code for normal trading paths.
- Complete the core structural goal of Phase 1.2: the late authoritative Admission Chain + Final Arbitration becomes the *only* effective path that can allow an order to reach a broker in REAL / sim_real_guard modes.

This slice closes the 1.2 removal series. After this, only cleanup, deprecation, and optimization work remains before we can declare the trusted-path mechanisms structurally eliminated.

**Falsifiable Predictions**:
- Within 14-21 days after merge (heavy SIM + paper-guard load): Zero successful orders that bypassed via the old B-004 short-circuit in strict modes.
- Guardian Aperture Integrity Score reaches ≥ 8.0–8.5 (major milestone from the original 2.0 baseline at the start of the 1.2 series).
- The god-flag and `skip_admission_chain_recheck` metadata become dead or near-dead code in all normal paths.
- Clean validation campaigns with no silent bypasses and acceptable performance characteristics.

**Measurement**:
- Guardian aperture scoring + violation events (especially B-004).
- Broker submission path coverage and timing.
- Final bypass inventory state (target: 0 remaining FATAL structural mechanisms).
- Supervisor + broker submission telemetry under load.

---

## Why This Is the Final Structural Slice (1.2.3)

Per the approved Phase 1.2 plan:
- 1.2.1 removed usage in reasoning_service.
- 1.2.2 removed usage in operations_service (the hottest supervisor path).
- 1.2.3 targets the actual short-circuit logic in the broker layer itself (`broker_bridge.py`).

This is the "root" of the last-mile escape hatch. Removing it here makes the bypass impossible at the point where orders are actually sent to the broker, regardless of how they arrived.

After this slice, the god-flag becomes mostly ornamental for normal flows and can be deprecated in a later cleanup phase.

---

## Design Approach (High Level)

- Remove or neutralize the early return in `broker_bridge.py:_run_final_arbitration`:
  ```python
  if bool(metadata.get("skip_admission_chain_recheck", False)):
      return True, "skipped_admission_chain_recheck"
  ```
- Ensure that in strict modes (`real`, `sim_real_guard`), this path is either removed or always falls through to the full `enforce_pre_trade_gate` call (protected by the existing Phase 1.1 `aperture_guard`).
- Update all places that set `skip_admission_chain_recheck` metadata (policy_engine, trade_workers, emergency paths, etc.) to no longer rely on it for bypassing in strict modes.
- Keep the Phase 1.1 `aperture_guard` enforcement on B-004 active until the short-circuit logic is fully gone.
- Add measurement around the broker re-check path.

This slice has broader surface area because multiple callers (policy_engine, runtime_workers, emergency flatten, etc.) set the metadata flag.

---

## Risks Specific to This Final Structural Slice

- **Broadest impact**: Affects every broker submission path (PaperBroker, CrossTradeBroker, any future brokers).
- **Metadata flag usage is scattered**: Several places set `skip_admission_chain_recheck`.
- **Emergency / force-close paths**: Some direct broker calls may still rely on this flag.
- **Performance**: The broker re-check will now run more often in strict modes.

**Mitigations**:
- Phase 1.1 `aperture_guard` remains the hard safety net.
- Start with aggressive warning + enforcement in strict modes before fully deleting the short-circuit.
- Careful audit of all callers that set the metadata flag.
- Strong measurement of broker submission latency.

---

## Success Criteria for Phase 1.2.3

- The `skip_admission_chain_recheck` short-circuit logic is removed or made impossible to use effectively in strict modes inside `broker_bridge`.
- All known places that set the metadata flag no longer result in a bypass for strict modes.
- Zero remaining FATAL structural bypass mechanisms in the inventory (target: 0).
- Guardian Aperture Integrity Score shows major improvement.
- Full validation campaigns (SIM + paper-guard) complete with no silent bypasses.
- Public 1.2.3 completion entry that formally closes the structural removal work of Phase 1.2.
- Clear transition to either cleanup/deprecation work or the parallel gate optimization track.

---

## Next Actions (Strict Sequence)

1. This hypothesis entry.
2. Enter dedicated Plan Mode for the detailed 1.2.3 implementation design (following the exact pattern used for 1.2.1 and 1.2.2).
3. After approval: implement the removal + necessary caller cleanups.
4. Comprehensive validation (emphasize all broker paths + emergency scenarios).
5. Publish telemetry + final inventory update + 1.2.3 completion entry.
6. Formal closure of the entire 1.2 structural removal series + decision on next phase (1.3 or optimization work).

---

*This is the final structural removal slice of Phase 1.2. After this, the "trusted path" architecture that was diagnosed in the original 2026-05-31 Elon analysis will be structurally eliminated.*

**We continue with the same iron discipline: no steps skipped, full protocol followed, safety net maintained.**

**Focus remains absolute on the end goal: a narrow, typed, un-bypassable, fully observable capital aperture.**