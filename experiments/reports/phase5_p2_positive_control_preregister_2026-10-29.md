# P2 positive-control respec — pre-registration (2026-10-29)

Locked **before** the control-respec rerun. Steve OK 2026-10-29 12:38 (Brussels).
Researchers D13 / C10 / C11. This file is additive. It does not rewrite
`phase5_first_cycle_preregister.md`, the 12 catalog templates, ADR-0062, or
holdout seal `85e4588fde77159315a72bdaa722d6487f93bbad9bf24999311f893950489d40`.

## Edge (unchanged known size)

At the first RTH bar of each Globex session the control knows the sign of that
session's last-RTH-close minus first-RTH-open on the **unadjusted** tape
(Panama series is not used for this PnL). It enters in that direction. The
null control shuffles those session signs (seed `20261029`) and uses the same
geometry. Known size remains the session RTH open-to-close move minus four-leg
costs.

## Geometry (locked here; not tuned on the 8/8 failure)

| field | value | reason |
|---|---|---|
| instrument | MES (MNQ only if MES train is missing) | same D13 tape as the first real-p2 control |
| session_filter | `rth` | C10 |
| session_end_flatten | `true` | C10; **this is the intended exit** |
| target_ticks | `20000` | 1:1 with stop; see motivation |
| stop_ticks | `20000` | 1:1 with target; not 8 and not 16/8 (C11) |
| time_stop_bars | `2000` | cannot fire inside one RTH session (~390 1m bars) |
| costs | CostModel 1.1.0 four-leg, unchanged | not retuned |
| holdout | pin `2026-01-28T23:00:00Z`, seal `85e4588f…`, unopened | no evaluation/tuning/calibration |

Motivation for 20000/20000, from the **definition** of the planted edge, not from
any observed first-bar range:

1. The known size is the full session RTH open-to-close. Any 1-minute stop or
   target smaller than that session move clips the planted edge, so a 50% null
   is no longer a test of session-direction detection.
2. 1:1 (target = stop) keeps a shuffled 50% null from becoming a 2R artefact.
3. Width is a CME 20% limit-move ceiling in ticks on MNQ: `25000 * 0.20 / 0.25
   = 20000`. MES 20% at the same index is smaller. Brackets therefore cannot
   clip a session OC on this universe; session-end flatten is the exit.
4. A 16-bar time-stop would also clip the known size into a 16-minute scalper.
   `time_stop_bars=2000` is past one RTH session so C10 flatten is what exits.
5. Catalog templates stay on their pre-registered 16/8 (or family geometry) and
   `time_stop_bars=16`. This table is **control-only**.

## Fail-closed

- If the planted control is not detected, or the null looks like an edge: stop
  the cycle (`positive_control_failed`). Do **not** iterate this geometry
  without a new Steve OK.
- DSR >= 0.95 and PBO hard 0.50 / warn 0.25 stay packaged floors.
- The 12 first-cycle configs are unchanged. They run only after the control
  passes.
- Holdout evaluation only if a survivor also passes the charter gate; report,
  do not promote. No SIM/REAL orders.
