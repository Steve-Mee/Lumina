# Self-play lab (ADR-0037 Phase 0)

**Status:** Lab scaffold — shadow ranking only. Default **off**.  
**Not production birth training.** Not REAL capital.

## One sentence

Variants on **frozen windows** → rank by **`tournament_score`** → **shadow report**. No orders. No progress mutation.

## Run

```bash
# Unit pack + offline fixture ranking
python scripts/validation/self_play_lab_gate.py

# Fixture only (skip pytest)
python scripts/validation/self_play_lab_gate.py --fixture --no-pytest

# Opt-in lab enabled for report gate (still no apply)
python scripts/validation/self_play_lab_gate.py --enable-lab --no-pytest

# JSON
python scripts/validation/self_play_lab_gate.py --json --no-pytest
```

## Module map

| Path | Role |
|------|------|
| `lumina_core/birth/self_play/types.py` | Config + variant result |
| `lumina_core/birth/self_play/gates.py` | REAL / freeze / disabled / apply block |
| `lumina_core/birth/self_play/scorer.py` | `tournament_score` ranking |
| `lumina_core/birth/self_play/report.py` | `self_play_lab_v1` report |

## Forbidden

- Auto REAL / sim_real_guard from self-play  
- Certificate floor drops  
- yaml twin `full_auto` force  
- Architecture auto-apply  
- Train through champion freeze  
- Birth progress mutation in Phase 0  

## Operator residuals (do these before Phase 1+)

Full board: [operator-residuals-or1-or6.md](operator-residuals-or1-or6.md) ·  
`python scripts/validation/operator_residuals_gate.py`

| ID | Task | Why |
|----|------|-----|
| OR1 | Fabric live SAFE_MODE / HB cancel on NT8 | Capital safety > lab depth |
| OR2 | Aperture ≥95% live samples | H1 honesty |
| OR3 | Perfect Birth campaign + intentional declare | No hollow unlock |
| OR4 | Twin promote evidence + SSOT audit | No yaml force |
| OR5 | Live freeze → accept or wipe only | Sacred hard-stop |
| OR6 | Recovery theater — no ladder spin | Single surface |

## Deferred

- **SP3** SIM apply under Twin  
- **SP4** Birth-loop observe hook  

See [ADR-0037](adr/0037-self-play-design.md).
