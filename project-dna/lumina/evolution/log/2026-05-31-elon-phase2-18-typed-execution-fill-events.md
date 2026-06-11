# 2026-05-31 — Phase 2 Slice 18: Publish Proper Typed `execution.fill` Events on the Event Bus with Full Lineage

**Parent**:
- `2026-05-31-elon-phase2-17-complete.md` (Slice 17 made fills visible inside the reconstruction helper and the human-readable provenance report)
- `2026-05-31-elon-phase2-16-complete.md` (Slice 16 started propagating lineage into Fill and OrderResult objects)
- `2026-05-31-elon-aperture-hardening-90-day-roadmap.md` (Phase 2 deliverable 2: "100% of agent proposals, risk allocations, arbitration decisions, and order submissions published as typed events with full lineage (decision_context_id + prev_hash chaining)")

**Protocol Status**: This is the formal opening hypothesis entry for Phase 2 Slice 18. No implementation begins until this entry and a dedicated Plan Mode are complete.

---

## Hypothesis

In Slices 15–17 we achieved:
- Cryptographic lineage (decision_context_id + prev_hash) now reaches actual Fill and OrderResult objects (Slice 16).
- Those fills are consumable and visible inside the reconstruction helper and the main provenance report (Slice 17).

**Current reality**:
- The lineage data exists inside the `raw` dict of Fill objects.
- However, fills are still not published as first-class, typed events on the main Event Bus (the declared universal spine of the system).
- The only downstream execution event that is properly typed today is the relatively coarse `trading_engine.execution.aggregate`.
- As a result, the full hash-chained lineage for what actually happened in the market is not yet "on the nervous system" in the same strict, observable, auditable way as the pre-trade path.

**Hypothesis**:
By introducing a proper typed `execution.fill` topic (with a clean Pydantic contract) and publishing it (best-effort) from the broker layer whenever a fill occurs — carrying the `decision_context_id` and `prev_hash` we already have — we will make the downstream half of the capital aperture first-class on the Event Bus.

This is the smallest reversible slice that meaningfully advances the original Phase 2 commitment of "full lineage for order submissions" being published as typed events, while making the entire chain observable on the single declared universal spine.

---

## Falsifiable Predictions

1. After the slice, a new typed topic `"execution.fill"` (or `"execution.fill.received"`) will exist in `EVENT_BUS_TOPIC_MODELS` with a proper Pydantic model.
2. When a fill is created/ingested (paper or live path), a typed `execution.fill` event will be published via `publish_validated`, carrying at minimum `decision_context_id`, `prev_hash`, and the key fill fields (symbol, side, quantity, price, commission, etc.).
3. The reconstruction helper will be able to pull these events from the main bus when present for a decision_context_id.
4. The provenance report will be able to surface them (building on Slice 17).
5. Zero behavior change to any fill logic, position management, or ledger updates. Publishing is best-effort and non-blocking.

---

## Scope (Strictly Limited)

**In scope**:
- Add a minimal but clean `ExecutionFill` (or `FillReceived`) Pydantic model in `schemas.py`.
- Register the topic in `EVENT_BUS_TOPIC_MODELS` (and consider adding it to `CRITICAL_EVENT_BUS_TOPICS` if we decide it should be strict).
- In `broker_bridge.py` (PaperBroker and the abstract/lifecycle points), after a fill is created or received, publish the typed event via the engine's event_bus (if available), including the lineage fields from the Fill's `raw` (or from the original Order).
- Do the same best-effort publishing point in the live broker fill ingestion path (CrossTrade) and in `trade_reconciler.ingest_fill_event` where appropriate.
- Small update to `decision_lineage.py` so `reconstruct_risk_decision_chain` can pull the new topic.
- One focused test that triggers a fill with lineage and verifies the typed event is published with correct fields and prev_hash.
- Public completion entry + Guardian note.

**Out of scope (deferred)**:
- Promoting the lineage fields on the `Fill` dataclass itself from `raw` to first-class fields (separate hygiene slice).
- Full downstream to P&L attribution.
- Making every possible execution detail a separate typed event.
- Shadow deployment integration.

---

## Why This Slice Now

We have spent three slices (15–17) pushing the hash chain into actual fills and making that data visible in reports.

The data is still "inside objects" rather than "on the Event Bus." 

The original 2026-05-31 plan and the 90-day roadmap are explicit: the goal is not just that the lineage exists, but that critical events — including order submissions and their downstream consequences — are published as **typed events on the Event Bus**.

Publishing a proper `execution.fill` topic is the direct, forcing-function next step that puts the downstream lineage onto the declared universal spine.

---

## Reversibility & Safety

- Publishing is best-effort and wrapped (never blocks fill handling).
- The new topic and model are additive.
- Can be removed or made non-critical easily.
- No changes to any fill price, commission, position, or ledger logic.

---

**This entry opens Phase 2 Slice 18.** Plan Mode + skill reviews (constitution-guard + event-bus-contract + risk-safety-review) required before implementation.

*Red thread: The single authoritative path must have its critical events — all the way through fills — published as typed, hash-chained events on the universal Event Bus.*