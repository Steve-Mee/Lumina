# ADR-0071: P2 hard stop, book split, NQ relative-value open

**Status:** Proposed
**Date:** 2026-10-30
**Deciders:** Onderzoeksteam answers 2026-10-30 08:12 (FABRIEK), 08:15 (NQOPEN),
and 08:33 (BOEKSPLIT) (forwarded by Steve; not Steve's opinion) + LUMINA Engineering

Addendum to ADR-0069 / 0070. Does not rewrite CostModel 1.2.0, DSR 0.95, PBO 0.50,
the 7/8 null gate, holdout pin `2026-01-28T23:00:00Z`, or Risk Core.

Binding input (FABRIEK): `docs/research/ONDERZOEKERS-ANTWOORDEN-FABRIEK-20261030T0812.md`
content sha256 `de73d38ccc30912a439b226f4248d5581f46d3253995dbbd6760fe1943c592f6`.

Binding input (NQOPEN): `docs/research/ONDERZOEKERS-ANTWOORDEN-NQOPEN-20261030T0815.md`
content sha256 `844843564c0a4f5c8b3e6fa56aaff1ff0a696107a2020de5de9534431ab18c92`.

Binding input (BOEKSPLIT): `docs/research/ONDERZOEKERS-ANTWOORDEN-BOEKSPLIT-20261030T0833.md`
content sha256 `a970bf171b9e38a0bdc69b919c7cc0484c711e99068bfcd765e9f6d5d6c21474`.

## Context

Post-kill ES (`p2p-*`) ended `all_kill_no_promotion` with DSR N = 150. The
research team asked for a factory diagnosis, a pre-registered hard stop, a
conditional NQ open, and then chose a **book split** instead of raising
min-DSR. Docs/code only. No new hypothesis pre-register. No new trial.

First principles: intellectual honesty (count cycles across books; DSR N is
per book), fail-closed (closed book accepts no new trials; new book stays
shut until a search-space pre-register), capital preservation (no
SIM/promotion, holdout sealed, Risk Core untouched).

## Decision

1. **Hard stop (verbatim).** After 3 full cycles OR 60–80 prereg hypotheses
   with 0 survivors, OR after 2 cycles where positive-control power is high
   but every real hypothesis fails after costs, the search space is declared
   insufficient, and then either it is changed fundamentally or research
   stops. Counted full cycles: `atr-es` (10), `limited-es` (6), `postkill-es`
   (3). Not counted: `first`, `four-instrument`, control-only null/midpoint
   runs. Clauses 1 and 3 are already tripped. 19 prereg hypotheses is below
   60. **This counter counts across books.** The split does not reset it.
2. **Book split, not a higher min-DSR.** Raising min-DSR after seeing N=150
   would be post-hoc. Close `p2-es-limited-postkill` at final N = **150**.
   New book `p2-next-search-space` starts at **N=0**. DSR/PBO use that book's
   N only. Floor stays 0.95.
3. **New book stays shut.** It opens only after an explicit search-space
   pre-register: lower turnover, longer horizon, at least one relative-value
   idea. NQ only under NQOPEN (relative-value ES vs NQ, pre-holdout, improved
   null `linear_magnitude`, positive control, fresh ids, no SIM/promotion).
   No such hypothesis pre-register is committed in this change.
4. **Forbidden.** New trials, new hypothesis pre-registers, raising min-DSR,
   opening holdout, Risk Core edits, merge, reusing closed-book CLI cycles
   (`first`, `four-instrument`, `atr-es`, `limited-es`, `postkill-es`).

## Consequences

### Positive

- DSR N=150 cannot silently deflate the next search-space cycle.
- The stop rule stays honest across books.
- NQ cannot be used as a same-space 1m single-instrument rerun.

### Negative

- Same-space strategy CLI cycles refuse because the old book is closed.
- The new book cannot receive trials until a search-space pre-register lands.

## Alternatives considered

1. Raise min-DSR at N=150 — rejected: post-hoc; 08:33 chose a split.
2. Leave `decision_required` unset — superseded by 08:33.
3. Count the archived 16/8 MES/MNQ lab as a full stop-cycle — rejected:
   different geometry; listed as not counted.
4. Merge the advisory 250-trial D13/ATR registries into the closed book —
   rejected: current DSR continuation is the limited-es/postkill book at 150.
5. Pre-register a relative-value hypothesis now — rejected: docs/code only.

## Links

- FABRIEK freeze: `docs/research/ONDERZOEKERS-ANTWOORDEN-FABRIEK-20261030T0812.md`
- NQOPEN freeze: `docs/research/ONDERZOEKERS-ANTWOORDEN-NQOPEN-20261030T0815.md`
- BOEKSPLIT freeze: `docs/research/ONDERZOEKERS-ANTWOORDEN-BOEKSPLIT-20261030T0833.md`
- Stop pre-register: `experiments/reports/phase5_p2_stop_criterion_preregister_2026-10-30.md`
- Ledger: `experiments/reports/phase5_p2_trial_ledger.json`
- Code: `lumina_research/cycles/stop_criterion.py`,
  `lumina_research/cycles/trial_ledger.py`,
  `lumina_research/cycles/search_space.py`,
  `lumina_research/cycles/nq_research.py`
- Related: ADR-0069, ADR-0070
