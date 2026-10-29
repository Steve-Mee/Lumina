# P2 step 4 control respec — real NT8 rerun (2026-10-29)

Steve OK 2026-10-29 12:38. Pre-register committed first (`75dd1453`), then
implementation (`1d46f0cb`), then this run. Holdout seal
`85e4588fde77159315a72bdaa722d6487f93bbad9bf24999311f893950489d40` reused, not
rewritten. Pin `2026-01-28T23:00:00Z` closed. Floors DSR 0.95 / PBO 0.50
unchanged. Templates unchanged. Raw CSVs not in git.

## Positive / null control

Planted session-direction hold (RTH-open to RTH-close, 1:1 20000-tick brackets,
`time_stop_bars=2000`) **detected**. Null shuffle **not** an edge.

| control | detected | gate passed | median OOS | +OOS | DSR | PBO | reject reasons |
|---|---|---|---|---|---|---|---|
| planted | True | False | 0.001238 | 1.00 | ~1.0 | 0.00 | `trial_count_below_pbo_configs`, `doubt` |
| null | False | False | -4.87e-05 | 0.50 | 0.341 | 0.00 | DSR, negative median OOS, static A2 |

D13 detection is median OOS > 0, ≥60% +OOS, no decay, and planted median > null.
The planted path meets that. Full-gate `passed=False` on the control itself is
only the two-config PBO trial-count doubt; it is not used to rank templates.

## Cycle

- tested 12, killed 12, survivors 0, kill_rate 1.0000
- n_days 595 (MNQ), WF `is_size=42 oos_size=69` target 8 windows
- holdout eval skipped (no independent survivors; window unopened)

## Per-config table

| config | verdict | death | trades | hitrate | BE | hitrate−BE | gross | net | +OOS | median OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| mr-mes-10-1.5 | kill | DSR, −median OOS, A2 | 31628 | 0.290 | 0.471 | −0.181 | −0.516 | −1.597 | 0.000 | −0.002637 |
| vi-mnq-10-0.55 | kill | DSR, −median OOS, A2 | 15192 | 0.180 | 0.565 | −0.385 | −0.280 | −0.312 | 0.000 | −0.000518 |
| rm-mes-10-0.40 | kill | DSR, −median OOS, A2 | 28135 | 0.295 | 0.471 | −0.176 | −0.443 | −1.512 | 0.000 | −0.002292 |
| or-mes-5-bo | kill | DSR, −median OOS, A2 | 40698 | 0.288 | 0.471 | −0.183 | −0.678 | −2.090 | 0.000 | −0.003372 |
| or-mnq-15-fade | kill | DSR, −median OOS, A2 | 75352 | 0.197 | 0.565 | −0.368 | −1.237 | −1.425 | 0.000 | −0.002296 |
| gap-mes-8 | kill | DSR, −median OOS, A2 | 533 | 0.259 | 0.471 | −0.212 | −0.013 | −0.021 | 0.000 | −3.46e-05 |
| vwap-mes-20-1.5 | kill | DSR, −median OOS, A2 | 28510 | 0.294 | 0.471 | −0.177 | −0.449 | −1.416 | 0.000 | −0.002349 |
| rc-mes-20-0.25 | kill | DSR, −median OOS, A2 | 25820 | 0.295 | 0.471 | −0.176 | −0.406 | −1.393 | 0.000 | −0.002268 |
| cr-mes-3 | kill | DSR, −median OOS, A2 | 22147 | 0.286 | 0.471 | −0.185 | −0.388 | −1.179 | 0.000 | −0.001916 |
| tod-mes-15 | kill | DSR, −median OOS, A2, decay | 2877 | 0.264 | 0.471 | −0.207 | −0.062 | −0.137 | 0.000 | −0.000228 |
| pb-mnq-20 | kill | DSR, −median OOS, A2 | 19354 | 0.202 | 0.565 | −0.363 | −0.305 | −0.364 | 0.000 | −0.000661 |
| vx-mes-20 | kill | DSR, −median OOS, A2 | 27531 | 0.290 | 0.471 | −0.181 | −0.456 | −1.375 | 0.000 | −0.002273 |

A2 = static median OOS not positive and +OOS share < 60%. Every config has
hitrate below break-even and 0/8 positive OOS windows. D14 (costs, IS/OOS
Sharpes, market-regime Sharpes, bootstrap n=48) is in
`experiments/reports/phase5_p2_results.md`.

## Survivors / holdout

None. Holdout was not opened. Nothing is proposed for promotion or SIM.

## Artefact vs honest kill

The session-hold control shows the gate **can** detect a known lookahead edge
on this tape (100% +OOS, DSR ~1). The 12 templates then die with costs larger
than gross and hitrate well below BE. That matches researchers F17 (1m OHLC
mean-reversion / volume imbalance a priori weak) more than a pipeline bug.
High trade counts (15k–75k on train) are the 1m scalping implementations, not
a holdout leak. No floor or template was changed after seeing these numbers.
