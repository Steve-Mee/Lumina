# LUMINA Birth experiment log

Certified synthetic tape (all rows unless noted): `source=synthetic_cloud_fixture`, seed `20260902`, hashes `7e86c2bb1c71d514` / `2466d3f41d60657b`, 213,120 ticks, 88 calendar days, 3 holdout regimes (`NEUTRAL`, `TREND_DOWN`, `TREND_UP`). Engine BRO-v2 / `BirthPhaseEngineV2`. `practice_mode=False`. No REAL. `LUMINA_FABRIC_SUPERVISOR=0`.

**Pinned floors (do not move):** S1 min 150; S2 occ [0.30, 0.70] min 250; S3 min 400 / edge −0.05 / occ [0.25, 0.75]; S4 min 100 / edge 0.0 / slack 0.10; S5 min 50 / edge −0.03 / Sharpe −2.0 / DD 25% of $50k; `POLICY_EDGE_MIN_TRADES=150`. Envelope S2–S5. In-band idle S3–S5. Re-arm 0.04. FORCE_OPEN refractory. S5 occupancy seed from S4. `force_qty_one`. Birth fills MES $5. Clip `$500+1 tick`. Plant = FORCE_OPEN only.

**Rollback airframe:** `cursor/s5-instrument-ssot-6657` @ `22793e7`. S1–S4 certified there. S5 had never passed before this ticket.

History is append-only. Do not delete prior rows.

---

## S2 — IMU / occupancy envelope

**Prompt:** S2 occupancy into 30–70% without lowering floors.
**Laws that work:** `occupancy_control_over` + FORCE_OPEN / FORCE_HOLD / FORCE_FLAT; ATR `force_open_stop_from_atr` so plants survive more than one bar.
**Failed path:** IMU-only plant died same-bar (hold/open ≈ 0.025); occupancy drifted to 0.871 and stalled.
**Result:** S2 receipt occupancy 0.604 in band. Birth stayed OPEN.
**SSOT:** `S2_IMU_VERDICT.md`

## S3 — skill split then live exam then in-band idle

**Prompt:** Volume ≠ skill. Then live S3 exam. Then PASSTHROUGH idle so policy can sample without FORCE_OPEN rain.
**Laws that work:** `POLICY_EDGE_MIN_TRADES=150`; skill clock = policy trades; `FOUNDATION_INBAND_IDLE_REGIMES` HOLD-tax in mixed; envelope stays on.
**Failed path:** First S3 live exam was 100% plant (`policy_sample 0 < 150`). Counting plant as skill was forbidden. Envelope-only follow-up was not enough until in-band idle.
**Result:** S3 certified after idle IMU (`S3_INBAND_IDLE_VERDICT.md`). Birth stayed OPEN.

## S4 — live exam HOLD-collapse

**Prompt:** S4 on the same tape after S3 idle.
**Failed path:** Gate B2 occupancy 1.0, `policy_sample 0`, envelope off on S4, HOLD under PASSTHROUGH, 0 closes.
**Law that works:** stage-local idle generalize (not a new `S5_IDLE_REGIMES`). Resume wrote verified S4 `foundation_v2`. Envelope later restored S2–S5 on the shared-IMU ticket.
**Result:** `S4_PASS_BIRTH_OPEN`. Birth stayed OPEN (no S5 / no fitness).
**SSOT:** `S4_LIVE_EXAM_VERDICT.md`

## S5 shared airframe IMU (PR #10)

**Prompt:** Envelope + in-band idle on S5. Do not invent a third idle kruk.
**Result:** Airframe live. S5 honest fail on measured OOS. Birth OPEN. `S5_IDLE_REGIMES` does not exist.
**SSOT:** `S5_LIVE_EXAM_VERDICT.md`

## S5 DD yardstick + FORCE_OPEN chatter bound (PR #11)

**Prompt:** Peak-to-trough DD percent-of-50k; refractory on FORCE_OPEN chatter.
**Result:** Yardstick REAL. S5 still fail: `oos_edge=-0.101`, `oos_dd=628` percent-of-50k. Birth OPEN.
**SSOT:** `S5_YARDSTICK_VERDICT.md` / `S5_DD_YARDSTICK_AUDIT.md`

## S5 notional + re-arm + S4 occupancy seed (PR #12)

**Prompt:** Clip `$500+1 tick`; Tooth A S5 seed from S4 occupancy; Tooth B re-arm 0.76.
**Result:** FORCE_OPEN on S5 → 0. Occupancy 0.280 by choice. Cap-hits 73.4% at NQ $20. `oos_sharpe=-4.52`, `oos_dd=219`. Birth OPEN.
**SSOT:** `S5_NOTIONAL_REARM_VERDICT.md`

## S5 instrument SSOT — MES $5 gym fills (PR #13)

**Prompt:** Birth gym fills settle MES $5. Same tape. Do not quiet ATR. Do not drop holdout.
**Laws that work:** `birth_gym_point_value` / `birth_fill_pnl_usd` / `fill_point_value` MES $5; `force_qty_one`; clip backstop. 0 rows at NQ $20. Cap-hits 498/1124 = 44.3%. Non-cap median |pnl| = $307.
**Measured book n=1124:** plant=0, FORCE_OPEN=0, occ=0.280, edge=+0.018 (clears −0.03), skill_wr 0.339 vs p_ft 0.321. Blockers: `oos_sharpe=-4.964`, `oos_dd=171.97` percent-of-50k. Mean −$119.61. Sum −$134,441.72. Exits stop=636 / time_stop=256 / target=232 / flatten=0. `target ∧ ¬gap` = 0. Gap-at-cap all +$501.25. Time-stop @ cap 9/256. MES-SSOT Gate 1 time-stop rewrite correctly NOT built (non-gap cap 29.9% < 30%).
**Result:** `S5_HONEST_FAIL_BIRTH_OPEN`. Ranking exists; expectancy does not. Instrument lie is dead. Process question remains.
**SSOT:** `S5_INSTRUMENT_SSOT_AUDIT.md` / `S5_INSTRUMENT_SSOT_VERDICT.md`

---

## This ticket — S5 process decomp (Gate 0 + M2)

**Prompt:** Birth Phase S5 process-decomposition agent. Gate 0 measure PR #13 `close_ledger` (reason × gap × regime × reward-vs-exam). At most one Gate 1 law if a trigger fires. One certified shadow on the same tape. Honest S5 / Birth-exit verdict.

**Gate 0:** PR #13 full ledger was not in git (worst-5 only). G0.A–G0.E written from published SSOT + this shadow’s receipt n=172 + mid-stage persist n=122. Join key `lumina_core/birth/sim_runner.py:704`. Holdout `_segment_break` = 0. Reward class on PR #13 live close: **mixed** (`compute_expectancy_reward` + occupancy add-on). FORCE_OPEN=0. Floor-neighborhood fraction 9550/9910 = 96.4% — sitting there by choice.

**Triggers (order, stop at first indicated AND implementable without floors):**
- M1 count trips (`target ∧ ¬gap` = 0/232) but flag is honest concat-gap physics → **not indicated**.
- **M2 indicated** — learner ≠ signed process-R on `clip_birth_exam_pnl` / `intended_risk_usd`.
- M3/M4 not reached.

**Gate 1 shipped:** M2 only. `birth_close_process_r(booked_pnl, intended_risk)` in `lumina_core/birth/s5_process_decomp.py`, wired from `lumina_core/rl/gym_birth_close.py:training_reward_after_book`. Occupancy add-on skipped on birth close (double-count). Open/hold/idle tax unchanged. Non-birth expectancy unchanged. Floors identical to PR #13. No `S5_IDLE_REGIMES`, no `MAX_PLANT`, no `MAX_TIME_STOP`, no `if synthetic` on fill/reward/exam.

**Shadow:** `--force` on cached fixture (same hashes). S1–S4 re-verified certified under MES $5 before S5 scored. S5: 172 / 172 / 0, occ 0.280, edge +0.076, `oos_sharpe=-0.943` > −2.0, `oos_dd_pct=14.576` ≤ 25 percent-of-50k, `pass_reason=foundation_pass settle=ok`. Fitness checksum `707b5ab9d6b9af96` matches `receipt_checksum(s5.to_dict())`. `is_birth_exit_sufficient(workspace) is True`.

**Verdict:** `BIRTH_MILESTONE_CLOSED`. Not REAL. Not Perfect Birth. Not certificate 0.48. Rollback SHA remains `22793e7` (S1–S4 did not regress; MES $5 did not regress).

**Learning:** π* was optimizing a mixed expectancy+occupancy close object while the exam graded MES $5 booked dollars / Sharpe / DD. Aligning the close reward with signed process-R on those same dollars collapsed the 1124-fill negative-mean farm (mean −$120, Sharpe −4.96) to a 172-fill book that still sits at occupancy 0.280 by choice, still qty=1 MES $5, and clears the pinned S5 floors. That is a learner/exam split, not a floor move and not a fill rewrite.
