# AWAKENING_OBJECTIVE_TRADE_AUDIT

## Gate 0 live-check + inspect_obj_protocol

```json
{
  "origin_main": "d0ba336daa0f608c593e49d26eb890c733ec5a46",
  "POLICY_EDGE_MIN_TRADES": 150,
  "OBSERVATION_DIM": 43,
  "pct_synthetic": 0.0,
  "PHYSICS_SLOPE_ABS": 0.12,
  "PROD_SLOPE_ABS": 0.15,
  "inspect_complete": true
}
```

```json
{
  "force_open_train_only": "lumina_core/birth/awakening_mark_eyes_env.py:111",
  "eval_refuses_true": "lumina_core/birth/awakening_mark_eyes_env.py:150",
  "slope_012_isolated": "lumina_core/birth/awakening_obj_tape.py:123",
  "prod_default_015": "lumina_core/birth/awakening_conv_enrich.py:13",
  "exam_seed_20260913": "lumina_core/birth/awakening_obj_tape.py:64",
  "floor_150": "lumina_core/birth/foundation_metrics.py:39",
  "both_leg_license": "lumina_core/birth/awakening_obj_flags.py:157",
  "genesis_eyes_ok_false": "lumina_core/birth/awakening_obj_flags.py:166",
  "no_oracle": "lumina_core/birth/awakening_obj_tape.py:167",
  "missing_sites": [],
  "gate0_complete": true
}
```

## T0 identity

```json
{
  "origin_main": "d0ba336daa0f608c593e49d26eb890c733ec5a46",
  "fixture_seed": 20260913,
  "fixture_train_hash": "3930475515f9576a",
  "baseline_sha256": "a9ffa8529e02f2d8f8a535be4dcce205a43abe20bdec492add78126a8181188b",
  "child_sha256": "cf70ae5b212ae5a5f86dbae67356433e550127984c3cd9be2ff936c373c14c96",
  "init_policy": "scratch",
  "obs_dim": 46,
  "OBSERVATION_DIM": 43,
  "POLICY_EDGE_MIN_TRADES": 150,
  "timesteps": 10000,
  "train_seed": 20260913,
  "splitter": "per_phase_60_40",
  "slope_abs_used": 0.12,
  "prod_slope_abs": 0.15,
  "train_force_open": true,
  "eval_force_open": false,
  "floor_waived": false,
  "prod_enricher_default_changed": false
}
```

## T1 honesty / G1 objective fixture

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

## T2 G2 a9ffa852 vs G4 scratch V1 child on THIS tape

### Leg A

```json
{
  "leg": "A",
  "n_policy_base": 0,
  "n_policy_child": 0,
  "wr_base": 0.0,
  "wr_child": 0.0,
  "mean_r_base": 0.0,
  "mean_r_child": 0.0,
  "n_H_base": 0,
  "n_H_child": 0,
  "bars_held_p50_base": 0.0,
  "bars_held_p50_child": 0.0,
  "delta_mean_r": 0.0,
  "delta_n_H": 0,
  "HOLE_OK": true,
  "MOVED": false,
  "S_THIN": true,
  "S_HARM": false,
  "S_MISSING": false
}
```

### Leg B

```json
{
  "leg": "B",
  "n_policy_base": 0,
  "n_policy_child": 0,
  "wr_base": 0.0,
  "wr_child": 0.0,
  "mean_r_base": 0.0,
  "mean_r_child": 0.0,
  "n_H_base": 0,
  "n_H_child": 0,
  "bars_held_p50_base": 0.0,
  "bars_held_p50_child": 0.0,
  "delta_mean_r": 0.0,
  "delta_n_H": 0,
  "HOLE_OK": true,
  "MOVED": false,
  "S_THIN": true,
  "S_HARM": false,
  "S_MISSING": false
}
```

## T3 license vs G2 books

```json
{
  "tag": "OBJ_THIN",
  "law": "NONE",
  "licensed_next_family": "H_NONE",
  "MOVED_A": false,
  "MOVED_B": false,
  "GENESIS_EYES_OK": false,
  "Proof": false,
  "REAL": "no",
  "floor_waived": false,
  "honesty": "LAW: #44 world payable, books thin ~40. This window FORCE_OPEN train-only. Production default unchanged. a9ffa852 is baseline, not clay. Scratch 46-dim V1. Floor 150 stays. GENESIS_EYES_OK stays false. OBJ_OK is not Evolution Proof. REAL=no. Source synthetic_cloud_fixture. License vs frozen a9ffa852 on THIS tape."
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

LAW: #44 world payable, books thin ~40. This window FORCE_OPEN train-only. Production default unchanged. a9ffa852 is baseline, not clay. Scratch 46-dim V1. Floor 150 stays. GENESIS_EYES_OK stays false. OBJ_OK is not Evolution Proof. REAL=no. Source synthetic_cloud_fixture. License vs frozen a9ffa852 on THIS tape.

Origin conv/strat/occupancy/genesis/physics/coupling/v2/polish artifacts were not overwritten.
GENESIS_EYES_OK is false. oracle_regime is false. REAL=no. Floor 150.
FORCE_OPEN train-only. Production enricher default remains ±0.15.

## flags

```json
{
  "source": "awakening_objective_trade",
  "train_force_open": true,
  "eval_force_open": false,
  "slope_abs_used": 0.12,
  "prod_slope_abs": 0.15,
  "world_ok": true,
  "fixture_seed": 20260913,
  "fixture_train_hash": "3930475515f9576a",
  "baseline_sha256": "a9ffa8529e02f2d8f8a535be4dcce205a43abe20bdec492add78126a8181188b",
  "child_sha256": "cf70ae5b212ae5a5f86dbae67356433e550127984c3cd9be2ff936c373c14c96",
  "init_policy": "scratch",
  "learn_called": true,
  "actual_timesteps": 10000,
  "A": {
    "n_policy_base": 0,
    "n_policy_child": 0,
    "mean_r_base": 0.0,
    "mean_r_child": 0.0,
    "n_H_base": 0,
    "n_H_child": 0,
    "wr_base": 0.0,
    "wr_child": 0.0,
    "n_W_base": 0,
    "n_W_child": 0,
    "bars_held_p50_base": 0.0,
    "bars_held_p50_child": 0.0,
    "delta_mean_r": 0.0,
    "delta_n_H": 0,
    "HOLE_OK": true,
    "MOVED": false,
    "S_THIN": true,
    "S_HARM": false,
    "S_MISSING": false
  },
  "B": {
    "n_policy_base": 0,
    "n_policy_child": 0,
    "mean_r_base": 0.0,
    "mean_r_child": 0.0,
    "n_H_base": 0,
    "n_H_child": 0,
    "wr_base": 0.0,
    "wr_child": 0.0,
    "n_W_base": 0,
    "n_W_child": 0,
    "bars_held_p50_base": 0.0,
    "bars_held_p50_child": 0.0,
    "delta_mean_r": 0.0,
    "delta_n_H": 0,
    "HOLE_OK": true,
    "MOVED": false,
    "S_THIN": true,
    "S_HARM": false,
    "S_MISSING": false
  },
  "tag": "OBJ_THIN",
  "GENESIS_EYES_OK": false,
  "law": "NONE",
  "licensed_next_family": "H_NONE",
  "evolution_proof_stamped": false,
  "REAL": "no",
  "playground": false,
  "hook_default": false,
  "oracle_regime": false,
  "floor_waived": false,
  "real_data_pct": 0.0,
  "G6_tag": "REAL_DOOR_LOCKED",
  "overall": "AWAKENING_OBJECTIVE_TRADE SHADOW_MEASURE",
  "phase_blocks": 6,
  "splitter": "per_phase_60_40",
  "gen_up": 71040,
  "gen_down": 71040,
  "gen_range": 71040,
  "train_up_frac": 0.2907986111111111,
  "train_down_frac": 0.29011042292292294,
  "hold_up_frac": 0.28937922297297297,
  "hold_down_frac": 0.2852031719219219,
  "MOVED_A": false,
  "MOVED_B": false,
  "missing_reason": "",
  "obs_dim": 46
}
```
