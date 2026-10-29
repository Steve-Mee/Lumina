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
Both majority-reliable (`≤16/32`); planted beats null; fail-closed **passed**.

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

The results table BE is `1 / (1 - RT_cost_ticks)` with placeholder
`target_ticks=1, stop_ticks=1` (ATR path still calls `require_geometry` for
the tick-floor band). It is **not** the break-even of 1.5×ATR. Open question
Q-REPORT-1.
