# 2026-05-31 — Phase 2 Slice 11 COMPLETE: Deeper prev_hash Chaining Starting from Proposal Events on the Main Bus

**Parent**: Approved plan for Slice 11.

**Status**: **SLICE COMPLETE**

---

## Delivered

- When proposals are dual-published to the main Event Bus (via the logic added in Slice 10), they now receive a proper `event_hash` attached to the DomainEvent metadata (using the existing `_domain_event_fingerprint`).
- The gate_entry emission logic now prefers looking up the preceding proposal event on the **main Event Bus** (instead of only the blackboard) and uses its `event_hash` as `prev_hash`.
- Fallback to blackboard lookup is kept for graceful transition.
- Minor polish to the reconstruction helper (prefers main-bus proposals).
- Strong focused test added.
- Guardian updated.
- This public completion entry.

**All changes are small, targeted, and additive.** The hash chain now properly starts from proposal events on the main bus when they are present.

---

## Measurements

- Proposal events on the main bus carry `event_hash`.
- `admission.gate_entry` sets `prev_hash` from the proposal event found on the main bus (when available for the decision_context_id).
- The reconstruction helper can now walk a verifiable chain starting from a main-bus proposal event.

---

## Fidelity to Global Plan

This slice delivers "actual deeper prev_hash chaining starting from the proposal events on the main bus" — the direct next forcing function after Slice 10 made proposals first-class typed events there.

It advances Phase 2 deliverables 2 and 4 by making the cryptographic chain begin at the agent proposal level on the declared universal spine.

**Red thread maintained. No deviations.**

---

**Phase 2 Slice 11 is complete.**

Ready for the next slice. High-value options:
- Expand the continuous chain further upstream (dream state formation, multi-agent coordination).
- Add best-effort hash chain validation warnings in the Guardian.
- Strengthen the reconstruction helper into a clean "full pre-trade decision provenance" report.
- Begin lineage treatment for order submission and fills.

Direct instruction for the next move.