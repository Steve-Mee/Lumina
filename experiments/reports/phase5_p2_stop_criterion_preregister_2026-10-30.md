# P2 hard-stop criterion — pre-registration (2026-10-30)

**Committed before any new hypothesis pre-register and before any new trial.**
This file locks the stop rule. It does **not** lock a new strategy config.

Binding input (Steve forwarded; **not** Steve's opinion):
`docs/research/ONDERZOEKERS-ANTWOORDEN-FABRIEK-20261030T0812.md`
content sha256 `de73d38ccc30912a439b226f4248d5581f46d3253995dbbd6760fe1943c592f6`
(prefix `de73d38c`).

NQ-open answers (same morning, not a hypothesis lock):
`docs/research/ONDERZOEKERS-ANTWOORDEN-NQOPEN-20261030T0815.md`
content sha256 `844843564c0a4f5c8b3e6fa56aaff1ff0a696107a2020de5de9534431ab18c92`
(prefix `84484356`).

Book-split answers (Steve forwarded; **not** Steve's opinion):
`docs/research/ONDERZOEKERS-ANTWOORDEN-BOEKSPLIT-20261030T0833.md`
content sha256 `a970bf171b9e38a0bdc69b919c7cc0484c711e99068bfcd765e9f6d5d6c21474`
(prefix `a970bf17`).

Stacked draft PR #72. **No merge. No SIM/REAL orders. Holdout pin
`2026-01-28T23:00:00Z` unopened. Risk Core untouched.** Docs/code only.

Does **not** rewrite CostModel 1.2.0, DSR 0.95, PBO 0.50, or the 7/8 null gate.

## Verbatim stop (locked)

Dutch (FABRIEK item 5):

```
na 3 volledige cycli of 60-80 prereg hypotheses met 0 survivors, of 2 cycli met hoge positive-control power maar alles faalt na kosten -> zoekruimte fundamenteel wijzigen of stoppen/herallocatie.
```

English (operational lock):

```
after 3 full cycles OR 60-80 prereg hypotheses with 0 survivors, OR after 2 cycles where positive-control power is high but every real hypothesis fails after costs, the search space is declared insufficient, and then either it is changed fundamentally or research stops.
```

Any one clause is enough. Same-space 1m short-horizon single-instrument ideas
are not a "fundamental change".

## Which cycles count so far

Counted **full strategy cycles** (pre-registered hypothesis grids through the
Validation Gate; 0 survivors). Control-only runs do not count.

| # | cycle | ids | n prereg | killed | survivors | high +control power | all fail after costs | source |
|---|---|---|---|---|---|---|---|---|
| 1 | `atr-es` | `p2a-*` | 10 | 10 | 0 | no (ATR D13 1.5×; 6.25% floor not yet the protocol) | yes | `phase5_p2_atr_es.json` |
| 2 | `limited-es` | `p2l-*` | 6 | 6 | 0 | yes (midpoint 6.25% floor clean, planted detected, null 7/8 0/32) | yes | `phase5_p2_limited_es_end.json` |
| 3 | `postkill-es` | `p2p-*` | 3 | 3 | 0 | yes (same midpoint protocol) | yes | `phase5_p2_postkill_end.json` |

**Counted totals:** 3 full cycles, 19 prereg hypotheses, 0 survivors, 2
high-power cycles where every real hypothesis failed after CostModel 1.2.0.

Never promote on gross. `p2p-vx-es` gross +0.230 / net −0.129 is a kill.

### Not counted (explicit)

| cycle | why it does not count as a full stop-cycle |
|---|---|
| `first` (MES/MNQ 12, 16/8) | archived lab, ADR-0068; different geometry |
| `four-instrument` (ES/NQ 16/8 translations) | NQ single-instrument stays closed; not the later midpoint-power protocol |
| `null-audit` / `null-only` | control-only; no strategy hypotheses |
| `midpoint-d13` / `midpoint-power` / `midpoint-power-floor` | control-only; no strategy hypotheses |

## Clause status at this lock

| clause | bar | status |
|---|---|---|
| 3 full cycles, 0 survivors | 3 / 3, survivors 0 | **tripped** |
| 60–80 prereg hypotheses, 0 survivors | 19 prereg (fail-closed trip at ≥ 60) | not tripped |
| 2 cycles, high +control power, all fail after costs | limited-es + postkill-es | **tripped** |

**Search space is declared insufficient.** Next work is a fundamental change
(longer horizon / lower turnover / relative-value ES vs NQ) **or** research
stops. This file does not pre-register that next hypothesis.

## Book split (08:33) — does not reset this counter

Chosen rule: **`split_books`**. Do **not** raise min-DSR (that would be
post-hoc). Closed book `p2-es-limited-postkill` final N = **150**. New book
`p2-next-search-space` starts at **N=0**; DSR/PBO use that book's N only.

This hard-stop counter **counts cycles and hypotheses across books**. The
split resets only the DSR/PBO ledger. After the split the counter is still
3 full cycles, 19 prereg hypotheses, 0 survivors.

A new book opens only after an explicit search-space pre-register (lower
turnover, longer horizon, at least 1 relative-value idea). NQ only under
NQOPEN. Improved null + positive control required. No such hypothesis
pre-register is in this change.
