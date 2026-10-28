# S3 in-band idle IMU verdict

`S3_PASS_BIRTH_OPEN` — PASSTHROUGH produced a real policy sample on the same certified tape. Stage-3 wrote a verified `foundation_v2` receipt. Birth stays OPEN (S4–S5 + fitness not done).

| Field | Value |
|---|---|
| engine | BRO-v2 / BirthPhaseEngineV2 |
| training_mode | certified |
| floors | S3 0.25–0.75, `S3_MIN_TRADES=400`, `S3_EDGE_MIN=-0.05`, `POLICY_EDGE_MIN_TRADES=150` unchanged (`lumina_core/birth/foundation_metrics.py:21,30,35-36,39`) |
| idle IMU present | yes — `s3_inband_idle_armed` `lumina_core/birth/stage3_inband_idle.py:43`; tax `s3_inband_hold_tax` `:74` wired `lumina_core/rl/reward_shaper.py:287-304` |
| HOLD-mask present | yes — `s3_inband_hold_mask` `stage3_inband_idle.py:175`; applied after envelope `sim_runner.py:583-600` via `maybe_s3_passthrough_mask` `:238` |
| plant tag invariant | FORCE_OPEN=`entry_is_plant True`; in-band explore/PASSTHROUGH=`False` (`plant_tag_for_entry` `stage3_inband_idle.py:224`) |
| tape | **reused generator / regenerated cache** same params: `source=synthetic_cloud_fixture` seed `20260902` hashes `7e86c2bb1c71d514` / `2466d3f41d60657b`, 213,120 ticks, 88 calendar days, 3 holdout regimes |
| S1 receipt verified | **True** certified (`reports/birth_cloud_run/s1_receipt.json`, trades=150, schema=`foundation_v2`) |
| S2 receipt verified | **True** certified (`reports/birth_cloud_run/s2_receipt.json`, trades=250, occupancy=0.620 in [0.30, 0.70], schema=`foundation_v2`) |
| S3 stage_trades | **400** |
| S3 policy_trades / plant_trades | **150 / 250** |
| S3 occupancy | **0.7198** in [0.25, 0.75] |
| s3_inband_explore | **0** (mask backstop unused this plant; π sampled L/S under `deterministic=False` while tax armed). Tax steps **967**. Replica test still replaces HOLD by bar 32. |
| participation_passthrough / force_open | **198326 / 380** at trades=325 (last HUD before pass); receipt `total_signals=251002`. PASSTHROUGH dominated. |
| S3 skill_wr / p_ft / edge | skill_wr=**0.5733** (86/150) · p_ft=**0.3381** · edge=**+0.2353** (not `policy_sample 0`, not `edge=-p_ft`) |
| pass_reason | `foundation_pass settle=ok` |
| S3 receipt verified certified | **True** (`reports/birth_cloud_run/s3_receipt.json`, schema=`foundation_v2`, constitution hard not present / 0) |
| is_birth_exit_sufficient | **False** (S1–S3 receipts only; no S4–S5; no fitness vector) |
| verdict | **S3_PASS_BIRTH_OPEN** |

## Gate A — tests

```
LUMINA_FABRIC_SUPERVISOR=0
.venv/bin/pytest tests/birth/test_s3_inband_idle.py tests/birth/test_s3_snapshot_skill_split.py tests/birth/test_stage2_participation_envelope.py tests/birth/test_foundation_pass.py -q --timeout=60
# 72 passed in 0.25s

.venv/bin/pytest tests/birth/ tests/test_m5_residual_loc.py -q --timeout=60
# 1290 passed, 3 skipped in 30.84s
```

Cloud-failure replica (`test_d_cloud_failure_replica_mask_replaces_hold_by_bar_32`): 40 PASSTHROUGH HOLDs → entry by bar 32, `entry_is_plant=False`.

Resume SSOT (`test_g_*`): trades=524 / policy=0 / plant=524 / settlement share ≥ 0.70 does **not** emit `settlement_share=0.00`; still honest `policy_sample 0 < 150` until new policy closes.

S2 envelope: `occupancy_control_over` still max; `cumulative_in_band_passthrough` still PASSTHROUGH when cumulative in band (`stage2_participation_envelope.py:205`).

Floors unchanged. `practice_mode=False`. No REAL. Fabric supervisor off.

## Gate B1 — certified-shadow plant (`--force`, workspace cache missing)

Workspace checkpoint/tick jsonl were missing → `--force` on the same `CloudFixtureSpec`. Fixture hashes matched. Env gap this VM: installed `torch==2.11.0` + `stable_baselines3==2.8.0` into `.venv` (same as S2 rerun; not a floor change).

S1+S2 re-passed in ~2 min. S3:

| t | trades | policy | blocker |
|---|---|---|---|
| 16:30:30 | 0 | 0 | `trades 0 < 400` + occupancy + `policy_sample 0 < 150` (warmup) |
| 16:31:01 | 92 | 91 | `trades 92 < 400;policy_sample 91 < 150` |
| 16:31:36 | 149 | 148 | `trades 149 < 400;policy_sample 148 < 150` |
| 16:32:09 | 151 | **≥150** | `trades 151 < 400` only — **no policy_sample** |
| 16:41:36 | **400** | **150** | **PASS** `foundation_pass settle=ok` |

Never `policy_sample 0 < 150` after occupancy in-band with PASSTHROUGH dominating.
Never `settlement_share=0.00`.
Never `edge=-p_ft` on policy=0.

Envelope `cumulative_in_band_passthrough` **not** reverted. FORCE_OPEN did not own the in-band book (plant=250 of 400 after policy sample already adequate; volume completed via envelope over-flat plant while skill clock stayed at 150).

## Birth

Milestone stays **OPEN**. S4 started on the same engine after S3 pass; this ticket does not close Birth.
