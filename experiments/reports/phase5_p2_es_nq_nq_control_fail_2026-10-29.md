# NQ D13 control failed (2026-10-29) — no respec

Pre-register: if planted is not detected or the null looks like an edge, **stop
that instrument**. Do not iterate geometry without a new Steve OK. ES passed
and its 9 `p2c-*` configs ran. NQ's 3 configs stayed `not_tested_control_failed`.

Holdout pin `2026-01-28T23:00:00Z` stayed closed. CostModel 1.2.0. Seed 20261029
for the shuffled null. Same 20000/20000 session-hold as ADR-0063.

## What the gate saw (session-day net after costs)

| root | arm | median OOS | +OOS share | DSR | `_detected` |
|---|---|---|---|---|---|
| ES | planted | +0.01240 | 1.00 | ~1.0 | yes |
| ES | null | −0.00072 | 0.375 | 0.176 | no |
| NQ | planted | +0.02736 | 1.00 | 1.0 | yes |
| NQ | null | **+0.00266** | **0.75** | 0.259 | **yes (null looks like an edge)** |

NQ planted is a real known-size session-OC edge (all 8 OOS windows positive,
DSR 1). The fail is the **null**: shuffled session signs still have median OOS
> 0 and 6/8 windows positive, which meets the static A2 share floor (0.60).
ES null stays negative (3/8 positive). MNQ on the micro tape passed this same
control in the cost-fix rerun.

NQ null OOS windows: `+0.0010, +0.0012, −0.0100, −0.0037, +0.0050, +0.0057, +0.0044, +0.0041`.

## What this is not

- Not a missing NQ tape (hash `9d41f220…` sealed, 1_089_745 rows).
- Not the July 2025 ES hole (NQ has those sessions).
- Not a geometry change and not a seed reroll. Both would be a respec.

Audit: `state/phase5-research-es-nq/es_nq/audit.jsonl` trials 3–4 (not committed).
