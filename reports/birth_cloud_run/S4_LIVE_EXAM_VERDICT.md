# S4 live exam verdict

`S4_PASS_BIRTH_OPEN` — Gate B2 on the same certified tape proved Stage-4 HOLD-collapse under PASSTHROUGH (`policy_sample 0`, occupancy `1.0`). One stage-local idle generalize was applied. `--resume` on the same checkpoint wrote a verified `foundation_v2` S4 receipt. Birth stays OPEN (S5 + fitness not done).

| Field | Value |
|---|---|
| engine | BRO-v2 / BirthPhaseEngineV2 |
| training_mode | certified |
| floors | `S4_MIN_TRADES=100`, `S4_EDGE_MIN=0.0`, `S4_MEAN_R_SLACK=0.10`, occupancy `[0.25, 0.75]`, `POLICY_EDGE_MIN_TRADES=150` unchanged (`lumina_core/birth/foundation_metrics.py`) |
| S3 idle law | unchanged — `S3_INBAND_REGIMES` still `{mixed, stage3_mixed, stage3}`; S3 over-band still disarmed |
| S4 envelope | **off** (`is_s2 or is_s3` only). Not re-implemented. |
| tape | `source=synthetic_cloud_fixture` seed `20260902` hashes `7e86c2bb1c71d514` / `2466d3f41d60657b`, 213,120 ticks, 88 calendar days, 3 holdout regimes |
| S1 receipt verified | **True** certified (`reports/birth_cloud_run/s1_receipt.json`) |
| S2 receipt verified | **True** certified (`reports/birth_cloud_run/s2_receipt.json`, occupancy=0.539 in [0.30, 0.70]) |
| S3 receipt verified | **True** certified (`reports/birth_cloud_run/s3_receipt.json`, trades=400, policy=150, edge=+0.2486) |
| S4 stage_trades / policy / plant | **150 / 150 / 0** |
| S4 occupancy | **0.5761** in [0.25, 0.75] |
| S4 skill_wr / p_ft / edge | skill_wr=**0.4600** (69/150) · p_ft=**0.3408** · edge=**+0.1192** (beats first-touch) |
| S4 mean_r / e_mech | mean_r=**0.2178** ≥ e_mech−0.10 (**−0.1598**); median_loss_r=**1.014** ≤ 1.5 |
| pass_reason | `foundation_pass settle=ok` |
| S4 receipt verified certified | **True** (`reports/birth_cloud_run/s4_receipt.json`, schema=`foundation_v2`, `verify_stage_pass_receipt` → `ok`) |
| is_birth_exit_sufficient | **False** (S1–S4 only; no S5; no fitness vector) |
| practice_mode | False. No REAL. `LUMINA_FABRIC_SUPERVISOR=0`. |

## Gate A — tests

```
LUMINA_FABRIC_SUPERVISOR=0
.venv/bin/pytest tests/birth/test_s3_inband_idle.py tests/birth/test_s3_snapshot_skill_split.py tests/birth/test_stage2_participation_envelope.py tests/birth/test_foundation_pass.py tests/birth/test_foundation_loopholes.py -q --timeout=60
# 99 passed
ruff + mypy --strict + pyright: clean on idle IMU + tests
```

S3 cloud replica still replaces HOLD by bar 32. S4 over-flat replica (`flat=1.0`, regime=`stage4_viable_plant`) replaces HOLD by bar 32, `entry_is_plant=False`. S3 over-band stays disarmed.

## Gate B2 — certified-shadow continue (`--force`, S3 idle unchanged)

Workspace cache missing → `--force` on the same `CloudFixtureSpec`. Fixture hashes matched. Engine continued S1→S2→S3→S4 without human restart.

| t | stage | trades | policy | occupancy | idle_armed | passthrough / force_open | blocker |
|---|---|---|---|---|---|---|---|
| 17:08:28 | S1 | 150 | — | — | — | — | **PASS** |
| 17:09:40 | S2 | 250 | — | in band | — | — | **PASS** |
| 17:21:51 | S3 | 400 | 150 | 0.719 | tax then disarm | PASSTHROUGH owned in-band | **PASS** |
| 17:22:10 | S4 | 0 | 0 | **1.0** | **False** | **5000 / 0** | HOLD under PASSTHROUGH |
| 17:23:30 | S4 | 0 | 0 | **1.0** | **False** | tax=0 explore=0 | `occupancy=1.0; policy_sample 0 < 150` |
| 17:23:59 | S4 | 0 | 0 | 1.0 | False | — | `history_unavailable` (S4 epoch cap, 0 closes) |

Measured blocker: `stage4_viable_plant` ∉ `S3_INBAND_REGIMES`, envelope off, π HOLD, 25,000 signals / 10,386 range-flat bars / **0 trades**. Exit `status=history_unavailable`, `total_trades=800`. Evidence: `s4_live_exam.log`, `s4_live_exam_b2_pre_followup.json`.

## Follow-up (exactly one, after B2)

Stage-local idle generalize in `lumina_core/birth/stage3_inband_idle.py`:

- `S4_IDLE_REGIMES = {stage4_viable_plant, stage4, viable_plant}`
- Same tax / HOLD-mask / plant-tag=FORCE_OPEN only
- S4 arms on PASSTHROUGH + flat + thin policy **even when over-flat** (no envelope to pull in-band)
- S3 in-band law unchanged. S2 dual IMU unchanged. Floors unchanged.

## Resume — same checkpoint / same tape (`--resume`)

Pause flag from fail-closed B2 stop cleared. Checkpoint kept S1–S3 receipts + S4 clocks at 0 / occupancy 1.0.

| t | trades | policy | occupancy | pass_reason |
|---|---|---|---|---|
| 17:29:21 | 0 | 0 | 1.0 | `trades 0 < 100; occupancy=1.0; policy_sample 0 < 150` |
| 17:29:53 | 86 | 86 | 0.650 | `trades 86 < 100; policy_sample 86 < 150` |
| 17:29:55 | 100 | 100 | 0.617 | `policy_sample 100 < 150` only |
| 17:30:25 | **150** | **150** | **0.576** | — |
| 17:30:37 | **150** | **150** | **0.576** | **PASS** `foundation_pass settle=ok` |

Plant trades stayed **0** (FORCE_OPEN never owned the book). HUD `s3_inband_explore=0` / `hold_tax_steps=0` this resume: π sampled L/S under PASSTHROUGH after the B2 collapse; the mask is the over-flat backstop, not the closer that printed this receipt. Settlement: stop=81 / target=69 / flatten=0 / unknown=0. Soft `risk_exceeds_1pct` warnings at resume open; hard constitution on the receipt is 0.

S5 started on the same engine and immediately HOLD-collapsed (`occupancy=1.0`, `policy_sample 0`). Out of scope. Epoch freeze + `history_unavailable` ended the plant. `is_birth_exit_sufficient=False`.

## Birth

Milestone stays **OPEN**. Do not promote S1–S4 to Birth exit. Next live exam is Stage-5 holdout + fitness vector on this tape.

**Risk Safety Review** (Score: 8/10)

- Fail-closed: Yes (S4 AND-gates + verified receipt; S5 honest fail)
- REAL mode stricter: n.v.t. (SIM / certified-shadow, no REAL)
- ConstitutionViolation event: soft warnings logged; hard count 0 on receipt
- Logging + traceability: Yes (B2 snapshot, resume log, HUD monitor)

Change can go through. Floors untouched. Stops ≤ 1%.
