# AWAKENING SELECT AUDIT

**Date:** 2026-09-03
**Engine:** BRO-v2. One pinned PPO continuation from frozen Birth-exit π*, then evaluate-only A/B.
**Capital:** SIM / certified-shadow. REAL=no. NT=no. `LUMINA_FABRIC_SUPERVISOR=0`.
**Zip init:** `reports/birth_cloud_run/artifacts/birth_exit_pi_star.zip`
sha256 `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03` (202268 bytes). Loadable. Not replaced.
**Birth S5 (untouched):** n=172 wr=0.395 plant=0 FORCE_OPEN=0 occ=0.280 mean≈−$20.7 sharpe=−0.943 dd=14.576% mean_r=−0.089 e_mech=−0.115 fitness `707b5ab9d6b9af96`.

This ticket does **not** reopen Birth. Does **not** move S5 floors. Does **not** flip `is_birth_exit_sufficient`. Does **not** drop NEUTRAL. Does **not** cap FORCE_OPEN. Does **not** stamp Evolution Proof on REGRESS / INCONCLUSIVE / n<500.

Gate 0 locked **before** `learn()`. Tests B/C/E green before `learn()`.

---

## GATE 0 — protocol dump (file:line)

Missing a required line = failed ticket. `inspect_select_protocol()["gate0_complete"]` = True.

### 0.1 Init

| Item | file:line |
|------|-----------|
| Load path resolver (Birth zip only; workspace-sibling = `resolve_pi_star_path`) | `lumina_core/birth/awakening_select.py:137` |
| π* geometry | `lumina_core/birth/birth_exit_policy_export.py:39` |
| sha256 assert == `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03` | `lumina_core/birth/awakening_select.py:147` const `:32` |
| Refuse `lumina_agents/ppo/*.zip` | `lumina_core/birth/birth_exit_policy_export.py:31` `is_gitignored_ppo_zip` |
| PPO.load (43-dim obs) | `lumina_core/birth/awakening_select_run.py` (`PPO.load`) |

If torch/sb3 missing: install CPU wheels, prove import. If still unloadable: `SELECT_INCONCLUSIVE_AWAKENING_OPEN` and STOP. No fake closes.

### 0.2 Isolated workspace

| Item | file:line |
|------|-----------|
| Workspace | `lumina_core/birth/awakening_select.py:72` → `reports/birth_cloud_run/awakening_select/workspace/` |
| Forbidden writes | `lumina_core/birth/awakening_select.py:49` `FORBIDDEN_WRITE_NAMES` |

Forbidden: `s{1..5}_receipt.json`, `lumina_birth_fitness_vector.json`, `birth_exit_pi_star.zip`, `grind_A_close_ledger.jsonl`, `grind_B_close_ledger.jsonl`.

### 0.3 Splits (locked; not swapped after seeing numbers)

| Split | seed | file:line |
|-------|------|-----------|
| TRAIN | 20260901 | `lumina_core/birth/awakening_select.py:27` |
| EVAL A | 20260902 | `:28` — cache hit must reproduce ticks `7e86c2bb1c71d514` / bars `2466d3f41d60657b` |
| EVAL B | 20260903 | `:29` — `price_sha16` ≠ A; ticks calendar fingerprint may collide (document, do not “fix”) |
| Train refuse 20260903 | | `awakening_select.py:96` `assert_train_seed` |
| Explicit holdout_b path refuse | | `awakening_select.py:105` |
| Generator | `synthetic_cloud_fixture` | `lumina_core/birth/synthetic_cloud_fixture.py:35` `SOURCE_LABEL` |

Do not quiet ATR. Three regimes stay. Train never opens 20260902/20260903. If the generator cannot emit 20260901: STOP `SELECT_INCONCLUSIVE` — do not silently train on 20260902.

### 0.4 Physics on train (same functions as Birth gym + grind)

| Piece | file:line |
|-------|-----------|
| `calibrate_birth_stops` | `lumina_core/birth/awakening_select_env.py:244` |
| `ForceOpenChatterBound()` | `awakening_select_env.py:89` |
| `decide_stage2_participation` (envelope ON) | `awakening_select_env.py:136` |
| refractory `chatter.blocks` | passed into `decide_stage2_participation` (`force_open_refractory=`) |
| MES $5 `birth_gym_point_value` | `lumina_core/rl/gym_environment.py:213` |
| qty=1 | `lumina_core/rl/gym_birth_close.py:26` |
| clip $500+1 tick | `gym_birth_close.py:27` |
| `birth_close_process_r` / `trade_r` | `gym_birth_close.py:55` |
| `plan_birth_exit_fill` | `lumina_core/rl/gym_stop_fill.py:38` |
| envelope eval kwargs | `awakening_grind_run.py:126` |
| chatter eval | `sim_runner.py:341` |
| refractory eval | `sim_runner.py:541` |

`G_MISWIRE` = False. Envelope ON. In-band idle S3–S5 ON. No `if synthetic`. No stage-pass stop at policy≥150 / foundation_pass. This is not an S5 exam.

### 0.5 Budget pinned in source BEFORE learn()

| Item | file:line |
|------|-----------|
| `AWAKENING_SELECT_PPO_TIMESTEPS = 10_000` | `lumina_core/birth/awakening_select.py:23` |
| `assert_budget` rejects ≠ pin and 100_000 | `awakening_select.py:113` |
| Why 10_000 | Birth polish quantum `foundation_complete.py:175` `polish_steps = min(10_000, polish_ppo_timesteps)`. Window 1000–50000. Not a CLI flag. Not a while-loop. |
| One `model.learn(` | `lumina_core/birth/awakening_select_run.py:136` |
| `save_weights` | `lumina_core/rl/ppo_trainer_weights.py:52` |
| Timestep cap callback | `awakening_select_run.py` `_timestep_cap_callback` — if trainer runs **more** than the pin: failed ticket. |

### 0.6 Child artifact schema

| Item | file:line |
|------|-----------|
| Sidecar keys | `lumina_core/birth/awakening_select.py:187` `child_sidecar_payload` |
| Zip | `reports/birth_cloud_run/artifacts/awakening_select_pi_star.zip` |
| JSON | `reports/birth_cloud_run/artifacts/awakening_select_pi_star.json` |

Required keys: `schema=awakening_select_pi_star_v1`, `sha256`, `bytes`, `init_path`, `init_sha256=8cc435c6…`, `timesteps`, `train_seed=20260901`, `train_ticks_sha16`, `train_price_sha16`, `exported_at` ISO-8601, `pre_polish_parent=true`, `gitignored_ppo_fallback=false`.

### 0.7 Baseline block — BASELINE_BIRTH_EXIT (verbatim PR #17 / #19)

Do **not** recompute by training. Copied from `AWAKENING_GRIND_AUDIT.md` / `AWAKENING_EDGE_AUDIT.md`.

**Leg A seed 20260902** ticks `7e86c2bb1c71d514` / bars `2466d3f41d60657b`

- n=218 wr_skill=0.34 mean$=−74.73 sharpe=−4.783 dd=33.982% of $50k
- occ=0.757 plant=68 FORCE_OPEN_bars=165 class=`GRIND_REGRESS`

PR #18 split (plant ≡ FORCE_OPEN on closes):

- A policy 150 mean$=−23.87 mean_r=−0.211
- A plant  68  mean$=−186.92 mean_r=−0.493
- `P_PARTICIPATION=False` `E_EDGE=True` `W_WIRE=False`

A policy reason table (PR #19):

| reason | n | wr | mean_r | mean$ |
|--------|---|----|--------|-------|
| stop | 96 | 0.00 | −1.038 | −117.09 |
| target | 35 | 1.00 | +1.212 | +136.62 |
| time_stop | 19 | 0.84 | +1.342 | +151.48 |

Hole cell: stop × NEUTRAL n=83, −1.038 R.
Stop loss-share of policy \|loss $\| = 0.988.
target ∧ gap = 0. `G_MISWIRE=False`. `G_MISLABEL=False`.
`T_TIME=False`. `T_TARGET=False`. `T_NEUTRAL=False` (trends also −EV, n=16<25).
`T_STOP_ONLY=True`.

**Leg B seed 20260903** price_sha16 ≠ A. ticks calendar fingerprint may collide (`7e86c2bb1c71d514` / `2466d3f41d60657b`).

- n=171 wr_skill=0.28 mean$=−44.32 sharpe=−3.865 dd=15.343%
- class=`INCONCLUSIVE` because n<172
- policy wr=0.28 mean_r=−0.329, targets +1.198 R, stops −1.062 R.

Payoff ≈ 1.21 : 1.04. Break-even WR ≈ 1.04/(1.21+1.04) ≈ 0.46.
Have 0.34. Geometry is not the bug. Selection is.

Classifier bounds in `awakening_grind.py` — **not retuned**:

```
BIRTH_N = 172
BIRTH_MEAN_USD = -20.7
REGRESS_MEAN_USD = -62.0
STABLE_SHARPE_GT = -2.0
REGRESS_SHARPE_LE = -3.0
STABLE_DD_MAX_PCT = 25.0
ONE_WAY_DD_PCT = 50.0
ADR0026_MIN_TRADES = 500
TRAIN = False
```

---

## GATE 0 — pre-learn status

- Tests B/C/E: run before `learn()` (see pytest log).
- Isolated workspace created at train time under `reports/birth_cloud_run/awakening_select/workspace/`.
- `learn()` not yet called when this Gate 0 section was written.
- Child zip exists only after Gate 1 (or honest `SELECT_INCONCLUSIVE_AWAKENING_OPEN` with no invented zip).

---

## GATE 1 — one selection law

Law: continue PPO from the frozen init under process-R for exactly `AWAKENING_SELECT_PPO_TIMESTEPS` (10000), then freeze the child zip.

One `model.learn(` at `awakening_select_run.py:136`. No while-WR. No early-stop on B. No second shot.

---

## GATE 2 — evaluate-only (filled after freeze)

Policy path for this rerun only: `awakening_select_pi_star.zip` via explicit `policy_path` (`awakening_grind_run.py:162`).
Default `resolve_frozen_policy_path` still refuses ppo zip and still prefers Birth-exit zip.

`train=False`. `learn()` raises on `EvaluateOnlyPolicy`. `optimizer_steps=0`.
`full_holdout_replay_frozen`, bar 0.

Ledgers (new files, PR #17 grind JSONL not clobbered):

- `reports/birth_cloud_run/artifacts/select_A_close_ledger.jsonl`
- `reports/birth_cloud_run/artifacts/select_B_close_ledger.jsonl`

Overfit: `SELECT_OVERFIT = (wr_policy_A - 0.34 >= 0.05) AND (wr_policy_B - 0.28 < 0.02)`.

Evolution Proof: `evaluate_evolution_proof` with `birth_exit_winrate=0.395349` and `polish_oos_winrate=wr_policy_B` (policy-only, matches PR #17 skill WR). Stamp `passed=True` only if overall=`GRIND_STABLE_AWAKENING_OPEN` AND `SELECT_OVERFIT=False` AND `n_B>=500` AND ADR-0026 inequalities pass on B. Else fail-closed.

Gate 2 numbers: see `AWAKENING_SELECT_VERDICT.md` after the shot.
