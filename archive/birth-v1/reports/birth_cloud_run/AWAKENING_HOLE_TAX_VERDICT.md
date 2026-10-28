# AWAKENING HOLE-TAX VERDICT

**Overall:** `GRIND_REGRESS_AWAKENING_OPEN HOLE_TAX_SHOT SELECT_OVERFIT=false HOLE_SUBSTITUTION=false HOLE_MOVED=false`

**Date:** 2026-09-03T11:06:27.001430+00:00
**Child sha256:** `ca2ae0e5fa6f0e54215fe6c833e2ebff608b5e99426a6e75ff5f7167d6bb0325`
**Init sha256:** `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03` (must stay `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03`)
**Control sha256:** `db7daf3b978fe80624608e27111627b5b9c3070e71118c66673df996123dd029` (PR #20, not used as init)
**SELECT_NOOP:** `False`
**hole_tax_r:** `1.0`
**Timesteps pin:** `10000` / requested `10000`
**optimizer_steps:** `220`
**SELECT_OVERFIT:** `False`
**HOLE_SUBSTITUTION:** `False`
**HOLE_MOVED:** `False`

Child vs BASELINE_PARENT (PR #17/#19) and CONTROL_SELECT (PR #20, no tax). Geometry unchanged. One tax variable.

| Leg | class | n | wr_all | wr_policy | mean$_all | mean$_policy | mean_r_policy | sharpe | dd% of $50k | occ | plant_n | FO closes | FO bars |
|-----|-------|---|--------|-----------|-----------|--------------|---------------|--------|-------------|-----|---------|-----------|---------|
| A hole-tax | GRIND_REGRESS | 211 | 0.3080568720379147 | 0.3333333333333333 | -69.90236979862026 | -28.956135211719193 | -0.25619038036381137 | -4.552234905374526 | 29.498800055017956 | 0.7565438962242298 | 61 | 61 | 111 |
| B hole-tax | GRIND_REGRESS | 180 | 0.3111111111111111 | 0.31333333333333335 | -45.106767083815534 | -23.344086897326296 | -0.28229412926554237 | -3.5108225814966976 | 16.658425047406872 | 0.7160991429233264 | 30 | 30 | 62 |
| A parent | GRIND_REGRESS | 218 | 0.303 | 0.34 | -74.73 | -23.87 | -0.211 | -4.783 | 33.982 | 0.757 | 68 | 68 | 165 |
| B parent | INCONCLUSIVE | 171 | 0.281 | 0.28 | -44.32 | -26.91 | -0.329 | -3.865 | 15.343 | 0.759 | 21 | 21 | 56 |
| A control | GRIND_REGRESS | 225 | 0.30666666666666664 | 0.3333333333333333 | -72.59384314264545 | -31.010356288345573 | -0.27389581954773 | -4.583245071164464 | 32.87462017478503 | 0.7599953671531156 | 75 | 75 | 149 |
| B control | INCONCLUSIVE | 182 | 0.3791208791208791 | 0.38666666666666666 | -34.246779716172504 | -14.950525227562903 | -0.17461574736072388 | -2.5271434898282914 | 12.966977405911381 | 0.7536715311558952 | 32 | 32 | 74 |

### Exits / hole cell (policy-only stop×NEUTRAL)

- A exits stop/target/time_stop = `{'stop': 144, 'target': 45, 'time_stop': 22}` stop×NEUTRAL `{'n': 86, 'mean_r': -1.0377589113836108, 'mean_usd': -117.0812092098568}` target_mean_r `1.2122160679783462` time_stop_mean_r `1.2229581555149693`
- B exits stop/target/time_stop = `{'stop': 120, 'target': 33, 'time_stop': 27}` stop×NEUTRAL `{'n': 87, 'mean_r': -1.0515524666548113, 'mean_usd': -86.89438793959869}` target_mean_r `1.1984173505564846` time_stop_mean_r `1.222113105211665`

- Evolution Proof stamped: `False`. passed_inequalities=`False`.
- polish_oos_winrate used: wr_policy_B (`0.31333333333333335`) — policy-only to match PR #17 skill WR.
- Birth receipts / fitness `707b5ab9d6b9af96`: **untouched**.
- REAL: **no**.
- `is_birth_exit_sufficient`: **True** as PR #14 left it.

Honesty: the hole-tax child still prints **stop × NEUTRAL at ≈ −1.04 R** (A n=86 mean_r=−1.038; B n=87 mean_r=−1.052). Eval `trade_r` stays the fill (no row < −1.5 R — the −1 R tax did not leak into exam dollars). Targets still print +R (A +1.212, B +1.198). WR_policy A 0.333 vs parent 0.34 / control 0.333; B 0.313 vs parent 0.28 / control 0.387. Plant A 61 vs parent 68 — not substitution. Geometry is not the bug. One shot. No second learn(). Playground does not open.

