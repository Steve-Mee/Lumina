# AWAKENING_ENRICHER_CONVERSION_AUDIT

## Gate 0 live-check + inspect_conv_protocol

```json
{
  "origin_main": "33ef9d0468bf6154ffb562160005fca57df0e6c0",
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
  "physics_slope_abs_012": "lumina_core/birth/awakening_conv_enrich.py:1",
  "prod_default_015": "lumina_core/birth/awakening_conv_enrich.py:13",
  "exam_seed_20260912": "lumina_core/birth/awakening_conv_tape.py:65",
  "per_phase_60_40_import": "lumina_core/birth/awakening_conv_tape.py:35",
  "fracs_25_25": "lumina_core/birth/awakening_conv_tape.py:294",
  "no_oracle_regime": "lumina_core/birth/awakening_conv_tape.py:159",
  "body_skipped": "lumina_core/birth/awakening_conv_run.py:129",
  "floor_150": "lumina_core/birth/foundation_metrics.py:39",
  "both_leg_license": "lumina_core/birth/awakening_conv_flags.py:166",
  "genesis_eyes_ok_false": "lumina_core/birth/awakening_conv_flags.py:151",
  "missing_sites": [],
  "gate0_complete": true
}
```

## T0 identity

```json
{
  "origin_main": "33ef9d0468bf6154ffb562160005fca57df0e6c0",
  "fixture_seed": 20260912,
  "fixture_train_hash": "b1f16c99e2989be1",
  "baseline_sha256": "a9ffa8529e02f2d8f8a535be4dcce205a43abe20bdec492add78126a8181188b",
  "child_sha256": "a8a93d6e4cc2dfd171d5130e01fd385c6db5aeb6de590fbb497e636a13015add",
  "init_policy": "scratch",
  "obs_dim": 46,
  "OBSERVATION_DIM": 43,
  "POLICY_EDGE_MIN_TRADES": 150,
  "timesteps": 10000,
  "train_seed": 20260912,
  "splitter": "per_phase_60_40",
  "slope_abs_used": 0.12,
  "prod_slope_abs": 0.15,
  "prod_enricher_default_changed": false
}
```

## T1 honesty / G2 conversion fixture

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

## T2 G4 a9ffa852 vs G6 scratch V1 child on THIS tape

### Leg A

```json
{
  "leg": "A",
  "n_policy_base": 42,
  "n_policy_child": 52,
  "wr_base": 0.23809523809523808,
  "wr_child": 0.09615384615384616,
  "mean_r_base": -0.5545069786110409,
  "mean_r_child": -0.8161211004897785,
  "n_H_base": 7,
  "n_H_child": 14,
  "bars_held_p50_base": 70.5,
  "bars_held_p50_child": 62.5,
  "delta_mean_r": -0.26161412187873756,
  "delta_n_H": -7,
  "HOLE_OK": false,
  "MOVED": false,
  "S_THIN": true,
  "S_HARM": true,
  "S_MISSING": false
}
```

### Leg B

```json
{
  "leg": "B",
  "n_policy_base": 40,
  "n_policy_child": 35,
  "wr_base": 0.125,
  "wr_child": 0.2,
  "mean_r_base": -0.7658356569114486,
  "mean_r_child": -0.6015565382666159,
  "n_H_base": 12,
  "n_H_child": 11,
  "bars_held_p50_base": 91.5,
  "bars_held_p50_child": 119.0,
  "delta_mean_r": 0.1642791186448327,
  "delta_n_H": 1,
  "HOLE_OK": true,
  "MOVED": false,
  "S_THIN": true,
  "S_HARM": false,
  "S_MISSING": false
}
```

## T3 license vs G4 books

```json
{
  "tag": "S_HARM",
  "law": "NONE",
  "licensed_next_family": "H_NONE",
  "MOVED_A": false,
  "MOVED_B": false,
  "GENESIS_EYES_OK": false,
  "Proof": false,
  "REAL": "no",
  "honesty": "LAW: #43 missed 25/25 by 1\u20133 points at |0.15|. This window tries |0.12| once. Production default unchanged. a9ffa852 is baseline, not clay. Scratch 46-dim V1. Floor 150 stays. GENESIS_EYES_OK stays false. CONV_OK is not Evolution Proof. REAL=no. Source synthetic_cloud_fixture. License vs frozen a9ffa852 on THIS tape."
}
```

## G7 REAL door

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

LAW: #43 missed 25/25 by 1–3 points at |0.15|. This window tries |0.12| once. Production default unchanged. a9ffa852 is baseline, not clay. Scratch 46-dim V1. Floor 150 stays. GENESIS_EYES_OK stays false. CONV_OK is not Evolution Proof. REAL=no. Source synthetic_cloud_fixture. License vs frozen a9ffa852 on THIS tape.

Origin strat/occupancy/genesis/physics/coupling/v2/polish artifacts were not overwritten.
GENESIS_EYES_OK is false. oracle_regime is false. REAL=no. Floor 150.
Production enricher default remains ±0.15.

## flags

```json
{
  "source": "awakening_enricher_conversion",
  "slope_abs_used": 0.12,
  "prod_slope_abs": 0.15,
  "splitter": "per_phase_60_40",
  "phase_blocks": 6,
  "gen_up": 71040,
  "gen_down": 71040,
  "gen_range": 71040,
  "train_up_frac": 0.29400494244244246,
  "train_down_frac": 0.29369994994994997,
  "hold_up_frac": 0.29598348348348347,
  "hold_down_frac": 0.28418262012012013,
  "world_ok": true,
  "fixture_seed": 20260912,
  "fixture_train_hash": "b1f16c99e2989be1",
  "baseline_sha256": "a9ffa8529e02f2d8f8a535be4dcce205a43abe20bdec492add78126a8181188b",
  "child_sha256": "a8a93d6e4cc2dfd171d5130e01fd385c6db5aeb6de590fbb497e636a13015add",
  "init_policy": "scratch",
  "learn_called": true,
  "actual_timesteps": 10000,
  "A": {
    "n_policy_base": 42,
    "n_policy_child": 52,
    "mean_r_base": -0.5545069786110409,
    "mean_r_child": -0.8161211004897785,
    "n_H_base": 7,
    "n_H_child": 14,
    "wr_base": 0.23809523809523808,
    "wr_child": 0.09615384615384616,
    "n_W_base": 7,
    "n_W_child": 4,
    "bars_held_p50_base": 70.5,
    "bars_held_p50_child": 62.5,
    "delta_mean_r": -0.26161412187873756,
    "delta_n_H": -7,
    "HOLE_OK": false,
    "MOVED": false,
    "S_THIN": true,
    "S_HARM": true,
    "S_MISSING": false
  },
  "B": {
    "n_policy_base": 40,
    "n_policy_child": 35,
    "mean_r_base": -0.7658356569114486,
    "mean_r_child": -0.6015565382666159,
    "n_H_base": 12,
    "n_H_child": 11,
    "wr_base": 0.125,
    "wr_child": 0.2,
    "n_W_base": 2,
    "n_W_child": 4,
    "bars_held_p50_base": 91.5,
    "bars_held_p50_child": 119.0,
    "delta_mean_r": 0.1642791186448327,
    "delta_n_H": 1,
    "HOLE_OK": true,
    "MOVED": false,
    "S_THIN": true,
    "S_HARM": false,
    "S_MISSING": false
  },
  "tag": "S_HARM",
  "GENESIS_EYES_OK": false,
  "law": "NONE",
  "licensed_next_family": "H_NONE",
  "evolution_proof_stamped": false,
  "REAL": "no",
  "playground": false,
  "hook_default": false,
  "oracle_regime": false,
  "prod_enricher_default_changed": false,
  "real_data_pct": 0.0,
  "G6_tag": "REAL_DOOR_LOCKED",
  "overall": "AWAKENING_ENRICHER_CONVERSION SHADOW_MEASURE",
  "MOVED_A": false,
  "MOVED_B": false,
  "missing_reason": "",
  "obs_dim": 46
}
```
