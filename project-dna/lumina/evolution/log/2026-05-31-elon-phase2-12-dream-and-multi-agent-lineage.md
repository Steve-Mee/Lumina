# 2026-05-31 — Phase 2 Slice 12: Extend Lineage Further Upstream — Dream State and Multi-Agent Coordination as the Earliest Root

**Parent**:
- `2026-05-31-elon-phase2-11-complete.md` (Slice 11 made deeper prev_hash chaining start from proposal events on the main bus)
- `2026-05-31-elon-aperture-hardening-90-day-roadmap.md` (Phase 2 deliverable 2: "100% of agent proposals, risk allocations, arbitration decisions... published as typed events with full lineage (decision_context_id + prev_hash chaining)")

**Protocol Status**: This is the formal opening hypothesis entry for Phase 2 Slice 12. No implementation begins until this entry and a dedicated Plan Mode are complete.

---

## Hypothesis

In Slice 08–11 we achieved:
- Proposals as the source of the `decision_context_id` root.
- Proposals as first-class typed events on the main Event Bus.
- The first deeper prev_hash chaining starting from proposal events on the main bus.

However, the true origin of most trading decisions is even further upstream — in the **dream state formation** and the **multi-agent coordination / meta-agent processes** that generate and select the proposals that eventually reach the gate.

Currently:
- Dream state and multi-agent coordination still live largely on the blackboard and internal structures.
- There is no typed Event Bus presence or hash-chained lineage connecting dream formation and agent coordination to the proposal → gate_entry → risk decision chain.
- The `decision_context_id` does not yet originate at the earliest point of decision formation (dream + coordination).

**Hypothesis**:
By beginning to treat key dream state updates and multi-agent coordination events as part of the upstream lineage (carrying or generating the `decision_context_id`, appearing on the main Event Bus where appropriate, and starting the hash chain from the earliest "thought" or "coordination" point), we will pull the lineage all the way back to the actual origin of trading intentions.

This is the smallest reversible slice that meaningfully extends the chain further upstream per the global plan, making the full pre-trade decision provenance traceable from the moment the system begins forming an intention.

---

## Falsifiable Predictions

1. After the slice, key dream state and multi-agent coordination events will carry the shared `decision_context_id` and begin participating in the main Event Bus lineage.
2. The reconstruction helper will be able to return chains that start from dream/coordination nodes for a given `decision_context_id`.
3. Guardian will show improved "Upstream Lineage Depth (Dream + Multi-Agent Coordination)".
4. Zero impact on dream formation, agent coordination, or any risk decision logic.

---

## Scope (Strictly Limited)

**In scope**:
- Ensure key dream state updates and multi-agent coordination events (when they lead to proposals) carry or inherit the `decision_context_id`.
- Begin publishing important coordination/dream events as typed events on the main Event Bus (or at minimum ensure they are visible in reconstruction).
- Make the earliest "intention formation" event the start of the hash chain (prev_hash from "GENESIS" or previous dream for that context).
- Minor updates to reconstruction helper and one focused test.
- Guardian note.

**Out of scope**:
- Full hash chaining or typed events for every single dream update or internal meta-agent thought (start with the key coordination points that lead to proposals).
- Changes to order submission / fills (still later).
- Shadow deployment (separate deliverable).

---

## Why This Slice Now

We have made excellent progress pulling the lineage upstream to proposals on the main bus. The next natural forcing function is to go one layer deeper — to the actual formation of intentions in the dream and multi-agent layer. This directly serves the spirit of "full lineage from the earliest point of decision formation."

This keeps the "small measurable reversible slices" discipline while steadily building the complete provenance spine demanded by the global plan.

---

## Reversibility & Safety

- All changes are additive lineage/observability.
- Can be disabled or rolled back easily.
- No behavior change to dream formation, coordination, or risk logic.

---

**This entry opens Phase 2 Slice 12.** Plan Mode + skill reviews (constitution-guard + event-bus-contract) required before implementation.

*Red thread: The single authoritative path must eventually have unbroken lineage from the very first moment the system begins forming a trading intention (dream + multi-agent coordination) all the way to the wire.*