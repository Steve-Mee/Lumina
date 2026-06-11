# 2026-05-31 — Phase 2 Slice 08 COMPLETE: Agent Proposals as the True Root of the Decision Lineage

**Parent**: `2026-05-31-elon-phase2-08-upstream-proposal-lineage.md`

**Status**: **SLICE COMPLETE**

---

## Delivered

- `AgentProposalPayload` now explicitly documents `decision_context_id`.
- `add_proposal` on the blackboard now ensures a `decision_context_id` is present for proposal topics (generated at proposal formation time if not provided, and mirrored into the payload).
- The canonical gate entry (`admission.gate_entry`) now prefers a `decision_context_id` coming from recent proposals on the blackboard over generating a fresh "gate:..." id.
- The reconstruction helper now best-effort surfaces recent proposal events for a given `decision_context_id`.
- Guardian updated with the new upstream coverage note.
- This public completion entry.

**All changes are additive and backward compatible.** Zero impact on proposal generation or risk decisions.

---

## Measurements

- When a proposal is created without an explicit id, it now receives a `decision_context_id` that becomes the root of the entire downstream lineage.
- When the gate processes proposals that carry a `decision_context_id`, the `admission.gate_entry` (and all subsequent risk events) use that same id.
- The lineage thread now starts at proposal formation for the first time.

---

## Fidelity to Global Plan

This slice directly advances Phase 2 deliverable 2:
> "100% of **agent proposals**, risk allocations, arbitration decisions... published as typed events with full lineage (decision_context_id + prev_hash chaining)"

We have made agent proposals the true root of the decision lineage, with a single unbroken `decision_context_id` flowing from proposal creation through the gate all the way to Final Arbitration.

**Red thread maintained. No deviations.**

---

**Phase 2 Slice 08 is complete.**

Ready for the next slice. High-value options:
- Make key proposal events also appear as first-class typed events on the main Event Bus (not just blackboard).
- Begin actual prev_hash chaining at the proposal level.
- Expand reconstruction to show a clean "full decision provenance" view starting from proposals.
- Connect dream state formation to the same lineage root.

Direct instruction for the next move.