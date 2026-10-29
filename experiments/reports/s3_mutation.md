# S2.5 NT-PIT + S3 sim_gate mutation testing

- mutants: `320`
- killed: `297`
- excluded equivalent: `23`
- non-equivalent: `297`
- unjustified survivors: `0`
- kill rate (non-equivalent): `1.0000`
- raw kill rate: `0.9281`

| excluded mutant | justification |
|---|---|
| `independence.py:boolop#6` | None series still fail-closed in _finite_series via list(None) TypeError. |
| `independence.py:boolop#8` | str series still fail-closed in _finite_series because chars are not floats. |
| `nt_tape.py:raise-to-pass#19` | is_forming_bar is ts>now; lookahead_future_bar is the same predicate. |
| `nt_tape.py:raise-to-pass#23` | is_forming_bar is ts>now; forming_bar_refused is the same predicate. |
| `independence.py:kw-bool#24` | min() equalizes lengths before zip; strict=True vs False is identical. |
| `sim_runtime.py:return-none#26` | evaluate() after evaluate_instrument(MES/MNQ) is the same ctx; dead second fail. |
| `nt_tape.py:raise-to-pass#30` | holdout_pin_is_closed() is hardcoded True; holdout_pin_open is unreachable. |
| `independence.py:binop#38` | sqrt(den_a/den_b) vs sqrt(den_a*den_b) is clamped to [-1, 1]; anti-corr stays -1. |
| `alarm_executor.py:kw-bool#41` | escalate is deleted unused in _execute; True vs False is a no-op. |
| `independence.py:const-float#45` | Pearson on finite series never exceeds 1.0, so the clamp body is unreachable. |
| `sim_runtime.py:binop#49` | gate_order cannot fail after bind_sim_gate of a ctx that already passed evaluate. |
| `sim_runtime.py:return-none#50` | gate_order cannot fail after bind_sim_gate of a ctx that already passed evaluate. |
| `independence.py:const-float#51` | Pearson on finite series never goes below -1.0, so the clamp body is unreachable. |
| `independence.py:unary#52` | Pearson on finite series never goes below -1.0, so the clamp body is unreachable. |
| `sim_runtime.py:return-none#52` | SimGateRefused is unreachable after evaluate() already passed on the same ctx. |
| `alarm_executor.py:except-pass#52` | sla_decision cannot refuse after miss_count is incremented to >= 1. |
| `sim_runtime.py:except-pass#53` | arm_research_place uses the same ctx evaluate() already passed. |
| `alarm_executor.py:kw-bool#58` | escalate is deleted unused in _execute; True vs False is a no-op. |
| `alarm_executor.py:compare#61` | elapsed>600 is redundant with sla_decision which already escalates on that wall. |
| `alarm_executor.py:compare-not#62` | elapsed>600 is redundant with sla_decision which already escalates on that wall. |
| `alarm_executor.py:compare#63` | decision==escalate already covers the reachable SLA-miss states. |
| `nt_tape.py:boolop#64` | None/str frames still refuse via missing to_dict after the or/and swap. |
| `alarm_executor.py:compare-not#64` | decision==escalate already covers the reachable SLA-miss states. |

| unjustified survivor | detail |
|---|---|
| (none) | |
