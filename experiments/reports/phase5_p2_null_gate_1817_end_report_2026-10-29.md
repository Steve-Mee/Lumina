# Onderzoeksteam 18:17 — null-gate + null-only FPR (2026-10-29)

Binding input (Steve forwarded; **not** Steve's opinion):
`docs/research/ONDERZOEKERS-ANTWOORDEN-NULLGATE-20261029T1817.md`
content sha256 `8d6dc539bef53d4e4bfe6ec6cdaefdd5f06d2508c11407f9648bb293dfd547c2`
(prefix `8d6dc539`). Unchanged.

Stacked draft PR #72 on #69. **No merge. No SIM/REAL orders. Holdout pin
`2026-01-28T23:00:00Z` unopened. Risk Core untouched. ES CSV not in git.**

DSR **0.95**, PBO **0.50**, planted A2 detection, CostModel **1.2.0** unchanged.
Seeds `20261029+i` unchanged. No seed reroll. No templates. No NQ. No holdout
eval. No strategy-run this turn.

---

## 1. Gate (chosen definition)

Primary: a seed is a false edge when A2 fires **and** +OOS ≥ 7/8.
Old A2 (`+OOS ≥ 5/8`) stays diagnostic. Always report both exact fractions.

Fail at `n_edge ≥ 4/32`. **4 is fail**, not monitor (supersedes 17:34).
`0–3/32` pass. Target FPR ceiling 5–10% under the strict definition.

## 2. Null strengthening

Production builder **v2** `linear_magnitude` (first principles, not tuned on ES):

1. Stronger detrend: OLS linear residual of session OC vs time index per WF partition
2. Session-shuffle of residual signs (same mixing as v1; ISO-week block of
   planted signs stays report-only extra, because replacing the session shuffle
   with week-block would keep intra-week drift)
3. Count-balance `|n_pos−n_neg|≤1`
4. Better window balance: greedy opposite-sign swaps that reduce
   `|sum(sign · |OC|)|`

v1 `mean_shuffle` is the before-score only. Null-only skips the extra 8
week-block seeds.

Research-run lock: CLI `first` / `four-instrument` / `atr-es` refuse until
`phase5_p2_null_only_validation.json` has `strict_gate_pass=true` and v2
`n_edge ≤ 3/32` on **both** ES and synthetic. `null-only` and `null-audit`
remain allowed.

## 3. Tape

Local ES PIT NT8 1m continuous, UTC, holdout already cut. Not committed.

| field | value |
|---|---|
| path | local only (`/tmp/lumina_null_only/ES/1m/nt8_es_1m.csv`) |
| bars | 818851 |
| first | `2023-10-01T22:01:00Z` |
| last | `2026-01-28T22:00:00Z` |
| sessions after prepare | 598 |
| WF | IS 45 / OOS 69 / 8 windows |
| holdout assert | no timestamp `>= 2026-01-28T23:00:00Z` |
| synthetic | 40 all-up RTH sessions from 2025-03-03 (before the pin) |

## 4. Exact FPR (before / after)

From `experiments/reports/phase5_p2_null_only_validation.json`
(`generated_at` `2026-10-29T17:33:06Z`). Unclipped 20000/20000 remap.
CostModel 1.2.0. 32 seeds. Extra week-block seeds skipped.

| tape | builder | exact A2 (old) | A2 share | exact 7/8 (strict) | strict share | ≤3/32 |
|---|---|---|---|---|---|---|
| synthetic | v1 `mean_shuffle` | **9/32** | 28.1% | **2/32** | 6.3% | yes |
| synthetic | v2 `linear_magnitude` | **0/32** | 0.0% | **0/32** | 0.0% | yes |
| ES | v1 `mean_shuffle` | **4/32** | 12.5% | **0/32** | 0.0% | yes |
| ES | v2 `linear_magnitude` | **6/32** | 18.8% | **0/32** | 0.0% | yes |

`strict_gate_pass`: **true**.

## 5. Goal met?

**Yes, under the chosen 7/8 definition.** After v2, `n_edge` is `0/32` on
synthetic and `0/32` on ES (`0% ≤ 10%`; `0–3` is the pass band; `4/32` would
fail).

v2 also killed the synthetic **old A2** leak (`9/32 → 0/32`). On ES, old A2
stayed a diagnostic leak and moved `4/32 → 6/32` (12.5% → 18.8%), still above
the 5–10% A2 band. That is not the cycle stop.

This attached ES v1 A2 (`4/32`) is not the frozen PIT unclipped ES A2 (`5/32`):
different file, holdout already cut, v1 re-scored here rather than reused.

## 6. What was not run

- No strategy-run, no template grid, no `p2b-*`, no ATR midpoint PIT
- No NQ templates (still closed)
- No holdout eval (pin never opened; tape contains no holdout bars)
- No positive-control-run on catalog templates

The lock file now *would* allow a later `first` / `four-instrument` / `atr-es`
cycle. This turn still stops after null-only.

## 7. Hygiene

- No live / SIM orders
- Risk Core not modified
- Tests not weakened (4/32 is now fail; research CLI without a passing JSON
  returns 2; DSR floor still 0.95)
- Week-block still 8 extra D13 trials when a null-audit runs; not a gate
- Seals `85e4588f` / `454b8d1f` / `cdf964b6` not rewritten

## 8. Open questions

1. ES raw A2 is still 6/32 after v2. Is a further A2-only repair wanted, or is
   strict `0/32` enough?
2. v2 strict FPR is `0/32`, below the 5% floor of the named 5–10% band. The
   written rule is a ceiling (`≤ 5–10%`) and `0–3` pass. Confirm that 0/32 is
   accepted rather than “too tight”.
3. NQ templates remain closed until a new approved pre-register.
4. ATR D13 `n_edge` is still missing (PIT JSON has no per-seed +OOS). ATR MES
   raw A2 `4/32` is now labeled fail as a diagnostic, not a new ATR rerun.
5. Midpoint D13 PIT (fade 1.0/1.2 and breakout 1.8/0.9) is still owed when
   CSVs are mounted — not this run.
