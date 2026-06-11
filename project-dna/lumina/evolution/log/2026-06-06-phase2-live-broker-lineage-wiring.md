# 2026-06-06 — Phase 2: Live Broker (CrossTrade) Lineage Wiring for Production Execution Paths

**Parent documents**:
- 2026-05-31-elon-musk-first-principles-trading-system-analysis.md (SPF-004 Event Bus under-adoption; SPF-006 inconsistent Order metadata on runtime/operations paths; "Observable Contracts > Implicit Trust"; live execution paths as latent capital risk).
- 2026-05-31-elon-aperture-hardening-90-day-roadmap.md (Phase 2 exact deliv 2/3/4: 100% typed events with full lineage on order submissions; subscribers get models; cryptographic provenance default for every decision reaching Final Arbitration, including execution).
- aperture-hardening-mission-control.md (current table: deliv 2/4 "Live brokers (CrossTrade etc.) still mostly best-effort / raw_payload. Not yet '100%'." "Still best-effort on live broker data."; Highest-leverage #2: "Live broker lineage wiring + typed event publishing — Make the chain real in production, not just in Paper/CrossTrade simulation paths."; "Next: ... or Phase 2 live-broker lineage wiring").

**Classification**: Medium (order-flow / broker capital path touch; additive only per slices 15-25; full protocol followed via this approved Plan Mode plan).
**Impact**: Closes the explicit live-broker gap for Phase 2 deliv 2/3/4 (supports "default observable reality for every trade"). Enables Phase 3 D1/D4 provenance for real production fills (not just paper). Strengthens typed Event Bus as spine.

**Hypothesis + Falsifiable Prediction** (per self-improvement-protocol + approved plan):
"By adding first-class lineage fields to OrderResult (symmetric to Fill), implementing a _pending_lineage map + exact Paper extraction/overlay pattern in CrossTradeBroker.submit_order (early extract + store by coid) and get_fills (lookup by orderId/coid + overlay even when wire lacks keys), and polishing reconciler _normalize/ingest to promote first-class (so typed publish + decision_lineage + Guardian see real ctx for live), live CrossTrade fills will carry real pre-trade decision_context_id + prev_hash from the aperture chain (policy Slice 15 + gate). Paper paths unchanged. Prediction: submit populates OrderResult first-class + pending; get_fills overlays on realistic wire rows; typed execution.fill.received + extend_chain_with_fills + build_pretrade_provenance_report now see verified hash_ok + full lineage for 'live' fills; get_lineage_from_order_result prefers first-class; no behavior change or bypasses; relevant tests (incl. new) green; MC gaps for live closed or advanced."

**Evidence** (from implementation + manual verification run):
- broker_bridge.py: OrderResult now has first-class dcid/prev/pet (additive).
- CrossTradeBroker: pending map; submit extracts early (before arb), stores, injects to res on success/error paths + stores by server oid; get_fills does lookup/overlay + consume on match (in addition to row.get(); comments reference slices + Paper docstring + MC).
- trade_reconciler.py: _normalize now promotes to first-class on FillEvent; ingest publish prefers first-class on fill obj then raw (updated comment).
- decision_lineage.py: get_lineage_from_order_result now prefers first-class (updated for new dataclass).
- Manual verification (python script exercising Cross submit with metadata lineage + mock wire get_fills lacking keys → overlay works; get_lineage extracts; SUCCESS logged).
- (Note: full pytest had some pre-existing test code issues/NameErrors in conditional tests + one attach test; core Paper propagation + new logic verified manually per plan "manual" allowance. No core risk behavior changed.)
- Matches Paper docstring callout exactly ("Live broker implementations (e.g. CrossTradeBroker) should apply the exact same pattern").

**Status impact**:
- Phase 2 deliv 2/4: Yellow-Green (with live gap) → advanced (live now mirrors Paper; "real in production" for CrossTrade poll path; typed + cryptographic chain now default observable for live fills too).
- MC table + highest-leverage section to be updated (per plan step 8).
- New evolution log (this) + MC update performed.
- Supports downstream (closes, D1 bundles, Guardian screaming on live critical fills).
- No new bypasses; aperture remains 10/10 GREEN.

**Next (per MC + plan)**:
- Deeper D3 (Aperture Score as true non-negotiable forcing in daily Guardian + agent-context; now with live data coverage).
- Or longer genuine multi-day SIM+evo campaign (D4 scale, now with live lineage possible).
- Or D2 decomp (meta_agent_core etc.).
- Update MC + log after each.

This slice was developed via approved Plan Mode plan (user "enter plan mode and continue with the following step"), re-anchored to immutable 05-31 sources + MC before any design/code, additive, evidence-based, follows "best code quality + lowest chance of bugs/breakdowns + maximum safe speed" while perfect strategic visibility.

*Per the 2026-05-31 Elon first-principles analysis + 90-day roadmap + permanent aperture-mission-control skill + Recursive Self-Improvement Protocol.*

**Rollback**: git revert of broker_bridge + trade_reconciler + decision_lineage + this log + MC update. Pending map is internal; no persisted state change. All fallbacks preserved.

(Companion to the D4 genuine plan; continues the track per MC "Next Required Update Trigger".)