# AWAKENING EDGE AUDIT

**Date:** 2026-09-03
**Engine:** BRO-v2 evaluate-only grind books from PR #17 / split identity from PR #18. No training. No new π*.
**Capital:** SIM / certified-shadow. REAL=no. NT=no. `LUMINA_FABRIC_SUPERVISOR=0`.
**Zip:** `reports/birth_cloud_run/artifacts/birth_exit_pi_star.zip`
sha256 `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03` (unchanged). Loadable. Not replaced.
**Birth S5 (untouched):** n=172 wr=0.395 plant=0 FORCE_OPEN=0 occ=0.280 mean≈−$20.7 sharpe=−0.943 dd=14.576% mean_r=−0.089 e_mech=−0.115 geometry_net_rr=1.767 fitness `707b5ab9d6b9af96`.

This ticket does **not** reopen Birth. Does **not** move S5 floors. Does **not** flip `is_birth_exit_sufficient`. Does **not** stamp `evolution_proof_passed=True`. Does **not** drop NEUTRAL. Does **not** cap FORCE_OPEN.

JSONL re-read, not invented: grind_A **218** rows, grind_B **171** rows. Disk still has no `force_open` column (PR #18 writer exists; Gate 2 of #18 skipped). Splitter uses plant fallback (Birth identity: plant ≡ FORCE_OPEN on closes). Occupancy bar series **missing** — not invented. Not required for E_EDGE.

---

## GATE 0 — live geometry dump (file:line)

| Piece | Grind | Birth S5 gym |
|-------|-------|--------------|
| `calibrate_birth_stops` | `awakening_grind_run.py:189` `calibrate_birth_stops(holdout)` default hold=90 | `stage_loop_session_phase_prepare_init.py:98` `calibrate_birth_stops(pool, max_hold_bars=hold)` hold=`oracle_max_hold_bars` default 90 |
| geometry object | `awakening_grind_run.py:139` `trade_geometry: geometry` | `stage_loop_rollout_cycle.py:140` `trade_geometry=self._birth_trade_geometry` |
| `stop_pct` / `target_pct` into gym | `sim_runner.py:255-256` `default_stop_pct/target_pct=geometry.*`; envelope `awakening_grind_run.py:135-136` | same `sim_runner.py:255-256` |
| `net_rr_after_cost` | `birth_trade_geometry.py:90` field; set in `_finalize_geometry` `:356` / `:398` | same function |
| time-stop bars | `sim_runner.py:307` `max_hold_bars = geometry.hold_bars` (floor 20 → 120) | same |
| `force_time` path | envelope `stage2_participation_envelope.py:256` `force_time_stop=True` → `sim_runner.py:593` `env.config.force_time_stop_this_step` → `gym_environment_step.py:204` `force_time_now` → `plan_birth_exit_fill` `:238` | same gym |
| fill function | `gym_stop_fill.py:38` `plan_birth_exit_fill` (stop beats target; gap uses close) | same call site `:238` |
| PnL | `notional_cap.py:24` `birth_fill_pnl_usd` called `gym_environment_step.py:283` | same |
| clip / qty=1 / MES $5 | `gym_birth_close.py:26-27` `clip_birth_exam_pnl(..., qty=1)`; `gym_environment.py:213` `birth_gym_point_value()` → $5 | same |
| `intended_risk_usd` | `foundation_metrics.py:58` `\|stop\| × price × qty × pv` | same |
| `trade_r` | `gym_birth_close.py:55` `booked_net / max(risk_usd, 1e-9)` | same. JSONL `trade_r` ≡ `pnl / intended_risk_usd` (max abs diff on policy A/B = 0). |

**G_MISWIRE = False.** Grind live stop/target/time-stop/fill **is** the Birth gym path. Pool for calibration differs (holdout vs stage/train ticks) but the function and gym fill are the same. That is not a dead wire.

JSONL inferred geometry (not a second calib): policy A mean `intended_risk_usd`=$112.80 at mean entry ≈$23,999.43, qty=1, pv=$5 → stop_pct≈0.000940. Every policy row qty=1, point_value=5.0, cap_usd=500.

---

## GATE 0 — policy-only tables

Policy-only = not plant and not force_open. Plant n = FORCE_OPEN n on these books.

### Grind A — seed 20260902 (all-row n=218, class `GRIND_REGRESS`)

Policy n=150 wr=0.340 sum$=−3580.33 mean$=−23.87 mean_r=−0.211 median_r=−1.038 cap_hit=2.

**By `close_reason` (policy-only)**

| reason | n | wr | sum $ | mean $ | mean_r | median_r | cap_hit |
|--------|---|----|-------|--------|--------|----------|---------|
| stop | 96 | 0.000 | −11240.25 | −117.09 | −1.038 | −1.038 | 0 |
| target | 35 | 1.000 | +4781.83 | +136.62 | **+1.212** | +1.212 | 0 |
| time_stop | 19 | 0.842 | +2878.09 | +151.48 | **+1.342** | +0.806 | 2 |

**By `regime` (policy-only)**

| regime | n | wr | sum $ | mean $ | mean_r | loss_share |
|--------|---|----|-------|--------|--------|------------|
| NEUTRAL | 134 | 0.358 | −2699.08 | −20.14 | −0.178 | **0.866** |
| TREND_DOWN | 9 | 0.000 | −1054.05 | −117.12 | −1.038 | 0.093 |
| TREND_UP | 7 | 0.429 | +172.79 | +24.68 | +0.223 | 0.041 |

**Reason × regime cells with n≥8**

| cell | n | wr | sum $ | mean_r |
|------|---|----|-------|--------|
| stop × NEUTRAL | 83 | 0.000 | −9716.80 | −1.038 |
| stop × TREND_DOWN | 9 | 0.000 | −1054.05 | −1.038 |
| target × NEUTRAL | 33 | 1.000 | +4509.12 | +1.212 |
| time_stop × NEUTRAL | 18 | 0.833 | +2508.60 | +1.234 |

Smaller cells (listed, not triggers): stop×TREND_UP n=4; target×TREND_UP n=2; time_stop×TREND_UP n=1.

- `target ∧ ¬gap` = **35**, mean_r=+1.212. `target ∧ gap` = **0**.
- Realized vs design: mean(trade_r \| target)=**+1.212**; mean(trade_r \| stop)=**−1.038**; Birth S5 `geometry_net_rr`=**1.767**; design stop R=−1. Stops are −R plus cost (honest). Targets print +R (honest). They do not print the 1.767 train-pool net RR; JSONL has no per-row `stop_pct`/`target_pct`. Not a fill lie.
- Time-stop loser $|$ / policy loser $|$ = 134.61 / 11374.86 = **0.012**.
- Stop loser $|$ / policy loser $|$ = **0.988**.
- Trends n=16, mean_r=−0.486.

The cell that prints policy mean_r −0.211 is **stop × NEUTRAL** (83 of 150, −1.038 R) against 35 honest targets at +1.212 R. WR 0.34 is too low for that payoff.

### Grind B — seed 20260903 (all-row n=171, class `INCONCLUSIVE` n<172)

Policy n=150 wr=0.280 sum$=−4036.03 mean$=−26.91 mean_r=−0.329 median_r=−1.052 cap_hit=0.

**By `close_reason` (policy-only)**

| reason | n | wr | sum $ | mean $ | mean_r | median_r | cap_hit |
|--------|---|----|-------|--------|--------|----------|---------|
| stop | 102 | 0.000 | −8954.27 | −87.79 | −1.062 | −1.052 | 0 |
| target | 25 | 1.000 | +2473.75 | +98.95 | **+1.198** | +1.198 | 0 |
| time_stop | 23 | 0.739 | +2444.49 | +106.28 | **+1.261** | +0.869 | 0 |

**By `regime` (policy-only)**

| regime | n | wr | sum $ | mean $ | mean_r | loss_share |
|--------|---|----|-------|--------|--------|------------|
| NEUTRAL | 137 | 0.270 | −3765.92 | −27.49 | −0.337 | **0.924** |
| TREND_DOWN | 6 | 0.167 | −335.54 | −55.92 | −0.677 | 0.048 |
| TREND_UP | 7 | 0.571 | +65.43 | +9.35 | +0.114 | 0.029 |

**Reason × regime cells with n≥8:** stop×NEUTRAL n=94 mean_r=−1.063; target×NEUTRAL n=21 mean_r=+1.198; time_stop×NEUTRAL n=22 mean_r=+1.302.

Smaller: stop×TREND_DOWN 5; stop×TREND_UP 3; target×TREND_DOWN 1; target×TREND_UP 3; time_stop×TREND_UP 1.

- `target ∧ ¬gap` = **25**, mean_r=+1.198. `target ∧ gap` = **0**.
- Realized vs design: mean_r(target)=+1.198; mean_r(stop)=−1.062; design net_rr 1.767 / stop −1.
- Time-stop loser share = 148.35 / 9102.63 = **0.016**.
- Stop loser share = **0.984**.
- Trends n=13, mean_r=−0.251.

Same physics. Same hole.

---

## GATE 0 — trigger flags (policy-only arithmetic)

### Grind A

| flag | value | arithmetic |
|------|-------|------------|
| **G_MISWIRE** | **False** | calibrate + trade_geometry + `plan_birth_exit_fill` + `birth_fill_pnl_usd` + clip qty=1 + MES $5 + force_time path all live (file:line above). |
| **G_MISLABEL** | **False** | 0/35 policy targets have trade_r≤0; mean_r(target)=+1.212. JSONL has no physical hit_stop dump; even with tags, targets are +R. |
| **T_TIME** | **False** | time_stop n=19≥10 but mean_r=+1.342 (not ≤−0.30) and loser share 0.012 (not ≥0.30). Time-stop here books open +R, not a clock that converts +R into −R. |
| **T_TARGET** | **False** | target n=35≥15 and mean_r=+1.212 (not ≤0). Targets print +R. |
| **T_NEUTRAL** | **False** | NEUTRAL loss_share 0.866≥0.70, but mean_r(trends)=−0.486 (not ≥−0.05) and n(trends)=16<25 and mean_r(NEUTRAL)=−0.178 (not ≤−0.25). Trends are also −EV. Tape is not the alibi. |
| **T_STOP_ONLY** | **True** | stop loser share 0.988≥0.70 AND mean_r(target)>0 AND not T_TIME. Normal stop physics + insufficient WR. |

### Grind B

| flag | value | arithmetic |
|------|-------|------------|
| **G_MISWIRE** | **False** | same path |
| **G_MISLABEL** | **False** | 0/25 targets trade_r≤0; mean_r=+1.198 |
| **T_TIME** | **False** | n=23, mean_r=+1.261, loser share 0.016 |
| **T_TARGET** | **False** | n=25, mean_r=+1.198 |
| **T_NEUTRAL** | **False** | NEUTRAL share 0.924 and mean_r(NEUTRAL)=−0.337≤−0.25, but mean_r(trends)=−0.251 (not ≥−0.05) and n(trends)=13<25 |
| **T_STOP_ONLY** | **True** | stop loser share 0.984, mean_r(target)>0, not T_TIME |

Occupancy bar series: **missing**. Terminal occ from PR #17 = 0.757 / 0.759. Not invented.

---

## GATE 1 — one law or none

First match. Stop.

1. `G_MISWIRE` → wire grind to Birth gym fill/geometry/time-stop. **Does not fire.**
2. `G_MISLABEL` → fix `close_reason` tag. **Does not fire.**
3. `T_TARGET` and not G_MISLABEL → law only if clip/gap marking differs on grind vs Birth. Clip/gap **shared** (`clip_gap_shared=True`: same `plan_birth_exit_fill` + `clip_birth_exam_pnl`). **Does not fire.** Targets are +R anyway.
4. Else (`T_TIME` / `T_NEUTRAL` / `T_STOP_ONLY` / none) → **no law.**

`T_STOP_ONLY` is “WR too low for the payoff.” That is Awakening selection/training later, not this PR. `T_NEUTRAL` does not license a regime skip. `T_TIME` does not license `MAX_TIME_STOP`.

**Gate 1 shipped: none. `EDGE_MEASURE_ONLY`.**

No new controller. No `S5_IDLE_REGIMES`. Envelope stays on. Floors untouched. No second law. `sim_runner.py` not grown.

---

## GATE 2 — evaluate-only rerun

**Skipped.** No law shipped. PR #17/#18 numbers stand:

| Leg | class | n | wr (skill/policy) | mean $ | sharpe | dd% of $50k | policy mean_r |
|-----|-------|---|-------------------|--------|--------|-------------|---------------|
| A seed 20260902 | `GRIND_REGRESS` | 218 | 0.34 | −74.73 | −4.783 | 33.982 | **−0.211** |
| B seed 20260903 | `INCONCLUSIVE` | 171 | 0.28 | −44.32 | −3.865 | 15.343 | **−0.329** |

ticks/bars A: `7e86c2bb1c71d514` / `2466d3f41d60657b`. Same zip bytes. Classifier bounds unchanged.

**Overall:** `GRIND_REGRESS_AWAKENING_OPEN` + `EDGE_MEASURE_ONLY`.

---

## ADR-0026 Evolution Proof (computed, fail-closed)

Ticket inequalities: n≥500 AND (OOS WR ≥0.45 OR +5pp vs Birth-exit WR 0.395).

Longer book n=**218** < 500. Policy WR 0.34 < 0.45. Lift 0.34−0.395= **−5.5pp**.

`evaluate_evolution_proof` (skill WR 0.34, n=218): `insufficient lift -5.5% (need 5.0% or OOS >= 45.0%)`. `passed_inequalities=False`.

**`evolution_proof_passed=True` not stamped.** Overall ≠ STABLE. Missing n≥500 = fail-closed.

---

## Birth / REAL

- Floors grep-identical to PR #14: `S5_SHARPE_FLOOR=-2.0`, `S5_DD_MAX_PCT=25`, MES $5, `POLICY_EDGE_MIN_TRADES=150`. No `S5_IDLE_REGIMES`.
- Receipts S1–S5 + fitness checksum `707b5ab9d6b9af96`: **untouched**.
- `is_birth_exit_sufficient`: **True** as PR #14 left it.
- REAL: **no**. Certificate 0.48 / PromotionGate: out of scope.
- Post-polish PPO unused. Grind still refuses `lumina_agents/ppo/*.zip`.
