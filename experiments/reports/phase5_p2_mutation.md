# Phase 5 P2 artefact-fix mutation testing

- mutants: `320`
- killed: `311`
- excluded equivalent: `9`
- non-equivalent: `311`
- unjustified survivors: `0`
- kill rate (non-equivalent): `1.0000`
- raw kill rate: `0.9719`

| excluded mutant | justification |
|---|---|
| `roll_verify.py:boolop#2` | FRIDAY_ROLL is date(2026-06-12), which is in NT8_ROLL_DATES and weekday()==4; both AND conjuncts are True, so AND vs OR is observationally identical on these constants. |
| `prepare.py:boolop#5` | previous_session is assigned at the end of every loop iteration, so `index > 0` already implies `previous_session is not None`; AND vs OR is identical. |
| `geometry.py:raise-to-pass#7` | floors_for() calls spec_for() first; every supported root is in CATALOG_DEFAULT_GEOMETRY, so pair is never None and the GeometryRefused raise is unreachable. |
| `roll_verify.py:boolop#7` | require_friday_roll() only runs after both friday flags are True on the current calendar; `not present or not is_friday` and `not present and not is_friday` are both False, so the raise never fires either way. |
| `cost_bands.py:raise-to-pass#9` | band_for() calls spec_for() first; unknown roots raise ContractError (a ValueError) before the trailing `raise ValueError`, so that raise is unreachable. |
| `seal.py:boolop#10` | seal_holdout() builds train/holdout via access_bars(), which already enforces train[-1] < pin <= holdout[0]; the leak OR is unreachable given that split. |
| `seal.py:raise-to-pass#11` | Same as boolop#10: the leak raise cannot fire because access_bars already returned a correct split, so deleting it is observationally identical. |
| `static_rules.py:return-bool#12` | structural_decay returns True for n<6 before spearman_rho; spearman_rho is finite for every n>=6 path because ranks_x is 1..n, so `not math.isfinite(rho)` is dead. |
| `holdout.py:raise-to-pass#13` | A 1-bar tape has first==last, so `start <= first or start >= last` always holds and the later span raise still fail-closes; the len<2 raise is redundant. |

| unjustified survivor | detail |
|---|---|
| (none) | |
