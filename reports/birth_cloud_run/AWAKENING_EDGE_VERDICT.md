# AWAKENING EDGE VERDICT

**Overall:** `GRIND_REGRESS_AWAKENING_OPEN` + `EDGE_MEASURE_ONLY`

Gate 0 policy-only autopsy on PR #17 grind JSONL (A n=218 / policy 150, B n=171 / policy 150, same zip
`8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03`).
Gate 1 = **no law**. Gate 2 skipped. PR #17/#18 grind numbers stand.

| Flag | A | B |
|------|---|---|
| `G_MISWIRE` | False (Birth gym fill path live) | False |
| `G_MISLABEL` | False (0/35 targets have trade_r≤0) | False (0/25) |
| `T_TIME` | False (time_stop mean_r=+1.342) | False (+1.261) |
| `T_TARGET` | False (target mean_r=+1.212) | False (+1.198) |
| `T_NEUTRAL` | False (trends also −EV, n=16<25) | False (n=13<25, trend mean_r=−0.251) |
| `T_STOP_ONLY` | **True** (stop loss-share 0.988) | **True** (0.984) |

Policy targets print +R. Policy stops print −R. Time-stops book +R. The hole is **stop × NEUTRAL** volume at WR 0.34 / 0.28 — payoff ~1.21 : 1.04 cannot carry that miss rate. That is not a dead wire and not a lying ledger.

| Leg | class | n | policy n | policy mean $ | policy mean_r | policy target mean_r | policy stop mean_r |
|-----|-------|---|----------|---------------|---------------|----------------------|--------------------|
| A | `GRIND_REGRESS` | 218 | 150 | −23.87 | −0.211 | +1.212 | −1.038 |
| B | `INCONCLUSIVE` | 171 | 150 | −26.91 | −0.329 | +1.198 | −1.062 |

- Birth receipts / fitness `707b5ab9d6b9af96`: **untouched**.
- Floors: PR #14. No `S5_IDLE_REGIMES`. MES $5. qty=1.
- `is_birth_exit_sufficient`: **True** as PR #14 left it.
- Evolution Proof `passed=True`: **not stamped** (overall ≠ STABLE; n=218 < 500; lift negative).
- REAL: **no**.
- `EDGE_MEASURE_ONLY` + still-negative policy mean_r is the honest win for this ticket.
