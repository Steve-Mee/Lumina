# S5 instrument SSOT audit — Gate 2

**Date:** 2026-09-03
**Engine:** BRO-v2 / `BirthPhaseEngineV2`
**training_mode:** certified
**practice_mode:** False
**REAL:** no

PR #12 booked 731 / 996 S5 closes at exactly ±$501.25 because the gym
settled `NQ SEP26` at $20 while geometry and the exam cap used MES $5.
This shadow collapses fill dollars to MES $5. The tape stays NQ-priced
(same hashes). The $500 / 1%-of-equity clip stays a GAP / equity backstop.

Floors are not raised.

---

## Two living instruments → one

| Layer | PR #12 (live) | This shadow |
|---|---|---|
| Tape symbol | `NQ SEP26` | `NQ SEP26` (same) |
| Tape hashes | `7e86c2bb1c71d514` / `2466d3f41d60657b` | **same** (`reused_manifest=true`) |
| Geometry PV | MES $5 | MES $5 |
| Cap math PV | MES $5 | MES $5 |
| Gym fill PV | **NQ $20** (`valuation_engine`) | **MES $5** (`birth_gym_point_value`) |
| Ledger `point_value` | 20 on all 996 | **5.0 on all 1124** |
| Closes at exactly ±$501.25 | **731 / 996 = 73.4%** | **498 / 1124 = 44.3%** |
| Closes with \|pnl\| < $400 | minority | **555 / 1124 = 49.4%** |
| max \|pnl\| | $501.25 | $501.25 (0 over cap) |
| qty | 1 | 1 |

SSOT: `lumina_core/birth/notional_cap.py` `birth_gym_point_value` /
`birth_fill_pnl_usd`. Live gym: `RLTradingEnvironment.fill_point_value`
+ `gym_environment_step` birth branch. Non-birth NQ still uses valuation $20.

---

## Series n / sum / min / max / mean

| Field | PR #12 S5 (996, NQ $20 + cap) | This shadow S5 (1124, MES $5 + cap) |
|---|---|---|
| n | 996 | **1124** |
| sum | −131,009.46 | **−134,441.72** |
| min | −501.25 | **−501.25** |
| max | +501.25 | **+501.25** |
| mean | −131.54 | **−119.61** |
| median | 731 at exactly ±501.25 | **−307.27** (typical MES geometry, not the cap) |

A 0.268% geometry stop at ~$23k × MES $5 ≈ $308. That is now the median
non-cap close. The same stop at NQ $20 was ~$1,133 and sat on the cap.

---

## Cap is a backstop (not the typical close)

| Population | n | at ±$501.25 |
|---|---|---|
| All S5 closes | 1124 | 498 (44.3%) |
| `gap=True` | 234 | **232** (99.1%) — GAP backstop |
| `gap=False` | 890 | 266 (29.9%) — 1% equity backstop on wide marks |
| Non-cap closes | 626 | 0 |
| Non-cap \|pnl\| | 626 | min $2.02 / median **$307.30** / max $483.21 / mean $262.56 |

Reasons: stop 636 / time_stop 256 / target 232 / flatten 0.
Cap-hits by reason: stop 266 / target 223 / time_stop 9.
All 232 gap-at-cap winners are +$501.25; all 266 non-gap-at-cap are −$501.25.

The remaining cap mass is the **1% of $50k** backstop on marks that travel
past geometry (target 0.483% × high NQ print × $5 > $500; stop blow-through
without a segment-break flag). It is not the 4× NQ/$20 lie. 0 closes book
above $501.25.

---

## Worst 5 closes (persisted `close_ledger`)

All: `qty=1`, `cap_usd=500`, `point_value=5.0`, `plant=False`.
Equity column is the exam yardstick (`S5_DD_EQUITY_USD=50000`).

| pnl | qty | pv | entry | risk_usd | trade_r | reason | gap |
|---|---|---|---|---|---|---|---|
| −501.25 | 1 | 5 | 22245.00 | 298.12 | −1.681 | stop | True |
| −501.25 | 1 | 5 | 32596.55 | 436.85 | −1.147 | stop | False |
| −501.25 | 1 | 5 | 28017.25 | 375.48 | −1.335 | stop | True |
| −501.25 | 1 | 5 | 23032.81 | 308.68 | −1.624 | stop | False |
| −501.25 | 1 | 5 | 22263.62 | 298.37 | −1.680 | stop | False |

Intended risk is MES geometry (~$300–$440). Booked mark hits the $500
backstop. A 1-lot NQ $20 fill of the same % move is not in this book.

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

## Exam dollars after the collapse

Last live (`birth.stage.not_passed` t=724, settle=ok):

- `oos_sharpe=-4.963946060463218` ≤ −2.0
- `oos_dd=171.97016780951932` unit=percent-of-50k > 25
- Full series n=1124: sharpe −4.972 / dd 266.90 (same unit)

PR #12 last live: sharpe −4.52 / dd 219.42. Collapsing PV does **not**
invent a pass. Sharpe is mostly scale-invariant once the 4× lie is gone;
DD is still a real process path on $50k. Floors not raised.
