# P2 drift-aware null — addendum after team answers (2026-10-29 17:34)

**Partial supersession (18:17):** `4/32` is fail, not borderline/monitor.
Production builder is `linear_magnitude`. See
`phase5_p2_null_v2_preregister_addendum_2026-10-29.md`.

Does **not** rewrite the original pre-register
`phase5_p2_multiseed_null_preregister_2026-10-29.md` (git `bf665e5d`).
Binding answers:
`docs/research/ONDERZOEKERS-ANTWOORDEN-9VRAGEN-20261029T1734.md`
sha256 `d792a116…`. Forwarded by Steve; not Steve's opinion.

Holdout pin `2026-01-28T23:00:00Z` stays closed. No SIM/REAL orders. Risk Core
untouched. DSR/PBO/A2 planted detection unchanged. Seeds unchanged
(`20261029+i`, no reroll). Builder still detrend **and** balance (Q-NULL-2).

## Reliability bar (replaces majority 16/32)

A seed hits A2 when median OOS > 0, +OOS share ≥ 0.60, and there is no
structural decay. Always report the exact fraction `n_a2/32`.

A seed is a **calibrated false edge** when A2 fires **and** +OOS ≥ 0.875 (7/8).
The cycle stop uses `n_edge`, not raw `n_a2`. Raw A2 has P≈0.36 on 8 fair
windows, so P(n_a2≥4)≈1; gating on raw A2 would Type-I a true null. 7/8 is
Bin(8,0.5) one-sided p≈0.035; then P(n_edge≥4 | 32)≈0.025 (conservative vs
the 5–10% true-null fail target).

| field | A2 diagnostic (`n_a2`) | calibrated gate (`n_edge`) |
|---|---|---|
| definition | median>0, +OOS≥0.60, no decay | A2 **and** +OOS≥0.875 |
| reliable | `≤ 3/32` | `≤ 3/32` |
| borderline | `== 4/32` (monitor; MES ATR) | `== 4/32` |
| unreliable | `≥ 5/32` | `≥ 5/32` (cycle stop) |
| majority 16/32 | **not** the gate | **not** the gate |

Week-block: 8 ISO calendar-week shuffles `20261129+i`. Extra reported check.
Not a gate. Month is too coarse (Q-NULL-3).

## Re-score of frozen PIT (no new bars)

Private CSVs are not in this workspace. Counts below are the **same** 32-seed
hits already recorded, classified under the new bar. Not a rerun.

### Action 1 — unclipped 20000/20000

| root | exact A2 | A2 status | exact 7/8 edge | edge status | old majority |
|---|---|---|---|---|---|
| MES | **6/32** | unreliable (diagnostic) | **0/32** | reliable | majority-pass |
| MNQ | **10/32** | unreliable (diagnostic) | **1/32** | reliable | majority-pass |
| ES | **5/32** | unreliable (diagnostic) | **0/32** | reliable | majority-pass |
| NQ | **8/32** | unreliable (diagnostic) | **0/32** | reliable | majority-pass |

Verdict: the **calibrated gate does not change** unclipped D13 (all `n_edge`
≤1/32, planted detected, planted beats median-of-medians). A2 rates 16–31%
remain above the 5–10% A2 target — a remaining leak diagnostic, not a cycle
stop. MNQ 7/8 seed: `20261059`. No seed reroll.

### Action 5 — ATR 1.5×ATR14

| root | exact A2 | A2 status | exact 7/8 edge |
|---|---|---|---|
| ES | **1/32** | reliable (3.1%, inside 5–10%) | **not in PIT JSON** (no per-seed +OOS) |
| MES | **4/32** | **borderline**, monitor | **not in PIT JSON** |

Planted still detected on both. Templates 10/10 DSR-kill unchanged.

NQ templates stay closed until a **new** approved pre-register (Q-NQ-1).
