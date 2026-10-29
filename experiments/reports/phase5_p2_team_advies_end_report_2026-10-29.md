# Onderzoeksteam 16:03 — P2 end report (2026-10-29)

Binding input (Steve forwarded; **not** Steve's opinion):
`docs/research/ONDERZOEKERS-ANALYSE-4MARKTEN-20261029T1603.md`
content sha256 `83476aa358b515f018002c79cf83caa33e335d281cc107e0f61b4be94b474df7`
(prefix `83476aa3`, freeze commit `51872204`). Unchanged.

This stacked draft sits on #69 (`cursor/fase5-p2-costfix-esnq-2249`).
**No merge. No SIM/REAL orders. Holdout pin `2026-01-28T23:00:00Z` unopened
(0 of max 1–2 evals). Risk Core untouched. Private CSVs not in git.**

CostModel **1.2.0** is the basis. Residual ETH-slippage: both RTH and ETH
coefficients are 0.10 and not SIM-fit
(`phase5_p2_eth_slippage_residual_bias_2026-10-29.md`).

Fail-closed: planted miss or unreliable null → stop, no respec, no seed
reroll. Did not fire on action 1 or action 5. Mid-range locks that the
advisory left as bands are listed as open questions (Q-NULL-*, Q-GEO-*);
they did not stop the cycle because the bands were implementable.

---

## Per action

| # | action | status | evidence |
|---|---|---|---|
| 1 | Pre-register + drift-aware 32-seed null on all 4; NQ closed until null reliable | ✅ | prereg `bf665e5d` + addendum `29b1606b`; ADR-0067; audit `50619454`. MES 6/32, MNQ 10/32, ES 5/32, NQ 8/32 A2. All planted. All majority-reliable (`≤16/32`). Median-of-medians negative. NQ templates still closed (action 5). |
| 2 | Pre-register per-family ATR/points geometry §2; 16/8 lab archive; positive control in that geometry | ✅ | prereg `aa4d9d1e` (content sha `e5a6501c…`); ADR-0068; archive `phase5_p2_16_8_lab_archive_2026-10-29.md`. Fade 1.0/1.2, breakout 1.8/0.9, gap no 1m bracket. Control 1:1 1.5×ATR14. |
| 3 | ES TRAIN gaps 2025-07-13/14/15 and 2025-11-28; holdout gaps unused; no MES fill | ✅ | `phase5_p2_gap_exclusion_2026-10-29.md` (`d970359b`). July hole is **instrument-specific** (ES+MNQ missing; NQ/MES present) — excluded ES+MNQ only, not all four. 2025-11-28 already `*` all four. Holdout Apr/May ES holes recorded, **not evaluated**. |
| 4 | Diagnostics: exit reasons, MFE/MAE, unbracket N=60, 1R/1R; gross/net ticks and points | ✅ | extra columns in `phase5_p2_atr_es_results.md` (not extra TrialRegistry strategy trials). Session_end dominates; time_stop=0. Hitrate ~0.48–0.52 vs 16/8 ~0.29. |
| 5 | Re-run only ES + MES control; 10 configs; new geometry; NQ not | ✅ | PIT 15:48–15:56Z. Dedicated seal `phase5_p2_atr_es_holdout_seal.json` `cdf964b6…` (does **not** rewrite `85e4588f` or `454b8d1f`). D13 passed. 10/10 kill, 0 survivors, holdout skipped. |
| 6 | No SIM-orders; no new 1m high-turnover templates | ✅ | grid excludes `close_reversal` / `volume_imbalance`; RTH-only session hold; zero orders. This report + stacked draft; no merge. |

---

## Pre-registration SHAs

| lock | git | content sha256 |
|---|---|---|
| advisory freeze | `51872204` | `83476aa358b515f018002c79cf83caa33e335d281cc107e0f61b4be94b474df7` |
| null prereg | `bf665e5d` (addendum in `29b1606b`) | `107f5d46741793cbd52e9eeffc1e372bba04bea86b81f81af2bda83dd13acea7` |
| ATR/points prereg | `aa4d9d1e` | `e5a6501c853e1db75cacc5710dfe8254066dbf2c34c33571b59f22c5dcf8c5a9` |
| 16/8 lab archive | with `aa4d9d1e` | `db92b3687e5b975a3679f8feaf4a8c0373fb3d75e8f0258952e9c365cc3667d2` |
| gap exclusion | `d970359b` | `f090f65d282b1e79fcd86209eed97f24d3af2f78ddfd68f3b7e64d2034f58cce` |
| ETH residual bias | `d970359b` | `59da978f59abaf08fbcd721ab8a141ba5a2302b7bc8fe33a61855717e1f573da` |
| ATR ES PIT JSON (untouched dump) | this commit | `19e3d9b9f5e8d1250f71c846367e2bd80f29ff5b7a94fdf4c2aa143e3765378f` |
| ATR ES holdout seal | this commit | `cdf964b6413985726a14b7d63375fef9fda52b9a39bedb512ecd43b73b1f8279` |
| live MES/MNQ seal (untouched) | #69 | `85e4588fde77159315a72bdaa722d6487f93bbad9bf24999311f893950489d40` |
| live ES/NQ seal (untouched) | #69 | `454b8d1f7fd8b0fe0ee43b9c4431515be3912e4859a6a268372ec1c3aff5abd4` |

Seeds locked before any PIT: drift `20261029+i` (`i=0..31`). Week-block extra
(action 1 only, report-only): `20261129+i` (`i=0..7`). No seed reroll.

---

## Action 1 — four-market null (unclipped 20000/20000, ADR-0067)

Fail-closed bar = majority-not-A2 (`n_a2 ≤ 16/32`). `≤3/32` is diagnostic only
(Q-NULL-1). Geometry here is still action-1 session-hold, not ATR.

| root | planted | null reliable | A2 | ≤10% diag | planted median OOS | null median-of-medians | week-block A2 | N |
|---|---|---|---|---|---|---|---|---|
| MES | yes | yes | 6/32 | no | +0.00124 | −4.40e-5 | 0/8 | 41 |
| MNQ | yes | yes | 10/32 | no | +0.00269 | −2.81e-5 | 1/8 | 41 |
| ES | yes | yes | 5/32 | no | +0.01240 | −7.98e-4 | 1/8 | 41 |
| NQ | yes | yes | 8/32 | no | +0.02694 | −5.52e-4 | 2/8 | 41 |
| **total** | **4/4** | **4/4** | | | | | | **164** |

NQ method leak is closed. NQ **templates** stay closed this cycle (action 5).

---

## Action 5 — ATR D13 then 10 ES configs (MES control only)

PIT `$LUMINA_RESEARCH_DATA_DIR`, work dir `/tmp/lumina_atr_es_work/`,
generated_at `2026-10-29T15:56:28Z`. n_days ES=598 (July ES hole dropped),
MES=600. Walk-forward 8 OOS windows (IS 45 / OOS 69 on ES).

### D13 in 1.5×ATR (not 20000/20000)

| root | planted median OOS | +OOS | A2 planted | null A2 | ≤10% | majority | median-of-medians | planted beats |
|---|---|---|---|---|---|---|---|---|
| ES | +0.01205 | 1.00 | yes | **1/32** | yes | yes | −0.000705 | yes |
| MES | +0.00122 | 1.00 | yes | **4/32** | no | yes | −7.77e-5 | yes |

A2 null seeds: ES `20261035`; MES `20261031`, `20261032`, `20261034`, `20261049`.
No respec. No seed reroll.

JSON `control_note` still quotes 20000/20000 — report artefact, see
`phase5_p2_atr_es_control_note.md`. Execution was 1.5×ATR.

### ES templates (all kill; 0 survivors; holdout skipped)

| config | family | ATR tgt/stop | verdict | DSR | median OOS | +OOS | n_trades | hitrate | session_end | stop | target | net pts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| p2a-mr-es | fade | 1.0 / 1.2 | kill | 0.000 | −0.00191 | 0.125 | 734 | 0.484 | 590 | 59 | 85 | −1542 |
| p2a-vwap-es | fade | 1.0 / 1.2 | kill | 0.000 | −0.00160 | 0.125 | 729 | 0.486 | 590 | 64 | 75 | −1986 |
| p2a-tod-es | fade | 1.0 / 1.2 | kill | 0.002 | −0.00058 | 0.375 | 589 | 0.494 | 473 | 41 | 75 | −412 |
| p2a-or-fade-es | fade | 1.0 / 1.2 | kill | 0.000 | −0.00159 | 0.000 | 695 | 0.463 | 588 | 49 | 58 | −2331 |
| p2a-or-bo-es | breakout | 1.8 / 0.9 | kill (DSR only) | 0.057 | **+0.00053** | **0.625** | 679 | 0.517 | 589 | 74 | 16 | **+785** |
| p2a-rm-es | momentum | 1.8 / 0.9 | kill (DSR only) | 0.097 | **+0.00090** | **0.625** | 510 | 0.524 | 422 | 73 | 15 | **+805** |
| p2a-rc-es | breakout | 1.8 / 0.9 | kill | 0.000 | −0.00084 | 0.125 | 682 | 0.509 | 589 | 81 | 12 | −857 |
| p2a-vx-es | breakout | 1.8 / 0.9 | kill | 0.000 | −0.00135 | 0.250 | 732 | 0.489 | 591 | 124 | 17 | −1748 |
| p2a-pb-es | pullback | 1.8 / 0.9 | kill (DSR only) | 0.049 | **+0.00066** | **0.625** | 462 | 0.519 | 400 | 56 | 6 | **+486** |
| p2a-gap-es | session | none | kill (DSR only) | 0.019 | **+0.00118** | **0.625** | 511 | 0.521 | 511 | 0 | 0 | **+433** |

PBO 0.200 on every row (CSCV with 8 slices). Floors unchanged: DSR≥0.95,
PBO 0.50, A2. time_stop_bars fired **0** times; almost all exits are
session_end. Unbracketed N=60 hitrate 0.476–0.507; 1R/1R 0.458–0.525
(gap 1R/1R = n/a, no stop).

Four configs have positive median OOS, +OOS 0.625, and positive net points.
They still die at DSR. That is **not** a survivor and **not** a holdout
candidate. Q-GEO-4.

BE `1.634` is a 1/1-tick placeholder (Q-REPORT-1).

---

## Trial counting (D13 counts)

Every `TrialRegistry` increment. Diagnostics (unbracket / 1R/1R) do **not**
add trials.

### This advisory cycle

| bucket | ES | MES | MNQ | NQ | total |
|---|---|---|---|---|---|
| Action 1 D13 (1 planted + 32 drift + 8 week-block) | 41 | 41 | 41 | 41 | **164** |
| Action 5 D13 ATR (1 planted + 32 drift; no week-block) | 33 | 33 | 0 | 0 | **66** |
| Action 5 ES templates (10 hyp + 10 val registry hits) | 20 | 0 | 0 | 0 | **20** |
| **advisory total** | **94** | **74** | **41** | **41** | **250** |

Unique ES strategy configs this grid: **10**. Unique D13 ATR configs: 33 per
root. Action-5 audit.jsonl has 86 `trial` events (66 + 20).

16/8 lab on #69 is archived, not this grid (MES/MNQ 12 + ES 9 + NQ untested).

---

## Seals / hygiene

| seal file | sha256 prefix | instruments | this cycle |
|---|---|---|---|
| `phase5_p2_holdout_seal.json` | `85e4588f` | MES, MNQ | **not rewritten** |
| `phase5_p2_es_nq_holdout_seal.json` | `454b8d1f` | ES, NQ | **not rewritten** |
| `phase5_p2_atr_es_holdout_seal.json` | `cdf964b6` | ES, MES | new, same pin, **unopened** |

Overwrite of `454b8d1f` is refused in `seal.py`. No MES→ES fill. No new 1m
high-turnover templates. No SIM.

---

## Open questions for the team (via Steve)

These were implementable midpoints, not silent inventions. Confirm or name
another lock; do **not** seed-reroll on the existing distribution.

1. **Q-NULL-1.** Fail-closed = majority-not-A2 (`≤16/32`) because `≤3/32` is
   tighter than chance on 6–8 OOS windows. MES ATR null is 4/32 (misses 10%,
   still majority). Confirm the bar.
2. **Q-NULL-2.** Builder is detrend **and** balance per window. Confirm vs
   exactly one of the two.
3. **Q-NULL-3.** Extra check is ISO-week block-shuffle (8 seeds, report-only),
   not calendar-month. Confirm.
4. **Q-GEO-1.** Fade 1.0/1.2 and breakout 1.8/0.9 are range midpoints.
   Confirm vs other values in the advisory bands.
5. **Q-GEO-2.** Session flatten vs calendar-day flatten for gap / opening-range.
6. **Q-GEO-3.** Unbracketed diagnostic N=60 (1h) vs another fixed N.
7. **Q-GEO-4.** Four ATR configs are gross/net positive with +OOS 0.625 and
   still fail DSR. Next lock: stop here, or a new **pre-registered** smaller
   grid (longer horizon / lower turnover) without touching these 10?
8. **Q-REPORT-1.** Results BE `1.634` is a 1/1-tick artefact. Recompute BE
   from ATR points on the next cycle, or drop the column?
9. **Q-NQ-1.** NQ null is now reliable on the unclipped control. Action 5
   forbade NQ templates. Confirm: NQ stays closed until the team asks for a
   new pre-register, or NQ may enter a later ATR grid?

No other unclear point blocked execution. July exclusion is motivated as
instrument-specific (action 3 allowed that). Holdout stays closed.

---

## What this is not

- Not a promotion, SIM fill, or LIVE_RELEASE.
- Not a holdout evaluation (0 of 1–2).
- Not a refutation of mean-reversion / breakout / gap as economics (16/8 is
  lab; ATR 10/10 is DSR-kill on this grid).
- Not an NT8 re-export / re-seal of ES holes.
- Not a merge.
