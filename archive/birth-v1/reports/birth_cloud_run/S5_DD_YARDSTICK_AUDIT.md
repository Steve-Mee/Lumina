# S5 DD yardstick audit (Gate 0)

**Date:** 2026-09-02
**Engine:** BRO-v2 / `BirthPhaseEngineV2`
**training_mode:** certified
**SSOT series:** `reports/birth_cloud_run/artifacts/lumina_birth_checkpoint.json` → `stage_metrics.stage_val_pnl`
**Live print:** `oos_dd=5757.715534191989` at `trades=532` (`s5_live_exam.log`)

This is math, not a floor move. `S5_DD_EQUITY_USD=50000` and `S5_DD_MAX_PCT=25` stay pinned.

---

## Call site that wrote 5757.72

| Step | File:line | What |
|---|---|---|
| 1 | `lumina_core/birth/sim_runner.py:653-659` | Each close appends `rl_close_accounting_net_usd` (USD) to `pnl_series` |
| 2 | `lumina_core/birth/stage_loop_rollout_cycle.py:263` | `stage_val_pnl.extend(rollout.pnl_series)` |
| 3 | `lumina_core/birth/stage_loop_iteration_pass.py:23` | `risk_metrics_from_pnl(self.stage_val_pnl)` |
| 4 | `lumina_core/birth/runway.py:134` | `max_drawdown_pct(pnl_series, equity=S5_DD_EQUITY_USD)` |
| 5 | `lumina_core/birth/certificate_evaluator.py` `_max_drawdown_pct` | Was peak-to-END; now peak-to-trough. Same number on this path. |
| 6 | `lumina_core/birth/stage_loop_iteration_pass.py:183-186` | S5 `oos_dd_pct = stage_val_max_dd` |
| 7 | `lumina_core/birth/curriculum_pass.py:188-193` | `_resolve_s5_holdout_oos` (uses same series if needed) |
| 8 | `lumina_core/birth/foundation_pass.py:180-181` | `oos_dd={snap.oos_dd_pct} > 25.0` |

Default `stage_val_max_drawdown_pct=100.0` in `curriculum_pass.py` was **not** used. 5757.72 is computed.

---

## PnL series (exact holdout / S5 window)

Live blocker printed at **532** closes. Checkpoint later has **533**.

| Field | 532 (live 5757.72) | 533 (checkpoint) |
|---|---|---|
| n | 532 | 533 |
| sum | −2,878,857.7670960003 | −2,880,869.5270446707 |
| min | −1,053,820.7964710598 | −1,053,820.7964710598 |
| max | +339,416.2 | +339,416.2 |
| mean | −5,411.38678025564 | −5,405.008493517205 |
| unit of one increment **before fix** | **USD** (`rl_close_accounting_net_usd`) | same |
| equity passed in | 50,000.0 (`S5_DD_EQUITY_USD`) | 50,000.0 |

Typical increment ~−$526 (MES $5 × ~0.5% of NQ price). Outliers are full-notional USD closes (e.g. −$1,053,820), not points stuffed into the percent field.

---

## A / B / C / D

| Field | 532 (live) | 533 (checkpoint) |
|---|---|---|
| A peak-to-end % (old fn) | **5757.715534191989** | 5761.739054089329 |
| B peak-to-trough % on $50k after unit fix | **5757.715534191989** | 5761.739054089329 |
| C dollar trough / 50000 × 100 | **5757.715534191989** | 5761.739054089329 |
| D converter used | pnl already USD — `sim_runner.py:653-659`; identity. `MES_POINT_VALUE_USD=5.0` is geometry SSOT, not applied again. | same |

B equals C because increments are already USD. B equals A because the path never made a new high above $50k and **ended at the trough**.

V-shape `[-5000, -5000, +8000]` proves the old formula is still a defect: peak-to-end ≈ 4%, true trough = 20%. Fixed. This live series simply does not recover.

---

## Classification

**REAL**

5757.72 is percent-of-$50k, not dollars stuffed into a percent field (that identity is `5757.72 / 50000 × 100 = 11.515%`, which would **pass** 25). It is not a currency mix (increments are USD). It is not produced by peak-to-end vs peak-to-trough (A = B on this path).

### 5757.72 explained (one sentence + arithmetic)

Peak never left `$50,000`. Sum of the 532 USD closes is `−2,878,857.767096`. Peak-to-end = peak-to-trough =

```
(50000 − (50000 − 2878857.767096)) / 50000 × 100
= 2878857.767096 / 50000 × 100
= 5757.715534191989
```

which matches the live `oos_dd=` string exactly.

The recorded holdout path lost ~57.58× the $50k yardstick. Worst-case 533 × $500 (1% of $50k) cannot do that. The 1% clip is 1% of **price** (and some FORCE_OPEN plants settled at full-notional USD). Envelope plant spray: FORCE_OPEN=6085, plant=384, policy=149, occ ended in-band 0.716.

---

## Gate 0 fix (formula only)

- `_max_drawdown_pct` / `max_drawdown_pct` / `risk_metrics_from_pnl` now use running peak-to-trough %.
- `_peak_to_end_drawdown_pct` kept as a private diagnostic.
- Floors unchanged. 5757 was not clamped to 25.
- Re-score of the **existing** S5 snapshot (`evaluate_foundation_pass(STAGE5_PROBE_HANDOFF)`):
  - `policy_sample 149 < 150` (do not round)
  - `oos_dd=5757.715534191989 > 25.0` (unit = percent-of-50k, proven)
  - `oos_sharpe` on the same 532 USD series = **−1.382** (clears −2.0). Live early print −2.30 was t=106, then left the blockers.
- Gate 0 alone does **not** pass S5. No fitness vector from this snapshot.

---

## Gate 1 decision

Indicated. Corrected yardstick still fails DD **and** skill. Measured cause is envelope plant spray (FORCE_OPEN chatter 6085 → 384 plant closes vs 149 policy). One bound: FORCE_OPEN refractory after a plant settles until min-dwell bars elapse (`force_open_plant.py` `ForceOpenChatterBound` + `decide_stage2_participation(..., force_open_refractory=)` at `stage2_participation_envelope.py`). In-band stays PASSTHROUGH. No `MAX_PLANT` cap. No `S5_IDLE_REGIMES`.

S5 skill clock: volume 50 is not terminal while policy &lt; 150, ticks remain, PASSTHROUGH, in-band, idle armed (`foundation_skill_clock.py`).

---

## Floors unchanged (grep proof)

```
lumina_core/birth/foundation_metrics.py
S5_DD_MAX_PCT = 25.0
S5_DD_EQUITY_USD = 50_000.0
S5_MIN_TRADES = 50
S5_EDGE_MIN = -0.03
S5_SHARPE_FLOOR = -2.0
POLICY_EDGE_MIN_TRADES = 150
```
