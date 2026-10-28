# S5 notional + re-arm verdict — Gate 0 + Gate 1

**Date:** 2026-09-02
**Engine:** BRO-v2 / `BirthPhaseEngineV2`
**training_mode:** certified
**practice_mode:** False
**REAL:** no
**LUMINA_FABRIC_SUPERVISOR:** 0
**Verdict:** `S5_HONEST_FAIL_BIRTH_OPEN`

This is not REAL-ready. This is not Perfect Birth. This is not the certificate 0.48 WR wall.
S5 failed on measured numbers after the notional cap and the occupancy seed/re-arm.
Birth stays OPEN. No fitness vector was written.

---

## Exam table

| Field | Value |
|---|---|
| engine | BRO-v2 / BirthPhaseEngineV2 |
| training_mode | certified |
| gate 0 shipped | yes + classification **GAP_BLOWTHROUGH** (secondary POINT_VALUE, QTY, MARK_WITHOUT_STOP) |
| gate 1 shipped | yes — Tooth A `lumina_core/birth/s5_occupancy_continuity.py:46` `apply_s5_occupancy_seed` at `stage_loop_session_phase_init.py:152`; Tooth B `stage2_participation_envelope.py:174-175` `in_band_seen` / `rearm_hysteresis=0.04` (re-arm at 0.76) |
| floors | S5 50 / edge -0.03 / sharpe -2.0 / dd 25 / equity 50000 / policy 150 / occ 0.25–0.75 unchanged |
| tape | reused cached fixture (`reused_manifest=true`); hashes `7e86c2bb1c71d514` / `2466d3f41d60657b`; seed 20260902; 213,120 ticks; 88 days; 3 holdout regimes (`NEUTRAL`, `TREND_DOWN`, `TREND_UP`) |
| S1–S4 receipts verified certified | True / True / True / True (`verify_stage_pass_receipt(..., training_mode=certified)` → `ok`) |
| S4 occupancy seeded into S5 | **0.4746419545071609** (`occupancy_seed_source=s4_receipt`) |
| S5 stage_trades / policy / plant | stall 996 / **996** / **0** (last live exam t=843, same plant=0 book) |
| S5 occupancy | **0.2799** in [0.25, 0.75]; control_flat 0.278 |
| S5 skill_wr / p_ft / edge | skill_wr **0.3695** vs p_ft **0.3212**; `edge_vs_first_touch=+0.0483` (clears −0.03; last live t=843 had no `oos_edge` blocker) |
| S5 oos_sharpe / oos_dd_pct | last live t=843: **oos_sharpe=-4.520616807327533** ≤ −2.0; **oos_dd=219.42404838146877** unit=**percent-of-50k**. Full series n=996: sharpe −4.841 / dd 262.02 (same unit, `max_drawdown_pct` peak-to-trough from $50k) |
| max \|close pnl\| on S5 | **$501.25** (`$500 + 1 tick`); 0 closes with \|pnl\| > 501.25; qty=1 on all 996 |
| participation_passthrough / force_open on S5 | passthrough **not persisted** on checkpoint persist (scorecard-only). **force_open=0**. last_mode **FORCE_HOLD**. force_hold=68967 / force_flat=26437 / force_exit=430 |
| s3_inband_explore / tax_steps on S5 | **0** / **157** |
| pass_reason | `foundation_fail:oos_sharpe=-4.520616807327533 <= -2.0;oos_dd=219.42404838146877 > 25.0 settle=ok` |
| S5 receipt verified certified | False (no pass receipt written) |
| fitness vector present + checksum ok | False (not written — S5 did not pass) |
| is_birth_exit_sufficient | False (`missing=('foundation_fitness_vector', 'foundation_five_receipts_v2')`) |
| verdict | `S5_HONEST_FAIL_BIRTH_OPEN` |

---

## Gate 0 (shipped)

Primary class of −$1,053,820: **GAP_BLOWTHROUGH**. See `S5_NOTIONAL_AUDIT.md`.

```
157.36 × $6,698 ≈ $1,053,821
$6,698 ≈ 0.01 × $33,491 × NQ $20 × ~1 lot
```

A 1-lot $500 stop cannot print that. 10 × $500 = $5,000 cannot. Exam PnL is now
`sign(raw) * min(|raw|, birth_close_cap_usd + one_tick)` with `force_qty_one=True`
and qty in the `apply_force_open_stop` dollar-cap denominator.

Live proof: max \|close\| = $501.25. Zero closes above the cap. Floors not raised.

---

## Gate 1 (indicated and shipped)

PR #11 plant/policy = 708/242 ≥ 1.5, FORCE_OPEN = 12,719, occ parked on 0.72,
S4 occ = 0.476 in-band. Historical clip of that book still ~191% DD. One law,
two teeth:

- Tooth A: S5 seeds occupancy from the verified S4 receipt when that occupancy
  is in [0.25, 0.75]. Does not invent 0.50. Missing/OOB still bootstraps.
- Tooth B: after in-band this stage, FORCE_OPEN only if `over_flat > 0.76`.
  First entry unchanged. S4 first FORCE_OPEN still fires.

Live proof: seed `s4_receipt` 0.4746, `occupancy_in_band_seen=True`,
**FORCE_OPEN=0**, **plant=0**, S4 plant stayed **1**. Occupancy ended 0.280
(in exam band). Idle explore 0 / tax 157. Envelope not disabled.
`cumulative_in_band_passthrough` not reverted. No `S5_IDLE_REGIMES`.
No `MAX_PLANT`.

`--force` (workspace had no S4-passed checkpoint). S1–S4 re-verified certified
under Gate 0+1 before S5 was scored.

---

## This shadow (same tape)

| Stage | verified certified | trades | policy / plant | occupancy | edge | pass_reason |
|---|---|---|---|---|---|---|
| S1 | True | 150 | 150 / 0 | 0.0 (not graded) | −0.046 | `foundation_pass settle=ok` |
| S2 | True | 250 | 234 / 16 | 0.366 in [0.30, 0.70] | −0.020 | `foundation_pass settle=ok` |
| S3 | True | 400 | 400 / 0 | 0.280 in [0.25, 0.75] | +0.139 | `foundation_pass settle=ok` |
| S4 | True | 151 | 150 / 1 | **0.475** in [0.25, 0.75] | +0.253 | `foundation_pass settle=ok` |

S5 last live (`birth.stage.not_passed` t=843, settle=ok) is the exam.
Stall HUD `median_loss_r=None` / `oos_*=None` / `days=0` is the same empty-snapshot
artifact as PR #10/#11.

| Field | Value |
|---|---|
| oos_edge | clears −0.03 (no blocker at t=843; stall HUD +0.048) |
| oos_dd_pct | **219.42** unit=percent-of-50k (full-series 996: 262.02) |
| oos_sharpe | **−4.52** ≤ −2.0 (full-series −4.84) |
| occupancy | 0.280 in [0.25, 0.75] |
| constitution hard | 0 |
| median_loss_r | 0.389 ≤ 1.5 |
| plant/policy | **0 / 996** (< 1.5; holdout is a policy book) |

Holdout PnL is all settled fills, clipped to the 1% cap. That is constitution,
not a policy-only hide.

---

## Honest blockers (do not paper over)

1. `oos_sharpe=-4.520616807327533 <= -2.0` — full holdout series, qty=1, cap live.
2. `oos_dd=219.42404838146877 > 25.0` — unit proven percent-of-50k. Peak-to-trough
   on the S5 USD series starting at $50k. Not 5757-as-dollars. Not a floor to raise.
   219% of $50k ≈ $109.7k peak-to-trough. 996 × $500 = $498k would still clear 25
   if the path never recovered; the path did not.

Policy beat first-touch (`+0.048`). The organism is no longer farming the holdout
from an empty occupancy clock. It still loses money in process-R on the reserved
regimes. That is a real S5 fail.

No second invention. No floor change. No stub vector. No `S5_IDLE_REGIMES`.

---

## Tests

`pytest tests/birth/test_foundation_loopholes.py tests/birth/test_s5_shared_imu.py tests/birth/test_s5_dd_yardstick.py tests/birth/test_s5_notional_cap.py tests/birth/test_foundation_pass.py -q --timeout=60`
`pytest tests/birth/ tests/test_m5_residual_loc.py -q --timeout=60` → **1347 passed, 3 skipped**.
ruff + mypy --strict + pyright clean on touched modules.
`LUMINA_FABRIC_SUPERVISOR=0`.
