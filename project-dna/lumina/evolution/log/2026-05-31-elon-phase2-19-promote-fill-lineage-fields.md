# 2026-05-31 — Phase 2 Slice 19: Promote Lineage Fields on the `Fill` Dataclass to First-Class (Instead of Only `raw`)

**Parent**:
- `2026-05-31-elon-phase2-18-complete.md` (Slice 18 published proper typed `execution.fill.received` events on the Event Bus with full lineage)
- `2026-05-31-elon-phase2-16-complete.md` (Slice 16 started propagating lineage into Fill and OrderResult objects via `raw`)
- `2026-05-31-elon-aperture-hardening-90-day-roadmap.md` (Phase 2 goal of clean, typed, observable lineage on critical execution events)

**Protocol Status**: This is the formal opening hypothesis entry for Phase 2 Slice 19. No implementation begins until this entry and a dedicated Plan Mode are complete.

---

## Hypothesis

In Slices 16 and 18 we achieved:
- Lineage (`decision_context_id` + `prev_hash`) is now carried on fills.
- Fills are published as first-class typed events on the Event Bus (`execution.fill.received`).

**Current reality**:
- The lineage on `Fill` objects lives only inside the `raw` dict (a catch-all passthrough field).
- This works functionally, but it is not clean, not typed at the dataclass level, and not obvious to future developers or auditors that the lineage is there.
- The `Fill` dataclass (and by extension `OrderResult` in some paths) still does not declare the lineage fields as first-class citizens, which weakens the long-term contract and makes the downstream lineage feel like an afterthought rather than a core part of the execution model.

**Hypothesis**:
By promoting the lineage fields (`decision_context_id`, `prev_hash`, `prev_event_topic`) to explicit, first-class fields on the `Fill` dataclass (with proper defaults and documentation), we will make the downstream lineage a clean, obvious, and enforceable part of the execution data model.

This is the smallest reversible hygiene slice that strengthens the contract we have been building across Slices 15–18, without changing any behavior.

---

## Falsifiable Predictions

1. After the slice, the `Fill` dataclass will have explicit optional fields for `decision_context_id`, `prev_hash`, and `prev_event_topic`.
2. All existing code paths that create `Fill` objects (paper broker, live broker paths, reconciler) will continue to work without modification (backward compatible via defaults).
3. The typed `execution.fill.received` event model and publishing logic will be updated to use the new first-class fields (or keep populating both for transition).
4. The reconstruction helper and provenance report will prefer the new first-class fields when present (with `raw` as fallback during transition).
5. Zero behavior change to any fill logic, position management, or ledger updates.

---

## Scope (Strictly Limited — Hygiene Slice)

**In scope**:
- Add three new optional fields to the `Fill` dataclass in `broker_bridge.py`:
  - `decision_context_id: str | None = None`
  - `prev_hash: str | None = None`
  - `prev_event_topic: str | None = None`
- Update the places that construct `Fill` objects (PaperBroker, CrossTradeBroker fill ingestion, any test helpers) to populate the new fields from the lineage that is currently in `raw` (or from the originating Order).
- Update the `ExecutionFill` Pydantic model (or keep it mapping from the dataclass) for consistency.
- Small, defensive updates in `decision_lineage.py` helpers to read from the new fields first, then fall back to `raw`.
- One focused test confirming the new fields are populated on created fills.
- Public completion entry + narrow Guardian / agent-context note.

**Out of scope (deferred)**:
- Removing the lineage from `raw` entirely (we can do a cleanup pass later once everything is migrated).
- Doing the same promotion on `OrderResult` or `Position` (can be follow-up slices).
- Changing any live broker wire protocol or fill polling logic.
- Adding new typed events (already done in Slice 18).

---

## Why This Slice Now

We have spent four slices (15–18) pushing the hash chain into fills and making it observable on the Event Bus and in reports.

The current implementation still hides the lineage in a generic `raw` dict. This is functional but not the clean, first-class contract the overall Phase 2 vision demands.

Promoting the fields is the natural, small, reversible hygiene step that makes the downstream lineage "real" at the model level, exactly as we did for pre-trade events earlier in the plan.

---

## Reversibility & Safety

- Adding optional fields with defaults is 100% backward compatible.
- All existing `Fill(...)` constructions continue to work.
- Can be reverted in one commit with no behavior change.
- No impact on any fill price, commission, position, risk, or ledger logic.

---

**This entry opens Phase 2 Slice 19.** Plan Mode + skill reviews (constitution-guard + event-bus-contract) required before implementation.

*Red thread: The lineage on the single authoritative path must not only exist — it must be clean, obvious, and first-class in the data models that carry it.*