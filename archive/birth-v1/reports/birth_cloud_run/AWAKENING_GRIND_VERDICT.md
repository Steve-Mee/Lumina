# AWAKENING GRIND VERDICT

**Overall:** `GRIND_REGRESS_AWAKENING_OPEN`

Frozen π* loaded from `reports/birth_cloud_run/artifacts/birth_exit_pi_star.zip`
(sha256 `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03`).
Evaluate-only. `train=False`. Optimizer steps 0. Envelope / FORCE_OPEN / MES $5 / clip / qty=1 unchanged.

This zip is a **certified S5-pass freeze** harvested before polish (Gate 1). PR #14 weight files were gone; this is not reconstructed PR #14 bytes. PR #14 receipts stay n=172 / fitness `707b5ab9d6b9af96`.

| Leg | class | n | wr | mean $ | sharpe | dd% of $50k |
|-----|-------|---|----|--------|--------|-------------|
| A seed 20260902 | `GRIND_REGRESS` | 218 | 0.34 | -74.73 | -4.783 | 33.982 |
| B seed 20260903 | `INCONCLUSIVE` | 171 | 0.28 | -44.32 | -3.865 | 15.343 |

**Why A is `GRIND_REGRESS`:** holdout exhausted, frozen loaded, n=218 ≥ 172, and all three ticket regress triggers fire: sharpe −4.783 ≤ −3.0, dd 33.982% > 25, mean $ −74.73 ≤ −62.

**Why B is `INCONCLUSIVE`:** n=171 < 172 (ticket Gate 1). Holdout exhausted. Same frozen bytes as A. Not a fake STABLE.

- Start: `full_holdout_replay_frozen`, bar index **0**.
- Train: **False**. Optimizer steps: **0**.
- Birth receipts: **untouched** (PR #14 S1–S5 + fitness). No new S5 receipt.
- `is_birth_exit_sufficient`: **True** as PR #14 left it. Regression here is an Awakening fact, not a Birth reopen.
- REAL: **no**.
- Evolution Proof `passed=True`: **not stamped** (overall ≠ STABLE; A n=218 < 500 and inequalities fail).
