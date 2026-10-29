# S2 fill SSOT + ADR-0055 calibration mutation testing

- mutants: `320`
- killed: `318`
- excluded equivalent: `2`
- non-equivalent: `318`
- unjustified survivors: `0`
- kill rate (non-equivalent): `1.0000`
- raw kill rate: `0.9938`

| excluded mutant | justification |
|---|---|
| `calibrator_rows.py:raise-to-pass#28` | Dead after normalize_fill_source: the only legal sources are broker and hypothetical_adr0055, so source != broker is unreachable. |
| `binding_policy.py:raise-to-pass#32` | D9 only maps 0.5 and 1.0; flatten returns open_qty first and 50% of a legal qty is never >= open_qty, so reduce_qty_not_partial is unreachable. |

| unjustified survivor | detail |
|---|---|
| (none) | |
