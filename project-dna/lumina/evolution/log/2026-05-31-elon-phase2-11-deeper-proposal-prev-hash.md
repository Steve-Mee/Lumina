# 2026-05-31 — Phase 2 Slice 11: Begin Deeper prev_hash Chaining Starting from Proposal Events on the Main Bus

**Parent**:
- `2026-05-31-elon-phase2-10-complete.md` (Slice 10 made key proposal events first-class typed events on the main Event Bus)
- `2026-05-31-elon-aperture-hardening-90-day-roadmap.md` (Phase 2 deliverable 2 + 4: full lineage with decision_context_id + prev_hash chaining from agent proposals)

**Protocol Status**: This is the formal opening hypothesis entry for Phase 2 Slice 11. No implementation begins until this entry and a dedicated Plan Mode are complete.

---

## Hypothesis

In Slice 08–10 we achieved:
- Proposals as the source of the `decision_context_id` root.
- First cryptographic link (proposal blackboard event_hash → gate_entry prev_hash).
- Proposals now published as first-class typed events on the main Event Bus.

However, the **deeper** prev_hash chaining starting from the proposal events themselves is not yet fully in place on the main bus. The proposal events on the main bus do not yet consistently carry their own `event_hash`, and the chain from proposal → gate_entry → risk allocation is not yet a clean, verifiable cryptographic sequence on the central spine.

**Hypothesis**:
By ensuring that when proposals are published to the main Event Bus they receive a proper `event_hash` (computed the same way as other main-bus events), and by making the gate_entry (and subsequent events) reliably set their `prev_hash` to the preceding proposal's `event_hash` (now that proposals are natively on the bus), we will create the first solid, deeper hash-chained segment starting from agent proposals on the main Event Bus.

This is the smallest reversible slice that begins "actual deeper prev_hash chaining from the proposal events" as the natural next step after making them first-class on the bus.

---

## Falsifiable Predictions

1. After the slice, proposal events published to the main bus will carry a non-empty `event_hash` in their metadata.
2. The `admission.gate_entry` event (and downstream risk events) will set `prev_hash` to the preceding proposal event's `event_hash` when the proposal is the direct predecessor for that `decision_context_id`.
3. The reconstruction helper will be able to walk and validate a clean hash chain starting from a proposal event on the main bus.
4. Guardian will show improved "Proposal-to-Gate Hash Chain Depth".
5. Zero impact on any trading or risk logic.

---

## Scope (Strictly Limited)

**In scope**:
- Ensure proposal events get proper `event_hash` when published to the main bus (in the dual-publish path in add_proposal).
- Strengthen the gate_entry emission logic to set `prev_hash` from the proposal event on the main bus (now that they are reliably there).
- Minor update to reconstruction helper for better proposal-starting chain walking.
- One focused test showing proposal → gate_entry hash link on the main bus.
- Guardian note.

**Out of scope**:
- Full prev_hash chaining across multiple proposals for the same decision.
- Dream state or upstream of proposals.
- Downstream to fills.
- Validation/enforcement of the chain (that comes later).

---

## Why This Slice Now

We just made proposals first-class on the main bus. The immediate next forcing function is to make the hash chain actually start from those proposal events on the bus. This directly advances the "prev_hash chaining" requirement starting from agent proposals.

---

## Reversibility & Safety

- All changes are refinements to metadata (event_hash / prev_hash) on already-typed events.
- Can be disabled easily.
- No behavior change to any decision logic.

---

**This entry opens Phase 2 Slice 11.** Plan Mode + skill reviews required before any code.

*Red thread: The single authoritative path must have continuous, cryptographic prev_hash chaining starting from the moment an agent forms a proposal.*