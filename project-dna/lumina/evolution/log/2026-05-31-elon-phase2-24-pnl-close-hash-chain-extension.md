# 2026-05-31 — Phase 2 Slice 24: Extend the Cryptographic Hash Chain into P&L Attribution, Position Close Events, and Netting (Using the Now-Real Verification Pattern)

**Parent**:
- `2026-05-31-elon-phase2-23-complete.md` (Slice 23 made actual cryptographic hash_ok real for fills)
- `2026-05-31-elon-phase2-22-complete.md` (Slice 22 made real fills automatically visible to provenance/Guardian)
- `2026-05-31-elon-aperture-hardening-90-day-roadmap.md` (Phase 2 goal: continuous, verifiable cryptographic hash chain covering the full trade lifecycle)
- `2026-05-31-elon-musk-first-principles-trading-system-analysis.md`

**Protocol Status**: This is the formal opening hypothesis entry for Phase 2 Slice 24. No implementation begins until this entry and a dedicated Plan Mode (with constitution-guard + event-bus-contract + risk-safety-review) are complete.

---

## Hypothesis

In Slices 17–23 we built a complete, automatically visible, and now cryptographically verifiable hash chain from the earliest upstream intention (dream/proposals) all the way through Final Arbitration into actual broker fills.

**Current reality**:
- The chain stops (or becomes best-effort only) the moment a position is closed or PnL is realized.
- `EconomicPnLService`, `golden_ledger.realized_close_from_broker_fill`, `CloseLegLedgerResult`, and the close events in `trade_reconciler` carry economic numbers but have no `decision_context_id` / `prev_hash` threading from the originating fill(s) or the pre-trade decision.
- `PnlProvenance` exists as a tiny enum (BROKER_RECONCILED vs SIM_INTERNAL) but carries no lineage.
- As a result, even with perfect upstream + fill lineage, an auditor or the Guardian cannot cryptographically prove that a particular realized PnL figure belongs to a specific decision_context_id, nor can they walk the hash chain from final_arbitration → fill → close → net PnL.

**Hypothesis**:
Now that we have (a) automatic access to real fills (Slice 22), (b) real `hash_ok` verification on those fills (Slice 23), and (c) all the economic close/PnL machinery already keyed off broker fills, we can extend the exact same lineage + hash verification pattern one layer further.

By threading `decision_context_id` + `prev_hash` from the closing fill(s) into `CloseLegLedgerResult` (and the events that carry realized PnL), and by updating the reconstruction / provenance / Guardian paths to pull and verify these close/PnL nodes, the cryptographic hash chain becomes continuous through the entire economic outcome of a decision.

This is the smallest reversible step that makes the full trade lifecycle (intention → gate → risk decision → fill → close → realized PnL) part of one auditable, hash-verified spine.

---

## Falsifiable Predictions

1. After the slice, `CloseLegLedgerResult` (and/or the close events emitted by trade_reconciler) will carry `decision_context_id` and `prev_hash` (sourced from the exit fill that triggered the close).
2. The reconstruction helper (or a lightweight extension) will be able to surface close/PnL nodes as downstream events for a given decision_context_id, with real `hash_ok` computed against the preceding fill node.
3. `build_pretrade_provenance_report` (and its markdown formatter) will include a "Closes & Realized PnL" section showing the linked economic outcome with hash status.
4. The Guardian will be able to include these nodes in its daily chain health checks (best-effort) and scream if a realized PnL figure for a ctx has a broken hash link back to its originating fill/final_arbitration.
5. Zero behavior change to any PnL calculation, golden ledger formulas, position management, or ledger updates. All existing economic tests remain green.

---

## Scope (Strictly Limited — Lifecycle Extension Slice)

**In scope**:
- Add `decision_context_id` and `prev_hash` fields (best-effort, optional) to `CloseLegLedgerResult`.
- Update the call sites in `trade_reconciler` (and `EconomicPnLService` callers) to propagate the lineage from the exit fill that is closing the leg.
- Small extension (or new lightweight helper) in `decision_lineage.py` to pull close/PnL events for a ctx and compute hash_ok against the preceding fill node(s).
- Updates to `build_pretrade_provenance_report` and `format_provenance_report_as_markdown` to surface a "Closes & Realized PnL (Downstream Lineage)" section when data is present.
- Minor Guardian baseline note so the daily run can optionally surface close/PnL lineage health.
- Focused tests proving lineage threading + hash_ok for closes.
- Public hypothesis + completion entries.

**Out of scope (deferred)**:
- Full multi-leg netting hash chain (can be a follow-up once the single-leg close pattern is proven).
- Changes to the actual PnL *numbers* or any golden ledger math.
- Live broker changes for close events (the emission side can come later; we are extending the consumer/reconstruction side first, consistent with how we did fills).
- Shadow deployment or gate optimization (separate tracks on the list).

---

## Why This Slice Now

We have spent the last several slices making the hash chain real, visible, and screaming all the way into fills. The very next forcing-function step on the original 90-day list is to continue that same chain into the economic outcome (P&L and closes). 

Without this, even perfect upstream + fill lineage leaves the most financially consequential part of every decision (what it actually made or lost) outside the verifiable spine. This is the natural and highest-leverage continuation after Slice 23.

---

## Reversibility & Safety

- All new fields are optional/best-effort.
- PnL calculation paths are untouched — we only add metadata.
- Can be fully reverted by removing the two fields and the small reconstruction extension with zero impact on numbers or behavior.
- No change to REAL-mode risk limits, order acceptance, or capital decisions.

---

**This entry opens Phase 2 Slice 24.** Plan Mode + skill reviews (constitution-guard + event-bus-contract + risk-safety-review) required before implementation.

*Red thread: The cryptographic hash chain must be continuous through the entire economic life of a decision — from the first intention all the way to realized PnL and position close. User directive "Proceed with the next phase 2 slice from the list" after Slice 23.*