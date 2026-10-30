# P2 existence-test pre-register — book `p2-existence-20261030` (2026-10-30)

**Locked. Not run.** This is a **separate book**. Existence tests **do not
count in DSR/PBO N**. They are not Validation Gate trials. A passing
direction later opens a **new** DSR book at N=0; directions are evaluated
separately with no shared book.

Binding input (Steve forwarded; **not** Steve's opinion):
`docs/research/ONDERZOEKERS-ANTWOORDEN-BESTAANSTOETSEN-20261030T1106.md`
content sha256 `6b9dc2a894b1f10d37e6a96745377627682de7b758ee1a9cd2b70b127a5f8ab4`
(prefix `6b9dc2a8`).

Canonical spec sha256
`5a3a54f429c768d2181a037ba99f029f47a6ffcc4d53cb79a7b16672deebec41`.

Stacked draft PR #72. **No merge. No SIM/REAL orders. Holdout pin
`2026-01-28T23:00:00Z` unopened. Risk Core untouched. No NQ trading. No
optimization. Do not retest the four atr-es configs. Do not run these
tests in this change.**

Does **not** rewrite CostModel 1.2.0, DSR floor 0.95, PBO 0.50, or Risk Core.
Stop counter stays tripped (3 cycles / 19 prereg / 0 survivors) across books
and is **not** incremented by this lock. `p2-next-search-space` stays
`research_line_stopped`.

## Book

| field | lock |
|---|---|
| id | `p2-existence-20261030` (sibling of `active_book`; does not replace it) |
| counts_in_dsr_n | **false** |
| trials_run | **false** |
| instrument | ES only |
| tape | pre-holdout ES `6100588d…`; holdout sealed |
| NQ / SIM / promotion / optimization | false |
| looser threshold (DSR 0.5, 5/8) | **not accepted** |
| atr-es retest | **false** (dead) |
| Test 3 options gamma | **not in this lock** |

## Test 1 — `ex-01-calendar-rebalance`

Mechanism (not optimized): forced rebalancing at known calendar windows
(month-end, quarter-end, index reconstitution, roll week).

**Rule implemented:** long ES from close of the day before the event to
close of the event day (or next day if the event is after close).

**Event kinds implemented:** `month_end`, `quarter_end` from the supplied
session-date sequence (calendar last trading day of the month / of Mar-Jun-
Sep-Dec). A truncated month whose last tape session is not the last calendar
day of that month is **not** tagged month-end.

**Event kinds blocked (ambiguity, not chosen):** `index_reconstitution`,
`roll_week`. `NT8_ROLL_DATES` is **not** a roll-week lock.

**Controls (text only, matching rule unresolved):** matched non-event days
in the same month.

**Kill:** excess return not positive and significant at p<0.05, **or**
effect size smaller than the cost of one trade.

## Test 2 — `ex-02-overnight-trend-20d`

Mechanism (not optimized): overnight premium + multi-day trend persistence.

**Rule implemented:** long ES RTH close to next RTH open **and** long only
if the previous **20-day** return is > 0 (hold overnight). Combined as one
test. Lookback **length** is 20. Lookback **unit** is unresolved.

**Not implemented:** 60-day and 120-day trend. Those numbers appear in the
mechanism sentence only.

**Controls (unresolved):** flat **or** random-entry baseline.

**Kill:** no positive excess return distinguishable from zero after costs.

## Statistic and cost (both unresolved)

The team listed two-sample t-test **or** bootstrap. This lock does not
choose. p<0.05 is locked; one-sided vs two-sided is not.

Cost of one trade is not chosen. Candidates on this box, none selected:

- ES commission round-trip $5.74 (ADR-0055 Free, $2.87/side)
- CostModel 1.2.0 four-leg (commission + half-spread + slippage + impact)
- ES one-way research band $3.00–$12.00

## Ambiguities (flagged, not chosen)

reconstitution dates source; roll-week definition; cost of one trade;
t-test vs bootstrap; 1–3 day expected window vs close-to-close rule;
event-after-close; matched-control definition; Test 2 flat vs random;
20-day unit; 60/120 not in the rule; unfiltered overnight vs combined
20d filter; p-value sidedness; excess-return units; RTH vs Globex event
day; month-end that is also quarter-end (one event or two).

## Not in this change

- No existence-test run on the ES tape
- No Validation Gate / DSR trial
- No Test 3 (options dealer gamma)
- No FX/commodities, no GP
- No 2nd cycle on `p2-next-search-space`
- No merge, SIM, promotion, holdout open, or Risk Core edit
