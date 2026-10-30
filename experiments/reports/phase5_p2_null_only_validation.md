# P2 null-only validation (2026-10-29 18:17)

- generated_at: `2026-10-29T17:33:06.753012+00:00`
- answers: `ONDERZOEKERS-ANTWOORDEN-NULLGATE-20261029T1817.md`
- answers_sha256: `8d6dc539bef53d4e4bfe6ec6cdaefdd5f06d2508c11407f9648bb293dfd547c2`
- CostModel: `1.2.0`
- holdout pin `2026-01-28T23:00:00Z`: asserted absent, unopened
- NQ: closed; templates: not run; strategy-run: locked until strict FPR passes
- seeds: `32`
- gate: A2 and +OOS ≥ 7/8; fail at ≥4/32; A2 count is diagnostic
- builder_before: `mean_shuffle`
- builder_after: `linear_magnitude`
- strengthening: v2 linear_magnitude: OLS linear detrend of session OC vs time index inside each WF partition, session-shuffle residual signs, count-balance |n_pos-n_neg|<=1, greedy magnitude-balance on |OC|. ISO-week block of planted signs stays report-only extra (8 seeds) and is skipped here.
- ES bars: `818851` sessions `598` first `2023-10-01T22:01:00Z` last `2026-01-28T22:00:00Z`
- strict_gate_pass: `True`

## Exact FPR

| tape | builder | exact A2 (old) | A2 share | exact 7/8 (strict) | strict share | ≤3/32 |
|---|---|---|---|---|---|---|
| synthetic | mean_shuffle | 9/32 | 0.281 | 2/32 | 0.062 | yes |
| synthetic | linear_magnitude | 0/32 | 0.000 | 0/32 | 0.000 | yes |
| ES | mean_shuffle | 4/32 | 0.125 | 0/32 | 0.000 | yes |
| ES | linear_magnitude | 6/32 | 0.188 | 0/32 | 0.000 | yes |
