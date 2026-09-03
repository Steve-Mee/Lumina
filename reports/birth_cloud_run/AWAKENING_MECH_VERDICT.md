# AWAKENING MECHANISM VERDICT

**Overall:** `GRIND_REGRESS_AWAKENING_OPEN` + `MECH_MEASURE_ONLY`

Gate 0 split on PR #17 grind JSONL (A n=218, B n=171, same zip
`8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03`).
Gate 1 = **no law**. Gate 2 skipped. PR #17 grind numbers stand.

| Flag | A | B |
|------|---|---|
| `P_PARTICIPATION` | False (union 0.312 / dollar 0.402) | False (0.123 / 0.226) |
| `E_EDGE` | **True** (policy n=150, mean_r=−0.211) | **True** (mean_r=−0.329) |
| `W_WIRE` | False (envelope + chatter + refractory live) | False |
| `BOTH_BAD` | False | False |

Policy-only is −EV on the longer clock. Plant/FORCE_OPEN closes are worse (−$187 mean on A) but they are not the alibi. Hiding REGRESS behind a FORCE_OPEN cap would be a failed ticket.

| Leg | class | n | policy n | policy mean $ | plant n | plant mean $ |
|-----|-------|---|----------|---------------|---------|--------------|
| A | `GRIND_REGRESS` | 218 | 150 | −23.87 | 68 | −186.92 |
| B | `INCONCLUSIVE` | 171 | 150 | −26.91 | 21 | −168.67 |

- Birth receipts / fitness `707b5ab9d6b9af96`: **untouched**.
- Floors: PR #14. No `S5_IDLE_REGIMES`. MES $5. qty=1.
- `is_birth_exit_sufficient`: **True** as PR #14 left it.
- Evolution Proof `passed=True`: **not stamped** (overall ≠ STABLE; n=218 < 500; lift negative).
- REAL: **no**.
- Schema only: `force_open` on `close_ledger_row` so the next live tape splits the same way. Not a second law.
