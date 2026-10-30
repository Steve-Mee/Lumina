# Research team answer (NOT Steve's opinion), relayed by Steve 2026-10-30 11:06 Europe/Brussels
Order accepted: 1 calendar rebalancing, 2 multi-day risk premium (overnight + trend 20/60/120), 3 options dealer gamma after data costs. FX/commodities and GP dropped.

Test 1 Calendar rebalancing: mechanism forced rebalancing by index funds/institutions at known calendar windows (month-end, quarter-end, index reconstitution, roll week). Expected: positive excess return in the 1-3 trading days around month-end, quarter-end, known index reconstitution dates vs control days. Rule (not optimized): long ES from close of day before event to close of event day (or next day if event after close). Controls: matched non-event days in same month. Test: two-sample t-test or bootstrap on excess return; kill if excess return not positive and significant at p<0.05, or effect size smaller than cost of one trade. Data pre-holdout only.

Test 2 Multi-day risk premium: overnight premium + multi-day trend persistence. Expected: positive overnight return (RTH close to next RTH open) and positive return to trend-following 20/60/120d. Rule (not optimized): long ES RTH close to next RTH open. Trend: long if previous 20-day return > 0, hold overnight. Controls: flat or random-entry baseline. Test same as above; kill if no positive excess return distinguishable from zero after costs. Pre-holdout only.

Q1: existence tests do NOT count in DSR N. A passing direction gets its full validation cycle in a NEW book, trial count from 0; directions evaluated separately, no shared book.
Q2: stop rule confirmed: 0 survivors over the three directions under full charter (DSR>=0.95, >=7/8 +OOS, net>0) = goal unattainable with current means. Looser threshold (DSR 0.5, 5/8) NOT accepted.
Q3: the 4 atr-es configs are dead; do not retest.
No trials run until the existence tests are locked in code. Agents may implement the pre-registration.
