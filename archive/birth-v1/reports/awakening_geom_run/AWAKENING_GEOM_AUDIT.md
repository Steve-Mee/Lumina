# AWAKENING_GEOMETRY_REWARD_AUDIT

## Gate 0 live-check + inspect_geom_protocol

```json
{
  "origin_main": "9b312648c591b4f7a6ee97784a29f633d88b7b03",
  "POLICY_EDGE_MIN_TRADES": 150,
  "OBSERVATION_DIM": 43,
  "pct_synthetic": 0.0,
  "inspect_complete": true,
  "scale_live": {
    "tag": "SCALE_BODY",
    "world_engineering_closed": true,
    "n_policy_child": [
      150,
      150
    ],
    "floor": 150
  },
  "seeds": [
    20260923,
    20260924,
    20260925
  ],
  "drift_rth": 8e-06
}
```

```json
{
  "target_frac_min_010": "lumina_core/birth/awakening_geom_touch.py:1",
  "geom_win_r_121": "lumina_core/birth/awakening_geom_reward.py:1",
  "geom_loss_r_104": "lumina_core/birth/awakening_geom_reward.py:1",
  "learn_skipped_unhittable": "lumina_core/birth/awakening_geom_train.py:35",
  "prod_slope_015": "lumina_core/birth/awakening_scale_enrich.py:14",
  "drift_8e_6": "lumina_core/birth/awakening_geom_tape.py:1",
  "force_open_train_only": "lumina_core/birth/awakening_mark_eyes_env.py:111",
  "floor_150": "lumina_core/birth/foundation_metrics.py:39",
  "world_engineering_closed_true": "lumina_core/birth/awakening_geom_flags.py:1",
  "genesis_eyes_ok_false": "lumina_core/birth/awakening_geom_flags.py:88",
  "missing_sites": [],
  "gate0_complete": true
}
```

## T0 identity

```json
{
  "origin_main": "9b312648c591b4f7a6ee97784a29f633d88b7b03",
  "seed_used": 20260923,
  "fixture_train_hash": "6300d15d39d089fa",
  "baseline_sha256": "a9ffa8529e02f2d8f8a535be4dcce205a43abe20bdec492add78126a8181188b",
  "child_sha256": "e49477f7165a96e7cd6bff137646757f18925b4fa22f7c444f94cb5276349e99",
  "init_policy": "scratch",
  "obs_dim": 46,
  "OBSERVATION_DIM": 43,
  "POLICY_EDGE_MIN_TRADES": 150,
  "timesteps": 10000,
  "drift_rth": 8e-06,
  "phase_blocks": 6,
  "nq_min": 12000.0,
  "nq_max": 28000.0,
  "splitter": "per_phase_60_40",
  "slope_abs_used": 0.004,
  "prod_slope_abs": 0.15,
  "target_frac_min": 0.1,
  "geom_win_r": 1.21,
  "geom_loss_r": -1.04,
  "train_force_open": true,
  "eval_force_open": false,
  "floor_waived": false,
  "guard_bypassed": false,
  "world_engineering_closed": true,
  "prod_enricher_default_changed": false
}
```

## T1 honesty / G1 geom fixture

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

## G2 first-touch

```json
{
  "n_policy_A": 150,
  "n_policy_B": 150,
  "n_policy_pooled": 300,
  "n_target": 117,
  "n_stop": 183,
  "n_time": 0,
  "target_frac": 0.39,
  "stop_frac": 0.61,
  "time_frac": 0.0,
  "unhittable": false,
  "baseline_thin": false,
  "TARGET_FRAC_MIN": 0.1,
  "A": {
    "n_policy": 150,
    "n_target": 55,
    "n_stop": 95,
    "n_time": 0,
    "target_frac": 0.36666666666666664,
    "stop_frac": 0.6333333333333333,
    "time_frac": 0.0
  },
  "B": {
    "n_policy": 150,
    "n_target": 62,
    "n_stop": 88,
    "n_time": 0,
    "target_frac": 0.41333333333333333,
    "stop_frac": 0.5866666666666667,
    "time_frac": 0.0
  }
}
```

## T2 G2 a9ffa852 vs G4 scratch V1 child on THIS tape

### Leg A

```json
{
  "leg": "A",
  "n_policy_base": 150,
  "n_policy_child": 150,
  "wr_base": 0.36666666666666664,
  "wr_child": 0.38,
  "mean_r_base": -0.19467500366792254,
  "mean_r_child": -0.1439822714691885,
  "n_H_base": 0,
  "n_H_child": 0,
  "bars_held_p50_base": 82.0,
  "bars_held_p50_child": 75.0,
  "delta_mean_r": 0.05069273219873405,
  "delta_n_H": 0,
  "HOLE_OK": true,
  "MOVED": true,
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
  "wr_base": 0.41333333333333333,
  "wr_child": 0.34,
  "mean_r_base": -0.10616013050481905,
  "mean_r_child": -0.24261560310879635,
  "n_H_base": 0,
  "n_H_child": 0,
  "bars_held_p50_base": 73.0,
  "bars_held_p50_child": 69.5,
  "delta_mean_r": -0.13645547260397728,
  "delta_n_H": 0,
  "HOLE_OK": true,
  "MOVED": false,
  "S_THIN": false,
  "S_HARM": true,
  "S_MISSING": false
}
```

## T3 license vs G2 books

```json
{
  "tag": "GEOM_HARM",
  "law": "NONE",
  "licensed_next_family": "H_NONE",
  "MOVED_A": true,
  "MOVED_B": false,
  "GENESIS_EYES_OK": false,
  "Proof": false,
  "REAL": "no",
  "floor_waived": false,
  "guard_bypassed": false,
  "world_engineering_closed": true,
  "honesty": "LAW: last world knob was SCALE. This window is the Awakening payoff. First-touch gate 0.10. Policy goal 0.46 is not the gate. Train close reward is +1.21 / \u22121.04 / 0.0. Eval still scores ledger mean_r. a9ffa852 is baseline, not clay. Scratch 46-dim V1. Floor 150 stays. GENESIS_EYES_OK stays false. GEOM_OK is not Evolution Proof. REAL=no. Source synthetic_cloud_fixture. License vs frozen a9ffa852 on THIS tape."
}
```

## G5 REAL door

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

LAW: last world knob was SCALE. This window is the Awakening payoff. First-touch gate 0.10. Policy goal 0.46 is not the gate. Train close reward is +1.21 / −1.04 / 0.0. Eval still scores ledger mean_r. a9ffa852 is baseline, not clay. Scratch 46-dim V1. Floor 150 stays. GENESIS_EYES_OK stays false. GEOM_OK is not Evolution Proof. REAL=no. Source synthetic_cloud_fixture. License vs frozen a9ffa852 on THIS tape.

Origin scale artifacts were not overwritten.
GENESIS_EYES_OK is false. oracle_regime is false. REAL=no. Floor 150.
FORCE_OPEN train-only. 1% guard not patched. Production enricher default remains ±0.15.
DRIFT_RTH used is 8.0e-6. PHYSICS_SLOPE_ABS used is 0.004.
world_engineering_closed is true. First-touch gate 0.10. Policy goal 0.46 is not the gate.

## flags

```json
{
  "source": "awakening_geometry_reward",
  "drift_rth": 8e-06,
  "slope_abs_used": 0.004,
  "prod_slope_abs": 0.15,
  "target_frac_min": 0.1,
  "target_frac": 0.39,
  "stop_frac": 0.61,
  "time_frac": 0.0,
  "unhittable": false,
  "geom_win_r": 1.21,
  "geom_loss_r": -1.04,
  "world_ok": true,
  "in_band": true,
  "seed_used": 20260923,
  "train_force_open": true,
  "eval_force_open": false,
  "baseline_sha256": "a9ffa8529e02f2d8f8a535be4dcce205a43abe20bdec492add78126a8181188b",
  "child_sha256": "e49477f7165a96e7cd6bff137646757f18925b4fa22f7c444f94cb5276349e99",
  "init_policy": "scratch",
  "learn_called": true,
  "actual_timesteps": 10000,
  "A": {
    "n_policy_base": 150,
    "n_policy_child": 150,
    "mean_r_base": -0.19467500366792254,
    "mean_r_child": -0.1439822714691885,
    "n_H_base": 0,
    "n_H_child": 0,
    "wr_base": 0.36666666666666664,
    "wr_child": 0.38,
    "n_W_base": 0,
    "n_W_child": 0,
    "bars_held_p50_base": 82.0,
    "bars_held_p50_child": 75.0,
    "delta_mean_r": 0.05069273219873405,
    "delta_n_H": 0,
    "HOLE_OK": true,
    "MOVED": true,
    "S_THIN": false,
    "S_HARM": false,
    "S_MISSING": false
  },
  "B": {
    "n_policy_base": 150,
    "n_policy_child": 150,
    "mean_r_base": -0.10616013050481905,
    "mean_r_child": -0.24261560310879635,
    "n_H_base": 0,
    "n_H_child": 0,
    "wr_base": 0.41333333333333333,
    "wr_child": 0.34,
    "n_W_base": 0,
    "n_W_child": 0,
    "bars_held_p50_base": 73.0,
    "bars_held_p50_child": 69.5,
    "delta_mean_r": -0.13645547260397728,
    "delta_n_H": 0,
    "HOLE_OK": true,
    "MOVED": false,
    "S_THIN": false,
    "S_HARM": true,
    "S_MISSING": false
  },
  "tag": "GEOM_HARM",
  "GENESIS_EYES_OK": false,
  "law": "NONE",
  "licensed_next_family": "H_NONE",
  "world_engineering_closed": true,
  "evolution_proof_stamped": false,
  "REAL": "no",
  "playground": false,
  "hook_default": false,
  "oracle_regime": false,
  "guard_bypassed": false,
  "floor_waived": false,
  "real_data_pct": 0.0,
  "G6_tag": "REAL_DOOR_LOCKED",
  "overall": "AWAKENING_GEOMETRY_REWARD SHADOW_MEASURE",
  "phase_blocks": 6,
  "splitter": "per_phase_60_40",
  "attempts": [
    {
      "seed": 20260923,
      "min": 20346.25,
      "max": 26969.0,
      "in_band": true
    }
  ],
  "price_min": 20346.25,
  "price_max": 26969.0,
  "fixture_train_hash": "6300d15d39d089fa",
  "MOVED_A": true,
  "MOVED_B": false,
  "missing_reason": "",
  "obs_dim": 46,
  "nq_min": 12000.0,
  "nq_max": 28000.0
}
```
