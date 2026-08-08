# Birth curriculum stage floors (normative SSOT)

**Status:** Locked / normative (2026-08-08)  
**Audience:** Operators, engineers, agents — no open debate after this doc  
**Code remains numeric SSOT for defaults;** this page is the **policy + language** SSOT.

---

## One-line doctrine (memorize this)

> **Stage 1 = breathe** (survival expectancy ≥ **−0.50** ≡ ~20% WR).  
> **Stage 2/3 = early motor quality** (expectancy ≥ **−0.15** ≡ ~35% WR), still **inside Birth**, not pro cert.  
> **Birth exit = phase survival proofs only** — never OOS 0.48, Perfect Birth, or REAL.  
> **`expectancy_proxy = effective_winrate − 0.50`** (rolling when eligible); not raw PnL for the stage floor.

If a checklist, chat, or older paragraph says something else about Stage 2/3 floors, **this document wins**.

---

## 1. Three layers — never conflate

| Layer | Question | Answer |
|-------|----------|--------|
| **A. Stage-pass (intra-Birth)** | May this curriculum stage graduate? | Stage 1 = **survival floors**. Stage 2/3 = **early-quality floors**. |
| **B. Birth-exit (phase)** | Is the newborn done enough for Phase Hub? | **Survival-only** proofs (curriculum / artifacts / certificate-as-evidence / crash-recovery path). |
| **C. Skill / cert / REAL** | Is this a competent capital-ready trader? | Playground+ skill EdgeScore; Proving/cert OOS walls; REAL multi-gate + human. |

Confusing A with B or C is how recovery theater and “newborn = pro” arguments start. Stop at the layer you mean.

---

## 2. Intra-Birth stage floors (canonical)

Expectancy on this page is always the **WR−0.50 proxy** used by EdgeScore
(`compute_expectancy_proxy` in `starship_edgescore_core.py`).

| Stage | Expectancy floor | WR hygiene | Other pass essentials | Framing |
|-------|------------------|------------|------------------------|---------|
| **Stage 1 Trend** (`birth_survival_pass_enabled: true`, default) | **≥ −0.50** (`birth_survival_expectancy_floor`) ≡ ~**20%** WR | Survival WR ≥ **0.20** | Volume, constitution 0, hold band, entropy alive, plant soft-block cap | Breathe / plant / closed loop |
| **Stage 2 Range** | **≥ −0.15** (`stage2_expectancy_floor`) ≡ ~**35%** WR | WR is **not** a Stage-2 pass-gate (`hygiene_ok` diagnostic) | Flat **30–70%**, round-trips, entropy, constitution 0, volume | Early motor quality in range |
| **Stage 3 Mixed** | **≥ −0.15** (same early-quality scale) | `stage3_winrate_floor` default **0.35** | Hold cap, entropy, constitution 0, volume | Deeper hygiene on train data |

When `birth_survival_pass_enabled` is **false**, Stage-1 uses skill-side floors (`stage1_winrate_pass_floor` 0.35, `stage1_expectancy_floor` −0.15). That mode is for later skill curriculum / Playground+, **not** the default Birth newborn path.

### Config keys (defaults)

| Key | Default | Role |
|-----|---------|------|
| `birth_survival_pass_enabled` | `true` | Stage-1 survival vs skill-side floors |
| `birth_survival_wr_floor` | `0.20` | Stage-1 survival WR |
| `birth_survival_expectancy_floor` | `-0.50` | Stage-1 survival expectancy |
| `stage1_expectancy_floor` | `-0.15` | Skill-side / Stage-3-linked quality scale |
| `stage2_expectancy_floor` | `-0.15` | **Stage-2 early-quality** (never survival −0.50) |
| `stage3_winrate_floor` | `0.35` | Stage-3 hygiene WR |

### Code SSOT

- Stage 1: `lumina_core/birth/starship_edgescore_stage1.py`
- Stage 2: `lumina_core/birth/starship_edgescore_stage2.py` (`stage2_expectancy_floor()`)
- Stage 3: `lumina_core/birth/starship_edgescore_stage3.py`
- Proxy math: `lumina_core/birth/starship_edgescore_core.py` (`compute_expectancy_proxy`)
- Birth phase exit: `lumina_core/maturity/birth_exit.py` + [ADR-0036](adr/0036-birth-exit-vs-maturation.md)
- Lock tests: `tests/birth/test_expectancy_stall.py` (Stage-2 floor is **not** survival −0.50)

---

## 3. Why it is this way (no renegotiation)

### Organism metaphor

1. **Stage 1 — first breath.** The organism must *live*: legal actions, constitution violations 0, plant not choked, entropy not dead. Wide survival floors (−0.50 / WR ~0.20) exist so we do not fail a newborn for not running a marathon.
2. **Stage 2/3 — first motor control, still in the nursery.** After breathing, the loop must become **non-dead and more selective**: range occupancy 30–70%, enough activity, and expectancy ≥ −0.15 so training does not burn the budget forever at ~25–30% WR. That is **early training discipline inside Birth**, not a daytrader certificate, not REAL capital, not “genius at birth.”
3. **Birth exit — leave the nursery.** Only proof that the closed loop *survived* (curriculum complete / artifacts / optional cert as evidence). **No** OOS driving test (0.48 WR), **no** Perfect Birth KPI conjunction as exit grade.
4. **Playground → Proving → REAL.** Skill EdgeScore, multi-day SIM, shadow/promotion, human REAL gates — where “pro” language belongs.

### Engineering why (without metaphor)

| Choice | If we did the opposite |
|--------|------------------------|
| Survival −0.50 only on Stage 1 | Stage 1 becomes an unfair skill wall → endless stall before plant is green |
| Survival −0.50 on Stage 2/3 | Budget burn, no quality signal, recovery theater, swarm no-lift loops |
| OOS 0.48 / Perfect Birth as Birth exit | Newborn graded as professional → ADR-0036 explicitly rejected |
| Stage-2 early-quality −0.15 | Minimal floor aligned with EdgeScore quality stack (rolling WR, expectancy stall, participation envelope) — **not** cert 0.48 |

**Therefore:** Stage 2/3 on expectancy ≥ −0.15 is **intentional progressive rigor after Stage-1 survival**, not a documentation bug and not “premature pro skill.”

---

## 4. Terminology lexicon (use these words only)

| Term | Use for | Do **not** use for |
|------|---------|---------------------|
| **Survival floors** | Stage-1 under survival mode; Birth-exit *phase* framing | Stage 2/3 pass criteria |
| **Early-quality floors** | Stage 2/3 (exp −0.15; Stage-3 WR 0.35) | Certificate OOS / REAL |
| **Skill floors (Playground+)** | Survival mode off / post-Birth skill EdgeScore | Default Stage-1 Birth pass |
| **Certificate / OOS walls** | Proving Ground + certificate pipeline | Birth-exit or Stage-1 survival |

### Fixed copy-paste sentences

- *Stage 1 = breathe (survival −0.50 / WR ~0.20). Stage 2/3 = early motor quality (expectancy ≥ −0.15), still inside Birth, not pro cert.*
- *Birth exit = phase survival proofs only — never OOS 0.48 or Perfect Birth.*
- *expectancy_proxy = WR − 0.50; −0.15 ≡ ~35% effective WR.*

---

## 5. Explicit anti-patterns (rejected)

1. Lowering `stage2_expectancy_floor` (or Stage-3 floors) to survival −0.50 “because Birth is newborn.”  
2. Calling Stage 2 pass a pure “survival pass” without **early-quality** floors.  
3. Claiming Stage 2 pass implies Perfect Birth, READY_FOR_REAL, or pro competence.  
4. Using Birth-exit to enforce OOS 0.48, Perfect Birth KPIs, or REAL multi-gates.  
5. Treating vanity Stage-1 WR 45% as the pass floor (diagnostic only).  
6. Silent train-through champion freeze, auto-wipe, yaml `full_auto`, or auto-REAL to “clear” a floor debate.

---

## 6. See also

| Doc | Role |
|-----|------|
| [ADR-0036 Birth exit vs maturation](adr/0036-birth-exit-vs-maturation.md) | Phase exit = survival; points here for intra-Birth floors |
| [Organism maturation phases](adr/organism-maturation-phases.md) | Genesis → REAL ladder; Birth internal stages |
| [Starship Birth](starship-birth.md) | EdgeScore / swarm / twin contract |
| [Stage 2 re-entry checklist](birth-stage2-certified-reentry-checklist.md) | Operator re-entry under early-quality rules |
| [Zero-human metrics runbook](birth-zero-human-metrics-runbook.md) | Unattended Birth; expectancy stall = early-quality |
| [Birth phase live validation](birth-phase-live-validation-runbook.md) | Live gates aligned to this SSOT |

---

## 7. Change control

Changing Stage-2/3 floors or redefining Stage 1 survival requires:

1. Explicit design decision (not chat improvisation)  
2. ADR-0036 / this SSOT update in the **same** change  
3. Matching code + tests  

Until then, the numbers and framing on this page are **closed**.
