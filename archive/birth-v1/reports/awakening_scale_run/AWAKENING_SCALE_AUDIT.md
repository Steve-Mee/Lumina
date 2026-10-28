# AWAKENING_SLOPE_SCALE_AUDIT

## Gate 0 live-check + inspect_scale_protocol

```json
{
  "origin_main": "57707207212fb782e0174be656c7746fa6a5d3ae",
  "POLICY_EDGE_MIN_TRADES": 150,
  "OBSERVATION_DIM": 43,
  "pct_synthetic": 0.0,
  "PHYSICS_SLOPE_ABS": 0.004,
  "PROD_SLOPE_ABS": 0.15,
  "inspect_complete": true,
  "drift_live": {
    "tag": "DRIFT_ENRICH_FAIL",
    "drift_rth": 8e-06,
    "in_band": true,
    "floor": 150
  },
  "seeds": [
    20260920,
    20260921,
    20260922
  ],
  "drift_rth": 8e-06
}
```

```json
{
  "physics_slope_abs_0004": "lumina_core/birth/awakening_scale_enrich.py:1",
  "identity_comment": "lumina_core/birth/awakening_scale_enrich.py:12",
  "prod_default_015": "lumina_core/birth/awakening_scale_enrich.py:14",
  "drift_rth_8e_6": "lumina_core/birth/awakening_scale_tape.py:57",
  "band_gate_no_clip": "lumina_core/birth/awakening_scale_tape.py:351",
  "max_three_seeds_20260920_22": "lumina_core/birth/awakening_scale_tape.py:60",
  "guard_1pct_unedited": "lumina_core/birth/birth_constitution_guard.py:39",
  "force_open_train_only": "lumina_core/birth/awakening_mark_eyes_env.py:111",
  "eval_refuses_true": "lumina_core/birth/awakening_mark_eyes_env.py:150",
  "floor_150": "lumina_core/birth/foundation_metrics.py:39",
  "genesis_eyes_ok_false": "lumina_core/birth/awakening_scale_flags.py:86",
  "world_engineering_stops": "lumina_core/birth/awakening_scale_flags.py:195",
  "missing_sites": [],
  "gate0_complete": true
}
```

## T0 identity

```json
{
  "origin_main": "57707207212fb782e0174be656c7746fa6a5d3ae",
  "seed_used": 20260920,
  "fixture_train_hash": "c9188a030e38e4bc",
  "baseline_sha256": "a9ffa8529e02f2d8f8a535be4dcce205a43abe20bdec492add78126a8181188b",
  "child_sha256": "b83d2b67ef9d79377ac33094b86d86eccdecd74d67c9a7f9338a1dc67c7b1c65",
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
  "train_force_open": true,
  "eval_force_open": false,
  "floor_waived": false,
  "guard_bypassed": false,
  "world_engineering_closed": true,
  "prod_enricher_default_changed": false
}
```

## T1 honesty / G1 scale fixture

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

## T2 G3 a9ffa852 vs G5 scratch V1 child on THIS tape

### Leg A

```json
{
  "leg": "A",
  "n_policy_base": 150,
  "n_policy_child": 150,
  "wr_base": 0.3933333333333333,
  "wr_child": 0.41333333333333333,
  "mean_r_base": -0.13990621213874965,
  "mean_r_child": -0.11045874813390434,
  "n_H_base": 0,
  "n_H_child": 0,
  "bars_held_p50_base": 92.0,
  "bars_held_p50_child": 83.5,
  "delta_mean_r": 0.02944746400484531,
  "delta_n_H": 0,
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
  "wr_base": 0.32666666666666666,
  "wr_child": 0.4266666666666667,
  "mean_r_base": -0.2673944664305332,
  "mean_r_child": -0.10514684035807188,
  "n_H_base": 0,
  "n_H_child": 0,
  "bars_held_p50_base": 86.0,
  "bars_held_p50_child": 116.0,
  "delta_mean_r": 0.16224762607246135,
  "delta_n_H": 0,
  "HOLE_OK": true,
  "MOVED": true,
  "S_THIN": false,
  "S_HARM": false,
  "S_MISSING": false
}
```

## T3 license vs G3 books

```json
{
  "tag": "SCALE_BODY",
  "law": "NONE",
  "licensed_next_family": "H_NONE",
  "MOVED_A": false,
  "MOVED_B": true,
  "GENESIS_EYES_OK": false,
  "Proof": false,
  "REAL": "no",
  "floor_waived": false,
  "guard_bypassed": false,
  "world_engineering_closed": true,
  "honesty": "LAW: detector scaled with drift. 0.12*(8e-6/2.4e-4)=0.004. This is the last synthetic-world knob. This window refuses out-of-band seeds and does not disable the 1% guard. Production default unchanged. a9ffa852 is baseline, not clay. Scratch 46-dim V1. Floor 150 stays. GENESIS_EYES_OK stays false. SCALE_OK is not Evolution Proof. REAL=no. Source synthetic_cloud_fixture. License vs frozen a9ffa852 on THIS tape."
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

LAW: detector scaled with drift. 0.12*(8e-6/2.4e-4)=0.004. This is the last synthetic-world knob. This window refuses out-of-band seeds and does not disable the 1% guard. Production default unchanged. a9ffa852 is baseline, not clay. Scratch 46-dim V1. Floor 150 stays. GENESIS_EYES_OK stays false. SCALE_OK is not Evolution Proof. REAL=no. Source synthetic_cloud_fixture. License vs frozen a9ffa852 on THIS tape.

Origin drift/band/obj/conv/strat/occupancy/genesis/physics/coupling/v2/polish artifacts were not overwritten.
GENESIS_EYES_OK is false. oracle_regime is false. REAL=no. Floor 150.
FORCE_OPEN train-only. 1% guard not patched. Production enricher default remains ±0.15.
Clip-as-success is forbidden. At most three seeds. DRIFT_RTH used is 8.0e-6.
PHYSICS_SLOPE_ABS used is 0.004. world_engineering_closed is true. Last world knob.

## flags

```json
{
  "source": "awakening_slope_scale",
  "drift_rth": 8e-06,
  "slope_abs_used": 0.004,
  "prod_slope_abs": 0.15,
  "nq_min": 12000.0,
  "nq_max": 28000.0,
  "seed_used": 20260920,
  "attempts": [
    {
      "seed": 20260920,
      "min": 16124.75,
      "max": 25283.5,
      "in_band": true
    }
  ],
  "price_min": 16124.75,
  "price_max": 25283.5,
  "in_band": true,
  "world_ok": true,
  "train_force_open": true,
  "eval_force_open": false,
  "baseline_sha256": "a9ffa8529e02f2d8f8a535be4dcce205a43abe20bdec492add78126a8181188b",
  "child_sha256": "b83d2b67ef9d79377ac33094b86d86eccdecd74d67c9a7f9338a1dc67c7b1c65",
  "init_policy": "scratch",
  "learn_called": true,
  "actual_timesteps": 10000,
  "A": {
    "n_policy_base": 150,
    "n_policy_child": 150,
    "mean_r_base": -0.13990621213874965,
    "mean_r_child": -0.11045874813390434,
    "n_H_base": 0,
    "n_H_child": 0,
    "wr_base": 0.3933333333333333,
    "wr_child": 0.41333333333333333,
    "n_W_base": 0,
    "n_W_child": 1,
    "bars_held_p50_base": 92.0,
    "bars_held_p50_child": 83.5,
    "delta_mean_r": 0.02944746400484531,
    "delta_n_H": 0,
    "HOLE_OK": true,
    "MOVED": false,
    "S_THIN": false,
    "S_HARM": false,
    "S_MISSING": false
  },
  "B": {
    "n_policy_base": 150,
    "n_policy_child": 150,
    "mean_r_base": -0.2673944664305332,
    "mean_r_child": -0.10514684035807188,
    "n_H_base": 0,
    "n_H_child": 0,
    "wr_base": 0.32666666666666666,
    "wr_child": 0.4266666666666667,
    "n_W_base": 0,
    "n_W_child": 0,
    "bars_held_p50_base": 86.0,
    "bars_held_p50_child": 116.0,
    "delta_mean_r": 0.16224762607246135,
    "delta_n_H": 0,
    "HOLE_OK": true,
    "MOVED": true,
    "S_THIN": false,
    "S_HARM": false,
    "S_MISSING": false
  },
  "tag": "SCALE_BODY",
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
  "overall": "AWAKENING_SLOPE_SCALE SHADOW_MEASURE",
  "phase_blocks": 6,
  "splitter": "per_phase_60_40",
  "fixture_train_hash": "c9188a030e38e4bc",
  "MOVED_A": false,
  "MOVED_B": true,
  "missing_reason": "",
  "obs_dim": 46
}
```
