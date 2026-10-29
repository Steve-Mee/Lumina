# Phase 2 research loop — kill-rate report

Distributions only. No single-backtest claim.

- seed: `20261028`
- hypotheses: **25**
- killed: **23**
- promoted (survivors): **2**
- kill rate: **0.9200**
- planted ids: `hyp-planted-0023-s464809217, hyp-planted-0024-s1256019940`
- planted survived: `hyp-planted-0023-s464809217, hyp-planted-0024-s1256019940`

## Why ideas die (per gate check)

| check | count |
|---|---|
| `dsr_below_threshold` | 23 |
| `negative_median_oos_after_costs` | 11 |
| `doubt` | 10 |
| `missing_or_undefined_wfe` | 10 |
| `wfe_below_threshold` | 3 |

## Per-candidate OOS distribution

| id | planted | gate | promoted | DSR | PBO | WFE | OOS median | OOS worst | pct+ | n_oos | reasons |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `hyp-noise-0000-s2088460572` | no | FAIL | no | 0.0014 | 0.0000 | n/a | -0.8242 | -0.8242 | 0.0000 | 9 | `missing_or_undefined_wfe,dsr_below_threshold,doubt` |
| `hyp-noise-0001-s1327243828` | no | FAIL | no | 0.0001 | 0.0000 | n/a | -1.3578 | -1.3578 | 0.0000 | 9 | `missing_or_undefined_wfe,dsr_below_threshold,negative_median_oos_after_costs,doubt` |
| `hyp-noise-0002-s1199329012` | no | FAIL | no | 0.0010 | 0.0000 | -4.5969 | -0.8667 | -0.8667 | 0.0000 | 9 | `dsr_below_threshold,negative_median_oos_after_costs,wfe_below_threshold` |
| `hyp-noise-0003-s1479552164` | no | FAIL | no | 0.2131 | 0.0000 | 0.6362 | 1.0670 | 1.0670 | 1.0000 | 9 | `dsr_below_threshold` |
| `hyp-noise-0004-s1555985896` | no | FAIL | no | 0.0054 | 0.0000 | n/a | -0.3976 | -0.3976 | 0.0000 | 9 | `missing_or_undefined_wfe,dsr_below_threshold,doubt` |
| `hyp-noise-0005-s1253421050` | no | FAIL | no | 0.3301 | 0.0000 | 1.4141 | 1.3847 | 1.3847 | 1.0000 | 9 | `dsr_below_threshold` |
| `hyp-noise-0006-s2013042981` | no | FAIL | no | 0.0063 | 0.0000 | n/a | -0.3318 | -0.3318 | 0.0000 | 9 | `missing_or_undefined_wfe,dsr_below_threshold,negative_median_oos_after_costs,doubt` |
| `hyp-noise-0007-s97563383` | no | FAIL | no | 0.0312 | 0.0000 | 0.6559 | 0.2082 | 0.2082 | 1.0000 | 9 | `dsr_below_threshold,negative_median_oos_after_costs` |
| `hyp-noise-0008-s1241774772` | no | FAIL | no | 0.0256 | 0.0000 | 3.5949 | 0.1462 | 0.1462 | 1.0000 | 9 | `dsr_below_threshold` |
| `hyp-noise-0009-s1468188361` | no | FAIL | no | 0.1634 | 0.0000 | 1.2700 | 0.9676 | 0.9676 | 1.0000 | 9 | `dsr_below_threshold` |
| `hyp-noise-0010-s455561258` | no | FAIL | no | 0.0000 | 0.0000 | n/a | -1.9335 | -1.9335 | 0.0000 | 9 | `missing_or_undefined_wfe,dsr_below_threshold,negative_median_oos_after_costs,doubt` |
| `hyp-noise-0011-s80735816` | no | FAIL | no | 0.0309 | 0.0000 | 1.7499 | 0.2435 | 0.2435 | 1.0000 | 9 | `dsr_below_threshold,negative_median_oos_after_costs` |
| `hyp-noise-0012-s1072134541` | no | FAIL | no | 0.0703 | 0.0000 | 20.6265 | 0.5855 | 0.5855 | 1.0000 | 9 | `dsr_below_threshold,negative_median_oos_after_costs` |
| `hyp-noise-0013-s1161127665` | no | FAIL | no | 0.0675 | 0.0000 | 0.3281 | 0.5746 | 0.5746 | 1.0000 | 9 | `dsr_below_threshold,negative_median_oos_after_costs,wfe_below_threshold` |
| `hyp-noise-0014-s304847128` | no | FAIL | no | 0.0049 | 0.0000 | n/a | -0.3316 | -0.3316 | 0.0000 | 9 | `missing_or_undefined_wfe,dsr_below_threshold,negative_median_oos_after_costs,doubt` |
| `hyp-noise-0015-s1764887916` | no | FAIL | no | 0.1015 | 0.0000 | 2.3711 | 0.7744 | 0.7744 | 1.0000 | 9 | `dsr_below_threshold` |
| `hyp-noise-0016-s564474925` | no | FAIL | no | 0.0883 | 0.0000 | 0.6287 | 0.7172 | 0.7172 | 1.0000 | 9 | `dsr_below_threshold` |
| `hyp-noise-0017-s15517151` | no | FAIL | no | 0.0249 | 0.0000 | -1.0033 | 0.2144 | 0.2144 | 1.0000 | 9 | `dsr_below_threshold,wfe_below_threshold` |
| `hyp-noise-0018-s986496812` | no | FAIL | no | 0.0006 | 0.0000 | n/a | -0.8700 | -0.8700 | 0.0000 | 9 | `missing_or_undefined_wfe,dsr_below_threshold,negative_median_oos_after_costs,doubt` |
| `hyp-noise-0019-s2084892231` | no | FAIL | no | 0.0055 | 0.0000 | n/a | -0.2583 | -0.2583 | 0.0000 | 9 | `missing_or_undefined_wfe,dsr_below_threshold,negative_median_oos_after_costs,doubt` |
| `hyp-noise-0020-s500792651` | no | FAIL | no | 0.2233 | 0.0000 | 0.8275 | 1.2360 | 1.2360 | 1.0000 | 9 | `dsr_below_threshold` |
| `hyp-noise-0021-s1280858948` | no | FAIL | no | 0.0059 | 0.0000 | n/a | -0.2224 | -0.2224 | 0.0000 | 9 | `missing_or_undefined_wfe,dsr_below_threshold,doubt` |
| `hyp-noise-0022-s1777274006` | no | FAIL | no | 0.0085 | 0.0000 | n/a | -0.1052 | -0.1052 | 0.0000 | 9 | `missing_or_undefined_wfe,dsr_below_threshold,doubt` |
| `hyp-planted-0023-s464809217` | yes | PASS | yes | 0.9999 | 0.0000 | 1.3865 | 5.4006 | 5.4006 | 1.0000 | 9 | `` |
| `hyp-planted-0024-s1256019940` | yes | PASS | yes | 0.9998 | 0.0000 | 1.1651 | 5.3584 | 5.3584 | 1.0000 | 9 | `` |

Each candidate's full OOS path values are in `phase2_kill_rate.json`.
