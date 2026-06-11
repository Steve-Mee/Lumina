# 2026-05-31 — Phase 2 Slice 15: Begin Downstream Lineage for Order Submission and Fills

**Parent**:
- `2026-05-31-elon-phase2-14-complete.md` (Slice 14 delivered the human-readable pre-trade provenance report)
- `2026-05-31-elon-phase2-13-complete.md` through earlier slices (continuous upstream-to-Final-Arbitration hash chain + screaming Guardian)
- `2026-05-31-elon-aperture-hardening-90-day-roadmap.md` (Phase 2 deliverable 2: "100% of agent proposals, risk allocations, arbitration decisions, **and order submissions** published as typed events with full lineage (decision_context_id + prev_hash chaining)")

**Protocol Status**: This is the formal opening hypothesis entry for Phase 2 Slice 15. No implementation begins until this entry and a dedicated Plan Mode are complete.

---

## Hypothesis

Across Slices 03–14 we have achieved:
- Full cryptographic lineage (decision_context_id + continuous prev_hash) from the earliest intention formation (dream/multi-agent) through proposals, gate_entry, risk.policy.decision, and Final Arbitration.
- Active screaming in the Guardian when that chain is broken (Slice 13).
- A clean, human-readable provenance report for any decision_context_id (Slice 14).

**Current reality**:
- The chain stops at Final Arbitration.
- Once Final Arbitration approves, the actual order that reaches the broker (via broker_bridge, order submission, fills, etc.) has **no lineage connection** back to the decision_context_id, the hash chain, or the upstream proposals.
- There is no `prev_hash` link from the last pre-trade event into the actual order submission / execution events.
- The "single authoritative path to the wire" is still incomplete on the downstream side. We have excellent visibility into *why* a decision was made, but poor cryptographic traceability into *what actually happened* once it left Final Arbitration.

**Hypothesis**:
By beginning to thread the same `decision_context_id` and `prev_hash` mechanism into the order submission and fill paths (starting with the first practical, high-value points in broker_bridge / order submission), we will extend the continuous hash chain past Final Arbitration and toward the actual market.

This is the smallest reversible slice that meaningfully begins closing the downstream gap in the "full lineage ... all the way to the wire" north star, while staying strictly within the "small measurable reversible slices" discipline.

---

## Falsifiable Predictions

1. After the slice, the `decision_context_id` from Final Arbitration will be carried forward (best-effort) into at least one key order submission event or fill-related event.
2. The first downstream `prev_hash` link(s) will be established (i.e. order submission events will reference the hash of the preceding Final Arbitration event for the same decision_context_id).
3. Reconstruction (or a simple extension) will be able to continue the chain past Final Arbitration for decision_context_ids that reached order submission.
4. Guardian will be able to note "Downstream lineage started" or surface the first downstream links in provenance reports.
5. Zero behavior change or risk impact on actual order submission, routing, or fill handling.

---

## Scope (Strictly Limited — First Downstream Slice)

**In scope**:
- Identify the earliest practical attachment points after Final Arbitration (most likely in `broker/broker_bridge.py` around `_run_final_arbitration` / order submission, or the immediate caller in reasoning_service / order_gatekeeper).
- Ensure `decision_context_id` is threaded from the Final Arbitration result into the order submission path (it already exists in many places via AdmissionContext; we need to make sure it survives to the broker call).
- On the first order-related events that are already published (or the first new ones we add), attach `prev_hash` pointing back to the Final Arbitration event's hash.
- Minimal update to `decision_lineage.py` so reconstruction can continue the chain if downstream events are present.
- One focused test proving the first downstream link (Final Arbitration → order submission event with matching decision_context_id and valid prev_hash).
- Small Guardian / provenance report note.
- Public completion entry.

**Out of scope (explicitly deferred)**:
- Full end-to-end downstream lineage (fills, partial fills, position updates, P&L attribution, etc.). That is a multi-slice effort.
- Changing any actual order routing, broker protocol, or execution logic.
- Making every possible fill event carry lineage (start with the submission boundary).
- Shadow deployment integration.

---

## Why This Slice Now

We have spent 14 slices making the pre-trade side of the capital aperture world-class: typed, hash-chained from the earliest intention, screaming when broken, and human-readable in minutes.

The chain is still "pre-trade only." The moment Final Arbitration says "yes," the decision disappears into the execution layer with no cryptographic lineage.

This is the direct next forcing function on the original list ("Begin lineage treatment for order submission and fills").

It keeps the momentum on the core Phase 2 deliverable of "full lineage ... order submissions" while staying small and reversible.

---

## Reversibility & Safety

- All changes are additive lineage/observability on the downstream side.
- Can be rolled back in minutes.
- No modification to order construction, submission logic, risk calculations, or broker communication.
- Best-effort threading (if the id or previous hash is not available, we simply don't link — existing behavior is preserved).

---

**This entry opens Phase 2 Slice 15.** Plan Mode + skill reviews (constitution-guard + event-bus-contract + risk-safety-review) required before implementation.

*Red thread: The single authoritative path must eventually have unbroken lineage from the very first moment the system begins forming a trading intention all the way to the wire — including what actually got submitted and filled.*