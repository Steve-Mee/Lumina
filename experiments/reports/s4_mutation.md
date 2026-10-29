# S4 SIM-entry hardening mutation testing

- mutants: `320`
- killed: `308`
- excluded equivalent: `12`
- non-equivalent: `308`
- unjustified survivors: `0`
- kill rate (non-equivalent): `1.0000`
- raw kill rate: `0.9625`

| excluded mutant | justification |
|---|---|
| `sim_protected.py:raise-to-pass#0` | Mixin _refuse is a type-stub; SimRuntime overrides it, so the raise is unreachable. |
| `sim_protected.py:const-int#1` | ProtectiveAttachPlan always carries companion_confirm_timeout_ms; getattr default 5000 is unused. |
| `protective_attach.py:continue-to-pass#5` | Empty mapping keys are stripped to ''; named account/connection lookup never matches them. |
| `continuity_meter.py:const-int#18` | Default fixture start hour 21 vs 00 is the same UTC weekday; bar sequence unchanged. |
| `continuity_meter.py:const-int#19` | Default fixture start minute 00 vs 01 is the same UTC weekday; bar sequence unchanged. |
| `continuity_meter.py:const-int#25` | Default fixture clock hour 21 vs 00 still leaves 241 weekdays before the pin. |
| `continuity_meter.py:const-int#26` | Default fixture clock minute 00 vs 01 still leaves 241 weekdays before the pin. |
| `alarm_executor.py:continue-to-pass#31` | Zero-qty rows never enter the flatten loop; open_strategy_qtys and live_qty==0 already exclude them. |
| `alarm_executor.py:kw-bool#37` | escalate is deleted unused in _execute; True vs False is a no-op. |
| `sim_protected.py:return-none#46` | SimRuntime refuses before _place_protected when submitter is None; mixin return None is dead. |
| `sim_protected.py:const-int#49` | _place_protected always passes timeout_ms into _submit_companion_stop; the 5000 default is unused. |
| `sim_protected.py:return-bool#50` | require_protective_stop already refuses empty stop_price; companion ValueError return is dead. |

| unjustified survivor | detail |
|---|---|
| (none) | |
