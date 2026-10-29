# P2 step 4 — real NT8 MES/MNQ, holdout sealed

- generated_at: `2026-10-29T11:24:25Z`
- command: `LUMINA_RESEARCH_DATA_DIR=/tmp/lumina_p2_data python -m lumina_research.proof research --data-dir /tmp/lumina_p2_data`
- floors unchanged: DSR >= 0.95, PBO hard 0.50 / warn 0.25
- holdout pin: `2026-01-28T23:00:00Z` (never opened for selection, tuning, or calibration)
- raw CSVs were loaded from `/tmp/lumina_p2_data` only; they are not in git

## Zip / CSV sha256

| file | sha256 | match |
|---|---|---|
| MES zip | `c5c094a199502fde9cc79f535441995ba7e326811e4e7e01bf1833a25c9c7b2e` | yes |
| MNQ zip | `a1cefabd46c4109a93bb219df45d134f9e3e16ffd3abc8250242c88a3ee5d6e8` | yes |
| MES csv | `a9e9100c5544d59120a37a994955633e835cec8938ed20048164d0f726cf9c01` | yes |
| MNQ csv | `47422de88a2f662c664425b87d79d29fa7a5854d99ed76dd0b946bee7e7a9bf1` | yes |

## New holdout seal

- seal_sha256: `85e4588fde77159315a72bdaa722d6487f93bbad9bf24999311f893950489d40`
- sealed_at: `2026-10-29T11:24:10.034285+00:00`
- previous_seals:
  - `6e8fa88e3aad048271cb52a63f76cbf4ed8a9261b85b85f03f631b872cf2e51b` (2026-01-29T00:00:00Z)
  - `51d55d770aa21fb8f10062c7aab53acebe4866e526eb3419501098bd67172a99` (23:00Z, bar counts pending recompute)
- `bar_counts_pending_recompute` is gone; counts below are from the real tapes at the 23:00Z pin

| instrument | n_bars | n_train | n_holdout | train last | holdout first | holdout last |
|---|---|---|---|---|---|---|
| MES | 1088731 | 820794 | 267937 | 2026-01-28T22:00:00Z | 2026-01-28T23:01:00Z | 2026-10-29T07:54:00Z |
| MNQ | 1083531 | 815584 | 267947 | 2026-01-28T22:00:00Z | 2026-01-28T23:01:00Z | 2026-10-29T07:38:00Z |

59 one-minute bars (23:01–23:59Z on 2026-01-28, after the Globex 22:00–23:00Z halt) moved from train into holdout versus the old 00:00Z split. Train last is strictly before the pin; holdout first is strictly after. n_days on the gate path: `595` Globex sessions, walk-forward `is_size=42 oos_size=69 target_windows=8`.

## Positive / null control

Official cycle: **stopped**, `stop_reason=positive_control_failed`, `n_tested=0`.

Gate audit (planted session-direction on MES train, then daily net):

| control | detected | passed_gate | median OOS | +OOS | DSR | observed SR |
|---|---|---|---|---|---|---|
| planted | False | False | -2.25e-05 | 0.0 | ~6e-11 | -0.275 |
| null shuffle | False | False | -3.00e-05 | 0.0 | ~1e-16 | -0.339 |

All eight planted OOS windows were negative. The null was not an edge. Fail-closed refused to rank the 12 pre-registered templates. Floors were not loosened.

## Per-config table

None of the 12 pre-registered configs were gated. Verdict for each is **untested** because the positive control failed closed. No trades, hitrate, gross/net, +OOS, or median OOS exist for them on this run. D14 is empty for the same reason. Survivors: none. Holdout evaluation: skipped; window still sealed.

| config | template | inst | verdict | death reason |
|---|---|---|---|---|
| mr-mes-10-1.5 | mean_reversion | MES | untested | positive_control_failed |
| vi-mnq-10-0.55 | volume_imbalance | MNQ | untested | positive_control_failed |
| rm-mes-10-0.40 | regime_momentum | MES | untested | positive_control_failed |
| or-mes-5-bo | opening_range_breakout | MES | untested | positive_control_failed |
| or-mnq-15-fade | opening_range_fade | MNQ | untested | positive_control_failed |
| gap-mes-8 | overnight_gap | MES | untested | positive_control_failed |
| vwap-mes-20-1.5 | vwap_distance | MES | untested | positive_control_failed |
| rc-mes-20-0.25 | range_compression | MES | untested | positive_control_failed |
| cr-mes-3 | close_reversal | MES | untested | positive_control_failed |
| tod-mes-15 | time_of_day_inventory | MES | untested | positive_control_failed |
| pb-mnq-20 | trend_pullback | MNQ | untested | positive_control_failed |
| vx-mes-20 | volatility_expansion | MES | untested | positive_control_failed |

## Artefact check (diagnostic on train only; not a second gate)

The planted control **did** fire on the real tape. It is not a missing-signal or empty-tape bug.

| diagnostic | planted | null |
|---|---|---|
| nonzero session-direction signals | 593 (322 long / 271 short) | same count, shuffled signs |
| 1m trades | 571 | 565 |
| reasons | target 231, stop 335, time_stop 5 | target 209, stop 351, time_stop 5 |
| hitrate | 0.408 | 0.375 |
| mean pnl ticks | -1.450 | n/a |
| first-RTH-bar range | median 21 ticks, p90 37, 583/593 >= 8 ticks | — |

The stated known size is the session RTH open-to-close move. The implementation clips that with 8/8 geometry, stop-on-touch, trade-through targets, and a 16-bar time-stop. On real MES 1m the first RTH bar almost always spans more than 8 ticks (median 21), so the lookahead is reduced to an open scalper that loses to the stop/target asymmetry plus costs. That is an artefact of the **control geometry versus 1m open range**, not evidence that the Validation Gate floors are wrong, and not a reason to loosen DSR/PBO.

No template, lookback, threshold, or floor was changed after seeing this. A later control respec (hold the known session direction to RTH close, 1:1, no 8-tick 1m clip) would need an explicit OK; it is not done here.

## What was not done

- Holdout was not opened (`holdout_prepared` stayed empty; no evaluation rows)
- No ranking, tuning, or calibration on holdout or on these results
- DSR 0.95 / PBO 0.50 floors unchanged
- Private CSVs were not committed
