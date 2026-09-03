# AWAKENING MECHANISM AUDIT

**Date:** 2026-09-03
**Engine:** BRO-v2 evaluate-only grind books from PR #17. No training. No new π*.
**Capital:** SIM / certified-shadow. REAL=no. NT=no. `LUMINA_FABRIC_SUPERVISOR=0`.
**Zip:** `reports/birth_cloud_run/artifacts/birth_exit_pi_star.zip`
sha256 `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03` (202268 bytes). Loadable. Not replaced.
**Birth S5 (untouched):** n=172 wr=0.395 plant=0 FORCE_OPEN=0 occ=0.280 mean≈−$20.7 sharpe=−0.943 dd=14.576% mean_r=−0.089 e_mech=−0.115 fitness `707b5ab9d6b9af96`.

This ticket does **not** reopen Birth. Does **not** move S5 floors. Does **not** flip `is_birth_exit_sufficient`. Does **not** stamp `evolution_proof_passed=True`.

---

## GATE 0 — live-path dump (file:line)

| Question | Answer |
|----------|--------|
| Does grind `run_evaluate_only` enable `foundation_occupancy_envelope`? | **Yes.** `s5_envelope_kwargs` `lumina_core/birth/awakening_grind_run.py:126` sets `participation_envelope_enabled` from `foundation_occupancy_envelope_enabled(STAGE5, cfg)` (default True). `range_patience_active=True` (`:127`). Live kwargs: band `[0.28, 0.72]`, hyst `0.0`, min_signals `50`, min_dwell `8`, window_bars `500`, `curriculum_regime=stage5_probe_handoff`, `exploration_steps=0`. |
| ForceOpenChatterBound / refractory / min-dwell / skill_clock? | **Chatter bound live** in `sim_runner.py:341` (`chatter = ForceOpenChatterBound()`). **Refractory passed** `sim_runner.py:541` (`force_open_refractory=chatter.blocks(int(participation_min_dwell_bars))`). **min-dwell in grind kwargs** `awakening_grind_run.py:129`. **`skill_clock_keeps_stage_open` is not a grind kwarg** (`foundation_skill_clock.py:10`). That clock is S5 exam stopping-time (keep stage open until skill sample). Grind already removes the exam clock (`full_holdout_replay_frozen` bar 0, `max_steps=len(holdout)`). Not a dead participation law. |
| How is `plant` tagged vs `FORCE_OPEN` vs policy on a close row? | Live entry: `sim_runner.py:626` `plant_tag_for_entry(force_open_this_step=...)` → `stage3_inband_idle.py:224` returns `bool(force_open_this_step)`. Trajectory `plant_entry` / `skill_grade`. Close row: `s5_close_ledger_trace.py:13` `plant` from `plant_entry`. **PR #17 JSONL had no `force_open` column.** Schema (not a second law): writer now persists `force_open`, falling back to `plant_entry` (Birth identity). Splitter on disk rows uses the same fallback. Overlap on PR #17 books = 100% of plant. **Bar-level** `participation_force_open` (grind A **165**, B **56**) is IMU mode counts, not close n. |
| Occupancy seed vs Birth S5 | Grind `occupancy_seed_kwargs` `awakening_grind_run.py:107`. S4 receipt occupancy **0.47336** in exam band → `stage_range_flat_bars=95`, `stage_range_total_signals=200` (`S5_SEED_SIGNALS`), `occupancy_in_band_seen=True`. Same formula as `apply_s5_occupancy_seed`. S5 exam glued occ **0.280** with FORCE_OPEN=0 because the exam stopped. Grind reseeds then keeps the longer clock. |
| Rolling occupancy window | S5 exam passes `occupancy_control_window=_occ_win` (`stage_loop_rollout_cycle.py:141`). Grind kwargs pass `occupancy_control_window_bars` but **not** the mutable window list → sim_runner rolling IMU is `None` (cumulative-only). Envelope is still **on**. Not `W_WIRE` (law not dead). Not wired this PR: `E_EDGE` owns Gate 1 → measurement-only. |
| JSONL columns grind_A / grind_B | Present: `plant`, `close_reason`, `gap`, `regime`, `trade_r`, `pnl`, `cap_hit` (+ `qty`, `point_value`, `intended_risk_usd`, `reward_on_close`, `source`, `stage`, `cap_usd`, `entry_price`, `risk_usd`). **Missing on disk:** `force_open`, occupancy series, `bar_index`. `force_open` added to `close_ledger_row` for the next live write. Occupancy time-series **not invented**. |

Hashes: grind_A **218** rows, grind_B **171** rows. Match PR #17 audit. Same zip. Ledgers re-read, not invented. Gate 2 skipped (no law).

---

## GATE 0 — dollar / R split

Close-row FORCE_OPEN uses plant fallback (Birth identity). Do not confuse with bar-level FORCE_OPEN 165 / 56.

### Grind A — seed 20260902 (n=218, class `GRIND_REGRESS`)

| bucket | n | wr | sum $ | mean $ | mean_r | cap_hit | stop | target | time_stop |
|--------|---|----|-------|--------|--------|---------|------|--------|-----------|
| policy (not plant, not FORCE_OPEN) | 150 | 0.340 | −3580.33 | −23.87 | −0.211 | 2 | 96 | 35 | 19 |
| FORCE_OPEN | 68 | 0.221 | −12710.54 | −186.92 | −0.493 | 15 | 53 | 15 | 0 |
| plant | 68 | 0.221 | −12710.54 | −186.92 | −0.493 | 15 | 53 | 15 | 0 |
| plant ∩ FORCE_OPEN | 68 | 0.221 | −12710.54 | −186.92 | −0.493 | 15 | 53 | 15 | 0 |
| all (no double-count) | 218 | 0.303 | −16290.87 | −74.73 | −0.299 | 17 | 149 | 50 | 19 |

PR #17 grind table `wr=0.34` is **skill / policy-only** WR (150 closes). All-row pnl WR = **0.303**.

- `target ∧ ¬gap`: policy 35 / FORCE_OPEN=plant 15 / all 50 (every target has `gap=False`).
- Loss-share by regime: NEUTRAL **0.764**, TREND_DOWN **0.221**, TREND_UP **0.015**.
- Occupancy time-series: **missing** on JSONL. Terminal occ from PR #17 = **0.757** (band `>0.75`). Fractions of bars in `[0.25,0.30]` / `[0.30,0.75]` / `>0.75` = **unknown**. Not invented.
- Bar-level FORCE_OPEN (telemetry, not a close bucket): **165**.

### Grind B — seed 20260903 (n=171, class `INCONCLUSIVE` n<172)

| bucket | n | wr | sum $ | mean $ | mean_r | cap_hit | stop | target | time_stop |
|--------|---|----|-------|--------|--------|---------|------|--------|-----------|
| policy (not plant, not FORCE_OPEN) | 150 | 0.280 | −4036.03 | −26.91 | −0.329 | 0 | 102 | 25 | 23 |
| FORCE_OPEN | 21 | 0.286 | −3542.15 | −168.67 | −0.389 | 6 | 15 | 6 | 0 |
| plant | 21 | 0.286 | −3542.15 | −168.67 | −0.389 | 6 | 15 | 6 | 0 |
| plant ∩ FORCE_OPEN | 21 | 0.286 | −3542.15 | −168.67 | −0.389 | 6 | 15 | 6 | 0 |
| all (no double-count) | 171 | 0.281 | −7578.18 | −44.32 | −0.337 | 6 | 117 | 31 | 23 |

- `target ∧ ¬gap`: policy 25 / plant 6 / all 31.
- Loss-share by regime: NEUTRAL **0.759**, TREND_DOWN **0.224**, TREND_UP **0.017**.
- Occupancy time-series: **missing**. Terminal occ PR #17 = **0.759** (`>0.75`). Not invented.
- Bar-level FORCE_OPEN: **56**.

---

## GATE 0 — trigger flags (from the table, not vibes)

Formulas:

- `P_PARTICIPATION` iff `((n_force + n_plant − n_overlap) / n ≥ 0.40` OR `|sum $ of (FORCE_OPEN ∪ plant)| / |sum $ of all losers| ≥ 0.50`) AND policy mean $ **>** overall mean $ AND `n_policy ≥ 40`.
- `E_EDGE` iff policy n≥80 AND (policy mean_r ≤ −0.15 OR policy mean $ ≤ −40).
- `W_WIRE` iff envelope off OR chatter-bound not constructed OR refractory not passed OR min-dwell dropped OR plant tag missing.
- `BOTH_BAD` iff P and E both True AND policy mean $ ≤ overall mean $ + 10.

### Grind A

| flag | value | arithmetic |
|------|-------|------------|
| union frac | 68/218 = **0.312** | < 0.40 |
| dollar share | \|−12710.54\| / 31604.15 = **0.402** | < 0.50 |
| policy mean vs overall | −23.87 **>** −74.73 | policy less bad |
| n_policy | 150 ≥ 40 | |
| **P_PARTICIPATION** | **False** | volume and dollar both miss |
| policy mean_r | **−0.211** ≤ −0.15, n=150≥80 | |
| **E_EDGE** | **True** | policy itself is −EV |
| **W_WIRE** | **False** | envelope on, chatter live, refractory live, min-dwell passed, plant column present |
| **BOTH_BAD** | **False** | P is False |

### Grind B

| flag | value | arithmetic |
|------|-------|------------|
| union frac | 21/171 = **0.123** | < 0.40 |
| dollar share | 3542.15 / 15652.27 = **0.226** | < 0.50 |
| **P_PARTICIPATION** | **False** | |
| policy mean_r | **−0.329** ≤ −0.15, n=150 | |
| **E_EDGE** | **True** | |
| **W_WIRE** | **False** | |
| **BOTH_BAD** | **False** | |

Hypothesis vs measurement: Birth S5 occupancy 0.28 with FORCE_OPEN=0 was exam stopping time. Frozen π* on the full holdout opens the tap (terminal occ 0.76, bar FORCE_OPEN 165, plant closes 68). Plant dollars are worse (−$187 mean). **Policy-only is still −EV** (A mean_r −0.211, mean −$23.87). That is `E_EDGE`, not a FORCE_OPEN costume.

---

## GATE 1 — one law or none

Rule list, first match, stop:

1. `W_WIRE` → wire existing Birth envelope + chatter-bound + min-dwell + refractory into grind kwargs. **Does not fire.**
2. `P_PARTICIPATION` and not `BOTH_BAD` and not `E_EDGE` → FORCE_OPEN chatter obey existing `ForceOpenChatterBound` after stage-pass. **Does not fire** (`P` false, `E` true).
3. `E_EDGE` or `BOTH_BAD` or neither P nor W → **no law.**

**Gate 1 shipped: none. `MECH_MEASURE_ONLY`.**

No new idle controller. No `S5_IDLE_REGIMES`. Envelope stays on. Floors untouched. No second law.

---

## GATE 2 — evaluate-only rerun

**Skipped.** No law shipped. PR #17 numbers stand:

| Leg | class | n | wr (skill) | mean $ | sharpe | dd% of $50k |
|-----|-------|---|------------|--------|--------|-------------|
| A seed 20260902 | `GRIND_REGRESS` | 218 | 0.34 | −74.73 | −4.783 | 33.982 |
| B seed 20260903 | `INCONCLUSIVE` | 171 | 0.28 | −44.32 | −3.865 | 15.343 |

ticks/bars A: `7e86c2bb1c71d514` / `2466d3f41d60657b`. Same zip bytes. Classifier bounds unchanged.

**Overall:** `GRIND_REGRESS_AWAKENING_OPEN` + `MECH_MEASURE_ONLY`.

---

## ADR-0026 Evolution Proof (computed, fail-closed)

Birth-exit WR = **0.395349**. Longer book n = **218** < 500.

`evaluate_evolution_proof` (skill WR 0.34): `insufficient lift -5.5% (need 5.0% or OOS >= 45.0%)`.
All-row pnl WR 0.303: lift −9.3%.

`passed_inequalities=False`. **`evolution_proof_passed=True` not stamped.** Overall ≠ STABLE. Missing n≥500 = fail-closed.

---

## Birth / REAL

- Floors grep-identical to PR #14: `S5_SHARPE_FLOOR=-2.0`, `S5_DD_MAX_PCT=25`, MES $5, `POLICY_EDGE_MIN_TRADES=150`. No `S5_IDLE_REGIMES`.
- Receipts S1–S5 + fitness checksum `707b5ab9d6b9af96`: **untouched**.
- `is_birth_exit_sufficient`: **True** as PR #14 left it.
- REAL: **no**. Certificate 0.48 / PromotionGate: out of scope.
- Post-polish PPO `6fafc5f0`: unused. Grind still refuses `lumina_agents/ppo/*.zip`.
