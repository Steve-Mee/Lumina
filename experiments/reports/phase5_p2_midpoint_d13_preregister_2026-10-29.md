# P2 midpoint D13 — pre-registration (2026-10-29 19:24)

Locked **before** the ES midpoint positive-control run. Does **not** rewrite
`phase5_p2_positive_control_preregister_2026-10-29.md`,
`phase5_p2_atr_geometry_preregister_2026-10-29.md`, CostModel 1.2.0, DSR 0.95,
PBO 0.50, holdout pin `2026-01-28T23:00:00Z`, or Risk Core.

Binding input (Steve forwarded; **not** Steve's opinion):
`docs/research/ONDERZOEKERS-ANTWOORDEN-NULLVAL-20261029T1924.md`
content sha256 `74e5941cc57fccaa5d08ea32bcf86bbc07b310db6efdabda431071bb4b9e777c`
(prefix `74e5941c`).

18:17 null-only stays standing: no separate raw-A2 repair; strict `n_edge` 0/32
is enough; 0/32 is accepted with a power caveat; the 7/8 gate is **not**
loosened. This file locks the next allowed run only.

Holdout pin stays closed. No SIM/REAL orders. No strategy-run (not even
limited). No catalog templates. No NQ. No holdout eval. Limited strategy-run
is a **later** step and needs a new team OK after this control.

## Tape

Local ES PIT NT8 1m continuous, UTC, holdout already cut. CSV is not committed.
Code asserts no timestamp `>= 2026-01-28T23:00:00Z`.

## Edge (known size / effectgrootte)

At the first RTH bar of each Globex session the control knows the sign of that
session's last-RTH-close minus first-RTH-open on the unadjusted tape. It holds
that direction until RTH close (`session_end_flatten=True`, C10).
`time_stop_bars=2000` cannot fire inside one RTH session. Four-leg CostModel
**1.2.0** unchanged.

Known size under a midpoint geometry is that session move **clipped** by the
causal ATR14 brackets of that family, minus costs:

| family | target | stop | clip |
|---|---|---|---|
| fade | `1.0×ATR14` | `1.2×ATR14` | win cap 1.0×ATR, loss cap 1.2×ATR |
| breakout | `1.8×ATR14` | `0.9×ATR14` | win cap 1.8×ATR, loss cap 0.9×ATR |

Causal ATR14 = mean RTH true-range of up to 14 **prior** sessions (current
session excluded). Midpoints are exact; not 1.5×ATR14 and not 20000/20000.
Catalog templates are not run.

## Detection threshold (drempel; not tuned on this ES tape)

Planted is **detected** when all of:

1. Effect-size floor: median OOS after costs `> 0`
2. A2: +OOS share `≥ 0.60` and no structural decay
3. Beats null: planted median OOS `>` median of the 32 v2-null median-OOS values

DSR and PBO are **reported**, not the detection switch. Charter floors stay
DSR 0.95 / PBO 0.50 and are not relaxed.

Always publish exact `median_oos`, `pct_positive`, `dsr`, `n_a2/32`, `n_edge/32`.

## Null control (same geometries)

Builder: production v2 `linear_magnitude`. Seeds: `20261029 + i` for `i=0..31`
(32 seeds, no reroll). Embargo 1 session. Extra ISO-week block seeds skipped
(report-only, not this control). ATR path **re-executes** each null (no
unclipped remap). Fail at `n_edge ≥ 4/32` (4 is fail). Raw A2 is diagnostic.

## Power rule (19:24)

Per geometry:

| planted detected | strict `n_edge` | verdict |
|---|---|---|
| yes | `≤ 3/32` | `clean` |
| no | `≤ 3/32` | `power_problem` (null silent, plant missed) |
| any | `≥ 4/32` | `null_leak` |

If **both** geometries are `clean`, the control passes. A limited strategy-run
still does **not** follow until a new team OK.

If any geometry is `power_problem` (null stays `≤ 3/32` and planted is not
detected): report that as a power problem and **stop**. Do not loosen the 7/8
gate. Do not run templates.

If any geometry is `null_leak`: stop; that is a leak, not a power miss.

## Fail-closed

- No seed reroll, no geometry respec, no midpoint move inside the band.
- `--cycle midpoint-d13` is a control cycle, not a strategy-run.
- CLI `first` / `four-instrument` / `atr-es` stay strategy-locked apart from
  the existing null-only JSON. This run does not invoke them.
