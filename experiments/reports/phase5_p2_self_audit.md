# P2 artefact-fix self-audit (researchers 2026-10-29 A1–F18, steps 1–4)

Zero-gap checklist. Evidence is file + test. C7/C8/F17/F18 are next-cycle and marked N/A for this PR.

| ID | Point | Status | Evidence |
|---|---|---|---|
| A1 | Document `n_days`; static WF ok | ✅ | `window_note`, `ValidationResults.n_days`, `test_n_days_is_documented_on_first_cycle_specs` |
| A2 | Replace WFE by median OOS>0, ≥60% +OOS, decay | ✅ | ADR-0061, `static_rules.py`, `gate.py` (`static_median_oos_not_positive`, `static_positive_share_below_60`, `static_structural_decay`); `test_static_rules_replace_wfe_and_skip_cpcv` |
| A3 | CPCV only with fit; else bootstrap/OOS dist | ✅ | `pipeline.evaluate_candidate` skips CPCV when `has_fit_step=False`; `block_bootstrap.py`; `test_evaluate_candidate_static_skips_cpcv_keeps_dsr_pbo` |
| B4 | MNQ/micro cost band in $ or bp | ✅ | `cost_bands.py` USD bands; `test_mnq_cost_band_is_usd_not_ticks` |
| B5 | Slippage + vol term; no `volatility_price=2.0` | ✅ | CostModel 1.1.0, `bar_volatility_price` = true range, `slippage_calibration.py` documented assumption (no SIM fills in repo); `test_slippage_uses_bar_true_range_never_fixed_two` |
| B6 | Trade-through fill; document touch vs slippage | ✅ | `fills.py` `FILL_POLICY=trade_through_strict`; `test_trade_through_rejects_touch_and_fills_through` |
| C7 | Pre-registered 3–5 grid / max trials | N/A | Next cycle after this re-run. Catalog stays 12/24. |
| C8 | Coarser bars / RTH-only next cycle | N/A | This cycle keeps 1m + RTH filter on the same 12 families. |
| C9 | Overnight gap = prior RTH close → today RTH open; VX 75th/90th | ✅ | `_overnight_gap` in `strategies.py`; catalog `vx-mes-20` threshold `0.75`; `test_overnight_gap_uses_prior_rth_close_to_today_rth_open`, `test_volatility_expansion_catalog_is_75th_percentile` |
| C10 | Session-end flatten and/or RTH + time-stop | ✅ | catalog `session_filter=rth`, `time_stop_bars=16`, `session_end_flatten=True`; `test_session_end_flatten_and_time_stop_close_at_bar_close` |
| C11 | No fixed 16/8 tick floor (ignore lab note) | ✅ | `require_geometry` only rejects `<1`; 16/8 remains first-cycle pre-registration; `test_geometry_has_no_fixed_tick_floor` |
| D12 | Market regimes, not strategy PnL | ✅ | `regime_robustness(..., market_returns=)`; `test_market_regimes_use_instrument_returns_not_strategy_pnl` |
| D13 | Positive control + null; fail if not detected | ✅ | `positive_control.py`; runner stops with `positive_control_failed`; `test_run_controls_detects_planted_edge_and_rejects_null`. Residual: real NT8 tape not mounted, so control ran on a constructed 22-session RTH tape. |
| D14 | Diagnostics: trades, hitrate vs BE, gross/net, costs, Sharpes, N | ✅ | `diagnostics.py`, report D14 table; `test_diagnostics_include_trades_hitrate_costs_and_sharpes` |
| E15 | Friday 2026-06-12 roll; indicators adjusted, PnL unadjusted | ✅ | `roll_verify.py`, `adjust.py`, `prepare_tape.signal_bars`; `test_friday_roll_and_back_adjust_leaves_pnl_unadjusted` |
| E16 | Holdout on session boundary; reseal; do not open | ✅ | Pin `2026-01-28T23:00:00Z`; legacy `2026-01-29T00:00:00Z` SHA `6e8fa88e…`; `test_holdout_pin_is_session_boundary_and_legacy_seal_recorded`. Residual: `n_train`/`n_holdout` pending recompute without CSVs (`bar_counts_pending_recompute`). |
| F17 | Longer horizon / macro / cross-asset next | N/A | Next cycle. |
| F18 | ES/NQ after fixes | N/A | Next cycle. Same 12 MES/MNQ templates only. |
| >90s gap | Review forced-exit; RTH holes only | ✅ | `prepare._breaks` requires both adjacent bars RTH; `test_overnight_holes_do_not_force_exit_rth_holes_do` |
| Exit PnL | Book at target/stop; trade-through; gap-through uses open | ✅ | `execution._bracket_exit`; `test_exit_bar_pnl_is_booked_at_target_or_gap_open`, `test_stop_exit_is_booked_at_stop_price` |
| DSR/PBO | Floors not loosened | ✅ | `FLOOR_DSR_PROBABILITY_MIN=0.95`, `FLOOR_PBO_HARD_REJECT=0.50`; static bundle still DSR-rejects |
| No SIM/Risk/S0 | Research propose-only | ✅ | No live `flatten`/order path in research execution (`clear_position`); no Risk Core / PromotionGate edits |
| Step 4 | Re-run same 12; do not open holdout | ⚠️ | Real CSVs absent → `phase5_p2_real_rerun_blocked.md`. Fixture pipeline `phase5_p2_fixture_pipeline.md` (12/12 tested, holdout_eval empty). |
| Mutation | ≥300 mutants, kill ≥0.80 | ✅ | 320 mutants, 260 killed, kill_rate **0.8125** (`phase5_p2_mutation.json`) |
| Coverage | Full research unit + fail-under 90 | ✅ | 406 passed / 6 deselected, **96.71%** line+branch on `lumina_research`. Full fast suite 2498 passed / 19 skipped / 269 deselected. |

## Residual risks

1. Real NT8 MES/MNQ CSVs were not in this environment (`LUMINA_RESEARCH_DATA_DIR` unset). Step 4 on the sealed tape is blocked, not failed. The holdout was not opened.
2. Positive control is proven on a constructed 22-session RTH tape, not yet on the real MES tape. Runner will fail-closed on the next real-P2 run if detection fails.
3. Seal bar counts (`n_train`/`n_holdout`) are still the 2026-01-29T00:00Z numbers until CSVs are mounted.
4. 60 of 320 AST mutants survived the kill battery (kill 0.8125). Several are equivalent (e.g. `band_for`/`floors_for` raises after `spec_for`; Friday `and` vs `or` when both sides are true). They are left unjustified rather than papered over.
5. Fixture 12-template tape is a monotonic synthetic path: several families emit no trades; `missing_regimes` can fire when a market-trend bucket is empty. That is fail-closed, not a loosened floor.
