# P2 midpoint power (2026-10-29 21:29)

- generated_at: `2026-10-29T20:49:57.647499+00:00`
- answers: `ONDERZOEKERS-ANTWOORDEN-MIDPOINT-20261029T2129.md` sha256 `af183d1d6a9f329942d84bf80854791d69b20cd4264a88ae3da1d9677116e757`
- pre-register: `phase5_p2_midpoint_power_preregister_2026-10-29.md` sha256 `785dbe86392873be12e5e43a80c9549a43c1b55640ed10bdbe974bc6fdcd5dcf`
- CostModel: `1.2.0`
- holdout pin `2026-01-28T23:00:00Z`: asserted absent, unopened
- NQ: closed; templates: not run; strategy-run: not run
- builder: `linear_magnitude`; seeds: `32`
- magnitudes: `1.00`, `0.50`, `0.25` of known size (linear scale of costed session net)
- planted drempel: median OOS > 0, +OOS ≥ `0.60`, no decay, beats null
- null fail-at: `4/32` on 7/8 `n_edge`
- ES bars: `818851` sessions `598` first `2023-10-01T22:01:00Z` last `2026-01-28T22:00:00Z`
- full_magnitude_clean: `True`

## Magnitude 1.00

- overall_verdict: `clean`

| family | tgt/stop | detected | passed_gate | median OOS | +OOS | DSR | PBO n | exact A2 | exact 7/8 | reject_reasons | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fade | 1/1.2 | yes | yes | 0.0116009 | 1.000 | 1.000 | 33 | 4/32 | 0/32 | — | clean |
| breakout | 1.8/0.9 | yes | yes | 0.0114575 | 1.000 | 1.000 | 33 | 2/32 | 0/32 | — | clean |

## Magnitude 0.50

- overall_verdict: `clean`

| family | tgt/stop | detected | passed_gate | median OOS | +OOS | DSR | PBO n | exact A2 | exact 7/8 | reject_reasons | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fade | 1/1.2 | yes | yes | 0.00580043 | 1.000 | 1.000 | 33 | 4/32 | 0/32 | — | clean |
| breakout | 1.8/0.9 | yes | yes | 0.00572874 | 1.000 | 1.000 | 33 | 2/32 | 0/32 | — | clean |

## Magnitude 0.25

- overall_verdict: `clean`

| family | tgt/stop | detected | passed_gate | median OOS | +OOS | DSR | PBO n | exact A2 | exact 7/8 | reject_reasons | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fade | 1/1.2 | yes | yes | 0.00290021 | 1.000 | 1.000 | 33 | 4/32 | 0/32 | — | clean |
| breakout | 1.8/0.9 | yes | yes | 0.00286437 | 1.000 | 1.000 | 33 | 2/32 | 0/32 | — | clean |

