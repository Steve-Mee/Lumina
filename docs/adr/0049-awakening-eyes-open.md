# ADR-0049: Awakening — First Watch

**Status:** Accepted  
**Date:** 2026-09-18  
**Deciders:** LUMINA Engineering (Steve + Grok)  
**Refines:** [ADR-0026](./0026-evolution-proof-gate.md) implementation (floors stay; loopholes close)  
**Relates:** [ADR-0036](./0036-birth-exit-vs-maturation.md), [ADR-0046](./0046-birth-foundation-evolvable-plant.md), [organism-maturation-phases.md](./organism-maturation-phases.md)

> **Current law (2026-10-06).** The phase is still named **Awakening**. Its exit is **First Watch**, not a child that beats Birth.
>
> One eval of the frozen Birth plant on holdout B. No `learn()`. Pass is fail-closed AND: Birth freeze intact, policy-only, n_B ≥ 500 from the ledgers on disk, occupancy 25–75% on that window, process-R (`median_loss_r` ≤ 1.5), the parent ledger present, STABLE (Sharpe > −2, DD ≤ 25%), weight sha equal to the Birth plant (`baseline_is_plant`), constitution violations = 0 and constitution blocks = 0 as counted by the rollout guard, a Twin-source watch of this run, recovery with the freeze held through that walk, and at least one observed regime.
>
> A different weight sha is `baseline_not_the_plant`. It does not pass. The paired CI of +0.05R and the anti-scalp line are written on the record and **do not open this door**. They are the exam before a Playground rule becomes the hand: the sentence is replayed on the sealed plant's session days, and `rule_exam_passed` scores that replay. Stored rows and a `passed: true` flag do not promote.
>
> Playground accepts the sealed baseline zip, including when that zip is the Birth plant. The seal counts only when the live zip, the Birth zip, and both ledgers still match the hashes in `state/lumina_first_watch_baseline.json`.
>
> SSOT: `lumina_core/maturity/awakening/law.py`. The decision table and amendments below are history. Where they disagree with this box, this box wins. Finished runs are not regraded.

## Context

Birth Foundation (ADR-0046) built an evolvable plant. Awakening is the first consciousness of that plant: prefer a better child than frozen π*, perceive regimes, recover without cheating.

The production runner was an evaluator: one 10k PPO shot, WR lift **or** 45% OOS, Twin `samples` dump, and `effective_min_trades = min(500, max(50, n×0.8))`. A live stamp marked Awakening complete on **133** policy closes (+10.3pp lift, OOS 43.6% — 45% not met). Learned still showed `ep_passed: false`. That is not truth-seeking (constitution #3).

Birth already rejected WR 20/35/40% as pass law. Awakening must not reintroduce a WR-only wall or a sample-count Twin.

## Decision

> Historical. Superseded for the exit by the current-law box at the top of this file (2026-10-06). Do not implement this table as the Awakening door.

Awakening exit is fail-closed AND. Floors from ADR-0026 stay (lift ≥ 5pp **or** OOS ≥ 45%) but they sit **on top of** the AND, never instead of it.

| Invariant | Law |
|-----------|-----|
| Birth freeze | Receipts, fitness, completed flag, `birth_exit_pi_star.zip` read-only |
| Train A / eval B | Holdout B never enters `learn()` |
| Policy-only skill | WR, lift, mean_r, edge, Sharpe from policy closes only |
| n_B ≥ 500 | Hard. `effective_min_trades` deleted. n < 500 → INCONCLUSIVE, not pass |
| STABLE | Sharpe > −2, DD ≤ 25% of $50k MES 1-lot. REGRESS / INCONCLUSIVE ≠ pass |
| Occupancy | Band 25–75% on the sample window (`occupancy_at_nb`) once n_B ≥ 500. Full-tape ratio is recorded, not a gate. Below 500, the full-tape ratio, because the sample window is not frozen yet |
| Process-R | `median_loss_r` ≤ 1.5 |
| Prefer-better | edge vs first-touch ≥ 0; child mean_r ≥ Birth fitness mean_r; child sha ≠ init sha |
| Twin-watch | Observations of **this** run (`state/awakening_twin_watch.jsonl`). Metrics dump is not proof |
| Recovery | Honest stall→retry without Birth mutation, floor-cut, or `expand_data` escape. Freeze held through ≥1 cycle proves the living clock; a stall is not required to pass |
| Regime | Slices attempted; insufficient tape → INCONCLUSIVE for that slice, never skip |
| Soft-complete | May warn on hub. Must not set `ok=True` |

Geometry BE (~0.46) is HUD skill pressure. WR ≥ BE remains a **Playground** gate (ADR-0046). Do not pull later walls into Awakening.

SSOT: `lumina_core/maturity/awakening/law.py`. Progress: `state/lumina_awakening_progress.json`. A continuum stamp of `awakening` completed that fails this law is healed to incomplete. Birth is not touched.

### Amendment (2026-09-23) — exam window, not the flat tail

The 22 Sep run kept Birth π* because keep-best gated the full-tape flat ratio. After `forbid_plant_open_after` (500 policy closes) the plant cannot pull the rest of holdout B back into band, so a 500-trade child lands near 0.88–0.91 while `occupancy_at_nb` sits inside 25–75%. Cycle 7 cleared lift (+6.1pp) and was discarded on that tail. The AND then scored the restored clone: occupancy 0.9051, lift 3.1%, `child_sha_equals_init`.

The band does not move. Once n_B ≥ 500, AND and keep-best read `occupancy_at_nb`. `occupancy_full_tape` stays on the record and on Telegram. Below n_B 500 the full-tape ratio remains the gate. A missing sample window at n_B ≥ 500 is `occupancy_missing`, fail-closed.

### Amendment (2026-09-23) — do not breed a GRIND child

The 23 Sep run kept Birth π* for a different reason. The occupancy sample window was inside 25–75% on every cycle. Cycles 1–8 each improved per-trade mean_r and were discarded for `stable_rank_drop` (drawdown 34–41% on ~2700 policy closes versus the parent's 7% on 500). The student zip was not reset, so cycles 2–8 fine-tuned that grind lineage. The final AND scored the restored cycle-0 clone: `mean_r` slightly under birth, lift 1.5%, `child_sha_equals_init`.

A `stable_rank_drop` now copies the exam incumbent back over the student, including when winrate and mean_r are better. An occupancy miss still continues the student. The DD cap, lift floor, and OOS floor do not move. The phase-exit Telegram names that parent and the best discarded child; `missing:` stays on the record. Cycle notices lead with VERWORPEN or BIJGEHOUDEN. That verdict is not a phase pass.

### Amendment (2026-09-24) — train on A toward the wall, do not move it

The 22 Sep and 23 Sep clocks failed Evolution Proof because the exam scored the restored parent (lift 3.1% and 1.5%). Train reward paid process-R and an occupancy potential. That potential pulls a too-flat parent into more trades. The 23 Sep children improved mean_R and still missed +5pp, with drawdown 34–41% on ~2700 policy closes. A reset on `stable_rank_drop` stops breeding that zip. It does not, by itself, move a 500-trade fine-tune across a 5pp winrate gap.

Tape A now adds two train-only terms. A win bonus of at most 0.15R is paid on a policy win after 50 policy closes, and only while the running tape-A winrate is still below the frozen parent's tape-A winrate plus 5pp. The parent winrate is one predict-only measurement on tape A, cached by parent sha. Holdout B is not that reference. A path-DD tax of 0.25R applies on the next policy close once 500 policy closes already exist and the USD drawdown of those closes has reached 20%. The tax is applied after occupancy shaping and is not clipped by the 0.05R potential cap. Eval ledgers stay raw process-R. The 5pp / 45% / 25% DD / n_B ≥ 500 floors do not move.

### Amendment (2026-09-24) — paired regret, same 0.05, no regrade

The 24 Sep clock (`20260923T224531Z`) kept a child at +1.4pp winrate. Mean R improved from about −0.31 to −0.14 and median loss R from about 1.09 to 0.35. Cycle 5 had +3.5pp and was replaced because mean R ticked up 0.009R. The tape-A win bonus (≤ 0.15R) did not move winrate; the loss-cut gradient did. That run stays a failed experiment. The bonus cap is not raised.

ADR-0026 inside this AND no longer treats a winrate point estimate as proof. Proof is the day-blocked 95% lower bound of child mean R minus a predict-only replay of frozen Birth π* on the same holdout B, ≥ +0.05R, n_B ≥ 500, plant closes excluded. OOS winrate ≥ 45% remains an alternate. A missing replay does not pass. Median win-R collapsing below half the parent's does not pass. Keep-best, when both paired deltas are present, keeps the higher delta. Winrate lift remains on the journal and is not the wall. Occupancy, STABLE, freeze, and the rest of this AND stay. Playground still owns mean R ≥ 0 and winrate ≥ breakeven.

### Amendment (2026-10-04) — the meter is the law that was already written

Run `20261003T102054Z-03ca4e86` stays a fail. It is not regraded.

Three meters made a pass unreachable for every plant. `default_eval` dropped `occupancy_at_nb`, so n_B ≥ 500 was `occupancy_missing` and keep-best treated the window as out of band. STABLE was fed `sharpe_from_pnl`, which multiplies the trade information ratio by √252. The −2 / −3 lines were written for `s5_holdout_sharpe`. A Birth-legal book near −0.23R per unit of risk was labeled `GRIND_REGRESS` near −3.7. The phase-exit law recomputed paired CI from the live holdout ledger, so a discarded last cycle replaced the kept child's CI.

> Historical meters from 2026-10-04. The +0.05R sentence in this paragraph is not the Awakening exit. See the current-law box.

The band, the −2 floor, the −3 regress line, and n_B ≥ 500 do not move. The sample window is still the occupancy gate once n_B ≥ 500, and a missing window still fails closed. Sharpe in this AND is the trade ratio. On keep, the child ledger and the parent replay are frozen beside the incumbent zip, and the law reads that pair. `parent_holdout_*` is that replay, with the parent's weight sha. Weight identity compares tensor storages inside `policy.pth`. A container resave is not a new child. Cycle 0 evaluates the frozen Birth zip. A leftover student zip is not cycle 0. Optimizer state is not the weight hash. Holdout B stays out of `learn()`.

### Amendment (2026-10-05) — train tax matches the anti-scalp clause

Runs `20261004T131609Z-69cf1cd0` and `20261004T200041Z-757b9115` stay fails. They are not regraded.

From 30 Sep 18:21 the live trainer no longer called the tape-A win bonus. `awakening_train_reward.py` was emptied and `SelectPhysicsEnv` paid raw process-R, a 0.05R participation bonus, and a 0.01R overhold tax. Eight fine-tunes still cut the typical winner. On `20261004T200041Z` the kept child (cycle 5) had median win 0.416R against the frozen parent's 1.018R, and day-blocked CI −0.037R. The phase exit named only `median_win_r_collapsed` because that check returned before the CI line. Both misses are now listed. Pass/fail is unchanged.

The 5 Oct clock (`20261005T050604Z`) ran that tax. It stays a fail. Cycle 1 cleared the anti-scalp line (median win 0.580R versus half of 1.018R) and missed only the day-blocked CI (−0.0056R, point delta +0.061R, 7 shared days). The tape-A probe median was 2.233R, so the flat −0.25R charge stays on for any book under 1.116R and then no longer distinguishes a small win from a large one. That flat tax is not the next experiment.

The trainer now pays the session-day residual on tape A: policy `trade_r` minus the frozen Birth mean `trade_r` of the entry bar's day, from one predict-only walk that reads `trade_r`. The flat −0.25R tax is unwired. A missing parent day leaves the close reward unchanged. Holdout B, +0.05R, the occupancy band, STABLE, and n_B ≥ 500 do not move. The 0.15R win bonus stays unwired.

### Amendment (2026-10-06) — First Watch is the exit

Run `20261006T044622Z-0a85fd99` stays a fail. It is not regraded. The day-residual clock kept median win 1.018R against 1.018R and missed paired CI −0.0478R. That residual is a closed experiment.

Awakening exit is the frozen plant's own holdout book. One eval, no `learn()`. The book must reach n_B ≥ 500, sit in the occupancy band, stay STABLE, keep the Birth weight sha, record zero constitution violations and zero constitution blocks from the rollout guard, show the regimes it saw, and keep the parent ledger on disk. A different weight sha is `baseline_not_the_plant`. The paired CI and the anti-scalp line are written on the record and do not open this door.

The +0.05R paired CI, still with the anti-scalp line and n_B ≥ 500, is required before a Playground rule becomes the hand. `rule_exam_passed` replays the sentence on the sealed plant's session days and scores that replay against the parent ledger. Stored rows and a file that only says `passed: true` do not promote. Playground accepts the sealed baseline zip, including when that zip is the Birth plant, only while the zip and both ledgers still match the seal hashes.

## Consequences

### Positive

- 133-trade lift cannot complete Awakening.
- Operator sees the same AND the engine uses.
- Birth plant stays the frozen parent.

### Negative

- Honest Awakening takes a longer clock (n_B ≥ 500). That is the point.
- One eval walking holdout B (`tape_exhausted`) is INCONCLUSIVE when n_B < 500. It is not a pass and not a clock stop. Cycles continue the child zip. Wipe is the only return to frozen π*.
- Plant FORCE_OPEN / FORCE_EXIT closes are occupancy airframe. Skill (WR, mean_r, Sharpe, edge) is policy-only. Zero plant closes is not a pass law.

## Alternatives considered

1. Keep `effective_min_trades` — rejected; it legalizes n=133 against the 500-trade wish.
2. WR-only pass (lift or 45%) — rejected; Birth already retired WR as pass law.
3. Twin dump `samples ≥ 10` — rejected; not watch of this run.
4. Soft-complete lab stamp — rejected in production.

## Links

- Code: `lumina_core/maturity/awakening/`
- Tests: `tests/maturity/test_awakening_law.py`
- Wipe kind: `awakening_only` (Genesis + Birth kept)
