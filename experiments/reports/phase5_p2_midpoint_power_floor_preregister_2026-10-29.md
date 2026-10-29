# P2 midpoint power floor — pre-registration (2026-10-29 22:08)

Locked **before** the ES 12.5%/6.25% planted-magnitude control run. Does **not**
rewrite CostModel 1.2.0, DSR 0.95, PBO 0.50, the 7/8 null gate, holdout pin
`2026-01-28T23:00:00Z`, Risk Core, the 19:24 midpoint D13 drempel, or the
21:29 100/50/25% power lock.

Binding input (Steve forwarded; **not** Steve's opinion):
`docs/research/ONDERZOEKERS-ANTWOORDEN-POWER-S4-20261029T2208.md`
content sha256 `991138fdd4b741041e3288387dd8aaf89a09652329ada7eec7eaa0f037bfae9d`
(prefix `991138fd`).

This file locks the next allowed **control** run only. No strategy-run (not even
limited). No catalog templates. No NQ. No holdout eval. No SIM/REAL orders.

## Cause lock (passed_gate) — unchanged from 21:29

`planted_passed_gate=false` on the 19:24 DSR-1.0 plant was control-wiring:
null PBO peers must be registered as trials **before** the planted gate.
That fix stays. The `trial_count_below_pbo_configs` check in `gate.py` is
**not** removed. Tests that trip it are **not** weakened.

## Tape

Local ES PIT NT8 1m continuous, UTC, holdout already cut. CSV is not committed.
Code asserts no timestamp `>= 2026-01-28T23:00:00Z`. Same bytes as 18:17/19:24
and 21:29 when the decompressed CSV sha256 is `6100588d…`. Last bar must be
`2026-01-28T22:00:00Z`.

## Magnitudes (effect size; not ATR multiples)

Same midpoints, same seeds, same v2 builder, same drempel, same
`passed_gate` wiring. The **known size** is the 19:24 planted session-direction
net (clipped ATR brackets minus four-leg costs). This run scales that
already-costed session net linearly:

| band | `planted_magnitude` | meaning |
|---|---|---|
| 12.5% | `0.125` | eighth of the costed session net |
| 6.25% | `0.0625` | sixteenth of the costed session net |

100/50/25% already ran (`phase5_p2_midpoint_power.json`) and stay frozen.
This cycle does **not** rewrite those files.

ATR multiples stay fade `1.0/1.2` and breakout `1.8/0.9`. Not rescaled.
Seeds stay `20261029 + i` for `i=0..31`. Null builder stays v2
`linear_magnitude`. ATR path still re-executes each null at full size, then
the same magnitude scale is applied to planted **and** null dailies so plant
vs null stays on one scale.

## Detection threshold (unchanged drempel)

Planted is **detected** when all of:

1. Effect-size floor: median OOS after costs `> 0`
2. A2: +OOS share `≥ 0.60` and no structural decay
3. Beats null: planted median OOS `>` median of the 32 v2-null median-OOS values

Packaged gate (`passed_gate`) is **reported** with `reject_reasons`, `dsr`,
`pbo`, `pbo.n_configs`, and +OOS as `n_positive/n_windows` (target 8/8).
Charter floors stay DSR 0.95 / PBO 0.50.

## Power rule (unchanged)

Per geometry **per magnitude**:

| planted detected | strict `n_edge` | verdict |
|---|---|---|
| yes | `≤ 3/32` | `clean` |
| no | `≤ 3/32` | `power_problem` |
| any | `≥ 4/32` | `null_leak` |

Goal: the **detection floor** of this lookahead plant. A miss at 12.5% or
6.25% with a silent null is a power finding, not a looser gate. A clean
row at 6.25% means the floor is at or below 6.25% of this plant; it does
**not** claim a realistic-strategy floor.

## Fail-closed

- No seed reroll, no geometry respec, no midpoint move, no drempel move.
- `--cycle midpoint-power-floor` is a control cycle, not a strategy-run.
- Limited strategy-run is **not** started from this file even if both
  bands are `clean`. The 22:08 team allowed a limited run after this check;
  this task still does not start it.
- CLI `first` / `four-instrument` / `atr-es` stay strategy-locked.
- Max trials = pre-registered count (32 nulls + 1 plant per geometry per
  magnitude; N=33 at the planted gate).
