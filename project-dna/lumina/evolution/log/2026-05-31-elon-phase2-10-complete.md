# 2026-05-31 — Phase 2 Slice 10 COMPLETE: Key Agent Proposal Events as First-Class Typed Events on the Main Event Bus

**Parent**: Approved plan for Slice 10.

**Status**: **SLICE COMPLETE**

---

## Delivered

- Registered the key proposal topics (`agent.rl.proposal`, `agent.news.proposal`, etc.) in `EVENT_BUS_TOPIC_MODELS` and `CRITICAL_EVENT_BUS_TOPICS` (reusing the existing `AgentProposalPayload`).
- Added dual-publish logic in `add_proposal` on the blackboard: after publishing to the blackboard, it now also publishes to the main `engine.event_bus` (if available) with the same payload (including `decision_context_id` from Slice 08).
- Minor documentation update in the reconstruction helper.
- Guardian updated with the new baseline.
- This public completion entry.

**All changes are additive.** Proposals continue to work exactly as before on the blackboard while now also appearing as first-class typed events on the main Event Bus.

---

## Measurements

- When `add_proposal` is called (the central path used by all agents), a typed proposal event now appears on the main Event Bus carrying the `decision_context_id`.
- The foundation for unified, main-bus-only reconstruction of the full lineage (proposals → gate entry → risk decisions) is now in place.

---

## Fidelity to Global Plan

This slice directly advances Phase 2 deliverable 2 by making agent proposals first-class typed events on the main Event Bus (the declared universal spine), with the lineage root (`decision_context_id`) already flowing from previous slices.

**Red thread maintained. No deviations.**

---

**Phase 2 Slice 10 is complete.**

Ready for the next slice. High-value options from the previous list:
- Begin actual deeper prev_hash chaining starting from the proposal events on the main bus.
- Expand reconstruction to produce a clean "full pre-trade decision provenance" report.
- Add best-effort hash chain validation warnings in the Guardian.
- Begin lineage treatment for order submission and fills.

Direct instruction for the next move.