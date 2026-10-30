# P2 midpoint power floor (2026-10-29 22:08)

- generated_at: `2026-10-29T21:59:07.387219+00:00`
- answers: `ONDERZOEKERS-ANTWOORDEN-POWER-S4-20261029T2208.md` sha256 `991138fdd4b741041e3288387dd8aaf89a09652329ada7eec7eaa0f037bfae9d`
- pre-register: `phase5_p2_midpoint_power_floor_preregister_2026-10-29.md` sha256 `8b548fdadb7377ed5fdbe0704bb341ec3d16e703a26b0c3992a219086ce4d9c9`
- csv sha256: `6100588d2f3e519bd815b8f952dc15f01d434cc2a2b70e6453d0c3a7477bbca6`
- CostModel: `1.2.0`
- holdout pin `2026-01-28T23:00:00Z`: asserted absent, unopened
- NQ: closed; templates: not run; strategy-run: not run
- builder: `linear_magnitude`; seeds: `32`
- magnitudes: `0.125`, `0.0625` of known size (linear scale of costed session net; detection floor)
- planted drempel: median OOS > 0, +OOS ≥ `0.60`, no decay, beats null
- null fail-at: `4/32` on 7/8 `n_edge`
- ES bars: `818851` sessions `598` first `2023-10-01T22:01:00Z` last `2026-01-28T22:00:00Z`
- full_magnitude_clean: `False`
- null_leaked: `False`

## Magnitude 0.125

- overall_verdict: `clean`

| family | tgt/stop | detected | passed_gate | median OOS | +OOS | DSR | PBO n | exact A2 | exact 7/8 | reject_reasons | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fade | 1/1.2 | yes | yes | 0.00145011 | 8/8 | 1.000 | 33 | 4/32 | 0/32 | — | clean |
| breakout | 1.8/0.9 | yes | yes | 0.00143219 | 8/8 | 1.000 | 33 | 2/32 | 0/32 | — | clean |

## Magnitude 0.0625

- overall_verdict: `clean`

| family | tgt/stop | detected | passed_gate | median OOS | +OOS | DSR | PBO n | exact A2 | exact 7/8 | reject_reasons | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fade | 1/1.2 | yes | yes | 0.000725053 | 8/8 | 1.000 | 33 | 4/32 | 0/32 | — | clean |
| breakout | 1.8/0.9 | yes | yes | 0.000716093 | 8/8 | 1.000 | 33 | 2/32 | 0/32 | — | clean |

