# ADR-0070: P2 post-kill follow-up — 2.4 ATR breakouts + TOD lookback-45

**Status:** Proposed
**Date:** 2026-10-30
**Deciders:** Onderzoeksteam answers 2026-10-30 06:38 (forwarded by Steve; not Steve's opinion) + LUMINA Engineering

Addendum to ADR-0069. Does not rewrite CostModel 1.2.0, DSR 0.95, PBO 0.50,
the 7/8 null gate, holdout pin `2026-01-28T23:00:00Z`, or Risk Core.

Binding input: `docs/research/ONDERZOEKERS-ANTWOORDEN-POSTKILL-20261030T0638.md`
content sha256 `311ea60a1e8b3f832884669791d9e324c578822f3793db781cb54b9e79590c3b`.

## Context

Limited ES (`p2l-*`) ended `all_kill_no_promotion`. The research team asked for
a short breakout diagnosis (MFE/MAE, exit mix, per-trade costs), then at most
two extra breakout trials at target 2.2–2.5 ATR instead of 1.8, plus one
refined TOD trial. Still net-negative breakouts close the family this cycle.
TOD that fails DSR / +OOS gates closes. Never promote on gross. No plants.
No new large cycle. ES only.

First principles: intellectual honesty (diagnose from the killed PIT, do not
invent a tape), fail-closed (preregister before any run; missing ES CSV
stops execution), capital preservation (no orders, holdout sealed, Risk Core
untouched).

## Decision

1. **Diagnosis is not a trial.** Read MFE/MAE, exit reasons, and four-leg
   costs from `phase5_p2_limited_es.json`. Do not increment `TrialRegistry`.
2. **Breakout stretch.** Fresh ids `p2p-rc-es` and `p2p-vx-es`. Target **2.4**
   ATR (one number in 2.2–2.5, not a search), stop 0.9. Same lookbacks as
   `p2l-rc-es` / `p2l-vx-es`. If both remain net negative after costs, close
   the breakout family this cycle.
3. **One TOD.** Fresh id `p2p-tod-es`. Same fade 1.0/1.2, RTH flatten. Pick
   slightly longer horizon (lookback **45**, not a new skip-open filter):
   session_filter is already RTH; catalog hold is 15–90 minutes. Fail DSR or
   +OOS-window gates → TOD closed. Never promote on gross.
4. **DSR N.** Continue from limited-es high-water **78**. Every new registry
   record counts. Midpoint controls, if re-run, also count. Method control
   stays fade 1.0/1.2 and breakout 1.8/0.9, not the 2.4 stretch.
5. **Tape.** Attached pre-holdout ES only, sha256 `6100588d…`. If that CSV is
   missing, stop: write `tape_missing_no_new_trials`. Do not invent bars.
   Families stay `pending_tape`.
6. **Forbidden.** NQ, promotion, SIM/REAL, plants, new large cycle, Risk Core
   edits, holdout open, extra variants after seeing results.

## Consequences

### Positive

- The 1.8 ATR kill is diagnosed before a stretch: session-end 80–86%, target
  ~2%, slippage-dominated costs, already net negative at a beatable gross BE.
- Three locked trials cannot expand into a search.

### Negative

- Stretching target to 2.4 ATR is a low-probability rescue given MFE≈MAE.
  That is the test the team allowed, not a reason to skip the lock.
- This environment does not mount `/tmp/lumina-es/ES_pre_holdout.csv`.
  Execution is blocked until that sha256 is attached.

## Alternatives considered

1. Close breakouts from diagnosis alone without the two extra trials —
   rejected: the team allowed the 2.2–2.5 re-run; closing needs the run.
2. Search 2.2 vs 2.5 — rejected: one number (2.4), max two trials.
3. Stricter RTH skip-open for TOD — rejected for this cycle: RTH is already
   locked; a new filter is extra surface. Longer horizon (45) is the pick.
4. Promote TOD on gross +0.10 — rejected.
5. Optional plants now — rejected.
6. Invent or synthesize an ES tape when the CSV is missing — rejected.

## Links

- Answers freeze: `docs/research/ONDERZOEKERS-ANTWOORDEN-POSTKILL-20261030T0638.md`
- Pre-register (commit `72078670`): `experiments/reports/phase5_p2_postkill_preregister_2026-10-30.md`
- Limited-es PIT: `experiments/reports/phase5_p2_limited_es.json`
- Code: `lumina_research/cycles/postkill_es.py`
- Related: ADR-0068, ADR-0069
