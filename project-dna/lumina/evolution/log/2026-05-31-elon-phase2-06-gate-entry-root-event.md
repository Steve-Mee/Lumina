# 2026-05-31 — Phase 2 Slice 06: Establish the Root of the Decision Lineage at Gate Entry

**Parent**:
- `2026-05-31-elon-phase2-05-complete.md`
- `2026-05-31-elon-aperture-hardening-90-day-roadmap.md` (Phase 2 deliverable 2: full lineage for risk allocations, arbitration decisions, and order submissions with decision_context_id + prev_hash chaining)

**Protocol Status**: This is the formal opening hypothesis entry for Phase 2 Slice 06. No implementation begins until this entry and a dedicated Plan Mode are complete.

---

## Hypothesis

We now have the Risk Allocation decision and Final Arbitration decision as typed, correlated, hash-chained events.

However, the lineage still lacks a clear **root**. The `decision_context_id` is generated inside `enforce_pre_trade_gate`, but there is no first-class typed event that marks "an order intent has entered the authoritative admission chain" as the starting point of the chain.

**Hypothesis**:
Emitting a minimal, lightweight typed event at the absolute earliest point in `enforce_pre_trade_gate` (right after generating the `decision_context_id`), called something like `admission.gate_entry` or `order_intent.received`, carrying the decision_context_id + initial context (symbol, proposed_risk, mode, etc.), will create the proper root of the decision lineage.

Subsequent events (Risk Allocation, Final Arbitration) can then chain back to this root via `prev_hash`.

This is the smallest possible slice that gives every pre-trade decision a single, unambiguous root on the Event Bus, directly advancing the "full lineage" requirement.

---

## Falsifiable Predictions

1. After this slice, every call to the canonical `enforce_pre_trade_gate` will immediately emit a typed `admission.gate_entry` (or equivalent) event with the `decision_context_id`.

2. The Risk Allocation decision event will carry a `prev_hash` that matches the fingerprint of this gate entry event (or the chain will be traceable back to it via the reconstruction helper).

3. `reconstruct_risk_decision_chain` (or a new small helper) can now return a clean chain starting from the gate entry root.

4. Guardian shows "Pre-Trade Decision Lineage Root Coverage" improving.

5. Zero impact on latency or any risk logic.

---

## Scope (Strictly Limited)

**In scope**:
- At the very beginning of `enforce_pre_trade_gate` (after creating `decision_context_id`), emit a small typed event on a new or existing critical topic (e.g. `admission.gate_entry`).
- Define a minimal Pydantic model for it (or reuse/extend an existing one).
- Ensure the event is published via `publish_validated` on the critical path.
- Update the reconstruction helper to recognize this as the root.
- Add one focused test.
- Guardian note + public entries.

**Out of scope**:
- Full agent proposal lineage (that comes later when we connect upstream).
- Changing any existing event structures significantly.
- Adding heavy payload to the root event.

---

## Why This Slice Now

The global plan wants **full lineage** with a clear chain. Without a root event at the moment the intent hits the authoritative gate, the lineage is still "floating" — it starts somewhere in the middle.

Creating the root now, while the chain is still small and manageable (gate entry → risk allocation → final arbitration), is the perfect incremental step.

It also creates a natural attachment point for future upstream lineage (agent proposal, dream state, etc.) when we expand further.

This is classic small, forcing-function, physics-first execution.

---

## Reversibility & Safety

- The new root event is purely additive and best-effort.
- Can be removed or made optional in < 1 minute.
- No effect on any decision or capital protection.

---

**This entry opens Phase 2 Slice 06.** Plan Mode + skill reviews (constitution-guard + event-bus-contract) required before implementation.

*Red thread: Every critical trading decision must eventually have a single, unbroken, hash-chained lineage starting from the moment it enters the authoritative aperture.*