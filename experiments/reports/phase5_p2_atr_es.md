# Phase 5 P2 research cycles

> **Control-note correction (not a rerun).** This PIT executed D13 as
> **1:1 1.5×ATR14** (`control_geometry_mode=atr`, ADR-0068). The generated
> `control_note` field still quotes the action-1 unclipped 20000/20000 text.
> JSON is the untouched PIT dump (`sha256 19e3d9b9…`). See
> `phase5_p2_atr_es_control_note.md`.
>

- generated_at: `2026-10-29T15:56:28.034138+00:00`
- hypotheses: `10` tested: `10` killed: `10` survivors: `0`
- kill_rate: `1.0000` (expectation > 0.90, diagnostic flag `expected_high_kill`)
- stopped: `False` reason: ``
- real data usable: `True`

## Data requirement (if unusable)

- **instruments**: P2 first cycle: MES and MNQ 1m; ES/NQ accepted later
- **bar_size**: NT8 1-minute bars first; 5m or 1d accepted only as a documented fallback
- **period**: recent 2-3 years; train split must still have >= 241 bars after the holdout lock
- **holdout**: last 9 calendar months (allowed 6-12); P2 NT8 tapes pin 2026-01-28T23:00:00Z (legacy 2026-01-29T00:00:00Z recorded, holdout unopened); access_bars(purpose=selection|tuning|calibration|gate) fails closed on holdout timestamps
- **format**: UTF-8 CSV header timestamp,open,high,low,close,volume (UTC ISO-8601 with offset)
- **paths**: $LUMINA_RESEARCH_DATA_DIR/{MES,MNQ}/1m/nt8_{mes,mnq}_1m.csv ; data/research/{MES,MNQ}/1m/*.csv ; optional data/research/VIX/1d/vix.csv for regime labels
- **code**: lumina_research.cycles.data.discover_data + lumina_research.cycles.holdout.access_bars

- searched: $LUMINA_RESEARCH_DATA_DIR, /workspace/data/research, /workspace/reports/playground_bar_archive
- missing instruments: (none)

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
| ES | 1 | 1 | 12.50 | 2.267 | -15.84 | 40.84 | 1.634 |

## Hypotheses

| id | template | inst | tested | passed | death | PBO | DSR | WFE |
|---|---|---|---|---|---|---|---|---|
| hyp-p2a-mr-es | mean_reversion | ES | True | False | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.200 | 0.000 | n/a |
| hyp-p2a-vwap-es | vwap_distance | ES | True | False | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.200 | 0.000 | n/a |
| hyp-p2a-tod-es | time_of_day_inventory | ES | True | False | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.200 | 0.002 | n/a |
| hyp-p2a-or-fade-es | opening_range_fade | ES | True | False | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.200 | 0.000 | n/a |
| hyp-p2a-or-bo-es | opening_range_breakout | ES | True | False | dsr_below_threshold | 0.200 | 0.057 | n/a |
| hyp-p2a-rm-es | regime_momentum | ES | True | False | dsr_below_threshold | 0.200 | 0.097 | n/a |
| hyp-p2a-rc-es | range_compression | ES | True | False | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.200 | 0.000 | n/a |
| hyp-p2a-vx-es | volatility_expansion | ES | True | False | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.200 | 0.000 | n/a |
| hyp-p2a-pb-es | trend_pullback | ES | True | False | dsr_below_threshold | 0.200 | 0.049 | n/a |
| hyp-p2a-gap-es | overnight_gap | ES | True | False | dsr_below_threshold | 0.200 | 0.019 | n/a |

## Survivors

None. Expected: most economically simple hypotheses die at the Validation Gate.

## Holdout seal

- sha256: `cdf964b6413985726a14b7d63375fef9fda52b9a39bedb512ecd43b73b1f8279`
- previous_seal: `6e8fa88e3aad048271cb52a63f76cbf4ed8a9261b85b85f03f631b872cf2e51b`
- windows: n_days=598 walk-forward is_size=45 oos_size=69 target_windows=8 units=globex_session_days
- n_days: `598`
- pin: `2026-01-28T23:00:00+00:00` Globex session boundary (legacy `2026-01-29T00:00:00Z` recorded)
- holdout sealed and unopened for ranking, tuning, and gate calibration
- 1m four-leg costs (ADR-0055/1.2 RTH-ETH session slippage) then Globex session-day resample
- floors unchanged: DSR>=0.95, PBO hard 0.50 / warn 0.25, min 6 OOS; static rules use A2 not WFE
- geometry is pre-registered per template; shadow only; zero orders; S0 freeze untouched
- positive_control_detected: `True` null_detected: `False`
- control: Planted edge: at the first RTH bar of each session, the control knows the sign of that session's last-RTH-close minus first-RTH-open (unadjusted). It holds that direction until RTH close (session flatten, C10). Brackets are 1:1 20000/20000 ticks (CME 20% limit-move ceiling; not an 8-tick clip) so a shuffled 50% null is not a 2R artefact. time_stop_bars=2000 cannot fire inside one RTH session. Four-leg costs unchanged. Known size is the session RTH open-to-close move minus costs. | ES: planted detected, null rejected; MES: planted detected, null rejected


## Holdout evaluation (survivors only, one pass)

Skipped: no independent survivors. The sealed window was not used for ranking or calibration.

