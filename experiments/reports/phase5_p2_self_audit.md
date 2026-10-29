# P2 artefact-fix independent audit (researchers 2026-10-29 A1–F18, steps 1–4)

Builder self-audit on PR 66 HEAD `6914704b` was **not** trusted. This file is the
auditor's checklist after verifying code + tests. Steve overrode C11: no fixed
16/8 tick floor. Charter: DSR/PBO floors must not loosen; holdout must not be
opened; pin `2026-01-28T23:00:00Z`.

| ID | Point | Status | Evidence (code + a test that fails if broken) |
|---|---|---|---|
| A1 | Document `n_days`; static WF ok | ✅ | `ValidationResults.n_days`, `session_day_count`; `test_n_days_sizes_from_session_count_not_bar_count` fails if `n_days` becomes bar count |
| A2 | Replace WFE by median OOS>0, ≥60% +OOS, decay | ✅ | **ADR-0062** (not 0061 — that number is S1 SIM whitelist on main); `static_rules.py`, `gate.py`; `test_static_rules_replace_wfe_and_skip_cpcv` |
| A3 | CPCV only with fit; else bootstrap/OOS dist | ✅ | `evaluate_candidate` skips CPCV when `has_fit_step=False`; `block_bootstrap.py`; `test_evaluate_candidate_static_skips_cpcv_keeps_dsr_pbo` |
| B4 | MNQ/micro cost band in $ or bp | ✅ | `cost_bands.py` USD bands; `test_mnq_usd_band_is_not_the_legacy_tick_interval` fails if MNQ band == legacy tick interval |
| B5 | Slippage + vol term; no `volatility_price=2.0` | ✅ | CostModel 1.1.0, `bar_volatility_price` = true range. Builder left `volatility_price=2.0` in `agents/synthetic.py`, `proof/gate_suite.py`, `tests/research/synthetic.py` — **fixed**. `test_research_source_has_no_fixed_volatility_price_two` |
| B6 | Trade-through fill; document touch vs slippage | ✅ | `fills.py` `FILL_POLICY=trade_through_strict`; `test_trade_through_rejects_touch_and_fills_through` |
| C7 | Pre-registered 3–5 grid / max trials | N/A | Next cycle. Catalog stays 12/24. |
| C8 | Coarser bars / RTH-only next cycle | N/A | This cycle keeps 1m + RTH filter on the same 12 families. |
| C9 | Overnight gap = prior RTH close → today RTH open; VX 75th/90th | ✅ | `_overnight_gap`; catalog `vx-mes-20` threshold `0.75`; `test_overnight_gap_uses_prior_rth_close_to_today_rth_open`, `test_volatility_expansion_catalog_is_75th_percentile` |
| C10 | Session-end flatten and/or RTH + time-stop | ✅ | catalog RTH + time-stop 16 + flatten; `test_session_end_flatten_and_time_stop_close_at_bar_close`; `test_flatten_off_does_not_emit_session_end` |
| C11 | No fixed 16/8 tick floor (Steve override) | ✅ | `require_geometry` only rejects `<1`; `test_geometry_has_no_fixed_tick_floor` |
| D12 | Market regimes, not strategy PnL | ✅ | Builder left fail-open: omitted `market_returns` fell back to strategy PnL. **Fixed** to `RegimeSnapshot.missing()`. `test_market_regimes_use_instrument_returns_not_strategy_pnl`; kill battery `omitted market_returns must be missing regimes` |
| D13 | Positive control + null; fail if not detected | ✅ | Builder `test_run_controls_detects_planted_edge_and_rejects_null` was theatre (it `pytest.raises(PositiveControlFailed)` then asserted `accepted`). **Fixed**. Attack tests: `test_flat_tape_positive_control_fails_closed`, `test_identity_null_is_not_accepted_as_an_edge`, `test_runner_stop_reason_is_positive_control_failed`. Evaluation exceptions wrap as `PositiveControlFailed`. |
| D14 | Diagnostics: trades, hitrate vs BE, gross/net, costs, Sharpes, N | ✅ | `diagnostics.py`; `test_diagnostics_include_trades_hitrate_costs_and_sharpes`; `test_unbalanced_hitrate_counts_only_winning_trades` |
| E15 | Friday 2026-06-12 roll; indicators adjusted, PnL unadjusted | ✅ | `roll_verify.py`, `adjust.py`, `prepare_tape.signal_bars`; `test_friday_roll_and_back_adjust_leaves_pnl_unadjusted`; `test_pnl_uses_unadjusted_prices_indicators_use_adjusted` |
| E16 | Holdout on session boundary; reseal; do not open | ✅ | Pin `2026-01-28T23:00:00Z`. Builder `prepare_for_purpose` dropped the explicit pin on short tapes; runner still filled `holdout_prepared`. **Fixed**: always pass `pinned_start_ns`; runner never materializes holdout. `test_locked_purposes_cannot_read_bars_at_or_after_holdout_pin`, `test_prepare_for_purpose_gate_drops_post_pin_bars` |
| F17 | Longer horizon / macro / cross-asset next | N/A | Next cycle. |
| F18 | ES/NQ after fixes | N/A | Next cycle. Same 12 MES/MNQ templates only. |
| >90s gap | Review forced-exit; RTH holes only | ✅ | `prepare._breaks` requires both adjacent bars RTH; `test_overnight_holes_do_not_force_exit_rth_holes_do`; `test_overnight_globex_gap_is_not_an_rth_hole` |
| Exit PnL | Book at target/stop; trade-through; gap-through uses open | ✅ | Builder left stop as trade-through (`bar.low < stop_px`). **Fixed** to fill on touch. Targets still trade-through. `test_stop_touch_and_gap_through_book_conservative_exits`, `test_target_touch_does_not_fill_trade_through_does` |
| Static embargo | `embargo_applied` only when embargo > 0 | ✅ | Builder used `embargo >= 0` (always true). **Fixed**. `test_static_embargo_zero_is_not_claimed_applied` |
| DSR/PBO | Floors not loosened | ✅ | `FLOOR_DSR_PROBABILITY_MIN=0.95`, `FLOOR_PBO_HARD_REJECT=0.50`; static bundle still DSR-rejects |
| No SIM/Risk/S0 | Research propose-only | ✅ | Three-dot vs `origin/main` is research-only. No Risk Core / PromotionGate / S0/S1 / order-path edits in this PR |
| Step 4 | Re-run same 12; do not open holdout | ⚠️ | Real CSVs absent → `phase5_p2_real_rerun_blocked.md`. Not executed. Fixture pipeline only. |
| Mutation | ≥300 mutants, non-equivalent kill ≥0.90 | ✅ | 320 mutants, 311 killed, 9 equivalent excluded, **0** unjustified survivors, kill_rate **1.0000** (`phase5_p2_mutation.json`) |
| Look-ahead | Indicators/regimes/roll/overnight | ✅ | `test_mean_reversion_does_not_look_ahead_to_future_bars`, `test_regime_labels_are_causal_in_past_windows` |
| Cost units | MNQ USD, not ticks | ✅ | `test_mnq_usd_band_is_not_the_legacy_tick_interval` |

## Builder holes closed on this branch

1. Stop exits now fill on touch; targets remain trade-through; gap-through still books at the open.
2. Omitted `market_returns` is `missing()` (fail-closed). Validation agent supplies a synthetic instrument series only when the extra field is absent, without reopening the strategy-PnL fallback.
3. Static `embargo_applied` is `embargo > 0`.
4. Runner never populates `holdout_prepared`. `prepare_for_purpose` honors the explicit pin below `P2_PIN_MIN_BARS`.
5. Positive-control evaluation exceptions become `PositiveControlFailed`. Theatre D13 test replaced by attack tests that can fail.
6. Leftover `volatility_price=2.0` removed from research synthetics/proof.
7. Static-rule WFE ADR numbered **0062** so it does not collide with S1 ADR-0061.
8. Mutation: 51 additional non-equivalent kills; 9 survivors justified as equivalent (dead raises after `spec_for`, constant-true Friday AND, redundant `index>0` conjunct, dead Spearman-NaN path, redundant 1-bar/span raise, seal leak check already enforced by `access_bars`).

## Residuals

1. Real NT8 MES/MNQ CSVs are not in this environment. Step 4 on the sealed tape is blocked, not failed. The holdout was not opened.
2. Positive control is proven on a constructed 22-session RTH tape, not yet on the real MES tape. Runner fail-closes on the next real-P2 run if detection fails.
3. Seal bar counts (`n_train`/`n_holdout`) stay pending until CSVs are mounted.
4. Nine equivalent AST mutants remain excluded with written reasons. Non-equivalent kill rate is 1.0.
5. Fixture 12-template tape is a monotonic synthetic path: several families emit no trades; empty market-trend buckets still fail-closed.
