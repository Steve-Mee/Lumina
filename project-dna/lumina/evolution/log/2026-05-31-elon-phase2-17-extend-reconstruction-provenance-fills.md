# 2026-05-31 — Phase 2 Slice 17: Extend Reconstruction and Provenance Reports to Surface Fills and Execution Events

**Parent**:
- `2026-05-31-elon-phase2-16-complete.md` (Slice 16 propagated lineage into Fill and OrderResult objects)
- `2026-05-31-elon-phase2-14-complete.md` (the human-readable pre-trade provenance report)
- `2026-05-31-elon-aperture-hardening-90-day-roadmap.md` (Phase 2/3 goal of making the full chain easily observable and auditable by humans)

**Protocol Status**: This is the formal opening hypothesis entry for Phase 2 Slice 17. No implementation begins until this entry and a dedicated Plan Mode are complete.

---

## Hypothesis

In Slice 16 we made the cryptographic lineage reach the actual fill level:
- Fill and OrderResult objects now carry `decision_context_id` + `prev_hash` (in their `raw` dicts) when created from an Order that had lineage.

**Current reality**:
- The data now exists in the execution objects.
- However, the reconstruction helper (`reconstruct_risk_decision_chain`) and the human-readable provenance report (`build_pretrade_provenance_report` + `format_as_markdown`) do not yet surface fills, execution events, or position updates.
- A human (or the Guardian) looking at a provenance report for a decision_context_id still only sees the pre-trade + submission story. The actual fills, slippage, commissions, and final position state remain invisible in the primary audit artifact.

**Hypothesis**:
By extending the reconstruction helper and the provenance report generator to natively consume and present downstream fill/execution data (using the lineage fields we just added), we will make the full chain — from earliest intention all the way through fills — visible and human-consumable in one place.

This is the smallest reversible slice that turns the downstream lineage work (Slices 15–16) into immediate, high-value observability for audits, post-trade analysis, and Guardian reporting.

---

## Falsifiable Predictions

1. After the slice, `reconstruct_risk_decision_chain` (or a small extension) will return fill/execution nodes when they exist for a decision_context_id, with proper prev_hash linking from the submission event.
2. The provenance report builder will include a new "Execution / Fills" section (or extend the existing downstream section) containing key fill details (price, quantity, commission, slippage if available) plus hash integrity status.
3. `format_as_markdown` will render the fills section cleanly in the human-readable report.
4. The Guardian will be able to surface fill-level information for recent decisions (at minimum via the provenance report helper).
5. Zero behavior change to any trading, risk, or ledger logic. All changes are read-only reporting extensions.

---

## Scope (Strictly Limited)

**In scope**:
- Extend `reconstruct_risk_decision_chain` (or add a companion function) to pull recent fills/execution events that carry `decision_context_id` (from broker fills, trade_reconciler, or any existing execution events).
- Update `build_pretrade_provenance_report` to include a "fills" / "execution" section when downstream data exists.
- Update `format_as_markdown` to render the new section nicely.
- Add one focused test that submits an order with lineage, captures the resulting fills, and verifies the report contains the fill data with correct linking.
- Small Guardian note (optional: surface fills in broken-chain warnings or provenance output).
- Public completion entry.

**Out of scope**:
- Adding new typed Event Bus topics for fills (can be done in parallel or later).
- Promoting the lineage fields on Fill/OrderResult from `raw` dict to first-class fields (separate hygiene slice).
- Full P&L attribution or multi-order netting logic.
- Changes to any live broker polling/websocket code.
- Shadow deployment integration.

---

## Why This Slice Now

We have spent significant effort (Slices 15 and 16) pushing the hash chain past Final Arbitration into real execution artifacts.

If we stop here, the downstream data exists but is hard to find and use. The highest-leverage next step is to make that data visible in the two primary tools humans use for understanding decisions:
- The reconstruction helper (programmatic)
- The provenance report (human + Guardian)

This directly serves the "one human, 20 minutes" audit goal and keeps the forcing function alive on the full end-to-end chain.

---

## Reversibility & Safety

- Purely additive read-only extensions to reporting functions.
- No side effects on trading, risk, fills, positions, or ledger.
- Can be removed in minutes.
- Best-effort (if no fill data exists for a ctx, the report simply omits the section or shows "no fills found").

---

**This entry opens Phase 2 Slice 17.** Plan Mode + skill reviews (constitution-guard + event-bus-contract) required before implementation.

*Red thread: The single authoritative path must not only be hash-chained — its complete history, including what actually happened in the market, must be trivially understandable by a human in minutes.*