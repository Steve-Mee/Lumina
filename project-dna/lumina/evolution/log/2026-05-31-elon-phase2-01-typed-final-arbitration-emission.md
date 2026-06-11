# 2026-05-31 — Phase 2 Slice 01: First Forcing Function — Emit Typed Final Arbitration Result on the Event Bus Spine

**Parent**: 
- `2026-05-31-elon-phase1-3-complete.md` (Phase 1.x series closed — aperture physically narrow, zero bypasses, zero traces)
- `2026-05-31-elon-aperture-hardening-90-day-roadmap.md` (Phase 2 Structural Closure)
- `2026-05-31-elon-musk-first-principles-trading-system-analysis.md` (global physics diagnosis + 60-day target)

**Protocol Status**: This is the formal opening hypothesis entry for the first concrete slice of Phase 2. No implementation work will begin until this entry exists and the approved Plan Mode document has been executed.

---

## Hypothesis (Strict Adherence to Global Plan)

Now that Phase 1 has made the capital aperture **narrow by construction** (the late authoritative Admission Chain + Final Arbitration is the single unavoidable path in strict modes, protected by a permanent regression detector), the next physics-grade step is to make that single path the **primary observable nervous system**.

The original 60-day target from the Elon first-principles analysis was:
> "Every critical trading decision (agent proposal → risk allocation → arbitration decision → order submit) is observable as a single correlated lineage on the Event Bus (one decision_context_id or hash chain spanning multiple topics)."

Today the infrastructure already exists:
- The topic `"risk.final_arbitration.result"` is registered with a strict Pydantic model (`FinalArbitrationResult`).
- The topic is listed in `CRITICAL_EVENT_BUS_TOPICS`.
- `publish_validated` + registry enforcement already exists and is fail-closed for critical topics.

**The gap**: The canonical call site (`order_gatekeeper.py` calling `FinalArbitration.check_order_intent`) never emits this critical typed event. The most important decision in the now-narrow aperture remains invisible on the central bus.

**Hypothesis**: Instrumenting the canonical single path to always publish the already-registered critical typed event (with decision_context_id threaded from the AdmissionContext) will be the highest-leverage, lowest-risk first move in Phase 2. It creates immediate, painful visibility into the current state of the "spine" (starting from 0%), establishes the forcing function pattern for the rest of Phase 2, and directly advances the 60-day lineage target without any behavior change to the gate itself.

This follows the exact pattern that succeeded in Phase 0/1.1: **first make the current inadequate reality impossible to ignore via forcing functions**, then close the gap in subsequent small slices.

---

## Falsifiable Predictions (Measurable within 14-30 days)

1. After this slice lands: Every execution of the canonical Final Arbitration path (in unit tests, SIM, and paper-guard) produces a `DomainEvent` on topic `"risk.final_arbitration.result"` carrying a validated `FinalArbitrationResult` payload (verifiable via `event_bus.history()` / `latest()`).

2. Guardian will report a new "Phase 2 Typed Spine — Final Arbitration Emissions" metric showing the % of arbitration decisions that appeared on the typed critical bus (baseline before slice = 0%).

3. `agent-context.md` will contain a visible "Event Bus Spine Health" block showing the gap and progress.

4. Any future code change that routes an order through Final Arbitration without the typed bus emission will be caught either by new tests or by Guardian degradation.

5. The change remains fully reversible in < 5 minutes with no impact on order acceptance behavior.

---

## Scope of This Slice (Deliberately Tiny)

**In scope (maximum 5 files)**:
- Add the publish of the existing critical model in `lumina_core/order_gatekeeper.py` immediately after the arbitration call (threading decision_context_id from the AdmissionContext).
- Add assertions in relevant tests that the event is emitted.
- Extend Guardian with one small new check for this critical topic.
- Publish this evolution entry + a slice completion entry.
- Minimal update to `agent-context.md`.

**Explicitly out of scope (to prevent deviation)**:
- Any change to FinalArbitration logic or its return value.
- Adding hash chaining or Merkle trees (later Phase 2 slice).
- Changing Event Bus implementation.
- Touching any other publish sites yet.
- Performance work on the gate.

---

## Skill Reviews (Mandatory Before Code)

This slice touches a core risk decision path + typed Event Bus contract.

- **event-bus-contract** skill will be applied (the topic is already critical and registered; we are finally using it from the canonical path).
- **constitution-guard** skill will be applied (risk decision transparency + fail-closed principles).

Results will be recorded in the slice completion entry.

---

## Why This Slice, Why Now (Global Plan Fidelity)

The 90-day north star requires the single path to be **fully typed, constitution-audited, Final-Arbitration-enforced, hash-chained**.

Phase 1 delivered "narrow + enforced".
Phase 2 must deliver "typed + observable as the universal spine".

Starting with the most important decision (Final Arbitration) emitting its already-modeled critical event is the smallest, most direct, most measurable step that makes the current gap scream. This is exactly how Elon-style first-principles execution has been conducted throughout this track: visibility and forcing functions before deeper structural work.

No deviations from the 2026-05-31 global plan will be tolerated.

---

## Reversibility & Safety

- Purely additive observability on an already-critical registered topic.
- If the publish causes any issue, it can be commented out or guarded by a one-line feature flag in minutes.
- No change to what orders are accepted or rejected.

---

**This entry opens the first concrete slice of Phase 2. Implementation will only begin after Plan Mode approval and skill reviews.**

*Red thread maintained. End goal in view. No deviations.*