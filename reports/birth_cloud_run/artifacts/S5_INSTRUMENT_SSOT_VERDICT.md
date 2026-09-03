# S5 instrument SSOT verdict — Gate 2

**Date:** 2026-09-03
**Engine:** BRO-v2 / `BirthPhaseEngineV2`
**training_mode:** certified
**practice_mode:** False
**REAL:** no
**LUMINA_FABRIC_SUPERVISOR:** 0
**Verdict:** `S5_HONEST_FAIL_BIRTH_OPEN`

This is not REAL-ready. This is not Perfect Birth. This is not the certificate 0.48 WR wall.
S5 failed on measured numbers after gym fills settled at MES $5.
Birth stays OPEN. No fitness vector was written.

---

## Exam table

| Field | Value |
|---|---|
| engine | BRO-v2 / BirthPhaseEngineV2 |
| training_mode | certified |
| instrument SSOT shipped | yes — `birth_gym_point_value()` = MES $5; tape stays `NQ SEP26` |
| floors | S5 50 / edge -0.03 / sharpe -2.0 / dd 25 / equity 50000 / policy 150 / occ 0.25–0.75 unchanged |
| tape | reused cached fixture (`reused_manifest=true`); hashes `7e86c2bb1c71d514` / `2466d3f41d60657b`; seed 20260902; 213,120 ticks; 88 days; 3 holdout regimes (`NEUTRAL`, `TREND_DOWN`, `TREND_UP`) |
| S1–S4 receipts verified certified | True / True / True / True (`verify_stage_pass_receipt(..., training_mode=certified)` → `ok`) |
| S4 occupancy seeded into S5 | **0.4999690613204628** (`occupancy_seed_source=s4_receipt`) |
| S5 stage_trades / policy / plant | stall **1124** / **1124** / **0** (last live exam t=724) |
| S5 occupancy | **0.2798** in [0.25, 0.75]; control_flat 0.262 |
| S5 skill_wr / p_ft / edge | skill_wr **0.3390** vs p_ft **0.3212**; `edge_vs_first_touch=+0.0178` (clears −0.03) |
| S5 oos_sharpe / oos_dd_pct | last live t=724: **oos_sharpe=-4.963946060463218** ≤ −2.0; **oos_dd=171.97016780951932** unit=**percent-of-50k**. Full series n=1124: sharpe −4.972 / dd 266.90 |
| ledger point_value | **5.0 on all 1124** (0 at NQ $20) |
| max \|close pnl\| on S5 | **$501.25** (`$500 + 1 tick`); 0 closes with \|pnl\| > 501.25; qty=1 on all 1124 |
| closes at exactly ±$501.25 | **498 / 1124 = 44.3%** (PR #12: 731 / 996 = 73.4%) |
| non-cap \|pnl\| median | **$307.30** (MES geometry, not the cap) |
| gap closes at cap | **232 / 234** — $500 is the GAP backstop |
| force_open / plant on S5 | **force_open=0**. **plant=0**. last_mode **FORCE_EXIT**. force_hold=49033 / force_flat=18602 / force_exit=259 |
| s3_inband_explore / tax_steps on S5 | **0** / **241** |
| pass_reason | `foundation_fail:oos_sharpe=-4.963946060463218 <= -2.0;oos_dd=171.97016780951932 > 25.0 settle=ok` |
| S5 receipt verified certified | False (no pass receipt written) |
| fitness vector present + checksum ok | False (not written — S5 did not pass) |
| is_birth_exit_sufficient | False (`missing=('foundation_fitness_vector', 'foundation_five_receipts_v2')`) |
| verdict | `S5_HONEST_FAIL_BIRTH_OPEN` |

---

## What shipped

Birth gym fills settle at MES $5 even when the certified tape is labeled NQ.

```
lumina_core/birth/notional_cap.py  birth_gym_point_value / birth_fill_pnl_usd
lumina_core/rl/gym_environment.py  fill_point_value()  (birth → MES $5)
lumina_core/rl/gym_environment_step.py  birth branch uses birth_fill_pnl_usd
```

`--force` (clean plant — prior S5 book was NQ $20). Same tape. S1–S4
re-verified certified under MES $5 fills before S5 was scored.
Envelope not disabled. No `S5_IDLE_REGIMES`. No `MAX_PLANT`.
`force_qty_one=True`. Cap + one tick unchanged.

---

## This shadow (same tape)

| Stage | verified certified | trades | policy / plant | occupancy | edge | pass_reason |
|---|---|---|---|---|---|---|
| S1 | True | 150 | 150 / 0 | 0.0 (not graded) | −0.026 | `foundation_pass` / verify `ok` |
| S2 | True | 250 | 239 / 11 | 0.337 in [0.30, 0.70] | −0.023 | `foundation_pass` / verify `ok` |
| S3 | True | 400 | 400 / 0 | 0.279 in [0.25, 0.75] | +0.072 | `foundation_pass` / verify `ok` |
| S4 | True | 151 | 150 / 1 | **0.500** in [0.25, 0.75] | +0.166 | `foundation_pass` / verify `ok` |

S5 last live (`birth.stage.not_passed` t=724, settle=ok) is the exam.
Stall HUD `oos_*=None` / `days=0` is the same empty-snapshot artifact as PR #10/#11/#12.

| Field | Value |
|---|---|
| oos_edge | **+0.018** clears −0.03 |
| oos_dd_pct | **171.97** unit=percent-of-50k (full-series 1124: 266.90) |
| oos_sharpe | **−4.96** ≤ −2.0 (full-series −4.97) |
| occupancy | 0.280 in [0.25, 0.75] |
| constitution hard | 0 |
| median_loss_r | 1.013 ≤ 1.5 |
| plant/policy | **0 / 1124** |

---

## Honest blockers (do not paper over)

1. `oos_sharpe=-4.963946060463218 <= -2.0` — full holdout series, qty=1, MES $5 fills, cap as backstop.
2. `oos_dd=171.97016780951932 > 25.0` — unit proven percent-of-50k. Peak-to-trough
   on the S5 USD series starting at $50k. Not 5757-as-dollars. Not a floor to raise.
   172% of $50k ≈ $86.0k peak-to-trough.

The 4× instrument lie is gone. π* still beats first-touch (`+0.018`) and still
loses dollars in process-R on the reserved regimes. That is a real S5 fail.

No second invention. No floor change. No stub vector. No `S5_IDLE_REGIMES`.

---

## Tests

`pytest tests/birth/test_s5_notional_cap.py tests/birth/test_s5_shared_imu.py tests/birth/test_s5_dd_yardstick.py tests/birth/test_foundation_loopholes.py tests/birth/test_foundation_pass.py tests/birth/test_birth_cloud_runner.py -q --timeout=60` → **88 passed**
`pytest tests/birth/ tests/test_m5_residual_loc.py -q --timeout=60` → **1352 passed, 3 skipped**.
ruff + mypy --strict + pyright clean on touched modules.
`LUMINA_FABRIC_SUPERVISOR=0`.
