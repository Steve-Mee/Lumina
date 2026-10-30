# P2 null v2 — pre-register addendum (2026-10-29 18:17)

Locked **before** the ES + synthetic null-only validation. Does **not** rewrite
`phase5_p2_multiseed_null_preregister_2026-10-29.md` (git `bf665e5d`) or open
holdout / NQ / templates.

Binding input (Steve forwarded; **not** Steve's opinion):
`docs/research/ONDERZOEKERS-ANTWOORDEN-NULLGATE-20261029T1817.md`
content sha256 `8d6dc539bef53d4e4bfe6ec6cdaefdd5f06d2508c11407f9648bb293dfd547c2`
(prefix `8d6dc539`).

Supersedes the 17:34 addendum row that marked `4/32` as borderline/monitor.

Holdout pin `2026-01-28T23:00:00Z` stays closed. No SIM/REAL orders. Risk Core
untouched. DSR 0.95 / PBO 0.50 / planted A2 detection unchanged. Seeds
unchanged (`20261029+i`, no reroll). No strategy-run, no template grid, no NQ,
no holdout eval until this null-only FPR lock clears.

## Gate (chosen definition)

A seed **hits A2** (diagnostic) when median OOS > 0, +OOS ≥ 0.60, no structural
decay. Always report exact `n_a2/32`.

A seed is a **calibrated false edge** when A2 fires **and** +OOS ≥ 0.875 (7/8).
The cycle stop and the FPR lock use `n_edge`, not raw `n_a2`.

| field | A2 diagnostic (`n_a2`) | calibrated gate (`n_edge`) |
|---|---|---|
| definition | median>0, +OOS≥0.60, no decay | A2 **and** +OOS≥0.875 |
| reliable | `≤ 3/32` | `≤ 3/32` |
| fail | `≥ 4/32` (4 is fail, not monitor) | `≥ 4/32` (cycle stop / lock) |
| majority 16/32 | **not** the gate | **not** the gate |

Target FPR under the **strict** definition: 5–10% ceiling. `0–3/32` passes.
`4/32` = 12.5% fails. Always publish the exact fraction.

## Production builder v2 (`linear_magnitude`)

v1 (`mean_shuffle`, frozen PIT): per WF partition, mean-detrend OC, shuffle
residual signs, count-balance `|n_pos−n_neg|≤1`.

v2 strengthening (first principles, not tuned on ES):

1. **Stronger detrend:** OLS linear residual of session OC vs time index
   inside each WF partition (not the partition mean).
2. **Session shuffle** of residual signs (same mixing as v1). Replacing this
   with an ISO-week block-shuffle would keep intra-week drift and raise FPR.
3. **Count-balance** `|n_pos−n_neg|≤1` (Q-NULL-2, unchanged).
4. **Better window balance:** greedy opposite-sign swaps that reduce
   `|sum(sign · |OC|)|` without breaking the count balance.

ISO calendar-week shuffle of **planted** signs, 8 seeds `20261129+i`, remains
report-only extra (Q-NULL-3). Null-only skips those 8.

## Null-only procedure (this run)

- Tapes: synthetic all-up leak probe (40 RTH sessions from 2025-03-03, before
  the holdout pin) **and** local ES PIT NT8 1m continuous UTC, holdout already
  cut. CSV is not committed. Code asserts no timestamp `>= 2026-01-28T23:00:00Z`.
- Geometry: unclipped 20000/20000 session-hold remap. CostModel 1.2.0.
- Score v1 then v2 on each tape. `fail_closed=False` so a leaking v1 still
  yields counts.
- Unlock research-run only if **both** ES v2 and synthetic v2 have
  `n_edge ≤ 3/32`. CLI cycles `first`, `four-instrument`, `atr-es` refuse
  otherwise. `null-only` and `null-audit` stay allowed.

If v2 still has `n_edge ≥ 4/32` on ES or synthetic: report the exact counts,
keep the lock, do **not** run templates. One pre-registered fallback if
needed: add weekday-mean removal after the linear residual, then a single
re-score. No seed reroll. No strategy-run while leaking.
