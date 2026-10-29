# S1 SIM whitelist + LIVE_RELEASE mutation testing

- mutants: `320`
- killed: `319`
- excluded equivalent: `1`
- non-equivalent: `319`
- unjustified survivors: `0`
- kill rate (non-equivalent): `1.0000`
- raw kill rate: `0.9969`

| excluded mutant | justification |
|---|---|
| `sim_account_guard.py:const-int#0` | process HMAC seal with urandom(0) still authenticates the frozen set |

| unjustified survivor | detail |
|---|---|
| (none) | |
