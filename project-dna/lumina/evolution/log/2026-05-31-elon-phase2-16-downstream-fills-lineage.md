# 2026-05-31 — Phase 2 Slice 16: Extend Downstream Lineage into Fills and Execution Events

**Parent**:
- `2026-05-31-elon-phase2-15-complete.md` (Slice 15 delivered the first cryptographic link from Final Arbitration into order submission — decision_context_id + prev_hash now travel with the Order at the broker boundary)
- `2026-05-31-elon-phase2-15-downstream-order-fills-lineage.md` (hypothesis for beginning downstream lineage)
- `2026-05-31-elon-aperture-hardening-90-day-roadmap.md` (Phase 2 deliverable 2: full lineage including order submissions, with the long-term goal of end-to-end provenance "all the way to the wire")

**Protocol Status**: This is the formal opening hypothesis entry for Phase 2 Slice 16. No implementation begins until this entry and a dedicated Plan Mode are complete.

---

## Hypothesis

In Slice 15 we successfully created the first downstream cryptographic link:
- At the post-Final-Arbitration submission boundary (`policy_engine.execute_order`), the `Order` object now reliably carries the pre-trade `decision_context_id` (recovered best-effort when missing) plus a `prev_hash` pointing to the preceding `risk.final_arbitration.result` event.

**Current reality**:
- The lineage now crosses from the pre-trade decision into the order submission act itself.
- However, once the order is accepted by the broker, the actual fills, partial fills, position updates, and execution events still have no lineage connection back to the authorizing decision_context_id or the hash chain.
- There is still a break in the "single authoritative path" between submission and what actually happened in the market (fills, slippage, position state).

**Hypothesis**:
By extending the same `decision_context_id` + `prev_hash` threading one step further — into the first fill/execution recording events after submission — we will make the lineage continuous from Final Arbitration through actual order execution.

This is the smallest reversible next slice that meaningfully advances the downstream half of the original Phase 2 deliverable ("full lineage for order submissions") and the long-term north star of unbroken provenance "all the way to the wire".

---

## Falsifiable Predictions

1. After the slice, fill/execution events (or the position update records that result from them) will carry the `decision_context_id` from the originating order.
2. At least one fill-related event or position update will contain a `prev_hash` that points back to the submission event (or the Final Arbitration event) for the same decision_context_id.
3. The reconstruction helper (or a lightweight extension) will be able to continue the chain past submission into at least the first fill/position state for affected decision_context_ids.
4. Zero behavior change or risk impact on actual fill handling, position management, or ledger updates.
5. The change remains best-effort and fully reversible.

---

## Scope (Strictly Limited — Second Downstream Slice)

**In scope**:
- Identify the immediate post-submission execution recording points (fills, position updates, or ledger entries in trade_workers, operations_service, or the broker result handling path).
- Thread `decision_context_id` from the submitted Order into the first fill/position recording events (best-effort).
- Attach `prev_hash` on the first downstream execution event(s), linking back to the submission (or the arbitration event).
- Minimal update to the reconstruction helper so it can surface these new downstream nodes when present.
- One focused test proving the submission → first fill/position cryptographic link.
- Public completion entry + narrow Guardian/provenance note.

**Out of scope (deferred to later slices)**:
- Full end-to-end downstream lineage (every partial fill, multiple orders from one decision, P&L attribution, etc.).
- Changing any fill logic, position calculations, or ledger writing behavior.
- Comprehensive event publishing for every execution detail.
- Shadow deployment integration.

---

## Why This Slice Now

Slice 15 gave us the first bridge across the pre-trade / execution boundary.

The chain is still broken immediately after submission. To keep the forcing-function momentum and continue delivering on the original 90-day roadmap commitment for "full lineage for order submissions", the next smallest measurable step is to pull the lineage one layer deeper into actual fills and position state.

This maintains the "small, reversible slices" discipline while steadily closing the downstream gap.

---

## Reversibility & Safety

- All changes are additive metadata and optional event enrichment on the execution recording path.
- Can be rolled back in minutes with no effect on trading, fills, positions, or risk.
- Best-effort only — if the id or previous hash is unavailable, existing behavior is unchanged.
- No modification to any fill logic, position calculations, or broker result handling.

---

**This entry opens Phase 2 Slice 16.** Plan Mode + skill reviews (constitution-guard + event-bus-contract + risk-safety-review) required before implementation.

*Red thread: The single authoritative path must eventually have unbroken cryptographic lineage from the first moment of intention all the way through submission and into what actually happened in the market.*