# P2 drift-aware multi-seed null — pre-registration (2026-10-29)

Locked **before** any multi-seed null run, geometry change, or ES rerun.
Binding input: onderzoeksteam advisory
`docs/research/ONDERZOEKERS-ANALYSE-4MARKTEN-20261029T1603.md`
content sha256 `83476aa358b515f018002c79cf83caa33e335d281cc107e0f61b4be94b474df7`
(prefix `83476aa3`, git freeze `51872204`). Forwarded by Steve; not Steve's opinion.

This file does **not** rewrite `phase5_p2_positive_control_preregister_2026-10-29.md`,
catalog 16/8, CostModel 1.2.0, DSR/PBO floors, or holdout seals `85e4588f…` /
`454b8d1f…`. Holdout pin `2026-01-28T23:00:00Z` stays closed. No SIM/REAL orders.

## Why

NQ D13 failed closed because a single permutation of session signs keeps the
up/down count. With positive drift that imbalance still clears A2 (median OOS
> 0 and ≥60% +OOS). The planted edge was real. The null leaked drift.

## Locked procedure (advisory action 1)

Geometry for this control stays ADR-0063: RTH session hold, 1:1 20000/20000
ticks, `time_stop_bars=2000`, `session_end_flatten=True`, CostModel 1.2.0.
Planted sign = sign(last RTH close − first RTH open) on the unadjusted tape.

### Seeds

| field | value |
|---|---|
| n_seeds | `32` (inside the advisory 20–50 band; not tuned on NQ) |
| seed_i | `20261029 + i` for `i = 0..31` |
| embargo | `1` session day (same as `evaluate_candidate`) |

No seed reroll. If the null is unreliable, stop and report. Do not draw new seeds.

### Drift-aware builder (both; advisory allowed either)

For each **non-overlapping** partition of Globex session days matching the
walk-forward layout:

1. first IS `[0, is_size)`
2. embargo `[is_size, is_size + embargo)`
3. successive OOS blocks of `oos_size`
4. leftover tail

Inside each partition, on sessions with a nonzero planted sign:

1. Detrend: residual = session OC − mean OC of that partition. Residual sign
   = `sign(residual)`; if residual is 0 keep the planted sign (do not drop the
   session).
2. Shuffle those residual signs with `random.Random(seed)` walking partitions
   in order (one RNG, continuing state).
3. Balance: flip the fewest majority signs, last-to-first in the shuffled
   list, until `|n_pos − n_neg| ≤ 1`. Zeros stay zero.

Write the resulting signs back onto the first-RTH-bar index of each session.
Sessions with no RTH move stay 0.

This is stricter than “detrend or balance”. Open question Q-NULL-2 if the team
wanted only one of the two.

### Reliability bar (engineering lock)

A seed **hits A2** when `_detected(null_eval, null_median=None)` is true:
finite median OOS > 0, +OOS share ≥ 0.60, no structural decay.

| field | value |
|---|---|
| reliable | `n_a2 ≤ floor(0.10 * n_seeds)` → at most **3 of 32** |
| planted pass | A2 on the planted tape **and** planted median OOS > median of the 32 null median-OOS values |
| fail-closed | planted miss **or** null unreliable → stop that instrument; no respec; no seed reroll |

10% is **not** a team number. It is locked here so the run is falsifiable.
Distribution is reported in full so the team can apply another bar without
rerolling. Open question Q-NULL-1.

### Week-block extra (advisory optional; report-only)

8 seeds `20261129 + i` for `i = 0..7`. ISO-week blocks of nonzero session
signs keep within-week order; week blocks are shuffled onto the chronological
nonzero slots. No detrend, no balance. A2 hit-rate is reported. It does **not**
decide pass/fail.

### Where it runs

Same builder on MES, MNQ, ES, NQ (gate split only; holdout sealed). NQ
strategy templates stay **closed** until that root’s null is reliable. A
failed MES/MNQ/ES planted or unreliable null stops later strategy reruns on
that root. No config respec.

### Trials

Every planted evaluation, every drift-aware seed, and every week-block seed
increments `TrialRegistry`. D13 counts. Report N per root and total.

### What this run is not

- Not a geometry change (action 2).
- Not an ES gap exclusion (action 3).
- Not a 12-config template rerun.
- Not a holdout evaluation.
- Not SIM orders.

## Open questions for the team (do not block this lock)

- Q-NULL-1: Is ≤10% A2 the intended reliability bar, or another threshold?
- Q-NULL-2: Confirm both detrend **and** balance vs exactly one of them.
- Q-NULL-3: Confirm ISO-week block-shuffle (not calendar month) as the extra.
