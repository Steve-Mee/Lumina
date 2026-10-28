# AWAKENING_MARK_EYES_V2_AUDIT

## Gate 0 live-check + inspect_v2_protocol

```json
{
  "origin_main": "2c45506b157ecf0d12a0066047f8692e3fccae5b",
  "POLICY_EDGE_MIN_TRADES": 150,
  "OBSERVATION_DIM": 43,
  "pct_synthetic": 0.0,
  "pct_real_historical": 0.0,
  "pct_real": 100.0,
  "inspect_complete": true
}
```

```json
{
  "mark_eyes_v2_obs_dim_48": "lumina_core/birth/awakening_mark_eyes_v2.py:27",
  "extra_length_5": "lumina_core/birth/awakening_mark_eyes_v2.py:28",
  "mfe_is_max_unreal_not_wick": "lumina_core/birth/awakening_mark_eyes_v2_obs.py:56",
  "d_unreal_first_bar_0": "lumina_core/birth/awakening_mark_eyes_v2_obs.py:57",
  "scratch_init_only": "lumina_core/birth/awakening_mark_eyes_v2_train.py:71",
  "forbidden_load_a9ffa852": "lumina_core/birth/awakening_mark_eyes_v2.py:3",
  "forbidden_load_cebe1804": "lumina_core/birth/awakening_mark_eyes_v2.py:57",
  "forbidden_load_8cc435c6": "lumina_core/birth/awakening_mark_eyes_v2.py:57",
  "seed_20260907": "lumina_core/birth/awakening_mark_eyes_v2.py:30",
  "start_et_2026_05_04": "lumina_core/birth/awakening_mark_eyes_v2.py:173",
  "floor_150": "lumina_core/birth/foundation_metrics.py:39",
  "license_both_legs": "lumina_core/birth/awakening_mark_eyes_v2_flags.py:144",
  "genesis_eyes_ok_forced_false": "lumina_core/birth/awakening_mark_eyes_v2_flags.py:161",
  "hooks_default_false": "lumina_core/birth/awakening_path_exit_k3.py:22",
  "hooks_shape_default_false": "lumina_core/birth/awakening_path_shape_k3_dead.py:57",
  "honesty_synthetic_0": "lumina_core/birth/data_source_honesty.py:22",
  "missing_sites": [],
  "gate0_complete": true
}
```

## T0 identity

```json
{
  "origin_main": "2c45506b157ecf0d12a0066047f8692e3fccae5b",
  "fixture_seed": 20260907,
  "fixture_train_hash": "5e7eae98d1b4d228",
  "baseline_sha256": "a9ffa8529e02f2d8f8a535be4dcce205a43abe20bdec492add78126a8181188b",
  "child_sha256": "1123282f0fe3715d66a6945db847f9c39dadfab071cef7279553725f6aa910c1",
  "init_policy": "scratch",
  "obs_dim_v1": 46,
  "obs_dim_v2": 48,
  "OBSERVATION_DIM": 43,
  "POLICY_EDGE_MIN_TRADES": 150,
  "timesteps": 10000,
  "train_seed": 20260907
}
```

## T1 honesty / G1 fixture

```json
{
  "pct_synthetic_cloud_fixture": 0.0,
  "pct_real_historical": 0.0,
  "pct_real": 100.0,
  "synthetic_source_reasons": [
    "synthetic_source:synthetic_cloud_fixture"
  ],
  "min_real_data_pct": 95.0,
  "G6_tag": "REAL_DOOR_LOCKED"
}
```

## T2 G2 a9ffa852 (46) vs G4 V2 child (48) on THIS tape

### Leg A

```json
{
  "leg": "A",
  "n_policy_base": 150,
  "n_policy_child": 150,
  "wr_base": 0.46,
  "wr_child": 0.4666666666666667,
  "mean_r_base": -0.008878971625966141,
  "mean_r_child": -0.005439365171116864,
  "n_H_base": 19,
  "n_H_child": 18,
  "bars_held_p50_base": 95.0,
  "bars_held_p50_child": 90.5,
  "delta_mean_r": 0.0034396064548492767,
  "delta_n_H": 1,
  "HOLE_OK": true,
  "MOVED": false,
  "S_THIN": false,
  "S_HARM": false,
  "S_MISSING": false
}
```

### Leg B

```json
{
  "leg": "B",
  "n_policy_base": 150,
  "n_policy_child": 150,
  "wr_base": 0.4066666666666667,
  "wr_child": 0.4533333333333333,
  "mean_r_base": -0.11208013882230176,
  "mean_r_child": -0.034917207118302124,
  "n_H_base": 37,
  "n_H_child": 42,
  "bars_held_p50_base": 90.0,
  "bars_held_p50_child": 80.5,
  "delta_mean_r": 0.07716293170399964,
  "delta_n_H": -5,
  "HOLE_OK": true,
  "MOVED": true,
  "S_THIN": false,
  "S_HARM": false,
  "S_MISSING": false
}
```

## T3 license vs G2 books

```json
{
  "tag": "V2_FAIL",
  "law": "NONE",
  "licensed_next_family": "H_NONE",
  "MOVED_A": false,
  "MOVED_B": true,
  "GENESIS_EYES_OK": false,
  "Proof": false,
  "REAL": "no",
  "honesty": "New 48-dim eyes, scratch body, NEW synthetic tape. Not a polish of a9ffa852. Floor POLICY_EDGE_MIN_TRADES=150 stays. GENESIS_EYES_OK stays false. V2_OK is not Evolution Proof. REAL=no. Source synthetic_cloud_fixture. License vs frozen a9ffa852 on THIS tape, not vs path_early / budget / polish books."
}
```

## G6 REAL door

```json
{
  "G6_tag": "REAL_DOOR_LOCKED",
  "REAL": "no",
  "rows": [
    {
      "function": "config.yaml mode",
      "result": "PASS",
      "why": "mode='sim' (must stay sim)"
    },
    {
      "function": "BirthCertificateThresholds.min_real_data_pct lumina_core/birth/birth_certificate.py:14",
      "result": "FAIL",
      "why": "real_data_pct=0.0 < min_real_data_pct=95.0"
    },
    {
      "function": "tick source",
      "result": "FAIL-CLOSED",
      "why": "source=synthetic_cloud_fixture (synthetic_cloud_fixture is not a REAL certificate)"
    },
    {
      "function": "ApplicationContainer.start lumina_core/container/container_lifecycle.py:164",
      "result": "PASS",
      "why": "container.start not called (broker connect forbidden)"
    },
    {
      "function": "NinjaTrader / Fabric / gRPC",
      "result": "PASS",
      "why": "NT/Fabric host not contacted"
    },
    {
      "function": "PromotionGate.evaluate lumina_core/evolution/promotion_gate.py:136",
      "result": "FAIL",
      "why": "no proving certificate / no promotion evidence on synthetic first life"
    },
    {
      "function": "evolution_proof_passed lumina_core/birth/evolution_proof_gate.py:137",
      "result": "FAIL",
      "why": "stamped=False (must stay false)"
    },
    {
      "function": "maturation_eligible_for_real lumina_core/maturity/maturation_progress.py:190",
      "result": "FAIL",
      "why": "eligible=False blockers=['Birth Certificate v2 issued', 'Evolution Proof passed', 'SIM stability READY_FOR_REAL (5-day green streak)', 'Promotion gate passed (shadow validation)', 'Perfect Birth Phase complete (twin vs Steve accuracy + never-stop recovery + auto-approval + shadow alignment)']"
    },
    {
      "function": "certificate OOS WR 0.48",
      "result": "FAIL",
      "why": "min_oos_winrate=0.48 not claimed"
    },
    {
      "function": "kill-switch / Dead Man lumina_core/risk/risk_gates.py:169",
      "result": "N/A",
      "why": "not armed against a live broker (no broker connect)"
    },
    {
      "function": "HardRiskController lumina_core/risk/risk_controller.py:36",
      "result": "PRESENT",
      "why": "risk engine independent of strategy (bounded context lumina_core/risk)"
    },
    {
      "function": "first live/SIM broker order",
      "result": "NONE",
      "why": "no container.start, no order path"
    },
    {
      "function": "lumina_core/rl/observation_builder.py:36 OBSERVATION_DIM",
      "result": "PASS",
      "why": "OBSERVATION_DIM=43 (must stay 43)"
    },
    {
      "function": "PATH_EXIT_K3_SHADOW / PATH_SHAPE_K3_SHADOW",
      "result": "PASS",
      "why": "exit=False shape=False default False"
    }
  ],
  "broken": [],
  "real_data_pct": 0.0,
  "source": "synthetic_cloud_fixture",
  "mode": "sim",
  "evolution_proof_stamped": false,
  "promotion_passed": false,
  "nt_called": false,
  "container_start_called": false,
  "observation_dim": 43
}
```

## Honesty

New 48-dim eyes, scratch body, NEW synthetic tape. Not a polish of a9ffa852. Floor POLICY_EDGE_MIN_TRADES=150 stays. GENESIS_EYES_OK stays false. V2_OK is not Evolution Proof. REAL=no. Source synthetic_cloud_fixture. License vs frozen a9ffa852 on THIS tape, not vs path_early / budget / polish books.

Origin genesis/budget/polish artifacts were not overwritten.
GENESIS_EYES_OK is false. polished_a9ffa852 is false. REAL=no. Floor 150. Scratch 10k.

## flags

```json
{
  "source": "awakening_mark_eyes_v2",
  "fixture_seed": 20260907,
  "fixture_train_hash": "5e7eae98d1b4d228",
  "baseline_sha256": "a9ffa8529e02f2d8f8a535be4dcce205a43abe20bdec492add78126a8181188b",
  "child_sha256": "1123282f0fe3715d66a6945db847f9c39dadfab071cef7279553725f6aa910c1",
  "init_policy": "scratch",
  "obs_dim_v1": 46,
  "obs_dim_v2": 48,
  "learn_called": true,
  "actual_timesteps": 10000,
  "A": {
    "n_policy_base": 150,
    "n_policy_child": 150,
    "mean_r_base": -0.008878971625966141,
    "mean_r_child": -0.005439365171116864,
    "n_H_base": 19,
    "n_H_child": 18,
    "wr_base": 0.46,
    "wr_child": 0.4666666666666667,
    "n_W_base": 48,
    "n_W_child": 47,
    "bars_held_p50_base": 95.0,
    "bars_held_p50_child": 90.5,
    "delta_mean_r": 0.0034396064548492767,
    "delta_n_H": 1,
    "HOLE_OK": true,
    "MOVED": false,
    "S_THIN": false,
    "S_HARM": false,
    "S_MISSING": false
  },
  "B": {
    "n_policy_base": 150,
    "n_policy_child": 150,
    "mean_r_base": -0.11208013882230176,
    "mean_r_child": -0.034917207118302124,
    "n_H_base": 37,
    "n_H_child": 42,
    "wr_base": 0.4066666666666667,
    "wr_child": 0.4533333333333333,
    "n_W_base": 47,
    "n_W_child": 40,
    "bars_held_p50_base": 90.0,
    "bars_held_p50_child": 80.5,
    "delta_mean_r": 0.07716293170399964,
    "delta_n_H": -5,
    "HOLE_OK": true,
    "MOVED": true,
    "S_THIN": false,
    "S_HARM": false,
    "S_MISSING": false
  },
  "tag": "V2_FAIL",
  "GENESIS_EYES_OK": false,
  "law": "NONE",
  "licensed_next_family": "H_NONE",
  "evolution_proof_stamped": false,
  "REAL": "no",
  "playground": false,
  "hook_default": false,
  "used_old_path_early": false,
  "polished_a9ffa852": false,
  "real_data_pct": 0.0,
  "G6_tag": "REAL_DOOR_LOCKED",
  "overall": "AWAKENING_MARK_EYES_V2 SHADOW_MEASURE",
  "MOVED_A": false,
  "MOVED_B": true,
  "missing_reason": ""
}
```
