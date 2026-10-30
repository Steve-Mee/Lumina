# ADR-0073: P2 existence tests (non-DSR sibling book)

**Status:** Proposed
**Date:** 2026-10-30
**Deciders:** Onderzoeksteam answers 2026-10-30 11:06 (BESTAANSTOETSEN)
(forwarded by Steve; not Steve's opinion) + LUMINA Engineering

Addendum to ADR-0072. Does not rewrite CostModel 1.2.0, DSR 0.95, PBO 0.50,
the 7/8 null gate, holdout pin `2026-01-28T23:00:00Z`, or Risk Core. Does not
reset the hard-stop counter. Does not reopen `p2-next-search-space`.

Binding input: `docs/research/ONDERZOEKERS-ANTWOORDEN-BESTAANSTOETSEN-20261030T1106.md`
content sha256 `6b9dc2a894b1f10d37e6a96745377627682de7b758ee1a9cd2b70b127a5f8ab4`.

Canonical spec sha256
`5a3a54f429c768d2181a037ba99f029f47a6ffcc4d53cb79a7b16672deebec41`.

## Context

The 10:00 GO on book `p2-next-search-space` produced 0 survivors and stopped
the DSR line. The research team then ordered two pre-registered **existence
tests** (calendar rebalancing; overnight RTH close→next RTH open plus a
20-day trend filter) as a **separate book that does not count in DSR N**.
A passing direction later gets a full Validation Gate cycle in a **new**
book at N=0. Docs/code lock only. **No run.**

First principles: intellectual honesty (implement only the stated rule;
flag every choice the team did not make), fail-closed (refuse reconstitution,
roll week, cost, and t-vs-bootstrap rather than inventing them), capital
preservation (no SIM/promotion, holdout sealed, Risk Core untouched, ES
only, no NQ trading).

## Decision

1. **Sibling book** `p2-existence-20261030` on the v3 ledger. `active_book`
   stays `p2-next-search-space` / `research_line_stopped`. `counts_in_dsr_n`
   is false. `trials_run` is false.
2. **Test 1** `ex-01-calendar-rebalance`: long ES previous close → event
   close. Implement `month_end` and `quarter_end` only. Block
   `index_reconstitution` and `roll_week`.
3. **Test 2** `ex-02-overnight-trend-20d`: long ES RTH close → next RTH
   open if previous 20-day return > 0. 60/120d are mechanism-only and are
   not implemented. Lookback unit is unresolved.
4. **Refuse the run** in code and in `python -m lumina_research.proof
   research --cycle existence`. The existence cycle skips the DSR ledger
   check so a refuse is not mis-attributed to `research_line_stopped`.
5. **Ambiguities stay unresolved** (reconstitution source, roll-week
   definition, cost of one trade, t-test vs bootstrap, and the rest listed
   in the prereg). No optimization. No atr-es retest. Looser DSR 0.5 / 5/8
   is not accepted. Test 3 (options gamma) is not in this lock.

## Consequences

### Positive

- Existence work cannot inflate DSR N or reset the stop counter.
- A later GO cannot pretend reconstitution or roll week were locked.
- CLI `existence` cannot accidentally start a DSR cycle.

### Negative

- The tests cannot actually run until the team names cost, statistic,
  reconstitution source, roll week, and the other flagged items.
- Month-end identification on a truncated month fail-closes (last tape
  session that is not the last calendar day is not month-end).

## Alternatives considered

1. Count existence tests in DSR N — rejected: 11:06 Q1.
2. Choose t-test, a cost, and NT8 roll dates so a run can proceed —
   rejected: implement only the rule; flag the rest.
3. Implement 60/120d because they appear in the mechanism sentence —
   rejected: the locked rule is 20-day only.
4. Run the tests in this change — rejected: explicit STOP.

## Links

- Team answers: `docs/research/ONDERZOEKERS-ANTWOORDEN-BESTAANSTOETSEN-20261030T1106.md`
- Operational lock: `experiments/reports/phase5_p2_existence_preregister_2026-10-30.md`
- Code: `lumina_research/cycles/existence.py`
- Related: ADR-0072
