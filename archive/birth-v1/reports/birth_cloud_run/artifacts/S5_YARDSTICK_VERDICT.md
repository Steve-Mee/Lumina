# S5 yardstick verdict — Gate 0 + Gate 1

**Date:** 2026-09-02
**Engine:** BRO-v2 / `BirthPhaseEngineV2`
**training_mode:** certified
**practice_mode:** False
**REAL:** no
**LUMINA_FABRIC_SUPERVISOR:** 0
**Verdict:** `S5_HONEST_FAIL_BIRTH_OPEN`

This is not REAL-ready. This is not Perfect Birth. This is not the certificate 0.48 WR wall.
S5 failed on measured numbers after the corrected yardstick. Birth stays OPEN. No fitness vector was written.

---

## Exam table

| Field | Value |
|---|---|
| engine | BRO-v2 / BirthPhaseEngineV2 |
| training_mode | certified |
| gate 0 shipped | yes + classification **REAL** |
| gate 1 shipped | yes — `lumina_core/birth/force_open_plant.py` `ForceOpenChatterBound` + `decide_stage2_participation(..., force_open_refractory=)` in `stage2_participation_envelope.py` |
| floors | S5 50 / edge -0.03 / sharpe -2.0 / dd 25 / equity 50000 / policy 150 / occ 0.25–0.75 unchanged |
| tape | regenerated same `CloudFixtureSpec` seed 20260902; hashes `7e86c2bb1c71d514` / `2466d3f41d60657b` (match PR #10) |
| S1–S4 receipts verified certified | True / True / True / True |
| S5 stage_trades / policy / plant | last live 781 / ≥150 (edge scored) / (stall 950 / 242 / 708) |
| S5 occupancy | 0.72 (in exam band 0.25–0.75; parked on controller hi) |
| S5 skill_wr / p_ft / edge | last live `oos_edge=-0.10125` ⇒ skill_wr ≈ 0.220 vs p_ft=0.3212 |
| S5 oos_sharpe / oos_dd_pct | last live sharpe not in blockers (t=91 printed **+1.86**; full-series **−0.467** — both clear −2.0). last live `oos_dd=628.4596614187112` unit=**percent-of-50k** |
| participation_passthrough / force_open on S5 | last_mode PASSTHROUGH / force_open **12719** (stall). Refractory active — not same-bar chatter. S4 FORCE_OPEN stayed **1**. |
| s3_inband_explore / tax_steps on S5 | 0 / 607 |
| pass_reason | `foundation_fail:oos_edge=-0.10125243257072061 < -0.03;oos_dd=628.4596614187112 > 25.0 settle=ok` |
| S5 receipt verified certified | False (no pass receipt written) |
| fitness vector present + checksum ok | False (not written — S5 did not pass) |
| is_birth_exit_sufficient | False |
| verdict | `S5_HONEST_FAIL_BIRTH_OPEN` |

---

## Gate 0 (shipped)

Classification of the PR #10 `5757.72` figure: **REAL**. See `S5_DD_YARDSTICK_AUDIT.md`.

```
(50000 − (50000 − 2878857.767096)) / 50000 × 100 = 5757.715534191989
```

Unit of one increment = USD (`sim_runner.py:653-659`). Equity = 50000. A = B = C on that series. Formula fixed to peak-to-trough anyway (V-shape would have under-reported). Floors not raised.

After the fix, the **existing** PR #10 snapshot still fails `policy_sample 149 < 150` and `oos_dd=5757.72 > 25`. No vector from that snapshot.

---

## Gate 1 (indicated and shipped)

PR #10 cause was envelope plant spray (FORCE_OPEN=6085, plant=384, policy=149, occ in-band). One bound: after a FORCE_OPEN plant settles, no second FORCE_OPEN until min-dwell bars elapse. In-band stays PASSTHROUGH. No `MAX_PLANT` cap. No `S5_IDLE_REGIMES`.

S5 skill clock: volume 50 is not terminal while policy < 150 and idle/PASSTHROUGH can still grow the sample. Live proof: S5 continued past 50 to 781 with edge scored (policy ≥ 150).

S4 replica: plant stayed **1**, FORCE_OPEN did not explode (PR #10 S4 plant=1 preserved).

---

## This shadow (same tape)

`--force` (workspace had no S4-passed checkpoint; S3-era / empty state). Fixture hashes match.

| Stage | verified certified | trades | policy / plant | occupancy | edge | pass_reason |
|---|---|---|---|---|---|---|
| S1 | True | 150 | 150 / 0 | 0.0 (not graded) | −0.060 | `foundation_pass settle=ok` |
| S2 | True | 250 | 86 / 164 | 0.627 in [0.30, 0.70] | n/a | `foundation_pass settle=ok` |
| S3 | True | 400 | 150 / 250 | 0.719 in [0.25, 0.75] | +0.255 | `foundation_pass settle=ok` |
| S4 | True | 151 | 150 / 1 | **0.476** in [0.25, 0.75] | +0.286 | `foundation_pass settle=ok` |

S5 last live (`birth.stage.not_passed` t=781, settle=ok):

| Field | Value |
|---|---|
| oos_edge | −0.10125 < −0.03 |
| oos_dd_pct | **628.46** unit=percent-of-50k (full-series 950 closes: 628.72) |
| oos_sharpe | full-series −0.467 > −2.0 (clears) |
| occupancy | 0.72 in [0.25, 0.75] |
| constitution hard | 0 |
| median_loss_r | 1.059 ≤ 1.5 |

Holdout PnL is still a plant-heavy book (stall plant=708 vs policy=242). FORCE_OPEN no longer same-bar chatters (refractory HUD true) but occupancy sat on 0.72 so the envelope legally re-armed after each min-dwell. That is not a disabled envelope. The exam is the holdout path: **628% of $50k** and **oos_edge −0.101**.

Stall HUD `median_loss_r=None` / `oos_*=None` / `days=0` is the same empty-snapshot artifact as PR #10. Last live `not_passed` is the exam.

---

## Honest blockers (do not paper over)

1. `oos_edge=-0.10125 < -0.03` — policy sample cleared 150; the pilot lost to first-touch on the holdout.
2. `oos_dd=628.46 > 25` — unit proven percent-of-50k. Peak-to-trough on the S5 USD series. Not 5757-as-dollars. Not a floor to raise.

No second invention. No floor change. No stub vector. No `S5_IDLE_REGIMES`.

---

## Tests

`pytest tests/birth/ tests/test_m5_residual_loc.py -q --timeout=60` → 1333 passed, 3 skipped.
ruff + mypy --strict + pyright clean on touched modules.
`LUMINA_FABRIC_SUPERVISOR=0`.
