# S3 live exam verdict

`S3_HONEST_FAIL_BIRTH_OPEN` — IMU split is live. Stage-3 did **not** write a `foundation_v2` receipt. Birth stays OPEN.

| Field | Value |
|---|---|
| branch / commit | `cursor/s3-live-exam-363f` (envelope follow-up `9248990`; this verdict on PR #7) |
| S3 IMU split present | **yes** — `POLICY_EDGE_MIN_TRADES=150` `lumina_core/birth/foundation_metrics.py:39`; volume=`int(trades)` `curriculum_pass.py:100` + `skill_trades=policy_trades` `:102–107` / `:162`; S3 `policy_sample` before edge `foundation_pass.py:91–92` then `:140` |
| tape | **regenerated** (workspace cache missing) same generator/params: `source=synthetic_cloud_fixture` seed `20260902` hashes `7e86c2bb1c71d514` / `2466d3f41d60657b`, 213,120 ticks, 88 calendar days, 3 holdout regimes |
| S1 receipt verified | **True** certified (`reports/birth_cloud_run/s1_receipt.json`, trades=150, schema=`foundation_v2`) |
| S2 receipt verified | **True** certified (`reports/birth_cloud_run/s2_receipt.json`, trades=250, occupancy=0.590 in [0.30, 0.70], schema=`foundation_v2`) |
| S3 stage_trades | **524** (live ≥ 400) |
| S3 policy_trades / plant_trades | **0 / 524** (first plant); after resume plant counter reset, still **policy=0**, **0 new closes** |
| S3 occupancy | **0.578** first plant (in [0.25, 0.75]); **0.639** at resume exit (still in band) |
| S3 skill_wr / p_ft / edge | skill_wr=**0.0** · p_ft=**0.3395** · edge=**None** (not `-0.338`, not `0 − p_ft`) |
| pass_reason | `foundation_fail:policy_sample 0 < 150` (at trades≥400, `settle=ok`). Resume also emitted `foundation_fail:settlement_share=0.00;policy_sample 0 < 150` after close-SSOT reset. |
| S3 receipt verified certified | **False** (no S3 receipt) |
| follow-up applied | **envelope** (one follow-up + one resume rerun; increment/attribution not applied) |
| is_birth_exit_sufficient | **False** (two receipts only; no S3–S5; no fitness vector) |
| verdict | **S3_HONEST_FAIL_BIRTH_OPEN** |

## Gate A — law is live

Replica `total=729 policy=0 p_ft=0.338 occupancy=0.576` → `foundation_fail:policy_sample 0 < 150 settle=ok`.
Does **not** emit `trades 0 < 400` or `edge=-0.338`. `edge is None`.
`occupancy_control_over` still exists (`stage2_participation_envelope.py`); not rewritten.
Floors unchanged: `S3_MIN_TRADES=400`, `S3_EDGE_MIN=-0.05`, `S3_OCCUPANCY=0.25–0.75`, `POLICY_EDGE_MIN_TRADES=150`. `practice_mode=False`. No REAL.

This session’s live S2 receipt still verifies certified (occupancy 0.590).

## Gate B2 — first certified-shadow plant (`--force`, dirty workspace)

Workspace checkpoint/tape were missing → `--force` (S1+S2 re-passed in ~1 min).

At `stage_trades=400+`:

```
birth.stage.not_passed stage=stage3_mixed trades=400 blockers=foundation_fail:policy_sample 0 < 150 settle=ok
```

Snapshot `reports/birth_cloud_run/s3_live_exam_b2_pre_followup.json` (trades=524):

| counter | value |
|---|---|
| stage_trades | 524 |
| stage_policy_trades | 0 |
| stage_plant_trades | 524 |
| occupancy | 0.5775 |
| occupancy_control_flat | 0.278 |
| participation_force_open | 1076 |
| participation_force_hold | 3581 |
| participation_force_flat | 20509 |
| participation_force_exit | 149 |
| participation_passthrough | **None (not dumped)** |
| participation_last_mode | FORCE_FLAT |
| constitution hard | 0 |
| pass_reason | `foundation_fail:policy_sample 0 < 150` |

Never `trades 0 < 400` while live volume ≥ 400.
Never `edge=-0.338` from wr=0.

B2 condition matched: `policy_trades==0` AND `stage_trades>=400` AND occupancy in band → follow-up 1.

## Follow-up 1 — envelope application (bands unchanged)

Rolling IMU 0.278 vs S3 `band_lo=0.28` kept FORCE_FLAT/FORCE_OPEN owning entries while **cumulative exam** occupancy 0.578 was in-band. Controller bands 0.28–0.72 and exam bands 0.25–0.75 were **not** changed.

Fix: `decide_stage2_participation(..., cumulative_in_band_passthrough=True)` on mixed/S3. When **cumulative** flat is inside controller bands → `PASSTHROUGH` / `exam_cumulative_in_band`. S2 dual IMU unchanged. `participation_passthrough` plumbed to stage loop + progress.

## Rerun (`--resume` from S3 checkpoint)

Envelope law took the book:

- First minute: `participation_passthrough=10000`, `last_mode=PASSTHROUGH`, `force_open=0`, `force_flat=0`, `occupancy_control_flat=0.591`.
- Policy produced **0 closes**. `stage_trades` stuck at 524. Occupancy drifted 0.577 → 0.639 (empty HOLD).
- Resume reset plant/policy/close counters → extra blocker `settlement_share=0.00` / `settlement SSOT missing`.
- Stagnation expand on the bounded certified fixture → `history_unavailable` (`birth.fail_closed.host_stop reason=history_unavailable`). Engine `status=history_unavailable`, `birth_exit_ok=False`.

So after the allowed envelope follow-up, the measured blocker is still **`policy_sample 0 < 150`** with volume in-band. This is **not** attribution stickiness (no new closes to mis-tag) and **not** a missing increment on a close. Policy under PASSTHROUGH did not enter.

## P0 (next session — no loopholes)

Do not lower floors. Do not count plant as skill.

1. **S3 PASSTHROUGH HOLD**: after exam-in-band PASSTHROUGH, PPO produced 0 entries / 0 closes across ~40k signals, then fail-closed `history_unavailable` on the finite tape. Need a skill-entry path that is still PASSTHROUGH (not FORCE_OPEN plant, not floor changes).
2. **Resume settlement SSOT**: checkpoint restore keeps `stage_trades` but zeros close-reason / policy / plant counters, so a legal resume emits `settlement_share=0.00` until new closes exist.
3. Follow-ups 2–3 (increment / attribution) were **not** indicated: zero new closes.

## Gate C

Not reached. S3 alone is not Birth exit. `is_birth_exit_sufficient()=False` (missing `foundation_five_receipts_v2` + `foundation_fitness_vector`).

## Capital / autonomy / experiment

SIM / certified-shadow only. `LUMINA_FABRIC_SUPERVISOR=0`. No `container.start()`. No NT. No live broker. Stops ≤ 1%. Organism continued S1→S2→S3 without human restart; crash-resume path used for the envelope rerun. Same tape. Honest fail. No loopholes.

## Risk Safety Review (Score: 8/10)

- Fail-closed: **Ja** — over-band still FORCE_OPEN; bounded tape → `history_unavailable`; no S3 receipt.
- REAL mode stricter: **n.v.t.** (SIM / certified-shadow, no REAL).
- ConstitutionViolation event: soft `risk_exceeds_1pct` only; hard constitution = 0.
- Logging + traceability: **Ja** — live counters + pass_reason + participation dump.

Waarschuwing: PASSTHROUGH can leave a HOLD policy with volume already in-band and no skill sample.

Conclusie: envelope follow-up mag door (bands/floors onaangeroerd). S3 receipt niet claimen.
