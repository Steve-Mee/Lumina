# LUMINA Awakening OBJECTIVE_TRADE experiment log

## 2026-09-04T19:36:40.371347+00:00 — AWAKENING_OBJECTIVE_TRADE

LAW: #44 world payable, books thin ~40. This window FORCE_OPEN train-only.
n_policy G2 base A/B=0/0 G4 child A/B=0/0
tag=`S_MISSING`

- tag=`S_MISSING` law=`NONE` licensed_next_family=`H_NONE` world_ok=`True`
- hash=`3930475515f9576a` seed=`20260913` slope_abs_used=`0.12` prod_slope_abs=`0.15` train_force_open=`False` eval_force_open=`False` baseline=`a9ffa8529e02f2d8` child=``
- init_policy=scratch learn_called=`False` actual_timesteps=`0` floor=150 floor_waived=false GENESIS_EYES_OK=false oracle_regime=false REAL=no G6=`REAL_DOOR_LOCKED`

LAW: #44 world payable, books thin ~40. This window FORCE_OPEN train-only. Production default unchanged. a9ffa852 is baseline, not clay. Scratch 46-dim V1. Floor 150 stays. GENESIS_EYES_OK stays false. OBJ_OK is not Evolution Proof. REAL=no. Source synthetic_cloud_fixture. License vs frozen a9ffa852 on THIS tape.

## 2026-09-04T19:40:55.957171+00:00 — AWAKENING_OBJECTIVE_TRADE

LAW: #44 world payable, books thin ~40. This window FORCE_OPEN train-only.
n_policy G2 base A/B=0/0 G4 child A/B=0/0
tag=`OBJ_THIN`

- tag=`OBJ_THIN` law=`NONE` licensed_next_family=`H_NONE` world_ok=`True`
- hash=`3930475515f9576a` seed=`20260913` slope_abs_used=`0.12` prod_slope_abs=`0.15` train_force_open=`True` eval_force_open=`False` baseline=`a9ffa8529e02f2d8` child=`cf70ae5b212ae5a5`
- init_policy=scratch learn_called=`True` actual_timesteps=`10000` floor=150 floor_waived=false GENESIS_EYES_OK=false oracle_regime=false REAL=no G6=`REAL_DOOR_LOCKED`

LAW: #44 world payable, books thin ~40. This window FORCE_OPEN train-only. Production default unchanged. a9ffa852 is baseline, not clay. Scratch 46-dim V1. Floor 150 stays. GENESIS_EYES_OK stays false. OBJ_OK is not Evolution Proof. REAL=no. Source synthetic_cloud_fixture. License vs frozen a9ffa852 on THIS tape.

Diagnosis (OBJ_THIN, not a second knob): seed 20260913 same #44 physics produced an unphysical NQ path (train/hold max ~1.46e7, >40k on ~55–60% of bars). FORCE_OPEN armed on the train factory and fired (Birth occupancy helper), but every plant was soft-blocked `risk_exceeds_1pct` (NQ×MES $5 vs 1% of $50k). Eval FORCE_OPEN off. G2 and G4 books are empty jsonl, n_policy 0/0 both legs. Entry refusal, not hold-to-cap. Floor 150 not waived. Next still one knob.
