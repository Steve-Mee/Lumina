# S4 SIM-entry hardening mutation testing

- mutants: `320`
- killed: `312`
- excluded equivalent: `8`
- non-equivalent: `312`
- unjustified survivors: `0`
- kill rate (non-equivalent): `1.0000`
- raw kill rate: `0.9750`

| excluded mutant | justification |
|---|---|
| `continuity_meter.py:const-int#18` | Default fixture start hour 21 vs 00 is the same UTC weekday; bar sequence unchanged. |
| `continuity_meter.py:const-int#19` | Default fixture start minute 00 vs 01 is the same UTC weekday; bar sequence unchanged. |
| `continuity_meter.py:const-int#25` | Default fixture clock hour 21 vs 00 still leaves 241 weekdays before the pin. |
| `continuity_meter.py:const-int#26` | Default fixture clock minute 00 vs 01 still leaves 241 weekdays before the pin. |
| `alarm_executor.py:continue-to-pass#31` | Zero-qty rows never enter the flatten loop; open_strategy_qtys and live_qty==0 already exclude them. |
| `alarm_executor.py:kw-bool#37` | escalate is deleted unused in _execute; True vs False is a no-op. |
| `continuity_meter.py:binop#54` | (n+1)%2 and (n-1)%2 have the same parity, so open polarity is unchanged. |
| `alarm_executor.py:kw-bool#73` | escalate is deleted unused in _execute; True vs False is a no-op. |

| unjustified survivor | detail |
|---|---|
| (none) | |
