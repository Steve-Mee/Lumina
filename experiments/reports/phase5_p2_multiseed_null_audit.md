# P2 drift-aware multi-seed null audit (2026-10-29)

- generated_at: `2026-10-29T15:24:32.514552+00:00`
- pre-register: `phase5_p2_multiseed_null_preregister_2026-10-29.md`
- CostModel: `1.2.0`
- seeds: `32` (`20261029`..`20261060`)
- A2 fail-closed cap (majority): `16` of 32
- A2 10% diagnostic: `3` of 32
- method_ready (MES/MNQ/ES planted+null): `True`
- NQ templates: **closed** this cycle (action 5 is ES+MES only)
- n_trials total: `164`
- holdout pin `2026-01-28T23:00:00Z`: closed

## Per root

| root | planted | null reliable | A2 hits | ≤10% diag | planted median OOS | null median-of-medians | days | IS/OOS | N | note |
|---|---|---|---|---|---|---|---|---|---|---|
| MES | True | True | 6/32 | no | 0.00124226 | -4.39908e-05 | 600 | 39/70 | 41 | accepted |
| MNQ | True | True | 10/32 | no | 0.00269109 | -2.80929e-05 | 595 | 42/69 | 41 | accepted |
| ES | True | True | 5/32 | no | 0.0124021 | -0.000798443 | 599 | 46/69 | 41 | accepted |
| NQ | True | True | 8/32 | no | 0.0269431 | -0.000551781 | 600 | 39/70 | 41 | accepted |

## Trials

- MES: `41`
- MNQ: `41`
- ES: `41`
- NQ: `41`
- total: `164`

## Fail-closed

- No seed reroll, no config respec.
- If MES, MNQ, or ES planted misses or the null is unreliable: stop later strategy reruns.
- NQ stays closed until its null is reliable; even then this cycle does not run NQ templates.

