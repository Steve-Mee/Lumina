## S2 IMU verdict
`BIRTH_MILESTONE_OPEN` — S2 `foundation_v2` receipt verified. S3–S5 + fitness still missing.

| Field | Value |
|---|---|
| engine | BRO-v2 / BirthPhaseEngineV2 |
| training_mode | certified (`practice_mode=False`) |
| floors | S2 0.30–0.70 unchanged (`S2_OCCUPANCY_MIN/MAX` in `lumina_core/birth/foundation_metrics.py`). S3 0.25–0.75 unchanged. Stop cap ≤ 1% unchanged. |
| occupancy_control_over used | yes — `lumina_core/birth/stage2_participation_envelope.py:82` (helper) and `:191` (`decide_stage2_participation` over_flat) |
| S2 receipt path | `reports/birth_cloud_run/s2_receipt.json` |
| verify_stage_pass_receipt certified | **True** (`reason=ok`) |
| cumulative occupancy | **0.604179** (receipt `occupancy` / `range_flat_ratio`; in [0.30, 0.70]) |
| rolling occupancy last window | 0.5969 at 250 S2 trades (`occupancy_control_flat`, both IMUs aligned). At S2 pass cumulative 0.604. |
| participation_force_open / hold / flat / exit / passthrough | Mid-S2 live (250 trades, occupancy 0.597): open=775, hold=946, last_mode=PASSTHROUGH. IMU-only stall (1146 trades, occupancy 0.871): open=253621, hold=6410, flat=12917, exit=82, last_mode=PASSTHROUGH. |
| median bars-in-trade during S2 | Mean in-market bars/trade ≈ 24.7 (`(1-0.604)*50826/815`). IMU-only stall hold/open ≈ 0.025 (same-bar death). ATR follow-up hold/open ≈ 1.22 at 250 trades. |
| stall reason if any | none on the passing ATR rerun. IMU-only rerun: `plateau_evolution_exhausted` / `stage2_metric` occupancy 0.871. |
| is_birth_exit_sufficient | **False** (S3–S5 receipts + fitness vector absent) |

## Tape
Same certified synthetic NQ fixture. Regenerated on this VM (cache gitignored) with `CloudFixtureSpec(seed=20260902)`. Hash `7e86c2bb1c71d514` / `raw_ticks_hash=2466d3f41d60657b` match PR #3. `source=synthetic_cloud_fixture`. 213,120 ticks, 88 days, 3 holdout regimes.

## Experiment 1 — IMU law only
`--force`, certified, 8000-trade budget. S1 receipt verified. S2 occupancy started **0.54 in-band** at 45 trades, then drifted to **0.871** and stalled at 1146 S2 trades. `participation_force_open=253621` (wiring OK). hold/open ≈ 0.025 → plants died same-bar. `occupancy_control_flat=0.47` vs cumulative 0.87.

## Experiment 2 — allowed follow-up 2 (ATR FORCE_OPEN stop)
`force_open_stop_from_atr` (`stage2_participation_envelope.py:99`): ATR × √min_dwell, constitution-clipped [0.0004, 1%], dollar-1% at qty=1. Gym soft-prior skipped only on FORCE_OPEN. `hit_stop` live. `closes_flatten=0`.

S2 passed at 815 trades, occupancy **0.604**. `verify_stage_pass_receipt(..., training_mode="certified") is True`. Engine entered S3 (expected; this ticket does not close Birth).

## Follow-ups not required
1. Instrumentation: FORCE_OPEN already reached sim_runner (253k on IMU-only).
3. Reward alignment: not applied; envelope + ATR plant was enough.
4. BIRTH-CLOUD-002: occupancy was the S2 blocker on IMU-only; passing receipt has `median_loss_r=1.055` and `unique_calendar_days=88`. Snapshot bug not masking this result.

## Pytest
- `tests/birth/test_stage2_participation_envelope.py tests/birth/test_stage2_occupancy_dwell_protect.py tests/birth/test_sim_runner_stall.py`: 45 passed
- `tests/birth/`: 1233 passed, 1 skipped

## Capital / autonomy
SIM / certified-shadow only. No REAL, no `container.start()`, `LUMINA_FABRIC_SUPERVISOR=0`. Crash-resume path untouched. Envelope remains airframe.
