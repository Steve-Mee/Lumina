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
| `hyp-noise-0000-s2088460572` | no | FAIL | no | 0.0013 | 0.0000 | n/a | -0.8315 | -0.8315 | 0.0000 | 9 | `missing_or_undefined_wfe,dsr_below_threshold,doubt` |
| `hyp-noise-0001-s1327243828` | no | FAIL | no | 0.0001 | 0.0000 | n/a | -1.3649 | -1.3649 | 0.0000 | 9 | `missing_or_undefined_wfe,dsr_below_threshold,negative_median_oos_after_costs,doubt` |
| `hyp-noise-0002-s1199329012` | no | FAIL | no | 0.0010 | 0.0000 | -4.7674 | -0.8737 | -0.8737 | 0.0000 | 9 | `dsr_below_threshold,negative_median_oos_after_costs,wfe_below_threshold` |
| `hyp-noise-0003-s1479552164` | no | FAIL | no | 0.2110 | 0.0000 | 0.6342 | 1.0609 | 1.0609 | 1.0000 | 9 | `dsr_below_threshold` |
| `hyp-noise-0004-s1555985896` | no | FAIL | no | 0.0053 | 0.0000 | n/a | -0.4047 | -0.4047 | 0.0000 | 9 | `missing_or_undefined_wfe,dsr_below_threshold,doubt` |
| `hyp-noise-0005-s1253421050` | no | FAIL | no | 0.3273 | 0.0000 | 1.4158 | 1.3782 | 1.3782 | 1.0000 | 9 | `dsr_below_threshold` |
| `hyp-noise-0006-s2013042981` | no | FAIL | no | 0.0061 | 0.0000 | n/a | -0.3387 | -0.3387 | 0.0000 | 9 | `missing_or_undefined_wfe,dsr_below_threshold,negative_median_oos_after_costs,doubt` |
| `hyp-noise-0007-s97563383` | no | FAIL | no | 0.0307 | 0.0000 | 0.6528 | 0.2020 | 0.2020 | 1.0000 | 9 | `dsr_below_threshold,negative_median_oos_after_costs` |
| `hyp-noise-0008-s1241774772` | no | FAIL | no | 0.0251 | 0.0000 | 3.6647 | 0.1393 | 0.1393 | 1.0000 | 9 | `dsr_below_threshold` |
| `hyp-noise-0009-s1468188361` | no | FAIL | no | 0.1616 | 0.0000 | 1.2709 | 0.9614 | 0.9614 | 1.0000 | 9 | `dsr_below_threshold` |
| `hyp-noise-0010-s455561258` | no | FAIL | no | 0.0000 | 0.0000 | n/a | -1.9405 | -1.9405 | 0.0000 | 9 | `missing_or_undefined_wfe,dsr_below_threshold,negative_median_oos_after_costs,doubt` |
| `hyp-noise-0011-s80735816` | no | FAIL | no | 0.0304 | 0.0000 | 1.7702 | 0.2368 | 0.2368 | 1.0000 | 9 | `dsr_below_threshold,negative_median_oos_after_costs` |
| `hyp-noise-0012-s1072134541` | no | FAIL | no | 0.0692 | 0.0000 | 23.6046 | 0.5787 | 0.5787 | 1.0000 | 9 | `dsr_below_threshold,negative_median_oos_after_costs` |
| `hyp-noise-0013-s1161127665` | no | FAIL | no | 0.0665 | 0.0000 | 0.3241 | 0.5685 | 0.5685 | 1.0000 | 9 | `dsr_below_threshold,negative_median_oos_after_costs,wfe_below_threshold` |
| `hyp-noise-0014-s304847128` | no | FAIL | no | 0.0048 | 0.0000 | n/a | -0.3383 | -0.3383 | 0.0000 | 9 | `missing_or_undefined_wfe,dsr_below_threshold,negative_median_oos_after_costs,doubt` |
| `hyp-noise-0015-s1764887916` | no | FAIL | no | 0.1001 | 0.0000 | 2.3984 | 0.7676 | 0.7676 | 1.0000 | 9 | `dsr_below_threshold` |
| `hyp-noise-0016-s564474925` | no | FAIL | no | 0.0870 | 0.0000 | 0.6274 | 0.7108 | 0.7108 | 1.0000 | 9 | `dsr_below_threshold` |
| `hyp-noise-0017-s15517151` | no | FAIL | no | 0.0244 | 0.0000 | -1.0501 | 0.2077 | 0.2077 | 1.0000 | 9 | `dsr_below_threshold,wfe_below_threshold` |
| `hyp-noise-0018-s986496812` | no | FAIL | no | 0.0005 | 0.0000 | n/a | -0.8769 | -0.8769 | 0.0000 | 9 | `missing_or_undefined_wfe,dsr_below_threshold,negative_median_oos_after_costs,doubt` |
| `hyp-noise-0019-s2084892231` | no | FAIL | no | 0.0053 | 0.0000 | n/a | -0.2660 | -0.2660 | 0.0000 | 9 | `missing_or_undefined_wfe,dsr_below_threshold,negative_median_oos_after_costs,doubt` |
| `hyp-noise-0020-s500792651` | no | FAIL | no | 0.2210 | 0.0000 | 0.8264 | 1.2293 | 1.2293 | 1.0000 | 9 | `dsr_below_threshold` |
| `hyp-noise-0021-s1280858948` | no | FAIL | no | 0.0058 | 0.0000 | n/a | -0.2295 | -0.2295 | 0.0000 | 9 | `missing_or_undefined_wfe,dsr_below_threshold,doubt` |
| `hyp-noise-0022-s1777274006` | no | FAIL | no | 0.0083 | 0.0000 | n/a | -0.1120 | -0.1120 | 0.0000 | 9 | `missing_or_undefined_wfe,dsr_below_threshold,doubt` |
| `hyp-planted-0023-s464809217` | yes | PASS | yes | 0.9999 | 0.0000 | 1.3865 | 5.4006 | 5.4006 | 1.0000 | 9 | `` |
| `hyp-planted-0024-s1256019940` | yes | PASS | yes | 0.9998 | 0.0000 | 1.1651 | 5.3584 | 5.3584 | 1.0000 | 9 | `` |

Each candidate's full OOS path values are in `phase2_kill_rate.json`.
