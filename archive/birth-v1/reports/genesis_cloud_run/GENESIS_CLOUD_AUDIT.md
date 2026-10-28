# GENESIS_CLOUD_AUDIT

## G0 Recon

```json
{
  "origin_main": "1d4f00631f480498522a2a036806ae076a2b588a",
  "HEAD": "7be1e7cba5e2b650c046600614c5324e43e6b006",
  "OBS": 43,
  "SOURCE_LABEL": "synthetic_cloud_fixture",
  "SCHEMA_VERSION": "cloud_fixture_v1",
  "DAYS": 90,
  "OLD_PARENT_PRESENT_DO_NOT_LOAD": true,
  "old_parent_zip_sha256": "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03",
  "fixture_seed": 20260904,
  "mode": "sim",
  "practice_mode": false
}
```

## G1 Fixture

```json
{
  "cache_schema_version": 1,
  "days": 88,
  "enrich_version": "trend_features_v1",
  "eth_bar_seconds": 60,
  "fixture_seed": 20260904,
  "hash": "5726ae7e83ff3d48",
  "holdout_pct": 0.2,
  "holdout_regimes": [
    "NEUTRAL",
    "TREND_DOWN",
    "TREND_UP"
  ],
  "holdout_tick_count": 43170,
  "path": "/workspace/reports/genesis_cloud_run/workspace/state/lumina_birth_cache_manifest.json",
  "raw_ticks_hash": "e2c9e5500b403094",
  "real_data_pct": 0.0,
  "regime_counts": {
    "NEUTRAL": 160573,
    "TREND_DOWN": 26294,
    "TREND_UP": 26253
  },
  "requested_days": 90,
  "rth_bar_seconds": 10,
  "schema_version": "cloud_fixture_v1",
  "source": "synthetic_cloud_fixture",
  "split_path": "/workspace/reports/genesis_cloud_run/workspace/state/lumina_birth_split_cache.json",
  "start_et": "2026-06-08T18:00:00-04:00",
  "symbol": "NQ SEP26",
  "tick_count": 213120,
  "ticks_path": "/workspace/reports/genesis_cloud_run/workspace/state/lumina_birth_ticks_cache.jsonl",
  "train_regimes": [
    "NEUTRAL",
    "TREND_DOWN",
    "TREND_UP"
  ],
  "train_tick_count": 166620
}
```

## G2 Birth

```json
{
  "status": "completed",
  "error": "",
  "timed_out": false,
  "birth_exited": true,
  "checkpoint": {},
  "progress": {
    "phase": "completed",
    "receipt_stages": [
      "stage1_trend",
      "stage2_range",
      "stage3_mixed",
      "stage4_viable_plant",
      "stage5_probe_handoff"
    ],
    "receipt_count": 5
  }
}
```

## G3 Birth exit

```json
{
  "exited": true,
  "missing": [],
  "proofs": [
    "foundation_five_receipts_v2",
    "foundation_fitness_vector"
  ],
  "fitness_checksum_ok": true,
  "fitness_checksum": "dc73a394b4dbc79a",
  "s5_checksum": "dc73a394b4dbc79a",
  "newborn_zip_sha256": "d313b107e99e03a5ce856226ccc6b352ae5fb01f995eccb4c0a6888988fda2af",
  "real_data_pct": 0.0,
  "decision": {
    "schema": "birth_exit_v1",
    "exited": true,
    "proofs": [
      "foundation_five_receipts_v2",
      "foundation_fitness_vector"
    ],
    "missing": [],
    "survival": {
      "birth_survival_pass_enabled": true,
      "wr_floor": 0.2,
      "expectancy_floor": -0.5,
      "plant_soft_block_rate_max_per_1k": 100.0,
      "note": "Survival floors for Birth EdgeScore only. Skill WR floor 0.35 applies when survival mode off; OOS 0.48 is Proving Ground / cert \u2014 not Birth exit."
    },
    "conflation_blockers": [],
    "next_phase": "awakening",
    "hub_after_exit": true,
    "policy": {
      "birth_exit_means": [
        "five_foundation_v2_receipts",
        "fitness_vector_checksum_ok",
        "legal_plant_hard_const_ok",
        "return_to_phase_hub"
      ],
      "birth_exit_does_not_require": [
        "deck_unlocked",
        "evolution_proof_passed",
        "first_sim_order_placed",
        "human_real_approval",
        "perfect_birth_autonomy_proven",
        "promotion_gate_passed",
        "real_trading_live",
        "shadow_validation_passed",
        "sim_mirror_api_ok",
        "sim_real_guard_stable",
        "perfect_birth_flag",
        "oos_wr_0_48",
        "twin_full_auto",
        "real_capital"
      ],
      "after_birth": {
        "surface": "phase_hub",
        "next_phase": "awakening",
        "perfect_birth": "awakening_or_phase2_unlock_not_birth_gate",
        "certificate_skill_walls": "proving_ground_and_cert_pipeline",
        "economic_viability": "playground",
        "risk_discipline": "apprenticeship",
        "evolution_proof": "awakening"
      },
      "adr": [
        "0036-birth-exit-vs-maturation",
        "0046-birth-foundation-evolvable-plant"
      ],
      "sufficient_proofs_all_of": [
        "foundation_fitness_vector",
        "foundation_five_receipts_v2"
      ]
    }
  }
}
```

## G4 MARK_EYES train

```json
{
  "status": "ok",
  "child_path": "/workspace/reports/genesis_cloud_run/artifacts/genesis_mark_eyes_pi_star.zip",
  "child_sha256": "a9ffa8529e02f2d8f8a535be4dcce205a43abe20bdec492add78126a8181188b",
  "learn_called": true,
  "actual_timesteps": 10000,
  "optimizer_steps": 90,
  "init_policy": "scratch",
  "train_hash": "5726ae7e83ff3d48"
}
```

## G5 Eval

```json
{
  "holdout_a_ticks": 21585,
  "holdout_b_ticks": 21585,
  "birth_A": {
    "n_policy": 150,
    "wr_policy": 0.4,
    "mean_r_policy": -0.13306818214641977,
    "n_H": 67,
    "ledger": "/workspace/reports/genesis_cloud_run/artifacts/genesis_birth_A_close_ledger.jsonl",
    "n_rows": 160
  },
  "birth_B": {
    "n_policy": 150,
    "wr_policy": 0.22,
    "mean_r_policy": -0.3946853762542806,
    "n_H": 55,
    "ledger": "/workspace/reports/genesis_cloud_run/artifacts/genesis_birth_B_close_ledger.jsonl",
    "n_rows": 159
  },
  "eyes_A": {
    "n_policy": 113,
    "wr_policy": 0.4424778761061947,
    "mean_r_policy": -0.06581195881282897,
    "n_H": 31,
    "ledger": "/workspace/reports/genesis_cloud_run/artifacts/genesis_mark_eyes_A_close_ledger.jsonl",
    "n_rows": 113
  },
  "eyes_B": {
    "n_policy": 103,
    "wr_policy": 0.4854368932038835,
    "mean_r_policy": -0.06422429818509125,
    "n_H": 21,
    "ledger": "/workspace/reports/genesis_cloud_run/artifacts/genesis_mark_eyes_B_close_ledger.jsonl",
    "n_rows": 103
  },
  "baseline_present": true,
  "G5_tag": "GENESIS_EYES_FAIL",
  "HOLE_MOVED_A": false,
  "HOLE_MOVED_B": false,
  "delta_n_H_A": 36,
  "delta_mean_r_A": 0.0672562233335908,
  "delta_n_H_B": 34,
  "delta_mean_r_B": 0.33046107806918934,
  "used_old_path_early": false,
  "eval_seeds_20260902_20260903": false
}
```

## G6 REAL door

G6_tag=`REAL_DOOR_LOCKED` REAL=`no`

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

## G7 Autopsy summary

Works=12 Weak=1 Broken=0 Forbidden-correct=2

- Fixture generator + certified cache: **Works**
- Birth S1: **Works**
- Birth S2 occupancy / envelope: **Works**
- Birth S3 in-band idle: **Works**
- Birth S4: **Works**
- Birth S5 + OOS sharpe: **Works**
- Birth exit + pi_star export: **Works**
- 43-dim newborn eval A/B: **Works**
- MARK_EYES wrapper 46-dim: **Works**
- MARK_EYES 10k scratch learn: **Works**
- MARK_EYES eval vs newborn: **Weak**
- T/DEAD/bounce families: **Forbidden-correct**
- REAL / Promotion / Proof door: **Forbidden-correct**
- Capital path (qty=1 MES $5 clip): **Works**
- Autonomy (checkpoint / no human T): **Works**

## Honesty

This run is first life. Old path_early / 8cc435c6 / 53df2d78 were not inputs.
Tape source synthetic_cloud_fixture. real_data_pct=0.0.
Birth exit ≠ REAL. Certificate OOS 0.48 ≠ Birth floor.
T/DEAD/bounce families were not rerun.
MARK_EYES init=scratch on the newborn, one 10k, hooks off.
Evolution Proof stamped: False.
REAL: no.
Playground: no.
G6 tag: REAL_DOOR_LOCKED.
