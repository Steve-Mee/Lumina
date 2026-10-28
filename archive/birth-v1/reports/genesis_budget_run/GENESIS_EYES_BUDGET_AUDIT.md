# GENESIS_EYES_BUDGET_AUDIT

## Gate 0 live-check + inspect_budget_protocol

```json
{
  "origin_main": "6ce936359a5d668f1fec6bc76dd6bedc0df55f66",
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
  "seed_20260905": "lumina_core/birth/genesis_eyes_budget.py:26",
  "start_et_2026_07_06": "lumina_core/birth/genesis_eyes_budget.py:140",
  "holdout_pct_0_40": "lumina_core/birth/genesis_eyes_budget.py:28",
  "min_ticks_per_leg_40000": "lumina_core/birth/genesis_eyes_budget.py:31",
  "student_sha_d313b107": "lumina_core/birth/genesis_eyes_budget.py:32",
  "student_sha_a9ffa852": "lumina_core/birth/genesis_eyes_budget.py:33",
  "forbidden_hash_5726ae7e": "lumina_core/birth/genesis_eyes_budget.py:34",
  "forbidden_hash_7e86c2bb": "lumina_core/birth/genesis_eyes_budget.py:35",
  "floor_150": "lumina_core/birth/foundation_metrics.py:39",
  "thin_refuses_budget_ok": "lumina_core/birth/genesis_eyes_budget_flags.py:144",
  "genesis_eyes_ok_forced_false": "lumina_core/birth/genesis_eyes_budget_flags.py:163",
  "learn_absent": "lumina_core/birth/genesis_eyes_budget.py:25",
  "hooks_default_false": "lumina_core/birth/awakening_path_exit_k3.py:22",
  "hooks_shape_default_false": "lumina_core/birth/awakening_path_shape_k3_dead.py:57",
  "synthetic_pct_zero": "lumina_core/birth/data_source_honesty.py:22",
  "missing_sites": [],
  "gate0_complete": true
}
```

## T0 identity

```json
{
  "origin_main": "6ce936359a5d668f1fec6bc76dd6bedc0df55f66",
  "fixture_seed": 20260905,
  "fixture_train_hash": "e963d1ce7d726ebf",
  "student_birth_sha256": "d313b107e99e03a5ce856226ccc6b352ae5fb01f995eccb4c0a6888988fda2af",
  "student_eyes_sha256": "a9ffa8529e02f2d8f8a535be4dcce205a43abe20bdec492add78126a8181188b",
  "OBSERVATION_DIM": 43,
  "POLICY_EDGE_MIN_TRADES": 150,
  "learn_called": false
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

## T2 evaluate-only (newborn vs child on THIS tape)

### Leg A

```json
{
  "leg": "A",
  "n_policy_birth": 150,
  "n_policy_child": 150,
  "wr_birth": 0.26666666666666666,
  "wr_child": 0.36666666666666664,
  "mean_r_birth": -0.3059336869183842,
  "mean_r_child": -0.17384175148455497,
  "n_H_birth": 53,
  "n_H_child": 29,
  "n_W_birth": 31,
  "n_W_child": 44,
  "bars_held_p50_birth": 11.0,
  "bars_held_p50_child": 89.0,
  "HOLE_MOVED": true,
  "S_THIN": false,
  "S_HARM": false,
  "S_MISSING": false
}
```

### Leg B

```json
{
  "leg": "B",
  "n_policy_birth": 150,
  "n_policy_child": 150,
  "wr_birth": 0.35333333333333333,
  "wr_child": 0.4666666666666667,
  "mean_r_birth": -0.2010227565202182,
  "mean_r_child": -0.045846176033353954,
  "n_H_birth": 73,
  "n_H_child": 37,
  "n_W_birth": 36,
  "n_W_child": 40,
  "bars_held_p50_birth": 20.0,
  "bars_held_p50_child": 90.0,
  "HOLE_MOVED": true,
  "S_THIN": false,
  "S_HARM": false,
  "S_MISSING": false
}
```

## T3 license

```json
{
  "tag": "BUDGET_OK",
  "law": "SHADOW",
  "licensed_next_family": "AWAKENING_MARK_EYES",
  "HOLE_MOVED_A": true,
  "HOLE_MOVED_B": true,
  "GENESIS_EYES_OK": false,
  "Proof": false,
  "REAL": "no",
  "honesty": "Frozen first-life zips sit a NEW thick paper. Not a second Birth. Not a second 10k. Floor POLICY_EDGE_MIN_TRADES=150 stays. GENESIS_EYES_OK stays false. BUDGET_OK is not Evolution Proof. REAL=no. Source synthetic_cloud_fixture."
}
```

## G4 REAL door

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

Frozen first-life zips sit a NEW thick paper. Not a second Birth. Not a second 10k. Floor POLICY_EDGE_MIN_TRADES=150 stays. GENESIS_EYES_OK stays false. BUDGET_OK is not Evolution Proof. REAL=no. Source synthetic_cloud_fixture.

G5 genesis half-ledgers were not overwritten. learn() was not called.
GENESIS_EYES_OK is false. REAL=no. Floor 150.

## flags

```json
{
  "source": "genesis_eyes_budget",
  "fixture_seed": 20260905,
  "fixture_train_hash": "e963d1ce7d726ebf",
  "holdout_tick_count": 86460,
  "ticks_per_leg": [
    43230,
    43230
  ],
  "student_birth_sha256": "d313b107e99e03a5ce856226ccc6b352ae5fb01f995eccb4c0a6888988fda2af",
  "student_eyes_sha256": "a9ffa8529e02f2d8f8a535be4dcce205a43abe20bdec492add78126a8181188b",
  "learn_called": false,
  "optimizer_steps": 0,
  "A": {
    "n_policy_birth": 150,
    "n_policy_child": 150,
    "n_H_birth": 53,
    "n_H_child": 29,
    "n_W_birth": 31,
    "n_W_child": 44,
    "wr_birth": 0.26666666666666666,
    "wr_child": 0.36666666666666664,
    "mean_r_birth": -0.3059336869183842,
    "mean_r_child": -0.17384175148455497,
    "bars_held_p50_birth": 11.0,
    "bars_held_p50_child": 89.0,
    "HOLE_MOVED": true,
    "S_THIN": false,
    "S_HARM": false,
    "S_MISSING": false
  },
  "B": {
    "n_policy_birth": 150,
    "n_policy_child": 150,
    "n_H_birth": 73,
    "n_H_child": 37,
    "n_W_birth": 36,
    "n_W_child": 40,
    "wr_birth": 0.35333333333333333,
    "wr_child": 0.4666666666666667,
    "mean_r_birth": -0.2010227565202182,
    "mean_r_child": -0.045846176033353954,
    "bars_held_p50_birth": 20.0,
    "bars_held_p50_child": 90.0,
    "HOLE_MOVED": true,
    "S_THIN": false,
    "S_HARM": false,
    "S_MISSING": false
  },
  "tag": "BUDGET_OK",
  "HOLE_MOVED_A": true,
  "HOLE_MOVED_B": true,
  "GENESIS_EYES_OK": false,
  "law": "SHADOW",
  "licensed_next_family": "AWAKENING_MARK_EYES",
  "evolution_proof_stamped": false,
  "REAL": "no",
  "playground": false,
  "hook_default": false,
  "used_old_path_early": false,
  "used_g5_halves_as_exam": false,
  "real_data_pct": 0.0,
  "G6_tag": "REAL_DOOR_LOCKED",
  "overall": "GENESIS_EYES_BUDGET SHADOW_MEASURE",
  "missing_reason": ""
}
```
