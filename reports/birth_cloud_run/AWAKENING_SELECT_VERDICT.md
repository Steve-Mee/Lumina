# AWAKENING SELECT VERDICT

**Overall:** `GRIND_REGRESS_AWAKENING_OPEN SELECT_SHOT SELECT_OVERFIT=false SELECT_NOOP=false`

**Date:** 2026-09-03T10:02:45.455451+00:00
**Child sha256:** `db7daf3b978fe80624608e27111627b5b9c3070e71118c66673df996123dd029`
**Init sha256:** `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03` (must stay `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03`)
**SELECT_NOOP:** `False`
**Timesteps pin:** `10000` / requested `10000`
**optimizer_steps:** `220`

Child vs BASELINE_BIRTH_EXIT (PR #17 skill WR 0.34 / 0.28). Geometry unchanged. Selection shot only.

| Leg | class | n | wr_all | wr_policy | mean$_all | mean$_policy | mean_r_policy | sharpe | dd% of $50k | occ | plant_n | FO closes | FO bars |
|-----|-------|---|--------|-----------|-----------|--------------|---------------|--------|-------------|-----|---------|-----------|---------|
| A child | GRIND_REGRESS | 225 | 0.30666666666666664 | 0.3333333333333333 | -72.59384314264545 | -31.010356288345573 | -0.27389581954773 | -4.583245071164464 | 32.87462017478503 | 0.7599953671531156 | 75 | 75 | 149 |
| B child | INCONCLUSIVE | 182 | 0.3791208791208791 | 0.38666666666666666 | -34.246779716172504 | -14.950525227562903 | -0.17461574736072388 | -2.5271434898282914 | 12.966977405911381 | 0.7536715311558952 | 32 | 32 | 74 |
| A baseline | GRIND_REGRESS | 218 | 0.303 | 0.34 | -74.73 | -23.87 | -0.211 | -4.783 | 33.982 | 0.757 | 68 | 68 | 165 |
| B baseline | INCONCLUSIVE | 171 | 0.281 | 0.28 | -44.32 | -26.91 | -0.329 | -3.865 | 15.343 | 0.759 | 21 | 21 | 56 |

### Exits / hole cell (policy-only stop×NEUTRAL)

- A exits stop/target/time_stop = `{'stop': 151, 'target': 51, 'time_stop': 23}` stop×NEUTRAL `{'n': 79, 'mean_r': -1.0377639065293784, 'mean_usd': -117.06630513776742}` target_mean_r `1.2122150350232215` time_stop_mean_r `0.8135511733151649`
- B exits stop/target/time_stop = `{'stop': 109, 'target': 51, 'time_stop': 22}` stop×NEUTRAL `{'n': 75, 'mean_r': -1.0675576786404861, 'mean_usd': -88.25842516168144}` target_mean_r `1.19844324296314` time_stop_mean_r `1.0083898218831873`

- Evolution Proof stamped: `False`. passed_inequalities=`False`.
- polish_oos_winrate used: wr_policy_B (`0.38666666666666666`) — policy-only to match PR #17 skill WR.
- Birth receipts / fitness `707b5ab9d6b9af96`: **untouched**.
- REAL: **no**.
- `is_birth_exit_sufficient`: **True** as PR #14 left it.

Honesty: the child still prints **stop × NEUTRAL at ≈ −1.04 R** (A n=79 mean_r=−1.038; B n=75 mean_r=−1.068). Targets still print +R (A +1.212, B +1.198). WR_policy A 0.333 vs baseline 0.34; B 0.387 vs 0.28. Geometry is not the bug. One shot. No second learn().

