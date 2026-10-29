# Fase 5 P2 first real research cycle (2026-10-29)

Safety-critical. Binding: RESEARCH_CHARTER.md, ADR-0059, Validation Gate floors. Propose-only. No orders.

## What ran

- Holdout pin `2026-01-29T00:00:00Z` hash-sealed before ranking (`experiments/reports/phase5_p2_holdout_seal.json`).
- NT8 1m unadjusted continuous MES/MNQ, UTC bar-close, 2023-10-01..2026-10-29. CSVs not in git. Manifest: `data/research/manifest.json`.
- Known GAPS.md windows dropped, never filled. NT8 roll dates flatten; no return across roll or known-gap intervals.
- 12 pre-registered MES/MNQ templates only. LLM did not add templates. WF 8 OOS windows, CPCV purge+embargo, DSR, PBO, ADR-0055 four-leg costs, tick floors 16/8, causal high-vol quiet mask (20d > 75th of trailing 252d).
- Shadow only. Live Risk Core / PromotionGate / S0 `UNGATED_PLACE_BLOCKED_S0` not written.

## Result

12/12 kill. Kill-rate 1.00 (`expected_high_kill`). No independent survivors. Holdout evaluation skipped (seal not used for selection). Floors not loosened.

See `experiments/reports/phase5_p2_results.md`.

## Residual risks

- UTC pin splits ~60 minutes of Globex session 2026-01-29 (18:00–19:00 ET) into train.
- MNQ 2026-07-17 listed as partial in GAPS.md; this cycle excludes the full UTC day.
- WFE undefined when an IS/OOS window has zero variance; gate treats that as doubt, not a pass.
- MNQ modeled one-way ticks sit above the briefed 1–2.5 band; CostModel was not retuned.
- Holdout remains sealed for a later cycle if a survivor ever appears.
