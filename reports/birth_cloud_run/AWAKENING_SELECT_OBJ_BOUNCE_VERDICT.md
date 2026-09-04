# AWAKENING_SELECT_OBJ_BOUNCE_VERDICT

**Overall:** `GRIND_REGRESS_AWAKENING_OPEN SELECT_OBJ_BOUNCE SHADOW_MEASURE`
**Date:** 2026-09-04T08:04:57.323538+00:00
**Evaluated zip sha256:** `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03`
**optimizer_steps:** `0`
**replay_ran:** `false`
**learn_called:** `false`
**BOUNCE_WEAK:** `0.50`
**gate1_tag:** `OBJ_NONE`
**Tag:** `OBJ_NONE`
**Law:** `NONE`
**Family:** `SELECT_OBJ:P_BOUNCE_WEAK`
**licensed_next_family:** `H_NONE`
**Evolution Proof stamped:** `False`
**Playground:** `no`
**REAL:** `no`

### Tm — Gate 1 measure
{
  "A": {
    "n_U3": 117,
    "n_H3": 71,
    "n_W3": 37,
    "n_defined": 117,
    "missing_share": 0.0,
    "n_h_hit": 1,
    "n_w_hit": 1,
    "cov_H": 0.014084507042253521,
    "cov_W": 0.02702702702702703,
    "lift": -0.012942519984773507,
    "S_SPLIT": false,
    "S_HARM": false,
    "S_THIN": false,
    "S_MISSING": false,
    "bounce_p10_H": 1.473907972313739,
    "bounce_p50_H": 3.4535698916557602,
    "bounce_p90_H": 6.274417291005704,
    "bounce_p10_W": 1.3189796015052506,
    "bounce_p50_W": 3.6227621772331418,
    "bounce_p90_W": 7.585096088875443,
    "bounce_p10_U": 1.3728228497122383,
    "bounce_p50_U": 3.6085267549473197,
    "bounce_p90_U": 7.205819011189682,
    "min_bounce_U": 0.3764944017797075,
    "BOUNCE_WEAK": 0.5
  },
  "B": {
    "n_U3": 126,
    "n_H3": 79,
    "n_W3": 42,
    "n_defined": 126,
    "missing_share": 0.0,
    "n_h_hit": 0,
    "n_w_hit": 0,
    "cov_H": 0.0,
    "cov_W": 0.0,
    "lift": 0.0,
    "S_SPLIT": false,
    "S_HARM": false,
    "S_THIN": false,
    "S_MISSING": false,
    "bounce_p10_H": 1.8284909480858058,
    "bounce_p50_H": 3.778908717111029,
    "bounce_p90_H": 7.531204135989247,
    "bounce_p10_W": 2.149604985237638,
    "bounce_p50_W": 3.832323266402124,
    "bounce_p90_W": 5.930536660192605,
    "bounce_p10_U": 1.8291681112218756,
    "bounce_p50_U": 3.764718728312776,
    "bounce_p90_U": 6.817995449790042,
    "min_bounce_U": 0.802030850456357,
    "BOUNCE_WEAK": 0.5
  },
  "BOUNCE_WEAK": 0.5
}

### T0 — identity
{
  "path_early_A_sha256": "4604b5082d9ab13e1fdabdfcc9577728117be7183a0accf69f8d599c7050d0eb",
  "path_early_B_sha256": "0a349eb2ab48e8f8194d177c8b4dee760ef2010647a9d2c8548292d953dc1356",
  "path_early_A_sha256_known": "4604b5082d9ab13e1fdabdfcc9577728117be7183a0accf69f8d599c7050d0eb",
  "path_early_B_sha256_known": "0a349eb2ab48e8f8194d177c8b4dee760ef2010647a9d2c8548292d953dc1356",
  "sha_match": true,
  "n_policy": 150,
  "n_policy_flags_A": null,
  "n_policy_flags_B": null,
  "optimizer_steps": 0,
  "hooks_false": true,
  "source": "awakening_select_obj_bounce",
  "BOUNCE_WEAK": 0.5,
  "replay_ran": false
}

### T4 — read-only prior hole
{
  "path_early_A": {
    "absent": false,
    "path": "reports/birth_cloud_run/artifacts/path_early_A_close_ledger.jsonl",
    "n": 84,
    "mean_r": -1.037529935379773
  },
  "path_early_B": {
    "absent": false,
    "path": "reports/birth_cloud_run/artifacts/path_early_B_close_ledger.jsonl",
    "n": 88,
    "mean_r": -1.0515286004324211
  },
  "path_exit_k3_A": {
    "absent": false,
    "path": "reports/birth_cloud_run/artifacts/path_exit_k3_A_close_ledger.jsonl",
    "n": 46,
    "mean_r": -1.0377699206838897
  },
  "path_exit_k3_B": {
    "absent": false,
    "path": "reports/birth_cloud_run/artifacts/path_exit_k3_B_close_ledger.jsonl",
    "n": 49,
    "mean_r": -1.051534869069244
  },
  "path_exit_k3_t025_A": {
    "absent": false,
    "path": "reports/birth_cloud_run/artifacts/path_exit_k3_t025_A_close_ledger.jsonl",
    "n": 61,
    "mean_r": -1.0377593524524136
  },
  "path_exit_k3_t025_B": {
    "absent": false,
    "path": "reports/birth_cloud_run/artifacts/path_exit_k3_t025_B_close_ledger.jsonl",
    "n": 54,
    "mean_r": -1.0515558189164496
  },
  "path_shape_k3_dead_A": {
    "absent": true
  },
  "path_shape_k3_dead_B": {
    "absent": true
  }
}

### Honesty
#27 T_LOCK A HOLE_MOVED; B mean_r worse. Promoting T_LOCK is forbidden.
#28 T_FP=-0.25 TRANSFER_FAIL. k=3 R-threshold family exhausted as a controller.
#29 DEAD SHAPE_NONE. n_h_hit=0/0. EPS_SIT=0.05 not widened.
This ticket locks BOUNCE_WEAK=0.50 a priori (half-R recovery off paper MAE), not A/B-fitted.
No flatten. No learn(). Both path hooks stayed False.
Median not used as threshold.
Gate 1 tag=OBJ_NONE lift A/B=-0.012942519984773507/0.0
min_bounce U3 A/B=0.3764944017797075/0.802030850456357
Tag: OBJ_NONE. Law: NONE.
licensed_next_family: H_NONE.
Playground: no.
Evolution Proof stamped: False.
REAL: no.

Playground does not open. No learn(). No flatten. Hook default off. Evolution Proof stamped: False.

