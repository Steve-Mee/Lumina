# 2026-05-31 — Phase 2 Slice 08: Extend Lineage Upstream — Agent Proposals and Dream State as the True Root

**Parent**:
- `2026-05-31-elon-phase2-07-complete.md` (Slice 07 made the hash chain continuous from Gate Entry root through Risk Allocation to Final Arbitration)
- `2026-05-31-elon-aperture-hardening-90-day-roadmap.md` (Phase 2 deliverable 2: "100% of **agent proposals**, risk allocations, arbitration decisions... published as typed events with full lineage (decision_context_id + prev_hash chaining)")

**Protocol Status**: This is the formal opening hypothesis entry for Phase 2 Slice 08. No implementation begins until this entry and a dedicated Plan Mode are complete.

---

## Hypothesis

We now have a clean, continuous hash-chained lineage for the core risk decision path, anchored at the `admission.gate_entry` root.

However, the true origin of most trading decisions is **upstream** — in agent proposals (RL, news, emotional twin, swarm, etc.) and the dream state / blackboard that feeds them into the gate.

Currently:
- The gate still generates its own `decision_context_id`.
- Agent proposals live primarily on the blackboard with `AgentProposalPayload`, but do not yet participate in the main Event Bus typed lineage with `decision_context_id` + `prev_hash`.
- There is no cryptographic link from a proposal all the way through the risk decisions to the wire.

**Hypothesis**:
Making agent proposals (and the dream state context that supports them) the **true root** of the lineage by:
1. Ensuring proposals carry or generate a `decision_context_id`.
2. Publishing key proposal events as typed events on the main Event Bus.
3. Having the Gate Entry root inherit / reference the proposal's `decision_context_id` instead of always minting a fresh one.
4. Beginning the hash chain from the proposal level.

...will deliver the next major segment of the required "full lineage from agent proposal to Final Arbitration".

This is the smallest reversible slice that meaningfully extends the chain upstream per the global plan.

---

## Falsifiable Predictions

1. After the slice, agent proposals will carry a `decision_context_id` (generated at proposal creation or when selected for the gate).
2. The `admission.gate_entry` event will use the proposal's `decision_context_id` when one is available from the blackboard/dream context, creating a single continuous lineage id from proposal through to arbitration.
3. Key proposal events will be observable on the Event Bus with the shared `decision_context_id`.
4. The reconstruction helper will be able to return chains that start from proposal/dream nodes.
5. Guardian will show "Upstream Lineage Coverage (Agent Proposals → Gate)" improving.
6. Zero impact on proposal generation logic or risk decisions.

---

## Scope (Strictly Limited)

**In scope**:
- Add `decision_context_id` field to `AgentProposalPayload` (optional for backward compat).
- Ensure that when proposals are published/selected for consideration, they get a `decision_context_id`.
- Modify the gate entry logic to prefer a `decision_context_id` coming from the proposal/blackboard context over generating a fresh gate-specific one.
- Begin publishing the main proposal topics (or a summary) as typed events on the Event Bus with the id.
- Start attaching `prev_hash` at the proposal level for the first proposals that feed a gate call.
- Update reconstruction helper and add 1-2 tests.
- Guardian note.

**Out of scope**:
- Full hash chaining for all proposal types and every dream update (start with the selected proposal that reaches the gate).
- Changes to blackboard implementation itself.
- Connecting fills/order submissions yet.

---

## Why This Slice Now

The global plan explicitly lists **agent proposals** as the first item that must have full lineage.

We have built a solid foundation from the gate downstream. Extending upstream now is the direct, logical, high-leverage next step. It also creates the natural attachment point for dream state and multi-agent coordination.

This keeps the "small measurable reversible slices" discipline while steadily building the complete provenance spine.

---

## Reversibility & Safety

- Adding the field to the payload is backward compatible (optional).
- The gate can fall back to generating its own id if no proposal id is present.
- All changes are additive lineage/observability.
- Can be disabled or rolled back easily.

---

**This entry opens Phase 2 Slice 08.** Plan Mode + skill reviews (constitution-guard + event-bus-contract) are required before implementation.

*Red thread: The single authoritative path must eventually have unbroken lineage from the moment an agent forms a proposal all the way to the wire.*