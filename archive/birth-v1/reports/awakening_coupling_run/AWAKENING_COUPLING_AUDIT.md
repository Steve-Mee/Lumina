# AWAKENING_ENRICHER_COUPLING_AUDIT

## Gate 0 live-check + inspect_coupling_protocol

```json
{
  "origin_main": "bbe41a5b2c77ec9528d5bab12b20f3f9e047bebe",
  "POLICY_EDGE_MIN_TRADES": 150,
  "OBSERVATION_DIM": 43,
  "pct_synthetic": 0.0,
  "inspect_complete": true
}
```

```json
{
  "cause_rules_order": "lumina_core/birth/awakening_coupling_diagnose.py:23",
  "fix_kind_equals_cause": "lumina_core/birth/awakening_coupling_fix.py:1",
  "no_oracle_regime": "lumina_core/birth/awakening_coupling_fix.py:76",
  "diagnose_seed": "lumina_core/birth/awakening_coupling_diagnose.py:21",
  "exam_seed": "lumina_core/birth/awakening_coupling_diagnose.py:22",
  "frac_25_25": "lumina_core/birth/awakening_coupling_diagnose.py:31",
  "floor_150": "lumina_core/birth/foundation_metrics.py:39",
  "both_leg_license": "lumina_core/birth/awakening_coupling_flags.py:168",
  "genesis_eyes_ok_false": "lumina_core/birth/awakening_coupling_flags.py:185",
  "hooks_false": "lumina_core/birth/awakening_path_exit_k3.py:22",
  "hooks_shape_false": "lumina_core/birth/awakening_path_shape_k3_dead.py:57",
  "body_skipped": "lumina_core/birth/awakening_coupling_run.py:121",
  "honesty_synthetic_0": "lumina_core/birth/data_source_honesty.py:22",
  "missing_sites": [],
  "gate0_complete": true
}
```

## T0 identity

```json
{
  "origin_main": "bbe41a5b2c77ec9528d5bab12b20f3f9e047bebe",
  "diagnose_seed": 20260908,
  "exam_seed": 20260909,
  "exam_hash": "",
  "baseline_sha256": "a9ffa8529e02f2d8f8a535be4dcce205a43abe20bdec492add78126a8181188b",
  "child_sha256": "",
  "cause": "OTHER",
  "fix_kind": "",
  "init_policy": "scratch",
  "obs_dim": 46,
  "OBSERVATION_DIM": 43,
  "POLICY_EDGE_MIN_TRADES": 150,
  "timesteps": 10000,
  "train_seed": 20260909
}
```

## T1 honesty / G1 diagnose + G3 exam

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
  "S_MISSING": true
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
  "S_MISSING": true
}
```

## T3 license vs G4 books

```json
{
  "tag": "COUPLING_UNKNOWN",
  "law": "NONE",
  "licensed_next_family": "H_NONE",
  "MOVED_A": false,
  "MOVED_B": false,
  "GENESIS_EYES_OK": false,
  "Proof": false,
  "REAL": "no",
  "honesty": "LAW: #40 WORLD_FAIL stood. This window diagnoses DOWN-death then one fix. a9ffa852 is baseline, not clay. Scratch 46-dim V1. Floor 150 stays. GENESIS_EYES_OK stays false. COUPLING_OK is not Evolution Proof. REAL=no. Source synthetic_cloud_fixture. License vs frozen a9ffa852 on THIS tape. No oracle regime stamp."
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

LAW: #40 WORLD_FAIL stood. This window diagnoses DOWN-death then one fix. a9ffa852 is baseline, not clay. Scratch 46-dim V1. Floor 150 stays. GENESIS_EYES_OK stays false. COUPLING_OK is not Evolution Proof. REAL=no. Source synthetic_cloud_fixture. License vs frozen a9ffa852 on THIS tape. No oracle regime stamp.

Origin genesis/budget/polish/v2/physics artifacts were not overwritten.
GENESIS_EYES_OK is false. oracle_regime is false. REAL=no. Floor 150.

## flags

```json
{
  "source": "awakening_enricher_coupling",
  "cause": "OTHER",
  "cause_detail": "none of GEN_ASYM/ENR_ASYM/FLOOR_CLIP; measured mechanism is generator block occupancy (gen_up_n=106560 gen_down_n=71040 gen_range_n=35520; train recovers up=40333 down=19593 so train_down=0.19067542366009893 < 0.25 while holdout already clears 25/25); enricher |slope|/ADX and floor/cap are symmetric",
  "fix_kind": "",
  "diagnose_seed": 20260908,
  "exam_seed": 20260909,
  "exam_hash": "",
  "train_up_frac": 0.0,
  "train_down_frac": 0.0,
  "hold_up_frac": 0.0,
  "hold_down_frac": 0.0,
  "world_ok": false,
  "baseline_sha256": "a9ffa8529e02f2d8f8a535be4dcce205a43abe20bdec492add78126a8181188b",
  "child_sha256": "",
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
    "S_MISSING": true
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
    "S_MISSING": true
  },
  "tag": "COUPLING_UNKNOWN",
  "GENESIS_EYES_OK": false,
  "law": "NONE",
  "licensed_next_family": "H_NONE",
  "evolution_proof_stamped": false,
  "REAL": "no",
  "playground": false,
  "hook_default": false,
  "oracle_regime": false,
  "real_data_pct": 0.0,
  "G6_tag": "REAL_DOOR_LOCKED",
  "overall": "AWAKENING_ENRICHER_COUPLING SHADOW_MEASURE",
  "enr_threshold_pos": 0.15,
  "enr_threshold_neg": -0.15,
  "MOVED_A": false,
  "MOVED_B": false,
  "missing_reason": ""
}
```
