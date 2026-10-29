# Onderzoeksteam 19:24 — midpoint D13 on ES (2026-10-29)

Binding input (Steve forwarded; **not** Steve's opinion):
`docs/research/ONDERZOEKERS-ANTWOORDEN-NULLVAL-20261029T1924.md`
content sha256 `74e5941cc57fccaa5d08ea32bcf86bbc07b310db6efdabda431071bb4b9e777c`
(prefix `74e5941c`). Unchanged.

Stacked draft PR #72 on #69. **No merge. No SIM/REAL orders. Holdout pin
`2026-01-28T23:00:00Z` unopened. Risk Core untouched. ES CSV not in git.**

Pre-register committed **before** the run: git `50f4d7cb`,
`experiments/reports/phase5_p2_midpoint_d13_preregister_2026-10-29.md`
content sha256 `6623363ef4200c3050526573547fb660ac5572d4251709a70109c5db21e75507`
(prefix `6623363e`).

DSR **0.95**, PBO **0.50**, CostModel **1.2.0**, seeds `20261029+i`, v2
`linear_magnitude` unchanged. No templates. No NQ. No holdout eval. No
strategy-run (not even limited).

---

## 1. 19:24 answers applied

1. No separate raw-A2 repair. Strict `n_edge` 0/32 from 18:17 stands. A2 stays
   diagnostic.
2. 0/32 is accepted with a power caveat. The 7/8 gate is not loosened.
3. Allowed run: planted session-direction under fade `1.0/1.2` and breakout
   `1.8/0.9` on the local ES pre-holdout tape, plus the v2 null under the same
   geometries. Limited strategy-run needs a **new** OK.

## 2. Tape

Same bytes as the 18:17 null-only ES file (sha256 `6100588d…`). 818851 bars,
`2023-10-01T22:01:00Z`–`2026-01-28T22:00:00Z`, 598 sessions. No timestamp
`>= 2026-01-28T23:00:00Z`.

## 3. Detection per geometry

Drempel (pre-registered): median OOS > 0, +OOS ≥ 0.60, no decay, planted
median > median of 32 v2-null medians. Exact counts:

| family | tgt/stop | planted detected | median OOS | +OOS | DSR | effect > 0 | beats null | exact A2 | exact 7/8 | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| fade | 1.0 / 1.2 | **yes** | 0.011601 | 1.000 | 1.000 | yes | yes | 4/32 | **0/32** | clean |
| breakout | 1.8 / 0.9 | **yes** | 0.011457 | 1.000 | 1.000 | yes | yes | 2/32 | **0/32** | clean |

`overall_verdict`: **clean**. JSON:
`experiments/reports/phase5_p2_midpoint_d13.json`.

The full Validation Gate package (`planted_passed_gate`) is **false** on both
rows even though A2, DSR 1.0, and beats-null hold. Detection used the
pre-registered drempel, not the packaged gate. Likely another charter metric
(PBO/WFE). Not used to override the planted detect.

## 4. Null control

v2 `linear_magnitude`, 32 seeds, extra week-block skipped, ATR re-execute (no
remap). Strict 7/8:

- fade `n_edge` **0/32** (raw A2 4/32 diagnostic)
- breakout `n_edge` **0/32** (raw A2 2/32)

Null stays silent under the chosen definition. Fade raw A2 4/32 is fail as a
**label** on the diagnostic count; cycle stop uses `n_edge`.

## 5. Power oordeel

**Not a power problem.** Planted hits the drempel on both geometries and the
null stays `0/32` 7/8. The 19:24 stop rule (silent null + missed plant) does
not fire.

A limited strategy-run still does **not** follow. That is a separate step and
needs a new team OK.

## 6. Hygiene

- No live / SIM orders
- Risk Core not modified
- Tests not weakened (4/32 still fail; 7/8 gate unchanged)
- Seals `85e4588f` / `454b8d1f` / `cdf964b6` not rewritten
- CSV not committed

## 7. Open vragen

1. `planted_passed_gate` is false despite DSR 1.0 and A2 detect. Which packaged
   metric rejects (PBO?)? Does a later limited run need the full gate on the
   plant, or is the pre-registered drempel enough?
2. Fade raw A2 is 4/32 under ATR midpoints (diagnostic). Same 19:24 rule: no
   A2-only repair.
3. Limited strategy-run still closed until a new OK.
4. NQ still closed. Midpoint D13 PIT on NQ is not this run.
