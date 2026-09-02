# S4 live exam verdict

`S4_HOLD_COLLAPSE_FOLLOWUP_ARMED` — Gate B2 on the same certified tape proved Stage-4 HOLD-collapse under PASSTHROUGH. One stage-local idle generalize is applied. Birth stays OPEN (S5 + fitness not done). Resume measurement follows this IMU.

| Field | Value |
|---|---|
| engine | BRO-v2 / BirthPhaseEngineV2 |
| training_mode | certified |
| floors | `S4_MIN_TRADES=100`, `S4_EDGE_MIN=0.0`, `S4_MEAN_R_SLACK=0.10`, occupancy `[0.25, 0.75]`, `POLICY_EDGE_MIN_TRADES=150` unchanged |
| tape | `source=synthetic_cloud_fixture` seed `20260902` hashes `7e86c2bb1c71d514` / `2466d3f41d60657b`, 213,120 ticks, 88 calendar days, 3 holdout regimes |
| S1 receipt verified | **True** certified (`reports/birth_cloud_run/s1_receipt.json`) |
| S2 receipt verified | **True** certified (`reports/birth_cloud_run/s2_receipt.json`) |
| S3 receipt verified | **True** certified (`reports/birth_cloud_run/s3_receipt.json`, trades=400, policy=150, edge=+0.2353) |
| S3 idle left as merged | `S3_INBAND_REGIMES` still `mixed` / `stage3_mixed` / `stage3` only. S3 over-band still disarmed. |
| S4 envelope | **off** (`is_s2 or is_s3` only in `stage_loop_rollout_pre_caps.py`). Not re-implemented. |
| is_birth_exit_sufficient | **False** |
| practice_mode | False. No REAL. `LUMINA_FABRIC_SUPERVISOR=0`. |

## Gate A — tests

```
LUMINA_FABRIC_SUPERVISOR=0
.venv/bin/pytest tests/birth/test_s3_inband_idle.py tests/birth/test_s3_snapshot_skill_split.py tests/birth/test_stage2_participation_envelope.py tests/birth/test_foundation_pass.py tests/birth/test_foundation_loopholes.py -q --timeout=60
# 99 passed
ruff + mypy --strict + pyright: clean on idle IMU + tests
```

S3 cloud replica still replaces HOLD by bar 32. S4 over-flat replica (`flat=1.0`, regime=`stage4_viable_plant`) now also replaces HOLD by bar 32, `entry_is_plant=False`.

## Gate B2 — certified-shadow continue (`--force`, same tape, S3 idle unchanged)

Workspace cache was missing → `--force` on the same `CloudFixtureSpec`. Fixture hashes matched. Engine continued S1→S2→S3→S4 without human restart.

| t | stage | trades | policy | occupancy | idle_armed | passthrough / force_open | blocker |
|---|---|---|---|---|---|---|---|
| 17:08:28 | S1 | 150 | — | — | — | — | **PASS** |
| 17:09:40 | S2 | 250 | — | in band | — | — | **PASS** |
| 17:21:51 | S3 | 400 | 150 | 0.719 | tax then disarm | PASSTHROUGH owned in-band | **PASS** `foundation_pass settle=ok` |
| 17:22:04 | S4 | 0 | 0 | None | **False** | warmup | `trades 0 < 100` + `policy_sample 0 < 150` |
| 17:22:10 | S4 | 0 | 0 | **1.0** | **False** | **5000 / 0** | HOLD under PASSTHROUGH |
| 17:23:30 | S4 | 0 | 0 | **1.0** | **False** | tax=0 explore=0 | `occupancy=1.0 not_in_25%-75%; policy_sample 0 < 150` |
| 17:23:59 | S4 | 0 | 0 | 1.0 | False | — | `history_unavailable` / data expansion exhausted (S4 epoch cap, 0 closes) |

Measured blocker (not assumed):

- `s3_inband_idle_armed=False` because `stage4_viable_plant` ∉ `S3_INBAND_REGIMES` and flat=1.0 is over-band.
- Envelope off → `FORCE_OPEN=0`. π HOLD → 25,000 signals / 10,386 range-flat bars / **0 trades**.
- Exit: `status=history_unavailable`, `total_trades=800` (S1+S2+S3 only), `birth_exit_ok=False`.

Evidence: `s4_live_exam.log`, `s4_live_exam_b2_pre_followup.json`, `s4_gate_b2_monitor.jsonl`.

## Follow-up (exactly one, after B2)

Stage-local idle generalize in `lumina_core/birth/stage3_inband_idle.py`:

- `S4_IDLE_REGIMES = {stage4_viable_plant, stage4, viable_plant}`
- Same tax / HOLD-mask / plant-tag=FORCE_OPEN-only
- S4 arms on PASSTHROUGH + flat + thin policy **even when over-flat** (no envelope to pull in-band)
- S3 in-band law unchanged. S2 dual IMU unchanged. Floors unchanged.

Resume (`--resume`, same checkpoint / same tape) is the S4 re-measure.
