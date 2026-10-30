# ATR ES PIT control-note correction (2026-10-29)

Not a rerun. Not a respec. Holdout pin `2026-01-28T23:00:00Z` stays closed.

## What ran

Action-5 D13 used `control_geometry_mode="atr"` in `atr_es_cycle`:

- planted session-direction at first RTH bar
- **1:1 1.5×ATR14** in index points (ADR-0068)
- session flatten, `time_stop_bars=2000`
- drift-aware 32-seed null (ADR-0067), no week-block seeds this cycle
- CostModel **1.2.0**

ES: planted median OOS `+0.01205`, +OOS `1.00`, null **1/32** A2, median-of-medians `−0.000705`.
MES: planted median OOS `+0.00122`, +OOS `1.00`, null **4/32** A2, median-of-medians `−7.77e-5`.
ADR-0069 re-score (no rerun): ES **1/32 reliable**; MES **4/32 borderline**
(monitor). Majority `≤16/32` is no longer the gate. Planted beats null.

## What the generated JSON still says

`experiments/reports/phase5_p2_atr_es.json` is the untouched PIT dump
(content sha256 `19e3d9b9f5e8d1250f71c846367e2bd80f29ff5b7a94fdf4c2aa143e3765378f`).
Its `control_note` quotes the action-1 unclipped **20000/20000** paragraph
because `run_controls` always attached `PLANTED_HORIZON_NOTE`. Execution did
**not** use 20000/20000; `execute_control(..., geometry_mode="atr")` set
`target_atr=stop_atr=1.5`.

Markdown reports carry a preamble pointing here. Code after this PIT emits
`horizon_note("atr")` on future runs. Reports were not regenerated.

## BE column `1.634`

The PIT JSON still stores `1.634` from `require_geometry(target_ticks=1,
stop_ticks=1)`. That is not an ATR break-even. Markdown results now use
per-family gross BE: fade `1.2/2.2 = 0.545`, breakout `0.9/2.7 = 0.333`,
gap `n/a` (ADR-0069). JSON dump is untouched PIT history.
