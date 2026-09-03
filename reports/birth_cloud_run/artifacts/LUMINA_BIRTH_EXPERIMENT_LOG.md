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

---

## This ticket — Awakening ENTRY hole autopsy (measure-only)

**Prompt:** Where does stop×NEUTRAL start — regime at OPEN or only at CLOSE?
**Train:** none. optimizer_steps=0. Parent zip 8cc435c6 only.
**Hygiene:** training_reward token removed from birth/; GitPython==3.1.59.
**Leg A** seed 20260902 n_all=217 n_policy=150 wr_policy=0.37333333333333335 mean_r=-0.16280700616093724 ticks=7e86c2bb1c71d514 price=aff3cb1e3a6f5014 hole={'n': 76, 'wr': 0.0, 'mean_r': -1.0520731660642308, 'mean_usd': -118.70721003287197, 'n_entry_neutral': 70, 'n_entry_trend': 6, 'n_entry_unknown': 0, 'frac_entry_neutral': 0.9210526315789473, 'frac_entry_trend': 0.07894736842105263, 'frac_regime_flip': 0.07894736842105263, 'median_bars_held': 13.5, 'p25_bars_held': 5.0, 'p75_bars_held': 30.5, 'median_mae_r': -8.901336301037603, 'median_mfe_r': 7.699734803615165, 'bars_held_missing': False, 'mae_r_missing': False} flags={'n_H': 76, 'frac_neu': 0.9210526315789473, 'frac_tr': 0.07894736842105263, 'frac_ft': 0.18421052631578946, 'missing_entry': 0.0, 'missing_mae': 0.0, 'H_MISSING_ENTRY': False, 'H_ENTRY_NEUTRAL': True, 'H_ENTRY_FLIP': False, 'H_FIRST_TOUCH': False, 'licensed_family': 'OPEN_DECISION', 'missing_fields': [], 'gate1': 'NONE'}.
**Leg B** seed 20260903 n_all=187 n_policy=150 wr_policy=0.34 mean_r=-0.24524752185084342 ticks=7e86c2bb1c71d514 price=e51ce9b724515e2e hole={'n': 82, 'wr': 0.0, 'mean_r': -1.0770073952838481, 'mean_usd': -89.01498215982033, 'n_entry_neutral': 73, 'n_entry_trend': 9, 'n_entry_unknown': 0, 'frac_entry_neutral': 0.8902439024390244, 'frac_entry_trend': 0.10975609756097561, 'frac_regime_flip': 0.10975609756097561, 'median_bars_held': 9.5, 'p25_bars_held': 5.0, 'p75_bars_held': 20.25, 'median_mae_r': -7.597623779527693, 'median_mfe_r': 6.17551471387498, 'bars_held_missing': False, 'mae_r_missing': False} flags={'n_H': 82, 'frac_neu': 0.8902439024390244, 'frac_tr': 0.10975609756097561, 'frac_ft': 0.17073170731707318, 'missing_entry': 0.0, 'missing_mae': 0.0, 'H_MISSING_ENTRY': False, 'H_ENTRY_NEUTRAL': True, 'H_ENTRY_FLIP': False, 'H_FIRST_TOUCH': False, 'licensed_family': 'OPEN_DECISION', 'missing_fields': [], 'gate1': 'NONE'}.
**Flags:** A missing=False neu=True flip=False ft=False; B missing=False neu=True flip=False ft=False. Licensed=`OPEN_DECISION`.
**Overall:** `GRIND_REGRESS_AWAKENING_OPEN ENTRY_HOLE_AUTOPSY ENTRY_MEASURE_ONLY`
**SSOT:** `AWAKENING_ENTRY_AUTOPSY_AUDIT.md` / `AWAKENING_ENTRY_AUTOPSY_VERDICT.md`

---

## This ticket — Awakening OPEN_SPLIT autopsy (measure-only)

**Prompt:** Among policy NEUTRAL opens, which at-OPEN feature separates hole from +R?
**Train:** none. optimizer_steps=0. Parent zip 8cc435c6 only.
**Landed:** PR #22 on main before replay (record merge SHA or green HEAD). Gate 0 SHA `25061876cd5d249d18fd8e12e5890d965f10f8c7`.
**Leg A** seed 20260902 n_U=131 n_H=74 n_W=46 wr_policy=0.34 tag=S_NONE winning_F=none.
**Leg B** seed 20260903 n_U=134 n_H=79 n_W=45 wr_policy=0.36 tag=S_NONE winning_F=none.
**Tag / winning F:** `S_NONE` / `none` licensed=`H_NONE`
**Overall:** `GRIND_REGRESS_AWAKENING_OPEN OPEN_SPLIT_AUTOPSY OPEN_MEASURE_ONLY`
**SSOT:** `AWAKENING_OPEN_SPLIT_AUDIT.md` / `AWAKENING_OPEN_SPLIT_VERDICT.md`

---

## This ticket — Awakening OPEN_POLICY_SIGNAL autopsy (measure-only)

**Prompt:** Among policy NEUTRAL opens, does the frozen π* value/entropy/action-margin separate hole from +R?
**Train:** none. optimizer_steps=0. Parent zip 8cc435c6 only.
**Landed:** PR #23 on main before replay (record merge SHA or green HEAD). Gate 0 SHA `a9c5e32b10ed517c78091806b9f58c8e65a3f621`.
**Leg A** seed 20260902 n_U=0 n_H=0 n_W=0 wr_policy=0.0 tag=S_MISSING winning_P=none.
**Leg B** seed 20260903 n_U=0 n_H=0 n_W=0 wr_policy=0.0 tag=S_MISSING winning_P=none.
**Tag / winning P:** `S_MISSING` / `none` licensed=`OPEN_DECISION`
**Overall:** `GRIND_REGRESS_AWAKENING_OPEN OPEN_POLICY_SIGNAL_AUTOPSY OPEN_MEASURE_ONLY`
**SSOT:** `AWAKENING_OPEN_POLICY_SIGNAL_AUDIT.md` / `AWAKENING_OPEN_POLICY_SIGNAL_VERDICT.md`

---

## This ticket — Awakening OPEN_POLICY_SIGNAL autopsy (measure-only)

**Prompt:** Among policy NEUTRAL opens, does the frozen π* value/entropy/action-margin separate hole from +R?
**Train:** none. optimizer_steps=0. Parent zip 8cc435c6 only.
**Landed:** PR #23 on main before replay (record merge SHA or green HEAD). Gate 0 SHA `a9c5e32b10ed517c78091806b9f58c8e65a3f621`.
**Leg A** seed 20260902 n_U=132 n_H=80 n_W=39 wr_policy=0.29333333333333333 tag=S_NONE winning_P=none.
**Leg B** seed 20260903 n_U=131 n_H=79 n_W=46 wr_policy=0.3333333333333333 tag=S_NONE winning_P=none.
**Tag / winning P:** `S_NONE` / `none` licensed=`H_NONE`
**Overall:** `GRIND_REGRESS_AWAKENING_OPEN OPEN_POLICY_SIGNAL_AUTOPSY OPEN_MEASURE_ONLY`
**SSOT:** `AWAKENING_OPEN_POLICY_SIGNAL_AUDIT.md` / `AWAKENING_OPEN_POLICY_SIGNAL_VERDICT.md`

---

## This ticket — Awakening PATH_EARLY autopsy (measure-only)

**Prompt:** Among policy NEUTRAL opens still open at locked k=3,5, do k-bar path bits separate hole from +R?
**Train:** none. optimizer_steps=0. Parent zip 8cc435c6 only.
**Landed:** PR #24 on main before replay. Gate 0 SHA `9a98853f08909c39205da647aa749a485c66c0a1`.
**Leg A** seed 20260902 n_U=126 n_H=78 n_W=39 U_3=117 U_5=106 wr_policy=0.30666666666666664 tag=S_MULTI winning_P=none.
**Leg B** seed 20260903 n_U=130 n_H=83 n_W=42 wr_policy=0.36 tag=S_MULTI winning_P=none.
**Tag / winning P:** `S_MULTI` / `none` licensed=`H_NONE`
**Overall:** `GRIND_REGRESS_AWAKENING_OPEN PATH_EARLY_AUTOPSY PATH_MEASURE_ONLY`
**SSOT:** `AWAKENING_PATH_EARLY_AUDIT.md` / `AWAKENING_PATH_EARLY_VERDICT.md`

---

## This ticket — Awakening PATH_UNREAL_K3 autopsy (measure-only)

**Prompt:** Among policy NEUTRAL opens still open at locked k=3, does path_k3_unreal_r separate hole from +R?
**Train:** none. optimizer_steps=0. Parent zip 8cc435c6 only. Candidate set size 1: P_K3_UNREAL_RED.
**Landed:** PR #25 on main. Gate 0 SHA `5079d66af8dfd74933989bac459e97d3fbb0daca`.
**Source:** `path_early_jsonl` skip_replay=false replay_ran=false
**Leg A** n_U=126 n_H=78 n_W=39 U_3=117 wr_policy=0.30666666666666664 tag=S_SPLIT winning_P=P_K3_UNREAL_RED.
**Leg B** n_U=130 n_H=83 n_W=42 U_3=126 wr_policy=0.36 tag=S_SPLIT winning_P=P_K3_UNREAL_RED.
**Tag / winning P:** `S_SPLIT` / `P_K3_UNREAL_RED` licensed=`PATH_EXIT:P_K3_UNREAL_RED`
**Overall:** `GRIND_REGRESS_AWAKENING_OPEN PATH_UNREAL_K3_AUTOPSY PATH_MEASURE_ONLY`
**SSOT:** `AWAKENING_PATH_UNREAL_K3_AUDIT.md` / `AWAKENING_PATH_UNREAL_K3_VERDICT.md`

---

## This ticket — Awakening PATH_EXIT K3 shadow (evaluate-only flatten-at-3)

**Prompt:** If we flatten a policy NEUTRAL-open still open at bar 3 when path_k3_unreal_r <= T_LOCK, does the evaluate-only book move the hole (n_H / mean_r) versus the frozen parent path without peeking the rest of the trade and without changing exam dollars?
**Train:** none. optimizer_steps=0. Parent zip 8cc435c6 only. T_LOCK=-0.04787176712367987. k=3. Median not recomputed.
**Landed:** PR #26 on main. Gate 0 SHA `334e367ffeec8fecf01b70f86b1dd84952064ebf`.
**skip_replay**=false replay_ran=true
**Leg A** n_exit=50 n_H base→shadow=78→40 wr_policy=0.26 tag=HOLE_MOVED
**Leg B** n_exit=57 n_H=42 wr_policy=0.22666666666666666 tag=HOLE_INTACT
**Tag / law:** `HOLE_MOVED` / `SHADOW` family=`PATH_EXIT:P_K3_UNREAL_RED`
**Overall:** `GRIND_REGRESS_AWAKENING_OPEN PATH_EXIT_K3_SHADOW SHADOW_MEASURE`
**SSOT:** `AWAKENING_PATH_EXIT_K3_AUDIT.md` / `AWAKENING_PATH_EXIT_K3_VERDICT.md`
