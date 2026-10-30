# Phase 5 P2 research cycles

- generated_at: `2026-10-30T09:37:01.494867+00:00`
- hypotheses: `4` tested: `4` killed: `4` survivors: `0`
- kill_rate: `1.0000` (expectation > 0.90, diagnostic flag `expected_high_kill`)
- stopped: `False` reason: ``
- real data usable: `True`

## Data requirement (if unusable)

- **instruments**: ES primary; NQ pair leg; no MES/MNQ
- **holdout**: pin 2026-01-28T23:00:00Z sealed; pre-holdout CSVs only
- **configs**: exactly RV-01, RV-02, LH-01, LH-03; LH-02/LH-04 dropped inside n=6
- **promotion**: none
- **sim_real**: none

- searched: /tmp/lumina-es/ES_pre_holdout.csv, /tmp/lumina-nq/NQ_pre_holdout.csv, /tmp/lumina-vix/VIX_daily_pre_holdout.csv, /tmp/lumina-macro/macro_events_pre_holdout.csv
- missing instruments: MES, MNQ

## Modeled costs vs instrument-specific USD/contract bands

| root | comm $/side | comm $ RT | half-spread $ | RTH $/contract | RTH bp | ETH $/contract | band $/contract | in_band | note |
|---|---|---|---|---|---|---|---|---|---|
| ES | 2.87 | 5.74 | 6.250 | 14.170 | 0.567 | 14.170 | 3.00-12.00 | False | modeled RTH one-way USD/contract sits outside the instrument-specific dollar band; CostModel coefficient is not retuned on holdout (see slippage_calibration) |
| NQ | 2.87 | 5.74 | 2.500 | 7.390 | 0.924 | 7.390 | 3.00-12.00 | True | modeled RTH one-way USD/contract sits in the instrument-specific dollar band |
| MES | 0.94 | 1.88 | 0.625 | 2.070 | 0.828 | 2.070 | 1.50-6.00 | True | modeled RTH one-way USD/contract sits in the instrument-specific dollar band |
| MNQ | 0.94 | 1.88 | 0.250 | 1.392 | 1.740 | 1.392 | 1.20-5.00 | True | modeled RTH one-way USD/contract sits in the instrument-specific dollar band |

## Costs and tick floors

| root | target ticks | stop ticks | tick $ | RT cost ticks | net target $ | net stop $ | BE win rate |
|---|---|---|---|---|---|---|---|
| ES | 1 | 1 | 12.50 | 2.267 | -15.84 | 40.84 | n/a |

## Hypotheses

| id | template | inst | tested | passed | death | PBO | DSR | WFE |
|---|---|---|---|---|---|---|---|---|
| hyp-p2s-rv-01 | mean_reversion | ES | True | False | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.357 | 0.000 | n/a |
| hyp-p2s-rv-02 | overnight_gap | ES | True | False | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.357 | 0.008 | n/a |
| hyp-p2s-lh-01 | range_compression | ES | True | False | dsr_below_threshold,static_positive_share_below_60 | 0.357 | 0.039 | n/a |
| hyp-p2s-lh-03 | close_reversal | ES | True | False | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.357 | 0.000 | n/a |

## Survivors

None. Expected: most economically simple hypotheses die at the Validation Gate.

## Holdout seal

- sha256: `c17138994a7fa198d27f829a618bdd459552cd3571382c95a8f64f54c88b8c07`
- previous_seal: `6e8fa88e3aad048271cb52a63f76cbf4ed8a9261b85b85f03f631b872cf2e51b`
- windows: n_days=598 walk-forward is_size=45 oos_size=69 target_windows=8 units=globex_session_days
- n_days: `598`
- pin: `2026-01-28T23:00:00+00:00` Globex session boundary (legacy `2026-01-29T00:00:00Z` recorded)
- holdout sealed and unopened for ranking, tuning, and gate calibration
- 1m four-leg costs (ADR-0055/1.2 RTH-ETH session slippage) then Globex session-day resample
- floors unchanged: DSR>=0.95, PBO hard 0.50 / warn 0.25, min 6 OOS; static rules use A2 not WFE
- geometry is pre-registered per template; shadow only; zero orders; S0 freeze untouched
- positive_control_detected: `True` null_detected: `False`
- control: Planted edge: at the first RTH bar of each session, the control knows the sign of that session's last-RTH-close minus first-RTH-open (unadjusted). It holds that direction until RTH close (session flatten, C10). Brackets are 1.8×ATR14 target / 0.9×ATR14 stop in index points (midpoint D13; not 16/8 and not the unclipped limit-move ceiling) so a shuffled 50% null is not a 2R artefact. time_stop_bars=2000 cannot fire inside one RTH session. Four-leg costs unchanged. Known size is the session RTH open-to-close move clipped at those ATR multiples minus costs. | fade 1/1.2: planted detected, passed_gate, null 7/8 0/32; breakout 1.8/0.9: planted detected, passed_gate, null 7/8 0/32


## Holdout evaluation (survivors only, one pass)

Skipped: no independent survivors. The sealed window was not used for ranking or calibration.

