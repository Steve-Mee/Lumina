# Phase 2 research loop — multi-seed kill-rate report

Independent seeds. Generators and gate floors were not retuned for this run.

- seeds: **10**
- hypotheses: **300**
- killed: **280**
- promoted: **20**
- overall kill rate: **0.9333**
- planted (designed edges): **20**
- false-kill rate (planted killed / planted): **0.0000**
- noise / nulls: **280**
- false-survivor rate (noise promoted / noise): **0.0000**

## Per seed

| seed | instrument | n | kill rate | planted killed | noise survived |
|---|---|---|---|---|---|
| `20261028` | `MES` | 30 | 0.9333 | 0/2 | 0/28 |
| `7` | `MNQ` | 30 | 0.9333 | 0/2 | 0/28 |
| `13` | `ES` | 30 | 0.9333 | 0/2 | 0/28 |
| `21` | `NQ` | 30 | 0.9333 | 0/2 | 0/28 |
| `42` | `MES` | 30 | 0.9333 | 0/2 | 0/28 |
| `99` | `MNQ` | 30 | 0.9333 | 0/2 | 0/28 |
| `123` | `ES` | 30 | 0.9333 | 0/2 | 0/28 |
| `256` | `NQ` | 30 | 0.9333 | 0/2 | 0/28 |
| `1024` | `MES` | 30 | 0.9333 | 0/2 | 0/28 |
| `4096` | `MNQ` | 30 | 0.9333 | 0/2 | 0/28 |

## Why ideas die (pooled gate checks)

| check | count |
|---|---|
| `dsr_below_threshold` | 280 |
| `doubt` | 161 |
| `missing_or_undefined_wfe` | 161 |
| `negative_median_oos_after_costs` | 141 |
| `wfe_below_threshold` | 42 |
| `missing_regimes` | 1 |

Each candidate's full OOS path values are in `phase2_kill_rate_multiseed.json`.
