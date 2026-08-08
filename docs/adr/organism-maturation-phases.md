# ADR: Organism Maturation Phases (Birth → Real)

**Status:** Accepted (design SSOT)  
**Date:** 2026-08-01  
**Normative Birth exit:** [ADR-0036 Birth Exit vs Maturation](./0036-birth-exit-vs-maturation.md) (H7 code SSOT: `maturity/birth_exit.py`)  
**Context:** Lumina is an experimental self-evolving daytrading organism. Birth must not be graded as professional trading competence.

## Decision

Maturation is a **capability ladder**, not a single certificate wall.

| Phase | Organism capability | Exit proof (examples) | Non-goals |
|-------|---------------------|----------------------|-----------|
| **Genesis** | Wiring exists | fabric GREEN, setup complete, charter | Training |
| **Birth** | Survive / breathe / closed loop | legal action rate, hard_const=0, checkpoint, entropy alive, Stage-1 loose expectancy | Phase-exit: WR≥35% / OOS 0.48 / Perfect Birth / REAL as exit grades (intra-Birth Stage 2/3 early-quality is separate — see below) |
| **Awakening** | Prefer better, perceive regimes | twin/shadow rising, recovery works, evolution proof | REAL capital |
| **Playground** | Move safely in SIM | first SIM order, deck unlock, skill EdgeScore/hygiene | REAL |
| **Apprenticeship** | Stable multi-day SIM | sim_real_guard streak, never-stop recovery | REAL |
| **Proving Ground** | Prove before capital | shadow validation, promotion gate, **full cert thresholds** | Live capital |
| **Real** | Trade money + keep evolving | fail-closed live + offline evolution | — |

## Birth survival pass (implementation)

When `birth_v2.curriculum.birth_survival_pass_enabled` (default **true**):

- Stage1 EdgeScore uses `birth_survival_wr_floor` (default **0.20**) and `birth_survival_expectancy_floor` (default **−0.50**).
- Plant gate: `soft_block_rate_per_1k` must be ≤ `birth_plant_soft_block_rate_max_per_1k` (default **100**).
- Skill-side Stage-1 floors (`stage1_winrate_pass_floor` 0.35, `stage1_expectancy_floor` −0.15) apply when survival mode is **false** (Playground+ skill curriculum).

REAL / certificate_thresholds for OOS WR 0.48 etc. are **unchanged** and apply at Proving Ground / certificate pipeline — not as the only Birth exit.

### Birth curriculum stages (internal — not phase-exit)

**Phase** Birth exits on survival proofs (ADR-0036). **Inside** Birth, stages ramp:

| Stage | Class | Expectancy (WR−0.50) | Role |
|-------|--------|----------------------|------|
| 1 Trend | Survival (default) | ≥ **−0.50** | First breath |
| 2 Range | **Early-quality** | ≥ **−0.15** | Motor control / range band |
| 3 Mixed | **Early-quality** | ≥ **−0.15** (+ WR ~0.35) | Deeper train hygiene |

Locked doctrine, why, and anti-patterns: **[birth-curriculum-stage-floors.md](../birth-curriculum-stage-floors.md)**.  
Do not call Stage 2/3 “survival −0.50” and do not call Stage 2 pass “pro skill / cert.”

## Phase Hub (operator home after Birth)

After Birth (and after each later phase), the operator returns to a **Genesis-like Phase Hub**:

- **Learned** summary from the completed phase
- **Next steps** + Start next phase
- **Checkpoint**: `state/lumina_phase_continuum.json` survives restart (no re-birth)
- **Wipe**: single phase or full maturation (back to Genesis/setup)
- **Advance mode** (hub toggle):
  - `manual` — operator starts each phase on PC
  - `telegram` — after phase complete, Telegram asks YES + token before next
  - `auto_evolve` — chain next phase automatically (**REAL never pure auto**)

## Depth wave (strict proofs)

Default `maturity.strict_exit_proofs: true` in `config.yaml`:

| Phase | Hard exit |
|-------|-----------|
| Awakening | evolution proof **and** twin samples ≥ N |
| Playground | deck + envelope sealed + first SIM order evidence |
| Apprenticeship | `sim_real_guard_stable` / READY_FOR_REAL (honest incomplete if not) |
| Proving Ground | promotion/shadow audit pass (never fabricated) |
| REAL | human `approve-real` + eligibility milestones |

Lab override: `maturity.experimental_soft_complete: true` re-enables soft stamps (hub warns).

Telegram: `TelegramNotifier.poll_for_replies` handles `YES`/`CONFIRM` + token; autopilot tick polls when `advance_mode=telegram`.

### Apprenticeship multi-day SIM

`maturity/apprenticeship_sim.py` runs `MultiDaySimRunner.evaluate_variants` and writes
`state/test_runs/apprenticeship_sim_day_YYYY-MM-DD.json` (`mode=sim`) into the stability ledger.
Never fabricates `READY_FOR_REAL` — re-evaluates `generate_stability_report` after writes.

Config: `maturity.apprenticeship_sim_days` (default 5).

### Telegram token TTL

`pending_advance.expires_at` set from `maturity.telegram_advance_token_ttl_sec` (default 86400).
Expired tokens → `token_expired` + clear pending. Hub can `POST /api/maturity/refresh-advance`.

## Consequences

- Newborn is not failed for not “walking.”
- Plant (legal actions) is the birth bottleneck.
- Swarm hard-stop must not kill a newborn before plant is green (re-tournament + plant_blocked skip).
- Cold start after birth → `app_surface=hub` (not deck). Deck is entered from hub.
- Incomplete phases show missing proofs on Phase Hub; no silent soft-complete in strict mode.

## Related code

- `maturity/birth_exit.py` — **H7 Birth exit SSOT** (survival proofs; not Perfect Birth / REAL)
- `starship_edgescore_stage1.py` — Stage-1 survival vs skill-side floors
- `starship_edgescore_stage2.py` / `stage3.py` — early-quality floors (see birth-curriculum-stage-floors.md)
- `birth_constitution_guard.py` — auto_clip plant
- `maturation_progress.py` — phase enum order
- `maturity/continuum.py` — durable hub SSOT
- `maturity/phase_runners/` — strict phase runners
- `maturity/shadow_helpers.py` — promotion audit helpers
- `maturity/maturity_service.py` — runners + advance
- `GET /api/maturity/birth-exit` — operator panel
- `docs/starship-birth.md` — Starship gates (skill layer)
