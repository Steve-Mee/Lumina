# 2026-05-31 — Phase 2 Slice 21: Activate Guardian Screaming Validation for Critical `execution.fill.received` Events (Downstream Lineage Integrity)

**Parent**:
- `2026-05-31-elon-phase2-20-complete.md` (Slice 20 made `execution.fill.received` a CRITICAL_EVENT_BUS_TOPIC with hard fail-closed validation)
- `2026-05-31-elon-phase2-13-complete.md` (Slice 13 introduced active hash chain screaming in the Guardian as a daily forcing function)
- `2026-05-31-elon-aperture-hardening-90-day-roadmap.md` (Phase 2 goal: Guardian as the permanent, visible, daily screaming detector for the full typed spine)
- `2026-05-31-elon-musk-first-principles-trading-system-analysis.md`

**Protocol Status**: This is the formal opening hypothesis entry for Phase 2 Slice 21. No implementation begins until this entry and a dedicated Plan Mode (with constitution-guard + event-bus-contract + risk-safety-review) are complete.

---

## Hypothesis

In Slice 20 we made `execution.fill.received` critical. Schema violations on downstream fill events with lineage now raise loudly instead of being swallowed.

**Current reality (post-Slice 20)**:
- The Guardian runs daily (or on demand) and actively screams on broken *pre-trade* hash chains (Slice 13 logic): it samples recent decision_context_ids, runs `reconstruct_risk_decision_chain`, checks `is_chain_healthy`, and verifies presence of core nodes (gate_entry + policy.decision + final_arbitration).
- It produces clear, actionable ⚠️ output when chains are broken or incomplete.
- However, the screaming logic stops at Final Arbitration. It does **not** yet inspect the critical `execution.fill.received` events that carry the first and second downstream cryptographic links (from Slice 15–19).
- Result: A ctx can have perfect pre-trade lineage all the way to Final Arbitration, yet the actual fill events (now on a critical topic) can be missing, malformed, or lack the expected `prev_hash` linkage — and the Guardian will say nothing.

**Hypothesis**:
By extending the existing Slice 13 screaming block in `validate_dna.py` (best-effort, non-fatal) to also sample recent critical `execution.fill.received` events from the bus (or blackboard fallback) and check that any fill events present for a sampled ctx carry proper lineage (`decision_context_id` + `prev_hash`), the Guardian will now scream loudly when the downstream cryptographic chain is broken or incomplete.

This is the smallest reversible change that turns the critical status from Slice 20 into a **visible daily forcing function** exactly like the pre-trade chain screaming from Slice 13.

The full end-to-end lineage (dream → proposals → gate → risk decisions → final arbitration → fills) becomes impossible to degrade silently without the Guardian yelling about it on every run.

---

## Falsifiable Predictions

1. After the slice, the Guardian will contain new (or extended) best-effort logic that pulls recent "execution.fill.received" events for sampled ctxs.
2. When a critical fill event exists for a ctx but is missing `decision_context_id` / `prev_hash` (or the linkage looks broken), the Guardian will emit a loud ⚠️ / 🔴 "DOWNSTREAM LINEAGE WARNING" section with the ctx and specific defect.
3. When all sampled fill events for recent ctxs have correct lineage, the Guardian will print a clean positive summary (e.g. "Phase 2 Downstream Fill Lineage Validation (Slice 21): N recent ctxs with fills, all have valid critical lineage").
4. The change is purely additive/best-effort inside the existing try/except block — zero impact on Guardian runs that have no bus or no recent fills.
5. The screaming remains non-fatal (Guardian itself can never be the cause of a production issue).

---

## Scope (Strictly Limited — Forcing Function Extension Slice)

**In scope**:
- Extend the existing Phase 2 Slice 13 screaming block in `scripts/dna_guardian/validate_dna.py` (the try block after the baseline prints).
- Best-effort sampling of recent "execution.fill.received" events (via bus.history if available, otherwise blackboard JSONL fallback, mirroring the existing pattern for proposals).
- For each sampled ctx that has fill events, use existing helpers (`get_lineage_from_fill` logic or direct payload inspection) to verify presence of `decision_context_id` + `prev_hash`.
- Loud, copy-pasteable warning output when downstream lineage is missing or broken on critical fill events (with exact CLI command for reconstruction + provenance report).
- Clean positive summary when healthy.
- One focused test (or extension of existing Guardian tests if any) proving the new warning path fires.
- Guardian baseline note + narrow agent-context.md update.
- Public hypothesis + completion entries.

**Out of scope (deferred)**:
- Pulling live Fill objects from broker/ledger (that is the separate "auto-pull recent fills" item on the list).
- Adding new heavy dependencies or requiring a full trading engine for Guardian runs.
- Complex hash verification on the fill events themselves (keep it simple presence + required fields check for this slice).
- Removing any "best-effort" wrappers.

---

## Why This Slice Now

We just spent Slice 20 making the downstream fill event **critical** (hard validation, no silent failures). Without active screaming in the daily Guardian, that critical status is only theoretical — problems on the execution side of the chain remain invisible to the most important forcing function (the Guardian).

This is the direct, high-leverage follow-on to Slice 13 (pre-trade screaming) + Slice 20 (critical downstream event). It completes the "make the entire continuous hash chain scream daily" arc for Phase 2.

It is the exact item that turns "the topic is now critical" into "humans see broken downstream lineage every single day and cannot ignore it."

---

## Reversibility & Safety

- All new logic is inside existing best-effort try/except blocks.
- Removing or commenting out the new 15-25 lines reverts the Guardian to previous behavior with zero side effects.
- No change to any trading, risk, order, or ledger code.
- Guardian remains safe to run in any environment (production or not).

---

**This entry opens Phase 2 Slice 21.** Plan Mode + skill reviews (constitution-guard + event-bus-contract + risk-safety-review) required before implementation.

*Red thread: The lineage must not only be typed and critical — the Guardian must actively scream when the critical downstream links are missing or broken. This is how we make problems impossible to ignore. User directive "Proceed with the next phase 2 slice from the list" after Slice 20.*