# S5 process decomp audit — Gate 0 + Gate 1

**Date:** 2026-09-03
**Engine:** BRO-v2 / `BirthPhaseEngineV2`
**training_mode:** certified
**practice_mode:** False
**REAL:** no

PR #13 left an honest MES $5 book that ranked (`oos_edge=+0.018`) and still
lost dollars (`mean −$119.61`, Sharpe −4.96, DD 172% of $50k). This ticket
decomposes that book (reason × gap × regime × reward) and ships **one** law.

The PR #13 full `close_ledger` (n=1124) was not copied to git — only worst-5.
This shadow persisted 122 S5 rows mid-stage, then wiped the checkpoint on
`birth_complete`. HUD / `foundation_v2` receipt n=172 is the exam census.
Numbers below say which source they come from. No invented dollars.

---

## G0.A Exits

### PR #13 MES $5 book (exam stall n=1124) — the book that decides Gate 1

Published SSOT: `S5_INSTRUMENT_SSOT_AUDIT.md` / `S5_INSTRUMENT_SSOT_VERDICT.md`.

| reason | n | wins | WR | sum $ | mean $ | median $ | mean trade_r | p50 \|trade_r\| | p95 \|trade_r\| | max \|trade_r\| | cap-hit n |
|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 1124 | 381 | 0.339 | −134441.72 | −119.61 | −307.27 | n/a | n/a | n/a | ~1.68 | 498 |
| stop | 636 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 1.681 (worst persisted) | 266 |
| target | 232 | 232 | 1.000 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 223 |
| time_stop | 256 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 9 |
| flatten | 0 | 0 | — | 0 | — | — | — | — | — | — | 0 |
| force_exit | 0 | 0 | — | 0 | — | — | — | — | — | — | 0 |

Cap-hits 498/1124 = 44.3%. Gap-at-cap 232/234 all +$501.25. Non-gap-at-cap 266 all −$501.25.
Non-cap median \|pnl\| = $307.30. max \|pnl\| = $501.25. qty=1, `point_value=5.0` on all 1124.

### This shadow after M2 (receipt n=172)

Source: `reports/birth_cloud_run/s5_receipt.json` (`foundation_pass settle=ok`).

| reason | n | wins | WR | sum $ | mean $ | median $ | mean trade_r | p50 \|trade_r\| | p95 \|trade_r\| | max \|trade_r\| | cap-hit n |
|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 172 | 68 | 0.395 | −3556.00 | −20.67 | n/a | −0.0887 | 1.014 (median_loss_r) | n/a | n/a | n/a |
| stop | 80 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| target | 47 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| time_stop | 45 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| flatten | 0 | 0 | — | 0 | — | — | — | — | — | — | 0 |
| force_exit | 0 | 0 | — | 0 | — | — | — | — | — | — | 0 |

Mid-stage persisted ledger (n=122 of 172, last checkpoint before pass): stop=52 / target=39 / time_stop=31. qty=1, `point_value=5.0` on all 122.

---

## G0.B Gap vs clean

### PR #13 (n=1124)

| slice | n | WR | mean $ | cap-hit n |
|---|---|---|---|---|
| target ∧ gap | 232 | 1.000 | +501.25 | 232 (gap-at-cap winners) |
| target ∧ ¬gap | **0** | — | — | 0 |
| stop ∧ gap | ≤2 (234−232 gap closes) | n/a | n/a | n/a |
| stop ∧ ¬gap | ~634 | n/a | n/a | 266 non-gap-at-cap are all −$501.25 |
| time_stop ∧ gap | n/a | n/a | n/a | 9 time_stop @ cap |
| time_stop ∧ ¬gap | n/a | n/a | n/a | n/a |

`target ∧ ¬gap` = **0** of 232 targets (0%). One sentence: every published target on the PR #13 book is a gap-at-cap +$501.25 winner; clean-target fills are extinct on that tape/policy, not on the fill function.

### This shadow persisted ledger (n=122)

| slice | n |
|---|---|
| gap=True | 9 |
| gap=False | 113 |
| target (all) | 39 |
| stop | 52 |
| time_stop | 31 |

`target ∧ ¬gap` is **not** ~0 here (39 targets vs 9 gaps total ⇒ at least 30 clean targets). M2 changed the close mix. Holdout fixture `_segment_break` count = **0** (join: split cache holdout 43170 ticks).

---

## G0.C Holdout regimes

**Join key:** `lumina_core/birth/sim_runner.py:704` — `regime = str(enriched[idx].get("regime", "NEUTRAL"))` at close, copied onto `close_ledger` by `lumina_core/birth/s5_close_ledger_trace.py:close_ledger_row` via `lumina_core/birth/stage3_inband_ssot.py:apply_s3_inband_rollout_metrics`. Do not invent regimes.

Holdout bars (certified fixture, seed 20260902, hashes `7e86c2bb1c71d514` / `2466d3f41d60657b`):

| regime | bars-in-regime | bar share |
|---|---|---|
| NEUTRAL | 33694 | 78.0% |
| TREND_UP | 5148 | 11.9% |
| TREND_DOWN | 4328 | 10.0% |

This shadow persisted closes (n=122):

| regime | n | WR | mean $ | sum $ | mean trade_r | bars-in-regime |
|---|---|---|---|---|---|---|
| NEUTRAL | 71 | n/a | n/a | n/a | n/a | 33694 |
| TREND_DOWN | 45 | n/a | n/a | n/a | n/a | 4328 |
| TREND_UP | 6 | n/a | n/a | n/a | n/a | 5148 |

Dollar loss share per regime: **not on disk** (checkpoint wiped at birth_complete; last persist had counts only). Count share of 122: NEUTRAL 58.2% / TREND_DOWN 36.9% / TREND_UP 4.9%. TREND_DOWN is over-represented vs 10% of holdout bars. Largest \|sum $\| regime: **unknown** (missing dollars). No regime reaches a countable 70% of n=122 (max 58% NEUTRAL). M4 not indicated.

Training-regime remainder the join yielded: none (only the three holdout labels).

---

## G0.D Reward vs exam

**PR #13 live S5 close expression** (file:line): `lumina_core/rl/gym_environment_step.py:385` called `compute_expectancy_reward` (`lumina_core/rl/reward_shaper.py:162`) then **added** `apply_gym_birth_occupancy_reward` on the same close bar.

Classification: **mixed** (process-R core × `loss_asymmetry_coeff` × ATR vol denom × direction bonus × WR term × drawdown/sharpe, then occupancy quality on close). Not signed process-R on `clip_birth_exam_pnl` output.

**Gate 1 M2 live expression** (file:line): `lumina_core/rl/gym_birth_close.py:training_reward_after_book` → `lumina_core/birth/s5_process_decomp.py:birth_close_process_r` = `booked_pnl_usd / max(intended_risk_usd, tick)`. Occupancy/idle tax stays on open/hold; skipped on birth close (would double-count R). Non-birth still `compute_expectancy_reward`.

Learner vs exam: **before M2, no** (named split). **after M2, yes** — same booked MES $5 dollars as `close_ledger.pnl`.

20-row sample (PR #13 worst-5 risks for cap-hits + MES 1R constructed non-cap / time_stop; reward = live M2 helper). Checkpoint wipe dropped the 122-row `reward_on_close` series.

| booked_pnl | intended_risk_usd | trade_r | reward_on_close | type |
|---|---|---|---|---|
| 501.25 | 298.12 | 1.6814 | 1.6814 | cap_hit_win |
| −501.25 | 436.85 | −1.1474 | −1.1474 | cap_hit_loss |
| −307.30 | 308.00 | −0.9977 | −0.9977 | noncap_stop |
| 307.30 | 308.00 | 0.9977 | 0.9977 | noncap_target |
| −80.00 | 310.00 | −0.2581 | −0.2581 | time_stop |
| 501.25 | 375.48 | 1.3350 | 1.3350 | cap_hit_win |
| −501.25 | 308.68 | −1.6238 | −1.6238 | cap_hit_loss |
| −298.12 | 298.12 | −1.0000 | −1.0000 | noncap_stop |
| 440.00 | 310.00 | 1.4194 | 1.4194 | noncap_target |
| −120.00 | 400.00 | −0.3000 | −0.3000 | time_stop |
| 501.25 | 298.37 | 1.6800 | 1.6800 | cap_hit_win |
| −501.25 | 298.12 | −1.6814 | −1.6814 | cap_hit_loss |
| −250.00 | 320.00 | −0.7812 | −0.7812 | noncap_stop |
| 380.00 | 305.00 | 1.2459 | 1.2459 | noncap_target |
| 40.00 | 300.00 | 0.1333 | 0.1333 | time_stop |
| −307.00 | 307.00 | −1.0000 | −1.0000 | noncap_stop |
| 501.00 | 440.00 | 1.1386 | 1.1386 | noncap_target |
| −200.00 | 310.00 | −0.6452 | −0.6452 | time_stop |
| 501.25 | 320.00 | 1.5664 | 1.5664 | cap_hit_win |
| −180.00 | 290.00 | −0.6207 | −0.6207 | noncap_stop |

---

## G0.E Occupancy vs floor

| field | value |
|---|---|
| FORCE_OPEN count on S5 | **0** (first_boot HUD; no regression) |
| last_mode | FORCE_HOLD |
| force_hold / force_flat / force_exit | 6576 / 2480 / 31 (last persist) |
| occupancy (exam) | 0.280 in [0.25, 0.75] |
| occupancy seed | `s4_receipt` 0.47336 |
| Fraction of S5 bars with occupancy in [0.25, 0.30] | **9550 / 9910 = 0.964** |
| s3_inband_explore / tax_steps | 0 / 107 |

Policy is **sitting at the floor neighborhood by choice**, not pinned by FORCE_OPEN. Do not lower `S3_OCCUPANCY_MIN`.

---

## M1–M4 (evaluated in order on the PR #13 book + live reward expression)

| trigger | indicated | number that tripped or missed |
|---|---|---|
| M1 clean-target extinction | **no** (count trips, not implementable) | `target ∧ ¬gap` = 0/232 = 0% ≤ 5% so the **count** trips. Holdout `_segment_break` = 0 native. Gaps are concat stamps (`curriculum_intra._stamp_and_concat_windows` / escalation). Flag is honest discontinuity physics. Ticket: if the tape really gaps through targets, M1 is NOT indicated. Do not retag. |
| M2 learner ≠ exam | **yes** | G0.D class = mixed, not signed process-R on `clip_birth_exam_pnl` / `intended_risk_usd`. |
| M3 time-stop bleed | not reached | time_stop 256/1124 = 22.8% ≥ 20% and mean $ unknown-negative on the stall book, but M2 already fired. This shadow time_stop 45/172 = 26.2%; not a 3R tail on PR #13 (worst printed trade_r ≈ −1.15 to −1.68). |
| M4 single-regime wreck | not reached | G0.C cannot prove ≥70% of dollar loss in one regime. 122-row count max is NEUTRAL 58%. |

**Gate 1 shipped:** **M2** — `lumina_core/birth/s5_process_decomp.py:birth_close_process_r` wired from `lumina_core/rl/gym_birth_close.py:training_reward_after_book` (file:line). Occupancy add-on skipped on birth close only.

---

## Floors unchanged (grep proof)

```
lumina_core/birth/foundation_metrics.py
S5_EDGE_MIN = -0.03
S5_SHARPE_FLOOR = -2.0
S5_DD_MAX_PCT = 25.0
S5_DD_EQUITY_USD = 50_000.0
S5_MIN_TRADES = 50
S3_OCCUPANCY_MIN = 0.25
S3_OCCUPANCY_MAX = 0.75
POLICY_EDGE_MIN_TRADES = 150
```

## Ledger point_value

PR #13: 5.0 on all 1124. This shadow persisted ledger: 5.0 on all 122. 0 rows at NQ $20.

## Synthetic dual-path

None on fill / reward / exam. `rg "if synthetic"` hits only first-boot UI top-up, not gym fills. No second valuation path. `birth_gym_point_value() == 5.0`. `S5_IDLE_REGIMES` / `MAX_PLANT` / `MAX_TIME_STOP` do not exist.
