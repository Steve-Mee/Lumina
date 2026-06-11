# 2026-05-31 — Phase 2 Slice 17 COMPLETE: Extend Reconstruction and Provenance Reports to Surface Fills

**Parent**:
- `2026-05-31-elon-phase2-16-complete.md`
- `2026-05-31-elon-phase2-17-extend-reconstruction-provenance-fills.md` (hypothesis)

**Status**: **SLICE COMPLETE**

---

## Delivered

- Added `extend_chain_with_fills(base_chain, fills)` helper in `decision_lineage.py`.
- Updated `build_pretrade_provenance_report` to accept `recent_fills` and include a "fills" section in the report dict.
- Updated `format_as_markdown` to render a clean "## Fills & Execution (Downstream Lineage)" section when fills are present.
- The existing Slice 16 extraction helpers (`get_lineage_from_fill` etc.) are now used inside the report flow.
- Guardian baseline note + narrow agent-context update.

All changes are purely additive read-only reporting extensions. Zero impact on any trading or risk logic.

**Skill Reviews**: constitution-guard 10/10, event-bus-contract 10/10.

---

## Measurements

All predictions from the hypothesis are met:
- Reconstruction can now include fill nodes when provided.
- The provenance report produces a structured "fills" section.
- The rendered Markdown shows fills cleanly with key data.
- The flow is usable by the Guardian and post-trade audits.

---

## Fidelity

This slice makes the downstream lineage data from Slices 15–16 actually visible and usable in the primary human/Guardian artifact — exactly the next forcing function after we put the data into the fills.

Red thread maintained with zero deviations.

**Phase 2 Slice 17 is complete.**

High-value next options:
- Promote lineage fields on Fill/OrderResult to first-class (instead of only `raw`).
- Publish proper typed `execution.fill` events on the Event Bus.
- Wire the report automatically to broker fills in the Guardian.
- Continue the chain into P&L attribution and multi-order netting.

Direct instruction for the next move required.