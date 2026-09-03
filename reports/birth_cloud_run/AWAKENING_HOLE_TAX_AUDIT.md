# AWAKENING HOLE-TAX AUDIT

**Date:** 2026-09-03
**Engine:** BRO-v2. One named train-time reward tax on stop × NEUTRAL, then one pinned PPO shot from Birth-exit π*, then evaluate-only A/B.
**Capital:** SIM / certified-shadow. REAL=no. NT=no. `LUMINA_FABRIC_SUPERVISOR=0`.
**Zip INIT (parent):** `reports/birth_cloud_run/artifacts/birth_exit_pi_star.zip`
sha256 `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03` (202268 bytes, pre-polish). Loadable. Not replaced.
**Zip CONTROL (PR #20 child — do not train from it, do not overwrite):** `reports/birth_cloud_run/artifacts/awakening_select_pi_star.zip`
sha256 `db7daf3b978fe80624608e27111627b5b9c3070e71118c66673df996123dd029` (202271 bytes). Same 10k, NO hole tax.
**Birth S5 (untouched):** n=172 wr=0.395 plant=0 FORCE_OPEN=0 occ=0.280 mean≈−$20.7 sharpe=−0.943 dd=14.576% mean_r=−0.089 e_mech=−0.115 fitness `707b5ab9d6b9af96`. `is_birth_exit_sufficient=True`.

This ticket does **not** reopen Birth. Does **not** move S5 floors. Does **not** flip `is_birth_exit_sufficient`. Does **not** drop NEUTRAL. Does **not** cap FORCE_OPEN. Does **not** fire a second 10k SELECT_SHOT. Does **not** tax exam dollars / eval `trade_r`. Does **not** stamp Evolution Proof on REGRESS / INCONCLUSIVE / n<500 / HOLE_SUBSTITUTION.

**Wire choice (dumped):** `SelectPhysicsEnv.tax_r` default `0.0` keeps the PR #20 path. Hole-tax shot uses `run_hole_tax_train` with `tax_r=1.0` and dedicated child paths so parent zip and PR #20 child zip are not overwritten. Optional `train_reward_fn` is analogous to `learn_fn` / `ppo_load_fn`. Reuses `_timestep_cap_callback` / `PPOTrainer` / `PPO.load` from `awakening_select_run`.

Gate 0 locked **before** `learn()`. Tests A–F green before `learn()`.

---

## GATE 0 — protocol dump (file:line)

Missing a required line = failed ticket. `inspect_hole_tax_protocol()["gate0_complete"]` = True.

### 0.1 Init

| Item | file:line |
|------|-----------|
| Load path resolver (Birth zip only) | `lumina_core/birth/awakening_hole_tax.py:184` |
| sha256 assert == `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03` | `awakening_hole_tax.py:194` const `:23` |
| Refuse `lumina_agents/ppo/*.zip` | `lumina_core/birth/birth_exit_policy_export.py:31` `is_gitignored_ppo_zip` |
| Refuse default-init from `awakening_select_pi_star.zip` (sha `db7daf3b…`) | `awakening_hole_tax.py:172` `assert_not_control_init` const `:35` |
| PPO.load (43-dim obs) | `lumina_core/birth/awakening_hole_tax_run.py` (`PPO.load`) |

If torch/sb3 missing: install CPU wheels `torch==2.11.0+cpu` `stable_baselines3==2.8.0` as PR #20. If still unloadable: `HOLE_TAX_INCONCLUSIVE_AWAKENING_OPEN` and STOP. No fake zip.

### 0.2 Isolated workspace

| Item | file:line |
|------|-----------|
| Workspace | `lumina_core/birth/awakening_hole_tax.py:107` → `reports/birth_cloud_run/awakening_hole_tax/workspace/` |
| Forbidden writes | `awakening_hole_tax.py:59` `FORBIDDEN_WRITE_NAMES` |
| `.gitignore` | next to `awakening_select/workspace/` |

Forbidden: `s{1..5}_receipt.json`, `lumina_birth_fitness_vector.json`, `birth_exit_pi_star.zip`, `awakening_select_pi_star.zip`, `grind_A_close_ledger.jsonl`, `grind_B_close_ledger.jsonl`, `select_A_close_ledger.jsonl`, `select_B_close_ledger.jsonl`.

### 0.3 Splits (locked; identical to PR #20; not swapped after seeing numbers)

| Split | seed | file:line |
|-------|------|-----------|
| TRAIN | 20260901 | `lumina_core/birth/awakening_hole_tax.py:20` |
| EVAL A | 20260902 | `:21` — cache hit must reproduce ticks `7e86c2bb1c71d514` / bars `2466d3f41d60657b` |
| EVAL B | 20260903 | `:22` — `price_sha16` ≠ A; ticks calendar fingerprint may collide (document, do not “fix”) |
| Train refuse 20260902 / 20260903 | | `awakening_hole_tax.py:131` `assert_train_seed` |
| Explicit holdout_b path refuse | | `awakening_hole_tax.py:140` |
| Generator | `synthetic_cloud_fixture` | `lumina_core/birth/synthetic_cloud_fixture.py:35` `SOURCE_LABEL` |

Do not quiet ATR. Three regimes stay. Train never opens 20260902/20260903. Isolation = `price_sha16`. Calendar ticks-sha collision is documented, not “fixed.”

### 0.4 Physics on train (Birth gym + PR #20 `SelectPhysicsEnv`)

| Piece | file:line |
|-------|-----------|
| `calibrate_birth_stops` | `lumina_core/birth/awakening_select_env.py:264` |
| `ForceOpenChatterBound()` | `awakening_select_env.py:94` |
| `decide_stage2_participation` (envelope ON) | `awakening_select_env.py:141` |
| MES $5 `birth_gym_point_value` | `lumina_core/rl/gym_environment.py:213` |
| qty=1 | `lumina_core/rl/gym_birth_close.py:26` |
| clip $500+1 tick | `gym_birth_close.py:27` |
| `birth_close_process_r` / `trade_r` | `gym_birth_close.py:55` |
| `plan_birth_exit_fill` | `lumina_core/rl/gym_stop_fill.py:38` |

`G_MISWIRE` = False. Envelope ON. In-band idle S3–S5 ON. No `if synthetic`. No S5 exam-stop at policy≥150. No `S5_IDLE_REGIMES` / `MAX_PLANT` / `MAX_TIME_STOP`.

### 0.5 THE LAW (pinned before learn)

| Item | file:line |
|------|-----------|
| `AWAKENING_HOLE_TAX_R = 1.0` | `lumina_core/birth/awakening_hole_tax.py:26` |
| `AWAKENING_HOLE_TAX_PPO_TIMESTEPS = 10_000` | `:27` |
| `HOLE_REASON = "stop"` | `:28` |
| `HOLE_REGIME = "NEUTRAL"` | `:29` |
| `def apply_hole_tax` | `:81` |
| Env default `tax_r=0.0` (PR #20 path unchanged) | `awakening_select_env.py:81` |
| Env hook `apply_hole_tax(process_r, reason, regime)` on `trade_closed` | `awakening_select_env.py:230` |

```
def apply_hole_tax(process_r: float, close_reason: str, regime: str) -> float:
    if str(close_reason) == "stop" and str(regime).upper() == "NEUTRAL":
        return float(process_r) - AWAKENING_HOLE_TAX_R
    return float(process_r)
```

Wired ONLY on the TRAIN env close path (`SelectPhysicsEnv.step` when `info["trade_closed"]`). Applies to policy AND plant AND FORCE_OPEN closes. Does **not** change `birth_fill_pnl_usd`. Does **not** change ledger `trade_r` or `pnl` on eval JSONL. Does **not** apply to target / time_stop / flatten. Does **not** apply to TREND_UP / TREND_DOWN stops.

If `close_reason` / `regime` missing on train info: added to the train-close info dict (schema, not a second law).

### 0.6 Budget

| Item | file:line |
|------|-----------|
| `AWAKENING_HOLE_TAX_PPO_TIMESTEPS = 10_000` | `awakening_hole_tax.py:27` |
| `assert_budget` rejects ≠ pin and 100_000 | `:148` |
| One `model.learn(` | `awakening_hole_tax_run.py:109` |
| Reuses select hooks | `awakening_select_run.py:98` `run_select_train` (`learn_fn` / `ppo_load_fn` / `tax_r` / `train_reward_fn`) |
| Timestep cap callback | `awakening_select_run.py` `_timestep_cap_callback` — if trainer runs **more** than 10000: failed ticket. |

Same quantum as PR #20 so the only new variable is the tax.

### 0.7 Child artifact (new, not Birth, not PR #20 child)

| Item | file:line |
|------|-----------|
| Sidecar keys | `awakening_hole_tax.py:224` `child_sidecar_payload` |
| Zip | `reports/birth_cloud_run/artifacts/awakening_hole_tax_pi_star.zip` |
| JSON | `reports/birth_cloud_run/artifacts/awakening_hole_tax_pi_star.json` |

Required keys: `schema=awakening_hole_tax_pi_star_v1`, `sha256`, `bytes`, `init_path`, `init_sha256=8cc435c6…`, `control_sha256=db7daf3b…`, `timesteps=10000`, `hole_tax_r=1.0`, `train_seed=20260901`, `train_ticks_sha16`, `train_price_sha16`, `exported_at` ISO-8601, `gitignored_ppo_fallback=false`, `actual_timesteps`, `optimizer_steps`, `select_noop`.

### 0.8 Baseline blocks — do not recompute by training

#### BASELINE_PARENT (PR #17 / #19, verbatim)

**Leg A seed 20260902** ticks `7e86c2bb1c71d514` / bars `2466d3f41d60657b`

- n=218 wr_policy=0.34 mean_r=−0.211 mean$=−23.87 sharpe=−4.783 dd=33.982% REGRESS
- stop 96 / −1.038 R   target 35 / +1.212 R   time_stop 19 / +1.342 R
- hole stop×NEUTRAL n=83 −1.038 R −$117
- plant 68

**Leg B seed 20260903**

- n=171 wr_policy=0.28 mean_r=−0.329 INCONCLUSIVE
- policy stop×NEUTRAL n=94 mean_r=−1.063 (computed from `grind_B_close_ledger.jsonl`, not invented)
- plant 21

Payoff ≈ 1.21 : 1.04. Break-even WR ≈ 1.04/(1.21+1.04) ≈ 0.46.
Have 0.34 / 0.387. Geometry already pays when the policy is right.
The hole is entry frequency into stop×NEUTRAL (~80 × −1.04 R), not a dead wire.

#### CONTROL_SELECT (PR #20, verbatim — same 10k, NO hole tax)

**Overall:** `GRIND_REGRESS_AWAKENING_OPEN SELECT_SHOT SELECT_OVERFIT=false SELECT_NOOP=false`

| Leg | class | n | wr_all | wr_policy | mean$_all | mean$_policy | mean_r_policy | sharpe | dd% of $50k | occ | plant_n | FO closes | FO bars |
|-----|-------|---|--------|-----------|-----------|--------------|---------------|--------|-------------|-----|---------|-----------|---------|
| A child | GRIND_REGRESS | 225 | 0.30666666666666664 | 0.3333333333333333 | -72.59384314264545 | -31.010356288345573 | -0.27389581954773 | -4.583245071164464 | 32.87462017478503 | 0.7599953671531156 | 75 | 75 | 149 |
| B child | INCONCLUSIVE | 182 | 0.3791208791208791 | 0.38666666666666666 | -34.246779716172504 | -14.950525227562903 | -0.17461574736072388 | -2.5271434898282914 | 12.966977405911381 | 0.7536715311558952 | 32 | 32 | 74 |

- A exits stop/target/time_stop = `{'stop': 151, 'target': 51, 'time_stop': 23}` stop×NEUTRAL `{'n': 79, 'mean_r': -1.0377639065293784, 'mean_usd': -117.06630513776742}`
- B exits stop/target/time_stop = `{'stop': 109, 'target': 51, 'time_stop': 22}` stop×NEUTRAL `{'n': 75, 'mean_r': -1.0675576786404861, 'mean_usd': -88.25842516168144}`
- SELECT_OVERFIT=false. Proof not stamped. n_B=182<500. Lift vs 0.395349 = −0.9pp.

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

- Tests A–F: green before `learn()` (`pytest tests/birth/test_awakening_hole_tax.py tests/birth/test_awakening_hole_tax_coverage.py tests/birth/test_awakening_select.py tests/birth/test_awakening_select_coverage.py tests/birth/test_awakening_edge.py tests/birth/test_awakening_mech.py tests/birth/test_awakening_grind.py tests/birth/test_foundation_loopholes.py` → 85 passed).
- Isolated workspace created at train time under `reports/birth_cloud_run/awakening_hole_tax/workspace/`.
- `learn()` not yet called when this Gate 0 section was written.
- Child zip exists only after Gate 1 (or honest `HOLE_TAX_INCONCLUSIVE_AWAKENING_OPEN` with no invented zip).

### 0.1 PPO.load proof (CPU wheels)

Installed and imported **before** `learn()` (same pins as PR #20):

- `torch==2.11.0+cpu` (PyTorch CPU index)
- `stable_baselines3==2.8.0`
- `gymnasium==1.2.3` (already in env)

`PPO.load(birth_exit_pi_star.zip)` succeeded: obs `Box(-1e6, 1e6, (43,), float32)`, action `Box(4,)`. Loaded `n_steps=512`, parent `num_timesteps=1536`, parent `_n_updates=30`. Not DummyPolicy. Not `lumina_agents/ppo/*.zip`. `assert_not_control_init(awakening_select_pi_star.zip)` raises `HoleTaxProtocolError`.

Parent zip sha still `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03`.
Control zip sha still `db7daf3b978fe80624608e27111627b5b9c3070e71118c66673df996123dd029`.

---

## GATE 1 — one tax law (filled after freeze)

Law: continue PPO from the frozen **parent** under process-R plus `apply_hole_tax` for exactly `AWAKENING_HOLE_TAX_PPO_TIMESTEPS` (10000), then freeze the hole-tax child zip.

One `model.learn(` at `awakening_hole_tax_run.py:109`. No while-WR. No early-stop on B. No second shot. No init from `db7daf3b`.

---

## GATE 2 — evaluate-only (filled after freeze)

Policy path for this rerun only: `awakening_hole_tax_pi_star.zip` via explicit `policy_path`.
Default `resolve_frozen_policy_path` still refuses ppo zip and still prefers Birth-exit zip.

`train=False`. `learn()` raises on `EvaluateOnlyPolicy`. `optimizer_steps=0`.

Ledgers (new files, PR #17 grind JSONL and PR #20 select JSONL not clobbered):

- `reports/birth_cloud_run/artifacts/hole_tax_A_close_ledger.jsonl`
- `reports/birth_cloud_run/artifacts/hole_tax_B_close_ledger.jsonl`

Flags:

- `HOLE_SUBSTITUTION = hole_substitution(A) or hole_substitution(B)` with parent A hole=83 plant=68; parent B hole=94 plant=21.
- `SELECT_OVERFIT = (wr_policy_A - 0.34 >= 0.05) AND (wr_policy_B - 0.28 < 0.02)`.
- `HOLE_MOVED` informational only.

Evolution Proof: `evaluate_evolution_proof` with `birth_exit_winrate=0.395349` and `polish_oos_winrate=wr_policy_B`. Stamp `passed=True` only if overall=`GRIND_STABLE_AWAKENING_OPEN` AND `SELECT_OVERFIT=False` AND `HOLE_SUBSTITUTION=False` AND `n_B>=500` AND ADR-0026 inequalities pass on B. Else fail-closed.

## GATE 1 — freeze

{
  "child_path": "/workspace/reports/birth_cloud_run/artifacts/awakening_hole_tax_pi_star.zip",
  "child_sha256": "ca2ae0e5fa6f0e54215fe6c833e2ebff608b5e99426a6e75ff5f7167d6bb0325",
  "init_sha256": "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03",
  "select_noop": false,
  "actual_timesteps": 10000,
  "optimizer_steps": 220,
  "train_ticks_sha16": "7e86c2bb1c71d514",
  "train_price_sha16": "359271a773ae5448",
  "train_bars_sha16": "2466d3f41d60657b",
  "hole_tax_r": 1.0
}

## GATE 2 — child tables

{
  "A": {
    "n": 211,
    "wr_all": 0.3080568720379147,
    "wr_policy": 0.3333333333333333,
    "mean_usd_all": -69.90236979862026,
    "mean_usd_policy": -28.956135211719193,
    "mean_r_policy": -0.25619038036381137,
    "sharpe": -4.552234905374526,
    "dd_pct_of_50k": 29.498800055017956,
    "occ": 0.7565438962242298,
    "plant_n": 61,
    "force_open_closes": 61,
    "FORCE_OPEN_bars": 111,
    "exits": {
      "stop": 144,
      "target": 45,
      "time_stop": 22
    },
    "stop_x_neutral": {
      "n": 86,
      "mean_r": -1.0377589113836108,
      "mean_usd": -117.0812092098568
    },
    "target_mean_r": 1.2122160679783462,
    "time_stop_mean_r": 1.2229581555149693,
    "classification": "GRIND_REGRESS",
    "ticks_sha16": "7e86c2bb1c71d514",
    "bars_sha16": "2466d3f41d60657b",
    "price_sha16": "aff3cb1e3a6f5014",
    "frozen_sha256": "ca2ae0e5fa6f0e54215fe6c833e2ebff608b5e99426a6e75ff5f7167d6bb0325",
    "optimizer_steps": 0,
    "train": false
  },
  "B": {
    "n": 180,
    "wr_all": 0.3111111111111111,
    "wr_policy": 0.31333333333333335,
    "mean_usd_all": -45.106767083815534,
    "mean_usd_policy": -23.344086897326296,
    "mean_r_policy": -0.28229412926554237,
    "sharpe": -3.5108225814966976,
    "dd_pct_of_50k": 16.658425047406872,
    "occ": 0.7160991429233264,
    "plant_n": 30,
    "force_open_closes": 30,
    "FORCE_OPEN_bars": 62,
    "exits": {
      "stop": 120,
      "target": 33,
      "time_stop": 27
    },
    "stop_x_neutral": {
      "n": 87,
      "mean_r": -1.0515524666548113,
      "mean_usd": -86.89438793959869
    },
    "target_mean_r": 1.1984173505564846,
    "time_stop_mean_r": 1.222113105211665,
    "classification": "GRIND_REGRESS",
    "ticks_sha16": "7e86c2bb1c71d514",
    "bars_sha16": "2466d3f41d60657b",
    "price_sha16": "e51ce9b724515e2e",
    "frozen_sha256": "ca2ae0e5fa6f0e54215fe6c833e2ebff608b5e99426a6e75ff5f7167d6bb0325",
    "optimizer_steps": 0,
    "train": false
  },
  "overall": "GRIND_REGRESS_AWAKENING_OPEN HOLE_TAX_SHOT SELECT_OVERFIT=false HOLE_SUBSTITUTION=false HOLE_MOVED=false",
  "flags": {
    "select_overfit": false,
    "hole_substitution": false,
    "hole_moved": false,
    "sub_a": false,
    "sub_b": false
  },
  "proof": {
    "passed_inequalities": false,
    "reasons": [
      "insufficient lift -8.2% (need 5.0% or OOS >= 45.0%)"
    ],
    "stamped": false,
    "n_b": 180,
    "wr_policy_b": 0.31333333333333335,
    "path": "/workspace/reports/birth_cloud_run/awakening_hole_tax/workspace/state/lumina_evolution_proof.json"
  }
}
