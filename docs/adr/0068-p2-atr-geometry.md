# ADR-0068: P2 per-family ATR/points geometry

**Status:** Proposed
**Date:** 2026-10-29
**Deciders:** Onderzoeksteam advisory 2026-10-29 16:03 (forwarded by Steve) + LUMINA Engineering

Addendum to ADR-0063 / 0067. New file. Catalog 16/8 is archived, not edited.

## Context

Fixed 16/8 on 1m dominated the first real-tape kills. Geometry must be
pre-registered per family in ATR or points, equal micro vs mini, with a
positive control in that geometry.

## Decision

1. Causal 14-session RTH ATR in **points**. Fade 1.0/1.2, breakout 1.8/0.9,
   gap/OR session-horizon with no 1m bracket.
2. Ten ES configs `p2a-*`. MES is the D13 ATR control only. NQ closed.
3. Control: session-direction plant, 1:1 1.5×ATR, ADR-0067 null.
4. 16/8 archived as lab, not economic death.

## Consequences

### Positive

- Micro and mini share the same point stop. Holding is the session.

### Negative

- 1.5×ATR may still clip a large session OC; fail-closed if the control misses.

## Alternatives considered

1. Keep 16/8 with more lookbacks — rejected: low-value, advisory stop.
2. Asymmetric control matching breakout 1.8/0.9 — rejected: 2R null artefact.
3. Calendar-day flatten — not locked; session flatten is C10.

## Links

- Pre-register: `experiments/reports/phase5_p2_atr_geometry_preregister_2026-10-29.md`
- Archive: `experiments/reports/phase5_p2_16_8_lab_archive_2026-10-29.md`
