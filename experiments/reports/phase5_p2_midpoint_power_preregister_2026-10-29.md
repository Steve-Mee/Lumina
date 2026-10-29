# P2 midpoint power — pre-registration (2026-10-29 21:29)

Locked **before** the ES 50%/25% planted-magnitude rerun. Does **not** rewrite
CostModel 1.2.0, DSR 0.95, PBO 0.50, the 7/8 null gate, holdout pin
`2026-01-28T23:00:00Z`, Risk Core, or the 19:24 midpoint D13 drempel.

Binding input (Steve forwarded; **not** Steve's opinion):
`docs/research/ONDERZOEKERS-ANTWOORDEN-MIDPOINT-20261029T2129.md`

This file locks the next allowed **control** run only. No strategy-run (not even
limited). No catalog templates. No NQ. No holdout eval. No SIM/REAL orders.

## Cause lock (passed_gate)

`planted_passed_gate=false` on the 19:24 DSR-1.0 / 100% +OOS plant is a
**control-wiring bug**, not a weak plant and not a reason to loosen the gate.

`run_controls` evaluated the planted candidate first with 32 null dailies as
PBO peers. `evaluate_candidate` then built a 33-config PBO matrix while
`TrialRegistry` still held **one** trial. `_judge` correctly appended
`trial_count_below_pbo_configs` and `doubt`. Historical confirmation:
`experiments/reports/phase5_p2_step4_control_respec.md` (same reject pair).

Fix, already in code before this run: record the 32 null configs as trials
**before** the planted gate (evaluate nulls first, plant last). Planted DSR is
deflated for N=33. The `trial_count_below_pbo_configs` check in `gate.py` is
**not** removed. Tests that trip it are **not** weakened.

Reject reasons are persisted on `ControlOutcome` so this cannot hide again.

## Tape

Local ES PIT NT8 1m continuous, UTC, holdout already cut. CSV is not committed.
Code asserts no timestamp `>= 2026-01-28T23:00:00Z`. Same bytes as 18:17/19:24
when the decompressed CSV sha256 is `6100588d…`.

## Magnitudes (effect size; not ATR multiples)

Same midpoints, same seeds, same v2 builder, same drempel. The **known size**
is the 19:24 planted session-direction net (clipped ATR brackets minus
four-leg costs). This run scales that already-costed session net linearly:

| band | `planted_magnitude` | meaning |
|---|---|---|
| 100% | `1.00` | current known size (gate-fix regression) |
| 50% | `0.50` | half the costed session net |
| 25% | `0.25` | quarter the costed session net |

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
`pbo`, and `pbo.n_configs`. Charter floors stay DSR 0.95 / PBO 0.50.

## Power rule (unchanged)

Per geometry **per magnitude**:

| planted detected | strict `n_edge` | verdict |
|---|---|---|
| yes | `≤ 3/32` | `clean` |
| no | `≤ 3/32` | `power_problem` |
| any | `≥ 4/32` | `null_leak` |

100% is the gate-fix regression: both geometries should stay `clean` and
`passed_gate` should no longer fail on `trial_count_below_pbo_configs`.
50% and 25% are the power measurement. A miss at 25% with a silent null is a
power finding, not a looser gate.

## Fail-closed

- No seed reroll, no geometry respec, no midpoint move, no drempel move.
- `--cycle midpoint-power` is a control cycle, not a strategy-run.
- Limited strategy-run is **not** started from this file even if 50%/25% are
  `clean`. That needs a new team OK.
- CLI `first` / `four-instrument` / `atr-es` stay strategy-locked.
