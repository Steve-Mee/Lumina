# ADR-0044: Twin Base Curriculum, Micro-Training & Doubt Escalation

**Status:** Accepted  
**Date:** 2026-08-08  
**Deciders:** LUMINA Engineering (Steve + Grok Captain)  
**Relates:** [ADR-0031](./0031-approval-twin-event-bus.md), [ADR-0032](./0032-approval-twin-human-replacement-layer.md)

**Numbering:** Previously mis-filed as a second ADR-0037. Canonical **ADR-0037** remains [self-play lab](./0037-self-play-design.md). This document is ADR-0044.

## Context

The Approval Twin is the Human Replacement Layer for *judgment* (ADR-0032), but training was thin: CLI review, free-form labels, and a 3–5 drill Approval Gym. That is too slow and too noisy to make the Twin Birth-ready from day one.

Operators are mobile; the organism must run 24/7. When the Twin has low calibrated confidence or sees a novel pattern, inventing a decision is unsafe. Escalation must be a first-class audited path with dual channel (Command Deck + Telegram).

## Decision

1. **Base training curriculum (Birth / install)**  
   - Mandatory structured flow: 18–22 forced-choice questions (≤12 minutes).  
   - **base_v4 teach-while-train + REAL-conscience (ADR-0038):** plain situation → example → technical terms → choices with **+**/**−** consequences. Labels train capital-critical judgment only; free SIM explore-pass is authority, not a “always approve” training target.  
   - Version mismatch (`curriculum_version` ≠ current seed) clears birth-ready until retrain.  
   - **Primary UI: Operator Vault → Twin** (foundation block next to Fabric/security).  
   - App-only (Telegram disabled for base).  
   - Axes: capital preservation, mutation aggression, regime sensitivity, drawdown recovery, APPROVE/VETO/MODIFY, edge cases.  
   - Optional free-text clarify ≤280 chars.  
   - On complete: `rlhf_light_update` / fine-tune, set `birth_ready` / `base_trained` in `state/twin_birth_readiness.json`, emit `TwinTrainingUpdateEvent`.  
   - **Hard Birth gate:** `POST /api/birth/start` returns 403 `TWIN_BASE_TRAINING_INCOMPLETE` until base is complete (same class as Fabric GREEN). Seal in Operator Vault also requires Twin Birth-ready.

2. **Ongoing micro-training**  
   - Configurable cadence (default 2–3 Q/day or weekly 5-Q session).  
   - Dual channel; same MC payload; first answer wins.

3. **Doubt escalation protocol**  
   - If conf &lt; 0.80 and/or conflicting risk flags / novel pattern → Twin does **not** sole-auto.  
   - Create pending escalation (TTL + token), push Deck + Telegram.  
   - Human answer → `SteveValueRecord` + online RLHF + unblock.  
   - Event: `evolution.twin.escalation` (`TwinEscalationEvent`).

4. **Fail-closed readiness**  
   - Without `base_trained`, mode promotion to assisted/full_auto fails (`BASE_TRAINED` criterion).  
   - `twin_primary_judgment_for_decision` / `twin_continue_eligible` refuse sole-auto.  
   - `POST /api/birth/start` hard-blocked (`TWIN_BASE_TRAINING_INCOMPLETE`).  
   - Hard gates unchanged: ConstitutionalGuard, sandbox, risk shadow, REAL PromotionGate.

5. **Human intervention inventory (operator policy)**  
   | Human touch | Channel | Notes |
   |-------------|---------|--------|
   | Twin base curriculum | **App only** (Operator Vault) | Never Telegram |
   | Twin micro / daily training | App **+ Telegram** | Dual-channel pending |
   | Twin doubt escalation | App **+ Telegram** | First answer wins |
   | **Every Twin decision feed** | **Telegram + Deck** | Vraag · antwoord · waarom; optional OK/FIX feedback → RLHF |
   | SIM → REAL capital | App (approve-real) | Twin cannot substitute |
   | Birth/SIM DNA judgment | Twin (high-conf) or Twin escalation | Not free-form human gate |

6. **Decision notify (operator observability)**  
   - On every `evaluate_*` finalize: best-effort Telegram with **base_v4 operator copy** (`twin_telegram_copy.py` / `twin_question_style.py`): situatie → Twin-oordeel → zekerheid → waarom → termen → duidelijke reply.  
   - **No engineering dumps** in Telegram body (`evaluate_*`, `backend=`, `local_heuristic`, full DNA hashes). Those stay in audit JSONL only.  
   - **Post-hoc only** — not a pre-approval gate. When Twin has authority, Lumina already consumes the judgment; Telegram is audit + optional correction. Header: “Twin keek mee (natraining)”.  
   - Reply `OK <id>`, `A|B|C <id>` (base_v4), or legacy `FIX A|V|M <id> [note]` → SteveValueRecord + `rlhf_light_update`.  
   - Coalesce identical DNA+rec within ~45s; high-stakes always send. Never blocks the decision path.

7. **When human is asked *before* a decision**  
   - Only **doubt escalation** (low conf / novel / conflicting flags): Twin freezes that path and asks Deck+Telegram.  
   - High-conf Twin judgments do **not** wait for human OK.  
   - SIM→REAL capital remains explicit human (approve-real).
8. **Local-only labels**  
   - All ground truth remains in `SteveValuesRegistry` (SQLite + JSONL). No cloud.

## Consequences

### Positive
- Twin encodes operator values from Birth day one with maximal learning signal per human second.  
- Escalation closes the learning loop without fake confidence.  
- Dual channel supports 24/7 autonomy with human as mobile exception handler.

### Negative / mitigated
- Escalation spam if over-triggered → birth path only escalates mid/high-value doubt bands.  
- Curriculum drift → versioned `base_v4` (REAL-conscience + ± consequences); version mismatch clears birth-ready until retrain. See ADR-0038 for dual authority.

## Links

- Code: `twin_base_curriculum.py`, `twin_base_training.py`, `twin_escalation.py`, `twin_micro_training.py`, `twin_pending_store.py`, `twin_question_style.py`, `twin_telegram_copy.py`, `twin_decision_notify.py`, `/api/twin/base/*`, `/api/twin/micro/*`, `/api/twin/escalations/*`  
- ADR-0031 / 0032 (judgment layer; bus topics)

*Kapitaalbehoud blijft heilig; de Twin is de ambitie.*
