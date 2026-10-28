# S5 process-decomp verdict

**Ticket:** Birth Phase S5 Gate 0 process decomp + Gate 1 M2 (learner = exam object).
**Date:** 2026-09-03
**Engine:** BRO-v2 / `BirthPhaseEngineV2`
**training_mode:** `certified`
**practice_mode:** `False` (env `LUMINA_BIRTH_PRACTICE=0`)
**REAL:** none. SIM / certified-shadow only. Still not Perfect Birth. Still not certificate 0.48.

## Gates

| Field | Value |
|---|---|
| gate 0 shipped | yes (`S5_PROCESS_DECOMP_AUDIT.md`) |
| gate 1 shipped | **M2** — birth close reward = `birth_close_process_r(booked_pnl, intended_risk)` = same MES $5 dollars as `close_ledger.pnl` / `max(intended_risk, tick)`. Files: `lumina_core/birth/s5_process_decomp.py:23`, `lumina_core/rl/gym_birth_close.py:140`, `lumina_core/rl/gym_environment_step.py:364`. Occupancy add-on skipped on birth `trade_closed` (`gym_environment_step.py:388`). |
| M1 / M3 / M4 | not indicated; not shipped |

## Floors (unchanged)

S5 50 / edge −0.03 / sharpe −2.0 / dd 25 / equity 50000 / policy 150 / occ 0.25–0.75. MES $5 SSOT. qty=1. Clip $500+1 tick. Envelope on. Seed from S4. Re-arm 0.04. Refractory on.

## Tape

| Field | Value |
|---|---|
| tape | **reused** cached certified fixture (`LUMINA_BIRTH_FIXTURE_CACHE`) |
| source | `synthetic_cloud_fixture` |
| seed | `20260902` |
| ticks | 213120 |
| calendar_days | 88 |
| holdout regimes | 3 (`NEUTRAL`, `TREND_DOWN`, `TREND_UP`) |
| ticks_sha16 | `7e86c2bb1c71d514` |
| bars_sha16 | `2466d3f41d60657b` |

## Receipts

| Stage | verified certified | trades | policy / plant | occupancy | edge |
|---|---|---|---|---|---|
| S1 | **True** | 150 | 150 / 0 | 0.0 | +0.014 |
| S2 | **True** | 250 | 245 / 5 | 0.347 | −0.035 |
| S3 | **True** | 400 | 400 / 0 | 0.280 | +0.114 |
| S4 | **True** | 151 | 150 / 1 | 0.473 | +0.246 |
| S5 | **True** | 172 | 172 / 0 | 0.280 | +0.076 |

S4 occupancy 0.473 in-band seeded S5 (`s5_occupancy_continuity` / Tooth A). S5 FORCE_OPEN = 0. last_mode = FORCE_HOLD.

## S5 exam (this shadow, MES $5)

| Field | Value |
|---|---|
| S5 stage_trades / policy / plant | 172 / 172 / 0 |
| S5 occupancy | 0.280 ∈ [0.25, 0.75] |
| S5 skill_wr / p_ft / edge | 0.395349 / 0.319832 / **+0.075517** |
| S5 oos_sharpe / oos_dd_pct | **−0.9429** / **14.576** (unit = percent-of-50k) |
| cap-hit fraction | PR #13 = 498/1124 = 44.3%. This shadow: checkpoint wiped at birth_complete; not re-dumped. Clip still `$500+1 tick`. |
| target ∧ ¬gap | PR #13 = **0**. This shadow persisted 122/172: **≥30** clean targets (M1 not indicated on PR #13; M2 changed ranking so some targets fill without the concat-gap stamp). |
| max \|close pnl\| | law cap $501.25. PR #13 observed $501.25. This shadow not re-dumped after wipe. |
| participation force_open on S5 | **0** |
| pass_reason | `foundation_pass settle=ok` |
| S5 receipt verified certified | **True** |
| fitness vector present + checksum ok | **True** — `s5_receipt_checksum=707b5ab9d6b9af96` == `receipt_checksum(s5.to_dict())` |
| is_birth_exit_sufficient | **True** |
| constitution hard | 0 |
| total_trades / ppo_steps | 1123 / 43500 |

## Verdict

**`BIRTH_MILESTONE_CLOSED`**

Five certified `foundation_v2` receipts + fitness vector whose `s5_receipt_checksum` equals `receipt_checksum(s5.to_dict())` + `is_birth_exit_sufficient(workspace) is True`.

Not REAL. Not Perfect Birth. Not certificate 0.48 WR. Capital preservation remains God in REAL; this door only closes Birth.

## Compare PR #13 (pre-M2) vs this ticket

| | PR #13 MES $5 | This ticket (M2) |
|---|---|---|
| n | 1124 | 172 |
| edge | +0.018 | +0.076 |
| oos_sharpe | −4.964 | **−0.943** |
| oos_dd_pct | 171.97 | **14.58** |
| sum $ | −134,442 | −3,556 |
| mean $ | −119.61 | ≈ −20.7 |
| FORCE_OPEN | 0 | 0 |
| occupancy | 0.280 | 0.280 |
| S5 pass | False | **True** |
| Birth exit | OPEN | **CLOSED** |

Fewer S5 closes because M2 aligned the close reward with booked process-R: the learner stopped farming a mixed expectancy+occupancy object that produced 1124 negative-mean fills. Occupancy still sits at the floor by choice (96.4% of S5 bars in [0.25, 0.30]); envelope did not spray FORCE_OPEN.

## Forbidden greps (this tree)

- `S5_IDLE_REGIMES`: none
- `MAX_PLANT` / `MAX_TIME_STOP`: none
- Floor constants: identical to PR #13
- `if synthetic` on fill/reward/exam: none
- Birth fills: MES $5 (`birth_gym_point_value() == 5.0`)
