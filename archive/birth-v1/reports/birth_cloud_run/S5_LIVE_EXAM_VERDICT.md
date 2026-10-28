# S5 live exam verdict — shared airframe IMU

**Date:** 2026-09-02
**Engine:** BRO-v2 / `BirthPhaseEngineV2`
**training_mode:** certified
**practice_mode:** False
**REAL:** no
**LUMINA_FABRIC_SUPERVISOR:** 0
**Verdict:** `S5_HONEST_FAIL_BIRTH_OPEN`

This is not REAL-ready. This is not Perfect Birth. This is not the certificate 0.48 WR wall.
S5 failed on measured numbers. Birth stays OPEN. No fitness vector was written.

---

## Law that landed (this ticket)

| Item | Status |
|---|---|
| Shared occupancy envelope S2–S5 | yes — `foundation_occupancy_envelope_enabled` at `lumina_core/birth/foundation_occupancy_envelope.py:40`, wired at `lumina_core/birth/stage_loop_rollout_pre_caps.py:179` |
| S3/S4/S5 controller | lo=0.28 hi=0.72 hyst=0.0, `cumulative_in_band_passthrough=True` |
| S2 dual IMU | unchanged (`occupancy_control_over = max`) |
| S4 over-flat idle skip removed | yes — `test_a_s4_over_flat_passthrough_disarmed` / `test_b_idle_s4_over_flat_disarmed` |
| `S5_IDLE_REGIMES` | does not exist |
| Floors | unchanged (see table) |

---

## Floors (unchanged)

| Floor | Value |
|---|---|
| S5_MIN_TRADES | 50 |
| S5_EDGE_MIN | -0.03 |
| S5_SHARPE_FLOOR | -2.0 |
| S5_DD_MAX_PCT | 25.0 |
| S5_DD_EQUITY_USD | 50_000 |
| POLICY_EDGE_MIN_TRADES | 150 |
| S5 occupancy exam | [0.25, 0.75] |
| S4_EDGE_MIN / S4_MIN_TRADES | 0.0 / 100 (unchanged SSOT) |
| S3_EDGE_MIN / S3_MIN_TRADES | -0.05 / 400 (unchanged SSOT) |
| S2 occupancy exam | [0.30, 0.70] |

---

## Tape

| Field | Value |
|---|---|
| source | synthetic_cloud_fixture |
| seed | 20260902 |
| replay_hash | 7e86c2bb1c71d514 |
| ticks_hash | 2466d3f41d60657b |
| ticks | 213120 |
| calendar_days | 88 |
| holdout_regimes | 3 (`regime_3`, `regime_4`, `regime_5`) |
| reuse | regenerated (same `CloudFixtureSpec`; hashes match PR #9 / S4 exam) |
| workspace | no prior checkpoint — `--force` required |

---

## S1–S4 receipts (re-verified certified under the NEW shared law)

| Stage | verified certified | trades | policy / plant | occupancy | edge | pass_reason |
|---|---|---|---|---|---|---|
| S1 | True | 150 | 150 / 0 | 0.0 (not graded) | -0.066 | `foundation_pass settle=ok` |
| S2 | True | 250 | 60 / 190 | 0.643 in [0.30, 0.70] | n/a | `foundation_pass settle=ok` |
| S3 | True | 400 | 150 / 250 | 0.720 in [0.25, 0.75] | +0.2286 | `foundation_pass settle=ok` |
| S4 | True | 151 | 150 / 1 | **0.480** in [0.25, 0.75] | +0.2192 | `foundation_pass settle=ok` |

S4 under the shared law is **not** the PR #9 B2 collapse (trades=0, occ=1.0, 5000 PASSTHROUGH / 0 FORCE_OPEN). Envelope fired FORCE_OPEN=1 at over-flat, then in-band idle produced the policy sample. Plant=1 on the volume clock. Policy=150.

S2 dual IMU intact: occupancy 0.643 in S2 exam band.

---

## S5 measured (checkpoint `stage_metrics` + last live `birth.stage.not_passed`)

| Field | Value |
|---|---|
| S5 stage_trades | 533 |
| S5 policy | 149 |
| S5 plant | 384 |
| S5 occupancy | 0.7163 (in exam band 0.25–0.75) |
| S5 skill_wr | 0.1812 (27 / 149 policy) |
| S5 first_touch_p_ft | 0.3212 |
| S5 edge | `policy_sample 149 < 150` (edge not scored; plant not counted as skill) |
| S5 oos_sharpe | last live printed `-2.30` at t=106; later dropped from blockers (passed `-2.0` floor). Stall HUD `None` is a stall-eval artifact (empty snapshot), not the live exam. |
| S5 oos_dd_pct | last live `5757.72` (t=532). Earlier live: 1057.8 (t=106), 3793.4 (t=412). |
| participation_force_open (S5) | 6085 |
| participation_force_hold (S5) | 1763 |
| participation_force_flat (S5) | 298 |
| participation last_mode | PASSTHROUGH (at stall) |
| s3_inband_explore (S5) | 0 |
| s3_inband_hold_tax_steps (S5) | 533 |
| s3_inband_idle_armed (S5) | True at stall (in-band, policy 149 < 150) |
| closes | stop=379 target=136 time_stop=18 flatten=0 |
| median_loss_r (live) | ~1.059 (pass; stall HUD `None` is artifact) |
| foundation_unique_calendar_days | 88 (replay would pass; stall HUD `days=0` is artifact) |
| pass_reason (last live) | `foundation_fail:policy_sample 149 < 150;oos_dd=5757.715534191989 > 25.0 settle=ok` |
| S5 receipt verified certified | False (no pass receipt written) |
| fitness vector present + checksum ok | False (not written — S5 did not pass) |
| is_birth_exit_sufficient | False |
| engine exit | `status=stage_stalled` `birth.cloud.exit=2` `total_trades=1484` |

Ticket anti-fail: this is **not** `policy_sample 0` + occupancy=1.0 + FORCE_OPEN=0. Envelope pulled occupancy in-band (0.716) and produced 149 policy + 384 plant. The remaining blockers are the pinned S5 floors.

---

## Exam table (required fields)

| Field | Value |
|---|---|
| engine | BRO-v2 / BirthPhaseEngineV2 |
| training_mode | certified |
| floors | S5 50 / edge -0.03 / sharpe -2.0 / dd 25 / policy 150 / occ 0.25–0.75 unchanged |
| envelope on S4/S5 | yes + `lumina_core/birth/foundation_occupancy_envelope.py:40` / `stage_loop_rollout_pre_caps.py:179` |
| S4 over-flat idle skip removed | yes + `test_a_s4_over_flat_passthrough_disarmed` / `test_b_idle_s4_over_flat_disarmed` |
| tape | regenerated, hashes `7e86c2bb1c71d514` / `2466d3f41d60657b` (match) |
| S1–S4 receipts verified certified | True / True / True / True |
| S5 stage_trades / policy / plant | 533 / 149 / 384 |
| S5 occupancy | 0.7163 |
| S5 skill_wr / p_ft / edge | 0.1812 / 0.3212 / `policy_sample 149 < 150` |
| S5 oos_sharpe / oos_dd_pct | last live sharpe `-2.30` then passed floor; oos_dd `5757.72` |
| participation_passthrough / force_open on S5 | last_mode PASSTHROUGH / force_open 6085 |
| s3_inband_explore / tax_steps on S5 | 0 / 533 |
| pass_reason | `foundation_fail:policy_sample 149 < 150;oos_dd=5757.715534191989 > 25.0 settle=ok` |
| S5 receipt verified certified | False |
| fitness vector present + checksum ok | False |
| is_birth_exit_sufficient | False |
| verdict | `S5_HONEST_FAIL_BIRTH_OPEN` |

---

## Honest blockers (do not paper over)

1. `policy_sample 149 < 150` — one policy close short of the skill floor. Plant 384 is volume, not skill.
2. `oos_dd=5757.72 > 25` — holdout / S5 window drawdown vs `$50k` equity far above `S5_DD_MAX_PCT`. The OOS fields are wired (they appeared in live `not_passed`). They fail the pinned floor.

No second invention. No floor change. No stub vector. No `S5_IDLE_REGIMES`.

---

## Tests

`pytest tests/birth/ tests/test_m5_residual_loc.py -q --timeout=60` → 1320 passed, 3 skipped.
ruff + mypy --strict + pyright clean on touched modules.
`LUMINA_FABRIC_SUPERVISOR=0`.
