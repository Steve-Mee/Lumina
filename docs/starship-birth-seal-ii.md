# Starship Birth Seal II — Implementation Plan

**Taakklasse: Complex.** Cert floors frozen. No yaml `full_auto` force. No big-bang rewrite of `plateau_escalator.py`.

## Goals (Musk)

1. **Delete vanity names** — tournament physics must say “tournament”, not “edgescore lift”.
2. **Champion sacred** — hard-stop writes explicit attention; prove no train path after reject.
3. **Compress theater surface** — extract evolution ladder tables/step API into a thin module; escalator remains detection/state host.
4. **Twin / cert** — still evidence-gated; no floor drop, no forced mode.

## Work items

| ID | Work |
|----|------|
| S2-1 | Write `swarm_tournament_*` progress/metrics keys; keep `swarm_edgescore_*` as read/write legacy aliases |
| S2-2 | Alias `swarm_tournament_lift` → same as `swarm_edgescore_lift` |
| S2-3 | Hard-stop: ensure `needs_attention` + recommended actions on progress; unit proof |
| S2-4 | New `plateau_evolution_ladder.py`; re-export from `plateau_escalator` |
| S2-5 | Docs pointer + tests |

## Explicit non-goals

- Lowering `BirthCertificateThresholds`
- Setting `approval_twin.mode: full_auto` in yaml
- Full split/delete of all plateau escalator god-surface LOC in one PR

## Status (executed)

| ID | Status | Notes |
|----|--------|-------|
| S2-1 | Done | Dual-write in progress/scorecard/session/data_ops + recovery reset |
| S2-2 | Done | `swarm_tournament_lift` + `swarm_edgescore_lift` wrappers; tests |
| S2-3 | Done | `needs_attention` via reject flags; hard-stop / no-train unit proofs |
| S2-4 | Done | `plateau_evolution_ladder.py`; escalator re-exports; LOC ratchet |
| S2-5 | Done | This plan + `docs/starship-birth.md` § Seal II |

**Locked still:** cert floors frozen; no yaml `full_auto` force.
