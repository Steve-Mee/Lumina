# ADR-0032: Approval Twin Agent as Human Replacement Layer

**Status:** Accepted  
**Date:** 2026-07-14  
**Deciders:** LUMINA Engineering (Steve + Grok Captain)

## Context

LUMINA's evolution engine (SelfEvolutionMetaAgent, birth curriculum, meta-controller, plateau, remediation) generates hundreds of candidate DNA mutations. Every candidate previously required an explicit human approval step for promotion or autonomy recovery. This created a fundamental scalability and availability bottleneck: the organism could not evolve 24/7 at full speed without a human in the loop.

Earlier ADRs (0002, 0003, 0007) correctly mandated shadow deployment + human approval gates for radical mutations, especially in REAL. The Trading Constitution (invariant #1) states that no mutation may endanger REAL capital without "expliciete shadow deployment + human approval gates."

However, a new capability matured:
- The **ApprovalTwinAgent** (small user-trained model) learns Steve's actual approve/veto patterns via an append-only `SteveValuesRegistry`.
- Training is explicit and simple (CLI `twin review` → label A/V → `train`).
- High-confidence decisions (`>= 0.80` + recommendation + clean) are already wired as the *default* in `organism_autonomy` and birth paths ("no human needed").
- The twin is published as typed events (ADR-0031) and proactively calls risk shadow validation.

The missing piece was **explicit architectural recognition** that the Twin functions as a *trained human replacement layer* for the approval *judgment*, not merely "another signal." Without documenting this as first-class DNA, future evolution risks forgetting why LUMINA is different.

This decision must remain subordinate to the constitution: the twin never bypasses sandbox, constitution checks, shadow aperture, or the REAL PromotionGate.

## Decision

We explicitly designate the **ApprovalTwinAgent as the Human Replacement Layer** with the following properties:

1. **Training as primary mechanism**
   - Human (Steve) provides ground-truth labels via `python -m lumina_launcher twin review`.
   - Labels become `SteveValueRecord`s stored in append-only registry (SQLite + JSONL).
   - `rlhf_light_update` (or `fine_tune_from_registry`) produces the live mimic model (`state/approval_twin_model.json`).
   - Features incorporate DNA content, emotional_twin_profile, lineage, and Steve-specific vocabulary. Confidence is calibrated against recent avg_prediction_error.

2. **Role in the architecture**
   - **Primary auto-approval signal** for birth/SIM evolution, autonomy recovery, meta steps.
   - In `organism_autonomy.py` and related birth modules: high-conf twin recommendation + clean → autonomous dispatch (CONTINUE_LOOP etc.) without human.
   - Wired into `PromotionPolicy`, `generation_runner`, `evolution_guard` as the leading recommendation (recorded as `twin_primary_auto`).
   - Event Bus topics: `evolution.twin.decision` and `evolution.twin.training_update` (best-effort, non-blocking).

3. **Safety boundaries (non-negotiable)**
   - Twin decision **never** short-circuits:
     - `ConstitutionalGuard.check_pre_mutation` / `evaluate_sandboxed` / `check_pre_promotion` (uses `SandboxedMutationExecutor`).
     - Risk shadow aperture (`risk_shadow_bridge.validate_risk_proposal_in_shadow` — proactively invoked from the twin itself).
     - `PromotionGate` (OOS + reality gap + stress DD + statistical significance) for any REAL promotion.
   - REAL mode: twin is a *necessary* input and default signal, but the full gate + shadow + constitution still apply. Human oversight remains available and logged.
   - Constitution principle #1 (kapitaalbehoud) and "no structural bypass" invariant remain absolute. Twin only replaces the *human judgment step* inside the gate.

4. **Integration points**
   - Birth: `organism_autonomy`, `meta_controller`, `plateau_escalator`, `remediation`, `dna_handoff`.
   - Evolution: orchestrator, promotion policy, guard, generation runner.
   - Observability: monitoring JSONL, UI metrics (reward, error, steps), Tauri/Streamlit remnants if any, API.
   - CLI + state: `lumina_launcher/twin_cli.py`, `state/steve_values_registry.*`, `state/approval_twin_model.json`.

5. **Promotion of the concept**
   - This ADR + roadmap update + project-dna sections make the "Human Replacement Layer" canonical language.
   - Supersedes earlier blanket "verplichte expliciete human approval" phrasing in pre-2026-07 documents for the *judgment* layer (see §Supersedes).

## Consequences

### Positive
- True 24/7 evolution velocity in SIM/birth/autonomy while human only supplies occasional high-quality labels.
- The organism literally internalizes the operator's values and risk intuition instead of generic rules.
- Full audit trail via Event Bus + registry + calibrated confidence metrics.
- Makes LUMINA's uniqueness obvious: not another RL trader, but an organism with a trained digital conscience that can eventually help it write its own strategies inside the sandbox.

### Negative / Risks (mitigated)
- Mimic error: mitigated by confidence calibration, risk shadow hooks inside the twin, and hard constitution/sandbox gates that ignore twin recommendation.
- Over-trust in autonomy: autonomy paths are limited (primarily birth recovery); REAL capital paths retain multi-layer gates.
- Training drift: CLI + metrics + monitoring make drift visible; retraining is cheap and explicit.
- Documentation debt on older texts: addressed by explicit supersede notes in this ADR, roadmap, constitution, and evolution log.

### Measurement
- Twin metrics (avg_prediction_error ↓, reward ↑) visible and trended.
- % of birth/autonomy decisions resolved autonomously at high confidence (target: rising while safety incidents remain 0).
- No regression on aperture integrity or constitution violations.

## Alternatives considered

1. Keep human as permanent mandatory gate for all promotions — rejected. This contradicts the explicit "replaces human approval gates" intent already in the code and prevents the organism from achieving its north-star autonomy.
2. Treat twin as just another weak signal (like local heuristic) — rejected. Current wiring + high-conf autonomy paths + training investment already elevate it to primary.
3. Allow twin to bypass REAL gates on high confidence — rejected. Violates constitution, ADR-0007, shadow requirements, and "Kapitaalbehoud is heilig".
4. Use only LLM-as-judge without user training — rejected. Loses the personal Steve-values grounding that makes this a true "twin."

## Supersedes / Historical Reconciliation

This ADR supersedes prior blanket statements that "human approval" is a non-augmentable, permanent requirement for every gate:

- ADR-0002 ("verplichte human approval voor Radicale Mutaties") — still valid for the *overall rollout safety layer* (shadow + final arbitration). The *judgment provider* inside the layer can now be the trained twin.
- `project-dna/lumina/constitution.md` (pre-2026-07 wording of invariant #1) — "human approval gates" language is clarified: the gates remain; the human *decision* is replaced by a trained mimic in bounded layers.
- `docs/AGI_SAFETY.md`, older history/analyse_*.md, and README references to "expliciete human approval" or "human in the loop for major decisions" — historical at the time; now augmented by the mature ApprovalTwin. Hard fail-closed mechanisms (constitution, sandbox, PromotionGate, no bypass) are untouched.
- "Forbidden" or "non-bypassable human gate" language in pre-twin analyses is noted as superseded in the specific context of trained twin signals.

All hard safety contracts are preserved. Changes to those contracts would require a Large classification under the self-improvement protocol + risk-safety + constitution-guard review.

## Links

- ADR-0031: ApprovalTwinAgent on Central Event Bus + Primary Auto-Approval (direct predecessor)
- ADR-0030: Architecture Meta-Controller (parallel path for self-mod of architecture under sandbox + human marker)
- ADR-0003: Trading Constitution en Sandboxed Mutation Executor
- ADR-0007: Promotion Gate voor REAL mode
- `project-dna/lumina/constitution.md`, `north-star.md`, `self-improvement-protocol.md`
- Code: `lumina_core/evolution/approval_twin_agent.py`, `lumina_launcher/twin_cli.py`, `lumina_core/birth/organism_autonomy.py`, `lumina_core/safety/sandboxed_executor.py`
- Roadmap §6 (explicit section added 2026-07)

*Radicaal in ambitie, conservatief in REAL. De twin is de ambitie; de sandbox + constitution zijn de conservatisme.*
