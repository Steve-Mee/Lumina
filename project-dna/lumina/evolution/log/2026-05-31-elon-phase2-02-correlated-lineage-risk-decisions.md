# 2026-05-31 — Phase 2 Slice 02: Correlated Lineage Between Risk Policy Decision and Final Arbitration on the Event Bus

**Parent**:
- `2026-05-31-elon-phase2-01-complete.md` (Slice 01 delivered typed emission of Final Arbitration result)
- `2026-05-31-elon-musk-first-principles-trading-system-analysis.md` (60-day target)
- `2026-05-31-elon-aperture-hardening-90-day-roadmap.md` (Phase 2 Structural Closure)

**Protocol Status**: This is the formal opening hypothesis entry for Phase 2 Slice 02. No implementation begins until this entry and a dedicated Plan Mode are complete.

---

## Hypothesis

Phase 2 Slice 01 successfully made the two most important risk decisions in the now-narrow aperture (Risk Policy decision + Final Arbitration decision) emit as first-class typed events on the critical Event Bus.

However, these two events are still not reliably **correlated** into a single observable lineage. Different parts of the gate may generate or fail to propagate a `decision_context_id`, and there is no explicit link between the "risk.policy.decision" event and the subsequent "risk.final_arbitration.result" event for the same order attempt.

**Hypothesis**:
Establishing a single, consistently generated `decision_context_id` at the entry point of the canonical pre-trade gate, propagating it through both the policy decision and the final arbitration decision, and adding simple chaining metadata (e.g. `policy_decision_ref` on the arbitration event) will create the first real "correlated lineage" on the bus for the core risk decisions.

This is the smallest possible slice that directly advances the explicit 60-day target from the original Elon analysis:
> "Every critical trading decision ... is observable as a single correlated lineage on the Event Bus (one `decision_context_id` or hash chain spanning multiple topics)."

It follows the proven pattern: make the current state (weak correlation) visible and enforceable first, then deepen (hash chaining, full provenance) in later slices.

---

## Falsifiable Predictions

1. After this slice, for any execution of the canonical gate in tests/SIM/paper-guard, the `risk.policy.decision` and `risk.final_arbitration.result` events for the same order attempt will share the exact same `decision_context_id` in their metadata.

2. The arbitration event will contain a reference (in metadata) to the policy decision event (e.g. via sequence number or a generated id), enabling simple reconstruction of the two-step risk decision chain.

3. Guardian will report a new "Correlated Lineage Coverage" metric (initially low, then rising) for risk decisions.

4. A new test will prove that the two events are linkable via the shared decision_context_id.

5. The change remains fully reversible and has zero impact on gate behavior or capital protection.

---

## Scope (Strictly Limited)

**In scope**:
- Ensure a single `decision_context_id` is generated (or taken from context) at the very start of `enforce_pre_trade_gate` / the admission process.
- Propagate this id consistently into both the existing RiskVerdict emission and the new Final Arbitration emission.
- Add lightweight chaining metadata on the arbitration event pointing back to the policy decision (using the event bus sequence or a simple id).
- Update the relevant test to assert the correlation.
- Extend Guardian with a basic lineage correlation check.
- Public evolution entry + completion entry.

**Out of scope** (to keep the slice small and reversible):
- Full cryptographic hash chaining (Merkle / prev_hash) — this will be Slice 03 or later.
- Lineage for agent proposals, dream state, etc. (later in Phase 2).
- Changes to any other publish sites.
- Performance or schema changes.

---

## Why This Slice Now (Global Plan Fidelity)

The global plan's 60-day success criterion is not just "events on the bus" — it is **correlated lineage**. We have two critical events thanks to Slice 01. Making them actually correlated is the direct, minimal, high-signal next step toward the north star.

This keeps the "small, measurable, reversible slices" discipline and the "first make the gap visible" pattern that has worked throughout the entire aperture hardening track.

No deviations from the 2026-05-31 Elon first-principles plan will be accepted.

---

## Reversibility & Safety

- All changes are additive metadata on already-emitted typed events.
- The id generation can be disabled with a one-line guard.
- No effect on any risk decision, blocking logic, or capital protection.

---

**This entry opens Phase 2 Slice 02.** Plan Mode and skill reviews (event-bus-contract + constitution-guard) are required before implementation.