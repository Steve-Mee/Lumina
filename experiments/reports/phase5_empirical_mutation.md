# Phase 4 monitoring mutation testing

- mutants: `320`
- killed: `288`
- excluded equivalent: `0`
- non-equivalent: `320`
- unjustified survivors: `32`
- kill rate (non-equivalent): `0.9000`
- raw kill rate: `0.9000`

| excluded mutant | justification |
|---|---|
| (none) | |

Equivalent survivors were **not** excluded: `n_non_equivalent` must stay `>= 320`, so they remain in the denominator. Kill rate `0.90` still clears `0.80`. Steve's four categories only (logging; rename/reorder; numerically identical; robust plateau). Unreached refuse arms were killed, not marked equivalent.

| survivor | Steve category | justification |
|---|---|---|
| `horizons.py:compare#0` `#1` `#3` | numerically identical | First medium-rank `if` is redundant with `stage_rank(medium) > stage_rank(chosen)` that already sets `horizon=medium` iff medium uniquely wins. |
| `material.py:const-int#10` | numerically identical | `pstdev` of one OOS value is `0.0`; empty OOS already refused. `len>=2` vs `>=0` does not change `oos_stdev`. |
| `vol_regime.py:const-int#14` `binop#15` | numerically identical | `min(len-1, int(pct*(len-1)))` clamp is already in-range for `pct∈[0,1]`. |
| `monitor.py:const-int#21` `#24` `#25` `#26` | do not move a decision | Guardian dummy `DecayAssessment` severity/votes are unused; `_apply` keys off `stage='suspended'`. |
| `material.py:unary#22` `const-int#23` `compare#24` `const-float#25` | numerically identical | `live_chunk` stdev is used only when `live_noise_vol` is `None`/`0`; ready windows compute noise, and `window>=2` makes the `else 1.0` / `>=0` arms dead. |
| `material.py:compare#26` `const-float#27` `compare#28` `boolop#29` `const-float#30` | numerically identical | `vol_scale` maps any `base>oos` back to OOS sigma for Sharpe; IC already covers every live-mean that could Sharpe-halt unscaled. |
| `vol_regime.py:const-int#47` `binop#48` `#49` `#50` `#51` `binop#52` | robust plateau | ±1 on trailing-history floor/end does not move ES/MES labels on the pinned tapes. |
| `monitor.py:boolop#52` `return-bool#53` `#59` | numerically identical | `SignalSuspended`/`Retired` `new_weight` Field(le=0) already forces `0.0` before the extra inequality. |
| `material.py:const-float#59` `#70` | numerically identical | Second-branch `< 1.0` vs `< 0.0` is unreachable after the positive-mean/expected first branch; at 0 both formulas agree. |
| `statistics.py:const-int#84` | numerically identical | `len(values)<3` vs `<0` still returns `None` via `len(diffs)<2`. |
| `material.py:const-float#89` | numerically identical | `vol_ratio` floor `1→0` is reached only after `live_dd >= raw_floor`, so lowering the floor cannot un-flag. |

| unjustified survivor | detail |
|---|---|
| `horizons.py:compare#0` | survived kill battery |
| `horizons.py:compare#1` | survived kill battery |
| `horizons.py:compare#3` | survived kill battery |
| `material.py:const-int#10` | survived kill battery |
| `vol_regime.py:const-int#14` | survived kill battery |
| `vol_regime.py:binop#15` | survived kill battery |
| `monitor.py:const-int#21` | survived kill battery |
| `material.py:unary#22` | survived kill battery |
| `material.py:const-int#23` | survived kill battery |
| `material.py:compare#24` | survived kill battery |
| `monitor.py:const-int#24` | survived kill battery |
| `material.py:const-float#25` | survived kill battery |
| `monitor.py:const-int#25` | survived kill battery |
| `material.py:compare#26` | survived kill battery |
| `monitor.py:const-int#26` | survived kill battery |
| `material.py:const-float#27` | survived kill battery |
| `material.py:compare#28` | survived kill battery |
| `material.py:boolop#29` | survived kill battery |
| `material.py:const-float#30` | survived kill battery |
| `vol_regime.py:const-int#47` | survived kill battery |
| `vol_regime.py:binop#48` | survived kill battery |
| `vol_regime.py:const-int#49` | survived kill battery |
| `vol_regime.py:binop#50` | survived kill battery |
| `vol_regime.py:const-int#51` | survived kill battery |
| `vol_regime.py:binop#52` | survived kill battery |
| `monitor.py:boolop#52` | survived kill battery |
| `monitor.py:return-bool#53` | survived kill battery |
| `material.py:const-float#59` | survived kill battery |
| `monitor.py:return-bool#59` | survived kill battery |
| `material.py:const-float#70` | survived kill battery |
| `statistics.py:const-int#84` | survived kill battery |
| `material.py:const-float#89` | survived kill battery |
