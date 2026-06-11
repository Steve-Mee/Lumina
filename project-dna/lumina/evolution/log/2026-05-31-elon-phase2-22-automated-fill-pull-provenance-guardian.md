# 2026-05-31 — Phase 2 Slice 22: Wire the Provenance Report and Guardian to Automatically Pull Recent Fills from Broker/Ledger for a decision_context_id (Full End-to-End Daily Forcing Function)

**Parent**:
- `2026-05-31-elon-phase2-21-complete.md` (Slice 21 activated Guardian screaming on critical fill events)
- `2026-05-31-elon-phase2-17-complete.md` (Slice 17 added manual `recent_fills=` support to the provenance report)
- `2026-05-31-elon-aperture-hardening-90-day-roadmap.md` (Phase 2 deliverable: automated daily end-to-end lineage visibility in Guardian + provenance)
- `2026-05-31-elon-musk-first-principles-trading-system-analysis.md`

**Protocol Status**: This is the formal opening hypothesis entry for Phase 2 Slice 22. No implementation begins until this entry and a dedicated Plan Mode (with constitution-guard + event-bus-contract + risk-safety-review) are complete.

---

## Hypothesis

In Slices 17–21 we built:
- The ability for `build_pretrade_provenance_report(..., recent_fills=...)` to surface execution fills.
- First-class lineage fields on Fill.
- Typed critical `execution.fill.received` events.
- Guardian daily screaming when those critical fill events lack proper lineage.

**Current reality**:
- The provenance report and Guardian screaming for fills still require the caller to manually provide `recent_fills`.
- In practice this means:
  - The CLI (`python -m lumina_core.risk.decision_lineage <ctx>`) produces incomplete reports (no fills section).
  - The Guardian screaming (Slice 21) is limited to whatever happens to be in the event bus history or blackboard JSONL at the moment of the run.
- The full cryptographic chain stops being "daily forcing function" the moment we leave the pre-trade gates, because real broker fills are not automatically pulled and attached.

**Hypothesis**:
By adding best-effort automatic fill pulling inside `build_pretrade_provenance_report` (and exposing it cleanly to the Guardian and CLI), using the existing broker's `get_fills()` / list_fills capability (now that fills carry first-class `decision_context_id` from Slices 19–20), we make the provenance report and Guardian screaming automatically complete for the downstream side.

When a broker (Paper or live via CrossTrade pattern) is available in the calling context, the report will automatically fetch recent fills, filter those carrying the target decision_context_id, and include them — with no change to the public API for callers who still want to pass their own list.

This turns the screaming we activated in Slice 21 into a complete, automated, daily end-to-end forcing function for the entire capital aperture lineage.

---

## Falsifiable Predictions

1. After the slice, calling `build_pretrade_provenance_report(ctx)` (with no `recent_fills`) in an environment that has a broker with recent fills for that ctx will automatically include a populated "fills" section.
2. The CLI `python -m lumina_core.risk.decision_lineage <ctx>` will now surface fills when data is available in the broker (no manual work required).
3. The Guardian (when it has access to a broker or engine) will be able to pass recent fills into the screaming / provenance path, making downstream warnings much more complete and actionable.
4. Existing callers that explicitly pass `recent_fills=` continue to work unchanged (backward compatible).
5. Zero behavior change to any trading, risk, order, or ledger logic. All existing tests for reconstruction and provenance remain green.

---

## Scope (Strictly Limited — Automation of Existing Capability)

**In scope**:
- Add best-effort automatic fill fetching logic inside (or called by) `build_pretrade_provenance_report` when `recent_fills` is not provided.
- Use the engine's broker (if present in context) and call its `get_fills()` / equivalent, then filter by `decision_context_id` using the first-class field (or raw fallback).
- Support the documented PaperBroker + CrossTrade pattern (and note the contract for other live brokers).
- Update the CLI entry point to benefit automatically.
- Small update in the Guardian to attempt passing broker fills when available (best-effort, inside existing try blocks).
- Guardian baseline note + narrow agent-context update.
- Public hypothesis + completion entries.
- Focused verification (manual CLI run + Guardian run showing improved fill data).

**Out of scope (deferred)**:
- Heavy new broker querying logic or pagination for very large histories (keep best-effort + recent only).
- Changes to live broker wire protocols or polling (that is the separate "wire live brokers to publish typed events" item).
- Full P&L / netting lineage (later item on the list).
- Removing the `recent_fills=` parameter (keep it for advanced callers and tests).

---

## Why This Slice Now

We have spent Slices 15–21 pushing lineage all the way into fills and making the critical fill events scream in the Guardian. The last major gap for "daily forcing function" is that the most important consumers (the provenance report and the Guardian) still require manual data feeding for the execution side.

Automating the pull is the smallest change that makes the entire continuous hash chain (dream → proposals → gates → risk decisions → final arbitration → real fills) visible and screaming with almost no extra work on every run or CLI invocation.

This is explicitly the next item called out in the Slice 21 (and earlier) completion lists and directly advances the 90-day roadmap commitment for automated end-to-end lineage observability.

---

## Reversibility & Safety

- The new auto-pull is best-effort and only activates when no explicit `recent_fills` are passed.
- Can be disabled or removed in one small change with no impact on existing callers.
- No change to order submission, risk decisions, or any capital-affecting path.
- All broker calls remain the same read-only patterns already used elsewhere.

---

**This entry opens Phase 2 Slice 22.** Plan Mode + skill reviews (constitution-guard + event-bus-contract + risk-safety-review) required before implementation.

*Red thread: The lineage must not only exist and scream when broken — the most important daily tools (Guardian + provenance report) must automatically see the full picture, including real execution fills, with zero manual steps. User directive "Proceed with the next phase 2 slice from the list" after Slice 21.*