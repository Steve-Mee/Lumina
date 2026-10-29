# P2 ATR geometry — addendum after team answers (2026-10-29 17:34)

Does **not** rewrite
`phase5_p2_atr_geometry_preregister_2026-10-29.md` (git `aa4d9d1e`).
Binding answers sha256 `d792a116…`.

## Midpoints (not final)

Fade **1.0 / 1.2** ATR and breakout **1.8 / 0.9** ATR are pre-registered
midpoints. Later moves inside the advisory bands need a new pre-register.
The positive control must pass under **exactly** these params. Existing ATR
D13 PIT used 1:1 **1.5×ATR14** (recorded, not rewritten). Midpoint D13 is
implemented in `execute_control(..., target_atr=, stop_atr=)` and
`required_midpoint_controls()`. Synthetic tape: planted is detected under
both midpoints. **PIT not executed here**: `$LUMINA_RESEARCH_DATA_DIR`
is unset and NT8 CSVs are not in git.

## Flatten

Gap / opening-range: flatten at the last allowed bar of the relevant session
(RTH when `session_filter="rth"`) or a pre-registered `time_stop_bars`.
Never UTC calendar midnight.

## Unbracket hitrate

Diagnostics report horizons **16, 60, and 120** bars. Not extra trials.
The 2026-10-29 15:56Z PIT only stored N=60. 16 and 120 need a PIT rerun
when CSVs are mounted.

## DSR-only kills (not survivors)

These four stay killed. DSR floor stays **0.95**. No promotion.

- `p2a-or-bo-es`
- `p2a-rm-es`
- `p2a-pb-es`
- `p2a-gap-es`

A lower-turnover version is a **fresh trial**: see
`phase5_p2_lower_turnover_preregister_proposal_2026-10-29.md`. **Not run.**

## Break-even

Per-family gross BE = `stop_atr / (target_atr + stop_atr)`:

| family | tgt/stop | BE |
|---|---|---|
| fade | 1.0 / 1.2 | 0.545 |
| breakout/momentum | 1.8 / 0.9 | 0.333 |
| gap (no bracket) | none | n/a |

The PIT column `1.634` was `require_geometry(target_ticks=1, stop_ticks=1)`
and is not an ATR break-even. JSON dump stays untouched as PIT history.

## NQ

Closed until a new pre-register is explicitly approved.
