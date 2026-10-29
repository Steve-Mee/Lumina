# Onderzoeksteam 17:34 — nine answers applied (2026-10-29)

Binding input (Steve forwarded; **not** Steve's opinion):
`docs/research/ONDERZOEKERS-ANTWOORDEN-9VRAGEN-20261029T1734.md`
content sha256 `d792a116b8afb26ca2237122ea08edf31147416bd1bc309e2073ea811556c28c`
(prefix `d792a116`). Unchanged.

Stacked draft PR #72 on #69 (`cursor/fase5-p2-costfix-esnq-2249`).
**No merge. No SIM/REAL orders. Holdout pin `2026-01-28T23:00:00Z` unopened
(0 of max 1–2 evals). Risk Core untouched. Private CSVs not in git.
`$LUMINA_RESEARCH_DATA_DIR` unset — ES/MES not re-run.**

DSR **0.95**, PBO **0.50**, A2 planted detection, CostModel **1.2.0** unchanged.

---

## What changed

| # | question | code / lock | PIT rerun |
|---|---|---|---|
| 1 | Null fails at ≥4/32 seeds that look like an edge, not 16/32; true null 5–10%; MES 4/32 borderline; exact count | `n_a2` diagnostic; calibrated 7/8 `n_edge` gate; cap 3; borderline 4 | **No** (no CSVs). Re-scored frozen unclipped seeds |
| 2 | Keep detrend **and** balance | Already both; docstring + tests lock both | No |
| 3 | ISO calendar-week shuffle, 8 seeds, extra only | Already extra; reports say not a gate | No |
| 4 | Midpoints 1.0/1.2 and 1.8/0.9; control must pass under them | Constants + `required_midpoint_controls()` + `execute_control(target_atr, stop_atr)` | Synthetic tape: planted detected. PIT midpoint D13 **not run** |
| 5 | Flatten at RTH session end or time stop, never calendar midnight | `_session_end_flags` + test vs 00:00 UTC | No |
| 6 | Unbracket hitrate 16, 60, 120 | `UNBRACKET_HORIZONS`; report columns | PIT only has N=60 |
| 7 | Four DSR-fails stay killed; no DSR relax; lower-turnover = fresh pre-register | `DSR_ONLY_KILLS`; proposal file **not run** | No |
| 8 | BE per geometry or drop column | Gross ATR BE 0.545 / 0.333 / n/a; drop 1.634 in markdown (win rate cannot exceed 1) | JSON PIT dump untouched |
| 9 | NQ closed until new approved pre-register | `nq_lock.py` | No NQ templates |

## Do the new null counts change the verdict?

**Calibrated gate: no. A2 diagnostic: remaining leak, not a stop. ATR templates: no.**

Raw A2 at ≥4/32 cannot be the cycle stop: with 8 OOS windows P(A2|fair)≈0.36
so a true null fails ≈100%, which contradicts "true null fails ≤5–10%".
"Looks like an edge" is therefore A2 **and** +OOS ≥ 7/8.

Action-1 unclipped (frozen JSON, same seeds, new bar):

| root | exact A2 | A2 status | exact 7/8 | edge status | old majority |
|---|---|---|---|---|---|
| MES | **6/32** | unreliable diagnostic | **0/32** | reliable | pass |
| MNQ | **10/32** | unreliable diagnostic | **1/32** | reliable | pass |
| ES | **5/32** | unreliable diagnostic | **0/32** | reliable | pass |
| NQ | **8/32** | unreliable diagnostic | **0/32** | reliable | pass |

A2 rates 16–31% sit above the 5–10% A2 target. That leak is smaller than the
old single-seed NQ failure, and it is **not** a calibrated false-edge majority.
No seed reroll. MNQ 7/8 seed: `20261059`.

Action-5 ATR D13:

| root | exact A2 | A2 status | exact 7/8 |
|---|---|---|---|
| ES | **1/32** | reliable (inside 5–10%) | not in PIT JSON |
| MES | **4/32** | **borderline**, monitor | not in PIT JSON |

ATR per-seed +OOS was not stored, so `n_edge` is not re-scored. Planted still
detected. ES ATR templates **10/10 kill, 0 survivors, holdout skipped**. The
four +OOS rows still die at DSR 0.057 / 0.097 / 0.049 / 0.019. They are not
holdout candidates.

## Data limitation

`LUMINA_RESEARCH_DATA_DIR` is unset. `data/research/` has no CSVs. CI does not
mount the private NT8 tapes. This change is **code + pre-registration +
report**. It does not rewrite seals `85e4588f`, `454b8d1f`, or `cdf964b6`.

Owed when CSVs are mounted (still fail-closed, still no holdout open):

- Midpoint positive control under fade 1.0/1.2 **and** breakout 1.8/0.9 on PIT
- Unbracket hitrate 16 and 120 on the ten ES configs
- Optional net (cost-adjusted) ATR break-even using the tape's ATR
- ATR D13 `n_edge` (needs per-seed +OOS)

## Hygiene

- No live / SIM orders
- Risk Core not modified
- Tests not weakened (null bar tightened vs majority 16/32; DSR floor still 0.95)
- Week-block still 8 extra D13 trials when a null-audit runs; not a gate

## Open questions

None of the nine 16:03 questions remain open. Remaining operational debt is
data-mount only (midpoint D13 PIT, N=16/120 hitrates, ATR `n_edge`). A `p2b-*`
lower-turnover grid stays unapproved until the team explicitly accepts that
pre-register.
