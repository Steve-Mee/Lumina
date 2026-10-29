# Onderzoeksteam 22:08 — ES midpoint power floor (12.5% / 6.25%)

Binding input (Steve forwarded; **not** Steve's opinion):
`docs/research/ONDERZOEKERS-ANTWOORDEN-POWER-S4-20261029T2208.md`
content sha256 `991138fdd4b741041e3288387dd8aaf89a09652329ada7eec7eaa0f037bfae9d`
(prefix `991138fd`).

Stacked draft PR #72 on #69. **No merge. No SIM/REAL orders. Holdout pin
`2026-01-28T23:00:00Z` unopened. Risk Core untouched. ES CSV not in git.**
Strategy-run (including limited) **not started**.

Pre-register committed **before** the run: git `f6d1f681`,
`experiments/reports/phase5_p2_midpoint_power_floor_preregister_2026-10-29.md`
content sha256 `8b548fdadb7377ed5fdbe0704bb341ec3d16e703a26b0c3992a219086ce4d9c9`
(prefix `8b548fda`).

DSR **0.95**, PBO **0.50**, CostModel **1.2.0**, seeds `20261029+i`, v2
`linear_magnitude`, fade `1.0/1.2`, breakout `1.8/0.9`, null-first
`passed_gate` wiring unchanged.

---

## 1. Tape

Same bytes as 18:17/19:24/21:29 (csv sha256 `6100588d…`). 818851 bars,
`2023-10-01T22:01:00Z`–`2026-01-28T22:00:00Z`, 598 sessions. No timestamp
`>= 2026-01-28T23:00:00Z`. Last bar `2026-01-28T22:00:00Z`.

## 2. Counts per magnitude and geometry

Drempel unchanged: median OOS > 0, +OOS ≥ 0.60, no decay, beats null.
Magnitude is a linear scale of the already-costed session net (same trades).
`full_magnitude_clean` in the JSON is `false` only because magnitude `1.0`
is not in this cycle (already reported at 21:29). Both tested bands are
`clean`. `null_leaked` is `false`.

| mag | family | detected | passed_gate | median OOS | +OOS | DSR | PBO n | exact A2 | exact 7/8 | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.125 | fade 1.0/1.2 | yes | **yes** | 0.001450 | **8/8** | 1.000 | 33 | 4/32 | **0/32** | clean |
| 0.125 | breakout 1.8/0.9 | yes | **yes** | 0.001432 | **8/8** | 1.000 | 33 | 2/32 | **0/32** | clean |
| 0.0625 | fade 1.0/1.2 | yes | **yes** | 0.000725 | **8/8** | 1.000 | 33 | 4/32 | **0/32** | clean |
| 0.0625 | breakout 1.8/0.9 | yes | **yes** | 0.000716 | **8/8** | 1.000 | 33 | 2/32 | **0/32** | clean |

12.5% median OOS is the exact eighth of the 19:24/21:29 100% row
(`0.011600853 × 0.125`). 6.25% is the exact sixteenth. Null `n_edge`
stays 0/32 on every row (raw A2 signs are scale-invariant).

JSON: `experiments/reports/phase5_p2_midpoint_power_floor.json`.

## 3. Detection floor

**Not a power problem** at 12.5% or 6.25% of this known-size lookahead
plant. The drempel still fires; the packaged gate still passes; the null
stays silent.

**Floor: at or below 6.25% of this plant.** Both bands are still saturated
(8/8 +OOS, DSR 1.0). This does **not** bound the minimum detectable edge
for a realistic strategy. It only shows that this session-direction plant
remains above the drempel at a sixteenth of current size.

The 7/8 gate was not loosened.

## 4. TOD decision (limited prereg, not run)

Checked existing ATR ES PIT (`p2a-tod-es`, same fade 1.0/1.2, RTH):
589 trades / 598 sessions (0.98/session) — **lowest** of the six families
that map to `p2l-*`. `_time_of_day` fires only on RTH bars in the first
30 minutes after the RTH open; exits are RTH flatten. Not high ETH
exposure. The 16/8 `p2c-tod-es-15` 2755-trade row is a different geometry.

**Keep `p2l-tod-es`. Six configs. No extra variants. Limited run not
started.**

Pre-register: `experiments/reports/phase5_p2_limited_es_preregister_2026-10-29.md`
(git `d7022bf6`).

## 5. Hygiene

- No live / SIM orders
- Risk Core not modified
- Tests not weakened (`trial_count_below_pbo_configs` still rejects; 4/32
  still fail; 7/8 unchanged; 100/50/25 lock unchanged)
- CSV not committed
- 21:29 power JSON/MD not rewritten

## 6. Open vragen

1. 6.25% of this plant is still saturated. A realistic-strategy floor
   needs a weaker *mechanism* (lower hit-rate), not a smaller scale of
   this lookahead session-direction plant.
2. Limited ES 6-config list is locked with TOD kept. The 22:08 team
   allowed a start after this check; this task did not start it.
