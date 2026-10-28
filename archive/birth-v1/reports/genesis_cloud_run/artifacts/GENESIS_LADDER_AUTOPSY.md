# GENESIS ladder autopsy

Filled from this run's disk only. Old path_early / 8cc435c6 / 53df2d78 were not inputs.

| Rung | Works / Weak / Broken / Forbidden-correct | Evidence (file + number) |
|------|-------------------------------------------|--------------------------|
| Fixture generator + certified cache | Works | 01_genesis_fixture_manifest.json source=synthetic_cloud_fixture hash=5726ae7e83ff3d48 days=88 ticks=213120 regimes=['NEUTRAL', 'TREND_DOWN', 'TREND_UP'] |
| Birth S1 | Works | s1_receipt.json schema=foundation_v2 trades=150 pass_criteria_id=closed_loop oos_sharpe=None |
| Birth S2 occupancy / envelope | Works | s2_receipt.json schema=foundation_v2 trades=250 pass_criteria_id=selectivity oos_sharpe=None |
| Birth S3 in-band idle | Works | s3_receipt.json schema=foundation_v2 trades=400 pass_criteria_id=mixed_regimes oos_sharpe=None |
| Birth S4 | Works | s4_receipt.json schema=foundation_v2 trades=151 pass_criteria_id=viable_plant oos_sharpe=None |
| Birth S5 + OOS sharpe | Works | s5_receipt.json schema=foundation_v2 trades=154 pass_criteria_id=probe_handoff oos_sharpe=-1.5241811786200314 |
| Birth exit + pi_star export | Works | g3_birth_exit_exam.json exited=true sha=d313b107e99e03a5ce856226ccc6b352ae5fb01f995eccb4c0a6888988fda2af fitness_ok=True |
| 43-dim newborn eval A/B | Works | genesis_birth_A/B_close_ledger.jsonl on this fixture holdout halves |
| MARK_EYES wrapper 46-dim | Works | genesis_mark_eyes_pi_star.zip init=scratch obs_dim=46 |
| MARK_EYES 10k scratch learn | Works | learn_called=true actual_timesteps=10000 seed=20260904 |
| MARK_EYES eval vs newborn | Weak | g5_eval.json tag=GENESIS_EYES_FAIL (not compared to old path_early 78/83) |
| T/DEAD/bounce families | Forbidden-correct | PATH_EXIT_K3_SHADOW default False; PATH_SHAPE_K3_SHADOW default False; not rerun |
| REAL / Promotion / Proof door | Forbidden-correct | g6_real_door.json G6_tag=REAL_DOOR_LOCKED REAL=no source=synthetic_cloud_fixture fixture_real_data_pct=0.0 engine_real_data_pct=100.0 (certified-cache accounting is not a REAL certificate) |
| Capital path (qty=1 MES $5 clip) | Works | lumina_core/rl/gym_stop_fill.py:32 birth_force_qty_one; lumina_core/birth/notional_cap.py:48 birth_close_cap_usd; lumina_core/birth/birth_trade_geometry.py MES $5 — untouched |
| Autonomy (checkpoint / no human T) | Works | checkpoint=False force=True reuse_data_manifest=True no T_LOCK |

## Weak / Broken causes + next experiment

- **MARK_EYES eval vs newborn** (Weak): HOLE_MOVED A/B=False/False n_policy=113/103 (need ≥150) Δn_H=36/34 Δmean_r=0.0672562233335908/0.33046107806918934 → `GENESIS_EYES_HOLD_COMPARE`
