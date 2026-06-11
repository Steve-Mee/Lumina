# 2026-05-31 — Phase 2 Slice 07: Make the Hash Chain Continuous from Gate Entry Root through Risk Allocation to Final Arbitration

**Parent**:
- `2026-05-31-elon-phase2-06-complete.md` (Slice 06 established the `admission.gate_entry` root event)
- `2026-05-31-elon-aperture-hardening-90-day-roadmap.md` (Phase 2 deliverables 2 & 4: full lineage with decision_context_id + prev_hash chaining + hash-chained provenance for risk allocations and arbitration decisions)

**Protocol Status**: This is the formal opening hypothesis entry for Phase 2 Slice 07. No implementation begins until this entry and a dedicated Plan Mode are complete.

---

## Hypothesis

In Slice 06 we created the true root of every pre-trade decision: the `admission.gate_entry` event, emitted at the absolute first moment an order intent enters the authoritative gate, carrying the `decision_context_id`.

We already have:
- Risk Allocation decision emitted as a typed event (Slice 05)
- Final Arbitration decision emitted as a typed event (Slice 01)
- Some prev_hash links between later events (Slices 03–05)

**Hypothesis**:
The current hash chain is still incomplete. The Risk Allocation event does not yet reliably carry a `prev_hash` pointing back to the new Gate Entry root, and the Final Arbitration event does not yet reliably chain back through the Risk Allocation event to the root.

By making the hash chain **continuous and explicit** from:
`admission.gate_entry` (root) → `risk.policy.decision` (allocation) → `risk.final_arbitration.result`

we will deliver the first complete, end-to-end hash-chained lineage segment for the core risk decision path.

This is the smallest possible next slice that turns the root event into a real, usable, tamper-evident foundation for the full lineage required by the global plan.

---

## Falsifiable Predictions

1. After this slice, for every execution of the canonical gate:
   - The Risk Allocation decision event will contain a `prev_hash` that matches the fingerprint of the `admission.gate_entry` root for the same `decision_context_id`.
   - The Final Arbitration event will contain a `prev_hash` (or chain reference) that correctly links back through the Risk Allocation event.

2. The reconstruction helper (`reconstruct_risk_decision_chain`) will return a clean, verified three-node chain starting from the gate entry root.

3. Guardian will report "Continuous Hash Chain Coverage (Gate Entry → Allocation → Arbitration)" improving toward 100%.

4. Any deliberate break in the chain (in tests) is detected by the reconstruction helper and/or Guardian.

5. Zero impact on latency, risk logic, or capital protection.

---

## Scope (Strictly Limited)

**In scope**:
- Ensure the Risk Allocation emission (from the risk policy step) captures and attaches the correct `prev_hash` from the Gate Entry root (using the ref we already store).
- Ensure the Final Arbitration emission attaches the correct `prev_hash` from the Risk Allocation event (refining the existing chaining logic).
- Minor updates to the reconstruction helper if needed to validate the full three-node chain.
- One or two focused tests that assert the continuous chain.
- Guardian note.
- Public evolution entries.

**Out of scope**:
- Expanding the chain upstream (agent proposals, dream state) — that is later work.
- Full Merkle tree or more sophisticated structures.
- Validation that breaks trades (visibility first).
- Any behavior change to the gate itself.

---

## Why This Slice Now

We have the root. We have the nodes. The missing piece is making the **chain actually continuous**.

This is the classic next forcing function after creating a root: immediately close the loop so the mechanism becomes real and any gap screams.

It directly fulfills the "prev_hash chaining" part of the global plan for the two most important risk decisions, now anchored at the true entry point.

---

## Reversibility & Safety

- All changes are refinements to metadata (`prev_hash` values) on already-emitted typed events.
- Can be reverted in minutes.
- No effect on any trading decision.

---

**This entry opens Phase 2 Slice 07.** Plan Mode + skill reviews (constitution-guard + event-bus-contract) are required before any code changes.

*Red thread: The single authoritative path must have continuous, hash-chained, reconstructible lineage starting from the exact moment an intent enters the aperture.*