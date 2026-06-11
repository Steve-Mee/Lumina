# 2026-05-31 — Phase 2 Slice 05: Extend Typed Event + Hash Chain to the Risk Policy Decision

**Parent**:
- `2026-05-31-elon-phase2-04-complete.md`
- `2026-05-31-elon-aperture-hardening-90-day-roadmap.md` (Phase 2 deliverable 2: "100% of agent proposals, **risk allocations**, arbitration decisions... published as typed events with full lineage (decision_context_id + prev_hash chaining)")

**Protocol Status**: This is the formal opening hypothesis entry for Phase 2 Slice 05. No implementation begins until this entry and a dedicated Plan Mode are complete.

---

## Hypothesis

In Slice 01–04 we made the two final risk decision points (`risk.policy.decision` summary + `risk.final_arbitration.result`) typed, correlated via `decision_context_id`, hash-chained, and reconstructible.

However, the actual **risk allocation decision** (the output of the Risk Policy step inside the admission chain) is still not emitted as a first-class typed event with its own lineage. The current `risk.policy.decision` is only a final summary at the very end of the gate.

**Hypothesis**:
Extracting / emitting the actual decision coming out of the Risk Policy step as a proper typed event (`risk.policy.decision` or a more precise `risk.allocation.decision`), ensuring it carries the `decision_context_id`, and making it the starting point of the hash chain (so Final Arbitration can chain back to it with `prev_hash`), will advance deliverable 2 of Phase 2 one significant step closer to "100% of ... risk allocations ... with full lineage".

This is the smallest next reversible slice that makes the risk allocation itself a visible, hash-chained node in the single authoritative path.

---

## Falsifiable Predictions

1. After this slice, the Risk Policy step will produce a typed event on a critical topic (e.g. `risk.policy.decision` or `risk.allocation.decision`) carrying the decision (approved / limits / reason) + `decision_context_id`.

2. The Final Arbitration event will reliably carry a `prev_hash` that matches the fingerprint of this risk allocation / policy decision event.

3. The reconstruction helper (`reconstruct_risk_decision_chain`) will now return at least three linked nodes for a typical approved path: Risk Policy decision → Final Arbitration → (final summary if separate).

4. Guardian will show improved "Risk Decision Chain Completeness" coverage.

5. Zero change to any risk calculation or blocking behavior.

---

## Scope (Strictly Limited)

**In scope**:
- In the `_risk_policy_step` (or immediately after it returns its verdict), emit a clean typed event with the risk policy outcome + `decision_context_id`.
- Ensure the Final Arbitration step (which runs later) can see and chain to this event's hash.
- Extend the reconstruction helper to include this new node in the chain.
- Update tests and Guardian notes.
- Public evolution entry.

**Out of scope**:
- Changing the final summary `risk.policy.decision` emission (we can keep or deprecate it later).
- Full agent proposal lineage.
- Any behavior change to risk limits or approvals.

---

## Why This Slice Now

Deliverable 2 of Phase 2 explicitly calls out "**risk allocations**" as one of the things that must be typed + fully lineaged.

We have the final arbitration side solid. The missing piece on the risk side is the actual allocation decision itself. Adding it as a first-class, hash-chained event is the direct, small next step.

This keeps the "one small measurable reversible slice at a time" discipline that has been non-negotiable throughout the entire track.

---

## Reversibility & Safety

- The new emission is purely additive observability.
- Can be removed or made conditional in < 2 minutes.
- No effect on any capital protection logic.

---

**This entry opens Phase 2 Slice 05.** Plan Mode + skill reviews (constitution-guard + event-bus-contract) are required before any code.

*Red thread: the single authoritative path must eventually carry 100% of risk allocations as typed, hash-chained, reconstructible events.*