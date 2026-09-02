# S5 notional audit — Gate 0

**Date:** 2026-09-02
**Engine:** BRO-v2 / `BirthPhaseEngineV2`
**training_mode:** certified
**practice_mode:** False
**REAL:** no

This is the dump of the closes that printed −$1,053,820 under a “≤1%” constitution.
Floors are not raised. 628 is not clamped to 25.

PR #10 / PR #11 checkpoints persisted `stage_val_pnl` + `stage_val_r` only.
Per-close `qty` / `close_reason` / gap were **not** on disk. Reconstruction uses
`pnl`, `trade_r` (qty-normalized), instrument `NQ SEP26` (`valuation_engine` pv=$20),
and MES $5 geometry SSOT. The next shadow persists `close_ledger` (qty, cap_usd,
reason, gap, plant, entry, risk, point_value).

---

## Series n / sum / min / max / mean

| Field | PR #10 holdout (live 532 / ckpt 533) | PR #11 S5 (stall 950) |
|---|---|---|
| n | 532 (live `oos_dd=5757.72`) / 533 (checkpoint) | 950 |
| sum | −2,878,857.77 (532) / −2,880,869.53 (533) | −2,120,334.68 |
| min | **−1,053,820.7964710598** | −631,258.80 |
| max | +339,416.20 | +778,641.20 |
| mean | −5,411.39 (532) / −5,405.01 (533) | −2,231.93 |
| median | ~−$526 typical increment | median −211.80; median \|pnl\| 348.71 |
| `stage_val_r` of min | −157.36 | −81.93 |

SSOT: `git show 7dd4a69:reports/birth_cloud_run/artifacts/lumina_birth_checkpoint.json` (PR #10)
and `reports/birth_cloud_run/artifacts/lumina_birth_checkpoint.json` (PR #11, n=950).

---

## Counts \|pnl\| > 1k / 2k / 10k / 100k

| Threshold | PR #10 (533) | PR #11 (950) |
|---|---|---|
| \|pnl\| > 1,000 | 179 | 297 |
| \|pnl\| > 2,000 | 162 | 268 |
| \|pnl\| > 10,000 | 84 | 146 |
| \|pnl\| > 100,000 | 33 | 56 |

Typical cluster (\|pnl\| < 2,000) is the ~1R MES-$5 / dollar-cap population.
The mean and the min are a different population: gap marks at NQ $20.

---

## Worst 5 closes

Per-close qty/reason were **not persisted**. Columns marked `*` are reconstructed
from `pnl / trade_r` and `NQ SEP26` pv=$20. `qty*` ≈ implied_risk / (0.01 × 29539.75 × 20).

### PR #10 (min = −$1,053,820.80)

| pnl | qty* | pv | entry* | exit* | stop_pct* | risk_usd* | trade_r | reason* | gap* | plant/policy | equity |
|---|---|---|---|---|---|---|---|---|---|---|---|
| −1,053,820.80 | ~1.13 | 20 | ~33,491 | mark ≪ stop (through/gap) | ~0.01 | 6,698 | −157.36 | stop+gap | True | unknown (book plant-heavy) | not persisted |
| −317,728.88 | ~0.54 | 20 | ~15,886 | gap mark | ~0.01 | 8,690 | −36.56 | stop+gap | True | unknown | not persisted |
| −312,846.95 | ~0.61 | 20 | ~18,086 | gap mark | ~0.01 | 7,218 | −43.34 | stop+gap | True | unknown | not persisted |
| −303,852.68 | ~0.68 | 20 | ~20,170 | gap mark | ~0.01 | 6,397 | −47.50 | stop+gap | True | unknown | not persisted |
| −256,321.76 | ~0.64 | 20 | ~18,910 | gap mark | ~0.01 | 3,777 | −67.86 | stop+gap | True | unknown | not persisted |

`qty*` near 1.0 on the worst close: this is **not** a 10-lot 1R stop ($5k). It is a
~157R mark. 1% of $50k × 533 cannot print a single −$1,053,820 close.

### PR #11 S5 (oos_dd = 628.46 percent-of-50k at t=781)

| pnl | qty* | pv | entry* | exit* | stop_pct* | risk_usd* | trade_r | reason* | gap* | plant/policy | equity |
|---|---|---|---|---|---|---|---|---|---|---|---|
| −631,258.80 | ~1.30 | 20 | ~38,525 | gap mark | ~0.01 | 7,705 | −81.93 | stop+gap | True | unknown (stall plant 708 / policy 242) | not persisted |
| −572,933.80 | ~1.17 | 20 | ~34,706 | gap mark | ~0.01 | 6,941 | −82.54 | stop+gap | True | unknown | not persisted |
| −566,383.80 | ~1.02 | 20 | ~30,056 | gap mark | ~0.01 | 6,011 | −94.22 | stop+gap | True | unknown | not persisted |
| −546,833.80 | ~1.37 | 20 | ~40,345 | gap mark | ~0.01 | 8,069 | −67.77 | stop+gap | True | unknown | not persisted |
| −473,429.74 | ~1.55 | 20 | ~45,776 | gap mark | ~0.01 | 9,155 | −51.71 | stop+gap | True | unknown | not persisted |

Implied risk ≈ 1% of NQ price × $20 × ~1 lot. Realized is 50–94R. That is a gap
mark, not a clipped stop.

---

## force_qty_one live on shadow config

**True** — `lumina_core/rl/gym_stop_fill.py` `birth_force_qty_one` now returns True
for every birth regime (including `stage5_probe_handoff`).

Live assignment: `lumina_core/birth/sim_runner.py` `force_qty_one=bool(birth_force_qty_one(...))`.

Pre-fix: helper was stage1/trend only. S2–S5 could size `qty = 1 + clip(action[1],0,1)*9`
(envelope `qty_frac=0.15` → 2 lots; `qty_frac=1` → 10). `apply_force_open_stop`
already zeroed `qty_frac` on FORCE_OPEN; PASSTHROUGH/idle could still ship 2–10.

---

## Cap helper file:line

`lumina_core/birth/notional_cap.py` — `birth_close_cap_usd`, `clip_birth_exam_pnl`,
`birth_stop_pct_dollar_cap` (qty in the denominator).

Gym books via `lumina_core/rl/gym_birth_close.py` `book_birth_close_net_usd`.
Plant stop: `lumina_core/birth/force_open_plant.py` `apply_force_open_stop`.

Booked exam PnL = `sign(raw) * min(|raw|, cap + one_tick)` with
`qty_for_exam = 1` and `equity = S5_DD_EQUITY_USD` ($500 + $1.25).

---

## Classification

**Primary: GAP_BLOWTHROUGH**

Secondary contributors:

- **POINT_VALUE** — gym `valuation_engine.point_value("NQ SEP26") = $20`; constitution /
  dollar-cap math used MES $5. Same gap is 4× the MES yardstick.
- **QTY** — `force_qty_one` was False on S5. Worst closes reconstruct near qty=1
  (FORCE_OPEN already zeroed `qty_frac`); PASSTHROUGH could still be 2–10.
- **MARK_WITHOUT_STOP** — flatten / time-stop / FORCE_EXIT also mark at raw close.
- Not **EQUITY_NOT_50K** as primary (DD equity was $50k; plant dollar-cap used gym
  `_equity` without qty — contributor to stop *price*, not the $1M booked mark).
- Not **ACCOUNTING** (`pnl = pv × qty × Δprice` is the formula; the mark is the lie).

### −$1,053,820 explained (one sentence + arithmetic)

A 1-lot NQ $20 fill marked at a segment/regime gap ~157R from a ~1% stop
(`intended_risk ≈ 1,053,820.80 / 157.36 ≈ $6,698 ≈ 0.01 × $33,491 × $20`) booked
the raw close, not the stop: `157.36 × $6,698 ≈ $1,053,821`. A 1-lot $500 stop
cannot do that. 10 lots × $500 = $5,000 cannot do that. `plan_birth_exit_fill`
uses gap close as mark; exam PnL was not clipped to `min(1% price × $5 × qty, $500)`.

---

## Floors unchanged (grep proof)

```
lumina_core/birth/foundation_metrics.py
S5_DD_MAX_PCT = 25.0
S5_DD_EQUITY_USD = 50_000.0
```

`S5_MIN_TRADES=50`, `S5_EDGE_MIN=-0.03`, `S5_SHARPE_FLOOR=-2.0`,
`POLICY_EDGE_MIN_TRADES=150` unchanged.

---

## Gate 1 decision (from this dump + PR #11 counters)

After clipping the existing PR #11 950-close series to ±($500 + 1 tick):

- clipped `oos_dd` ≈ **191%** of $50k (still > 25) — honest process DD on a
  plant-heavy book, not a reason to raise the floor
- clipped Sharpe ≈ **−4.30** (fails −2.0 on that historical path)
- stall plant/policy = 708/242 = **2.93 ≥ 1.5**
- FORCE_OPEN = 12,719 while occ parked on 0.72

Gate 1 is **indicated** (Tooth A + Tooth B, one law): S5 bootstrapped from an
empty occupancy clock after S4 ended in-band at 0.476, then re-armed at
`band_hi + hyst=0.72`. No `S5_IDLE_REGIMES`. No `MAX_PLANT`.

If the live shadow after Gate 0+1 still has `oos_dd > 25` (percent-of-50k) or
`oos_edge < -0.03`, that is B2 — a real S5 fail.
