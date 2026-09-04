# AWAKENING_PHYSICAL_DRIFT_AUDIT

## Gate 0 live-check + inspect_drift_protocol

```json
{
  "origin_main": "275919e18a00fcc02e32052606ed46b1d06570d9",
  "POLICY_EDGE_MIN_TRADES": 150,
  "OBSERVATION_DIM": 43,
  "pct_synthetic": 0.0,
  "PHYSICS_SLOPE_ABS": 0.12,
  "PROD_SLOPE_ABS": 0.15,
  "inspect_complete": true,
  "band_live": {
    "tag": "BAND_WORLD_FAIL",
    "attempts": [
      {
        "seed": 20260914,
        "min": 18044.5,
        "max": 13538023.5,
        "in_band": false
      },
      {
        "seed": 20260915,
        "min": 18714.25,
        "max": 13977321.25,
        "in_band": false
      },
      {
        "seed": 20260916,
        "min": 21051.25,
        "max": 15568974.0,
        "in_band": false
      }
    ],
    "floor": 150
  },
  "seeds": [
    20260917,
    20260918,
    20260919
  ],
  "drift_rth": 8e-06
}
```

```json
{
  "drift_rth_8e_6": "lumina_core/birth/awakening_drift_tape.py:56",
  "phase_blocks_6": "lumina_core/birth/awakening_drift_tape.py:59",
  "nq_min_max": "lumina_core/birth/awakening_drift_tape.py:53",
  "no_clip_as_success": "lumina_core/birth/awakening_drift_tape.py:367",
  "at_most_three_seeds": "lumina_core/birth/awakening_drift_tape.py:60",
  "seeds_20260917_19": "lumina_core/birth/awakening_drift_tape.py:60",
  "guard_1pct_unedited": "lumina_core/birth/birth_constitution_guard.py:39",
  "force_open_train_only": "lumina_core/birth/awakening_mark_eyes_env.py:111",
  "eval_refuses_true": "lumina_core/birth/awakening_mark_eyes_env.py:150",
  "floor_150": "lumina_core/birth/foundation_metrics.py:39",
  "both_leg_license": "lumina_core/birth/awakening_drift_flags.py:174",
  "genesis_eyes_ok_false": "lumina_core/birth/awakening_drift_flags.py:183",
  "missing_sites": [],
  "gate0_complete": true
}
```

## T0 identity

```json
{
  "origin_main": "275919e18a00fcc02e32052606ed46b1d06570d9",
  "seed_used": 20260919,
  "fixture_train_hash": "79397a6f2e866fff",
  "baseline_sha256": "a9ffa8529e02f2d8f8a535be4dcce205a43abe20bdec492add78126a8181188b",
  "child_sha256": "",
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
  "slope_abs_used": 0.12,
  "prod_slope_abs": 0.15,
  "train_force_open": true,
  "eval_force_open": false,
  "floor_waived": false,
  "guard_bypassed": false,
  "used_old_drift_00024": false,
  "prod_enricher_default_changed": false
}
```

## T1 honesty / G1 drift fixture

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
  "HOLE_OK": false,
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
  "HOLE_OK": false,
  "MOVED": false,
  "S_THIN": false,
  "S_HARM": false,
  "S_MISSING": false
}
```

## T3 license vs G3 books

```json
{
  "tag": "DRIFT_ENRICH_FAIL",
  "law": "NONE",
  "licensed_next_family": "H_NONE",
  "MOVED_A": false,
  "MOVED_B": false,
  "GENESIS_EYES_OK": false,
  "Proof": false,
  "REAL": "no",
  "floor_waived": false,
  "guard_bypassed": false,
  "used_old_drift_00024": false,
  "honesty": "LAW: 0.00024 * 35520 bars \u2248 5000\u00d7. Band identity pins 8e-6. This window refuses out-of-band seeds and does not disable the 1% guard. Production default unchanged. a9ffa852 is baseline, not clay. Scratch 46-dim V1. Floor 150 stays. GENESIS_EYES_OK stays false. DRIFT_OK is not Evolution Proof. REAL=no. Source synthetic_cloud_fixture. License vs frozen a9ffa852 on THIS tape."
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

LAW: 0.00024 * 35520 bars ≈ 5000×. Band identity pins 8e-6. This window refuses out-of-band seeds and does not disable the 1% guard. Production default unchanged. a9ffa852 is baseline, not clay. Scratch 46-dim V1. Floor 150 stays. GENESIS_EYES_OK stays false. DRIFT_OK is not Evolution Proof. REAL=no. Source synthetic_cloud_fixture. License vs frozen a9ffa852 on THIS tape.

Origin band/obj/conv/strat/occupancy/genesis/physics/coupling/v2/polish artifacts were not overwritten.
GENESIS_EYES_OK is false. oracle_regime is false. REAL=no. Floor 150.
FORCE_OPEN train-only. 1% guard not patched. Production enricher default remains ±0.15.
Clip-as-success is forbidden. At most three seeds. DRIFT_RTH used is 8.0e-6.

## flags

```json
{
  "source": "awakening_physical_drift",
  "drift_rth": 8e-06,
  "phase_blocks": 6,
  "nq_min": 12000.0,
  "nq_max": 28000.0,
  "seed_used": 20260919,
  "attempts": [
    {
      "seed": 20260917,
      "min": 16599.25,
      "max": 30164.0,
      "in_band": false
    },
    {
      "seed": 20260918,
      "min": 20299.75,
      "max": 29357.0,
      "in_band": false
    },
    {
      "seed": 20260919,
      "min": 17278.5,
      "max": 24703.5,
      "in_band": true
    }
  ],
  "price_min": 17278.5,
  "price_max": 24703.5,
  "in_band": true,
  "world_ok": false,
  "slope_abs_used": 0.12,
  "prod_slope_abs": 0.15,
  "train_force_open": false,
  "eval_force_open": false,
  "baseline_sha256": "a9ffa8529e02f2d8f8a535be4dcce205a43abe20bdec492add78126a8181188b",
  "child_sha256": "",
  "init_policy": "scratch",
  "learn_called": false,
  "actual_timesteps": 0,
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
    "HOLE_OK": false,
    "MOVED": false,
    "S_THIN": false,
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
    "HOLE_OK": false,
    "MOVED": false,
    "S_THIN": false,
    "S_HARM": false,
    "S_MISSING": false
  },
  "tag": "DRIFT_ENRICH_FAIL",
  "GENESIS_EYES_OK": false,
  "law": "NONE",
  "licensed_next_family": "H_NONE",
  "evolution_proof_stamped": false,
  "REAL": "no",
  "playground": false,
  "hook_default": false,
  "oracle_regime": false,
  "guard_bypassed": false,
  "floor_waived": false,
  "used_old_drift_00024": false,
  "real_data_pct": 0.0,
  "G6_tag": "REAL_DOOR_LOCKED",
  "overall": "AWAKENING_PHYSICAL_DRIFT SHADOW_MEASURE",
  "splitter": "per_phase_60_40",
  "fixture_train_hash": "79397a6f2e866fff",
  "MOVED_A": false,
  "MOVED_B": false,
  "missing_reason": "",
  "obs_dim": 46
}
```
