# S1 SIM whitelist + LIVE_RELEASE mutation testing

- mutants: `320`
- killed: `268`
- excluded equivalent: `6`
- non-equivalent: `314`
- unjustified survivors: `46`
- kill rate (non-equivalent): `0.8535`
- raw kill rate: `0.8375`

| excluded mutant | justification |
|---|---|
| `sim_account_guard.py:const-int#0` | process HMAC seal with urandom(0) still authenticates the frozen set |
| `admission_s1_steps.py:boolop#0` | agent_id log coalescing; admission decision unchanged |
| `live_release.py:boolop#3` | log helper coalesces empty agent_id; reject decision unchanged |
| `live_release.py:boolop#4` | log helper coalesces empty approved_by; reject decision unchanged |
| `live_release.py:kw-bool#65` | canonical body key insertion order already matches sort_keys=True |
| `live_release.py:return-tuple-bool#150` | clock.tzinfo is None is unreachable after astimezone/now(timezone.utc) |

| unjustified survivor | detail |
|---|---|
| `sim_account_guard.py:boolop#13` | survived kill battery |
| `sim_account_guard.py:compare#14` | survived kill battery |
| `sim_account_guard.py:compare-not#15` | survived kill battery |
| `live_release.py:compare#20` | survived kill battery |
| `live_release.py:compare-not#21` | survived kill battery |
| `live_release.py:return-none#22` | survived kill battery |
| `live_release.py:if-not#23` | survived kill battery |
| `sim_account_guard.py:compare#24` | survived kill battery |
| `sim_account_guard.py:compare-not#25` | survived kill battery |
| `sim_account_guard.py:if-not#26` | survived kill battery |
| `live_release.py:return-none#27` | survived kill battery |
| `sim_account_guard.py:not#27` | survived kill battery |
| `sim_account_guard.py:if-not#28` | survived kill battery |
| `admission_s1_steps.py:compare#28` | survived kill battery |
| `admission_s1_steps.py:compare-not#29` | survived kill battery |
| `admission_s1_steps.py:if-not#30` | survived kill battery |
| `admission_s1_steps.py:compare#31` | survived kill battery |
| `live_release.py:if-not#32` | survived kill battery |
| `live_release.py:return-none#33` | survived kill battery |
| `admission_s1_steps.py:compare-not#32` | survived kill battery |
| `admission_s1_steps.py:if-not#33` | survived kill battery |
| `live_release.py:except-pass#34` | survived kill battery |
| `sim_account_guard.py:compare#34` | survived kill battery |
| `sim_account_guard.py:compare-not#35` | survived kill battery |
| `sim_account_guard.py:if-not#36` | survived kill battery |
| `live_release.py:compare#44` | survived kill battery |
| `live_release.py:compare-not#45` | survived kill battery |
| `live_release.py:compare#46` | survived kill battery |
| `live_release.py:compare-not#47` | survived kill battery |
| `live_release.py:boolop#48` | survived kill battery |
| `sim_account_guard.py:compare#49` | survived kill battery |
| `live_release.py:if-not#50` | survived kill battery |
| `sim_account_guard.py:compare-not#50` | survived kill battery |
| `live_release.py:compare#51` | survived kill battery |
| `sim_account_guard.py:ifexp-swap#51` | survived kill battery |
| `live_release.py:compare-not#52` | survived kill battery |
| `sim_account_guard.py:boolop#58` | survived kill battery |
| `sim_account_guard.py:compare#59` | survived kill battery |
| `sim_account_guard.py:compare-not#60` | survived kill battery |
| `sim_account_guard.py:boolop#61` | survived kill battery |
| `sim_account_guard.py:if-not#62` | survived kill battery |
| `live_release.py:boolop#63` | survived kill battery |
| `sim_account_guard.py:if-not#63` | survived kill battery |
| `live_release.py:boolop#64` | survived kill battery |
| `live_release.py:const-int#82` | survived kill battery |
| `live_release.py:return-bool#85` | survived kill battery |
