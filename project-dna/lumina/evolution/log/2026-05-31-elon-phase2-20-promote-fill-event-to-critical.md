# 2026-05-31 — Phase 2 Slice 20: Promote `execution.fill.received` to `CRITICAL_EVENT_BUS_TOPICS`

**Parent**:
- `2026-05-31-elon-phase2-19-complete.md` (Slice 19 made lineage first-class on Fill + publishers prefer it)
- `2026-05-31-elon-phase2-18-complete.md` (Slice 18 introduced the proper typed `execution.fill.received` + ExecutionFill model)
- `2026-05-31-elon-aperture-hardening-90-day-roadmap.md` (Phase 2 goal: clean, typed, observable, non-bypassable lineage on the universal spine with Guardian as daily forcing function)
- `2026-05-31-elon-musk-first-principles-trading-system-analysis.md`

**Protocol Status**: This is the formal opening hypothesis entry for Phase 2 Slice 20. No implementation begins until this entry and a dedicated Plan Mode (with constitution-guard + event-bus-contract + risk-safety-review) are complete.

---

## Hypothesis

In Slices 18 and 19 we achieved:
- A strict Pydantic `ExecutionFill` model carrying full lineage (`decision_context_id` + `prev_hash` + `prev_event_topic`).
- Best-effort publishing of `execution.fill.received` from the two primary fill paths (PaperBroker and trade_reconciler).
- First-class lineage fields on the central `Fill` dataclass with publishers and extraction helpers preferring them.
- Reconstruction and provenance reports can surface these events.

**Current reality**:
- The topic is registered in `EVENT_BUS_TOPIC_MODELS` and therefore gets model validation on `publish_validated`.
- However, it is **not** present in `CRITICAL_EVENT_BUS_TOPICS`.
- Consequence: validation failures on this topic are **swallowed** (publish_validated returns None, no exception propagates). This is the same soft path used for non-critical topics.
- The downstream cryptographic link (the only execution-side continuation of the hash chain after Final Arbitration) can still fail silently under load, during refactors, or in live broker paths — exactly the class of silent bypass the entire aperture hardening program exists to eliminate.

**Hypothesis**:
By adding `"execution.fill.received"` to `CRITICAL_EVENT_BUS_TOPICS` (a one-line change in schemas.py), we activate the existing strict machinery in EventBus:
- Any schema violation or missing model on a critical fill event will **hard-fail** (re-raise) instead of being swallowed.
- This makes the typed downstream lineage part of the same non-ignorable contract as `risk.final_arbitration.result`, `admission.gate_entry`, and the proposal topics.
- Combined with the first-class fields from Slice 19, the continuous hash chain now has a loud failure mode on its final segment.

This is the smallest reversible step that turns the execution-side lineage from "best-effort observable" into "critical and impossible to degrade silently".

---

## Falsifiable Predictions

1. After the slice, `"execution.fill.received"` will appear in `CRITICAL_EVENT_BUS_TOPICS` in schemas.py.
2. Publishing a malformed payload (missing required fields or bad lineage) to the topic via `publish_validated` will raise (instead of returning None) when the topic is critical.
3. The existing reconstruction in `decision_lineage.py` and the two publishers will continue to function unchanged (the model already exists; we only change the strictness flag).
4. Guardian baseline will record the new critical status; a future screaming rule for critical fill events with broken lineage can be added in a follow-up without API change.
5. Zero behavior change for all current successful fill publications in paper and test paths. All relevant tests remain green.

---

## Scope (Strictly Limited — Typed Spine Enforcement Slice)

**In scope**:
- Add the string `"execution.fill.received"` (or the constant `EXECUTION_FILL_RECEIVED_TOPIC`) to the `CRITICAL_EVENT_BUS_TOPICS` frozenset in `lumina_core/agent_orchestration/schemas.py`.
- One focused test (or extension of the existing Slice 18 test) proving that a bad publish to this now-critical topic raises instead of swallowing.
- Defensive update in `decision_lineage.reconstruct_risk_decision_chain` (or a small helper) to surface "critical fill event present but lineage missing" as a distinct anomaly (best-effort).
- Guardian baseline note + narrow agent-context.md paragraph.
- Public hypothesis + completion entries.

**Out of scope (deferred to later slices)**:
- Adding many new live subscribers or complex fill consumers (P&L attribution, auto-reconciliation, etc.).
- Changing any live broker wire format.
- Promoting the topic in BLACKBOARD_TOPIC_MODELS (different concern).
- Full Guardian screaming rule for malformed critical fill events (can be a tiny follow-up once the flag is set).
- Removing the "best-effort" wrapper from the two publishers (that is a separate reliability slice).

---

## Why This Slice Now

Slices 15–19 built the actual cryptographic and typed downstream chain. The last missing piece for "continuous hash chain on the declared universal spine" is making the final execution event **critical** under the same rules that already protect the pre-trade gates and Final Arbitration.

This directly advances two Phase 2 forcing functions from the 90-day roadmap:
- Typed events with strict contracts.
- Guardian as daily screaming detector (once critical, future degradations become impossible to miss in CI or Guardian runs).

It is the exact next item called out in the Slice 18 and Slice 19 completion lists.

---

## Reversibility & Safety

- Removing one string from a frozenset is a one-line revert with zero behavior impact on successful paths.
- All current publishers already produce valid `ExecutionFill` payloads (proven by Slice 18/19 tests).
- No change to any order, risk, position, or ledger logic.
- The strictness only activates on **bad** publishes — which is the desired fail-closed outcome.

---

**This entry opens Phase 2 Slice 20.** Plan Mode + skill reviews (constitution-guard + event-bus-contract + risk-safety-review) required before implementation.

*Red thread: The lineage on the single authoritative path must not only exist and be first-class — the events that carry it must be under the same un-bypassable critical contract as the gates that precede them. User directive "Proceed with the next phase 2 slice from the list" after Slice 19 completion.*