# Evolutionary Debt

Dit document catalogiseert de grootste knelpunten die de toekomstige evolueerbaarheid van Lumina momenteel beperken. Het is een levend document.

**Laatste update**: 2026-05-31 (Elon Musk first-principles aperture analysis + new #0 top debt item)

## Huidige Top Debt Items (2026-05)

Elk item bevat: concrete observaties, impact op evolvability, hypothese voor verbetering en meetbaar signaal van vooruitgang.

**⚠️ NEW TOP PRIORITY (2026-05-31)**: See the detailed first-principles analysis in `evolution/log/2026-05-31-elon-musk-first-principles-trading-system-analysis.md`. The items below are now secondary to **Aperture Erosion**.

### 0. Capital Aperture Erosion — Bypass Flags, Incomplete Contracts & Under-Adopted Event Bus (Elon Analysis 2026-05-31)

**Observaties** (evidence from static mapping):
- Three explicit structural bypass layers: `admission_chain_final_arbitration_approved` mutable engine flag, `skip_final_arbitration` param (policy_engine.py:70, operations_service.py:304, reasoning_service.py:261), and `skip_admission_chain_recheck` metadata flag (broker_bridge.py:129).
- Only ~6 publish sites for the "central" Event Bus across the entire core; most coordination remains dict-based blackboard polling and direct attribute access on large orchestrators.
- 4 Order construction sites with varying metadata completeness; dream_snapshot dict fallbacks used in several paths.
- Large concentration points (meta_agent_core.py 76KB, runtime_workers.py 75KB, lumina_engine.py) still exist despite prior refactoring.
- Historical full-state reset culture (thousands of files) as evidence of insufficient migration resilience.

**Impact op Evolvability & Mission Risk**:
- Directly tensions with Constitution Invariants 1 (kapitaalbehoud heilig), 5 (safety vóór evolutie), and fail-closed principle.
- Makes safe self-evolution dramatically harder: any agent or DNA mutation can more easily find a path around the "narrow aperture".
- Provenance of trading decisions remains partial and fragile.

**Hypothese voor verbetering**:
When the three bypass mechanisms are removed (or made structurally impossible outside time-boxed, audited SIM experiments), the Event Bus becomes the mandatory universal spine with model instances for subscribers, and every Order path carries complete typed lineage, the probability of surviving autonomous REAL operation for 5+ years increases by ≥5-10x while safe evolution velocity also rises (measured via aperture integrity score + Guardian + live incident rate).

**Meetbaar signaal van vooruitgang**:
- Zero active bypass mechanisms in REAL / sim_real_guard / paper-guard paths (static + runtime assertions + Guardian checks).
- ≥95% of pre-trade decisions reconstructible end-to-end via Event Bus lineage within 5 seconds.
- New "Aperture Integrity Score" (Guardian extension) ≥ 9.0 within 90 days.
- No new full-state resets required for core trading/risk state changes.

**Status**: Identified + publicly documented (2026-05-31 Elon entry). Concrete hardening plan executed through Phase 1.3.4.

**Resolved (Phase 1.3.4 zero-trace hygiene)**: All four FATAL structural bypass mechanisms (B-001..B-004) eliminated with no traces remaining in source, tests, or active documentation. The authoritative gate is the only path. aperture_guard now functions as permanent regression detector (any call in strict modes is fatal). See evolution/log/2026-05-31-elon-phase1-3-4-zero-trace-hygiene-complete.md and aperture.yaml (active_structural_bypass_count: 0).

---

### 1. Monolithische LuminaEngine
**Observaties**:
- Verantwoordelijkheden over te veel domeinen (PnL berekening, RL training, backtesting, risk management, dream state, order routing).
- Legacy compat-laag nog aanwezig in meerdere lagen (stand mei 2026).

**Impact op Evolvability**:
- Maakt het moeilijk om bounded contexts te definiëren en unit tests te isoleren.
- Verhoogt cognitieve load bij elke refactor.

**Hypothese voor verbetering**:
Wanneer de legacy compat-laag volledig verwijderd is en de engine verantwoordelijkheden beperkt zijn tot execution + state management, wordt redeneren over veranderingen significant makkelijker (gemeten via tijd tot eerste werkende refactor na verandering).

**Meetbaar signaal van vooruitgang**:
- Legacy compat-laag verwijderd in ≥ 3 kernmodules.
- Aantal cross-domain calls in engine/ gedaald met ≥ 40% (gemeten via static analysis).

**Status**: In progress (meerdere refactors in 2026-Q1/Q2).

### 2. Legacy Compat Layers
**Observaties**:
- Dunne delegatie- en adapter-lagen aanwezig in `engine/`, `risk/` en meta-agent lagen (stand mei 2026).

**Impact op Evolvability**:
- Vertraagt de transitie naar echte bounded contexts.
- Verhoogt regressierisico bij elke structurele verandering.

**Hypothese**:
Het verwijderen van deze lagen reduceert de tijd die nodig is om een significante architectuurwijziging veilig door te voeren met ≥ 30%.

**Meetbaar signaal**:
- Aantal adapter/delegatie bestanden gedaald.
- Minder dan 2 actieve "compat" modules in de codebase bij de volgende DNA review.

### 3. Risk Layer Complexiteit
**Observaties**:
- Zware mixin-structuur (`RiskGatesMixin`, `OrderGatekeeper` etc.) met veel impliciete interacties.

**Impact op Evolvability**:
- Kleine, gerichte evolutie-stappen vereisen disproportioneel veel context.

**Hypothese**:
Het opsplitsen van de risk laag in kleinere, expliciet gecontracteerde componenten (via Event Bus) maakt het mogelijk om risk-gerelateerde features te evolueren zonder de hele engine te begrijpen.

**Meetbaar signaal**:
- Nieuwe risk features kunnen worden toegevoegd/testbaar gemaakt zonder wijzigingen in > 3 bestanden buiten de risk bounded context.

### 4. Event Bus Contract Maturity
**Observaties**:
- Niet alle belangrijke beslissingen (risk decisions, evolutie-beslissingen, governance) worden als typed events gepubliceerd (stand mei 2026).

**Impact op Evolvability**:
- Beperkt de observability en de capaciteit van meta-agents om patronen te ontdekken.

**Hypothese**:
Wanneer alle constitution-critical en evolution-critical beslissingen via typed Pydantic events gaan, wordt Decision Impact Tracking en post-hoc analyse significant makkelijker.

**Meetbaar signaal**:
- ≥ 80% van de RiskDecision en ConstitutionViolation events zijn getypt en gepubliceerd via de Event Bus.

### 5. Meta-Evolutie van DNA zelf nog jong
**Observaties**:
- Het Recursive Self-Improvement Protocol v2.0 en de DNA Guardian tooling zijn geïntroduceerd in mei 2026.
- Er is nog weinig historische data over de effectiviteit van meta-verbeteringen (weinig "before/after" metingen).

**Impact op Evolvability**:
- Het zelfverbeteringsproces is nog deels anekdotisch in plaats van evidence-based.

**Hypothese**:
Door structureel Guardian-scores + LLM reviews te gebruiken bij elke significante DNA-wijziging, stijgt de waarheidsdichtheid en bruikbaarheid van project-dna/ meetbaar (doel: gemiddelde Truth Density van kern-DNA bestanden ≥ 8.5 binnen 90 dagen).

**Meetbaar signaal**:
- `current-reality/evolutionary-debt.md` haalt bij een Guardian run een Truth Density ≥ 8.0.
- Ten minste 3 meta-verbeteringen in evolution/log/ refereren expliciet naar Guardian/LLM bevindingen als input.

### 6. SIM vs REAL scheiding nog deels impliciet
**Observaties**:
- Constitution en Admission Chain zijn mode-aware.
- Er bestaan nog plekken in de codebase waar de scheiding tussen SIM/Paper en REAL niet expliciet genoeg is afgedwongen (stand mei 2026).

**Impact op Evolvability**:
- Verhoogt het risico dat experimentele logica per ongeluk doorsijpelt naar REAL (kapitaalrisico).

**Hypothese**:
Expliciete, fail-closed scheiding op alle kritieke paden reduceert de kans op constitutionele schendingen in REAL significant.

**Meetbaar signaal**:
- Geen constitutionele schendingen in REAL gerelateerd aan mode-lekkage in de komende 6 maanden.
- Alle order-flow en risk paden hebben expliciete mode-checks met duidelijke foutafhandeling.

## Hoe deze lijst wordt onderhouden

- Nieuwe debt items worden toegevoegd via het Recursive Self-Improvement Protocol + Guardian signal (inclusief LLM review indien gebruikt).
- Items worden verwijderd of gedowngraded alleen als er aantoonbare, meetbare vooruitgang is geboekt (zie "Meetbaar signaal" per item).
- De lijst wordt minimaal elke 90 dagen geëvalueerd als onderdeel van de formele DNA review, inclusief Guardian score op dit bestand zelf.

**Doel**: Deze lijst moet over tijd korter en minder kritiek worden, niet langer. Als hij groeit of de items vaag blijven, faalt ons zelfverbeteringsproces.

**Huidige focus (2026-05)**: `current-reality/evolutionary-debt.md` zelf was lang het zwakste DNA-bestand (meerdere Guardian scans op 7.0 of lager, inclusief LLM review van 6/10). Na deze verbetering steeg de Truth Density naar 9.4/10 (Guardian run 2026-05-29). Dit blijft een focuspunt totdat het consistent boven 8.5 scoort en concrete follow-up acties laat zien.

## Wave A residual (2026-07-28)

- ~150+ files still >=350 LOC outside Wave A hotspots (birth/twin/shadow/schemas/app splits reduced selected modules; bulk of large-file debt remains for Wave B).
- Hybrid quarantine inventory: see `docs/hybrid-quarantine.md` (defaults preserve legacy stub outcomes).
- Intentionally deferred: `birth/engine.py` composition root, `scripts/dna_guardian/validate_dna.py`, Tauri UI gods, test megasuites.

## Wave B residual / B2 (2026-07-28)

Wave B1 + safety-critical (SC) facade splits completed for: birth (engine, config, certificate_pipeline, starship_edgescore, plateau_terminal, plateau_evolution_handler, stage_loop_data_ops, stage_loop_session), evolution (orchestrator_core, approval_twin_bus, approval_twin_evaluators), engine (market_data_service), runtime (headless_runtime, headless_production), ppo_trainer, risk (risk_controller + risk_controller_status, decision_lineage), and safety/trading_constitution. runtime_entrypoint remains oversized pending B2.

Deferred Wave B2 targets:
- backtester_engine (and related backtest god surfaces)
- admin_endpoints_core
- observability_service
- twin_metrics_store
- twin_training_service
- broker bridge / fabric modules
- order_gatekeeper
- launcher fabric diagnostics
- remaining 400-600 LOC engine services (incl. further runtime_entrypoint reduction)

## Wave B2 complete / B3 residual (2026-07-28)

Wave B2 facade splits verified complete for target modules (PR-C5 smoke + LOC + hybrid inventory + focused pytest):

- `admin_endpoints_core`, `backtester_engine`, `observability_service`, `twin_metrics_store`, `twin_training_service`
- `fabric_connection_diagnostics`, `reasoning_service`, `proposal_generator`
- broker: `bridge_service`, `fabric_client`; engine: `runtime_entrypoint`

Hybrid quarantine inventory defaults remain fail-soft / legacy-preserving (`require_true_backtest` / `require_trace_verdict` and related inventory keys default `false`; see `docs/hybrid-quarantine.md`).

Wave B3 leftovers:

- `order_gatekeeper` (already under 400 LOC; optional further polish only)
- `cross_trade_broker` optional polish
- remaining engine modules still >=500 LOC: `supervisor_phase_state_machine`, `market_data_history`, `performance_validator`, `local_inference_engine`, `meta_agent_core`, `sim_stability_checker`
- `scripts` / `validate_dna` (DNA guardian) deferred
- Tauri UI gods deferred

## Wave B3 complete / Wave C residual (2026-07-28)

Wave B3 PR-D3 engine facade splits verified complete for:

- `supervisor_phase_state_machine` (133 LOC)
- `market_data_history` (185 LOC)
- `performance_validator` (394 LOC)
- `local_inference_engine` (382 LOC)
- `meta_agent_core` (366 LOC)
- `sim_stability_checker` (397 LOC)

Hybrid quarantine inventory defaults remain fail-soft / legacy-preserving (`require_true_backtest` / `require_trace_verdict` still `false`; see `docs/hybrid-quarantine.md`). Focused pytest for this wave: 29 passed.

Wave C leftovers:

- `scripts/dna_guardian/validate_dna.py`
- Tauri UI gods: `birthStageScorecard`, `BotConfigForm`, `BirthPhaseScreen`, `ApprovalTwinTrainPanel`, `BirthHelixVisual`
- optional `order_gatekeeper` / `cross_trade` polish under 500 LOC

## Wave C complete (2026-07-29)
Note validate_dna + five Tauri façades done with LOC. Residual: optional order_gatekeeper/cross_trade polish under 500 only; modularization campaign waves A–C closed for declared god targets.

## Optional polish + Hybrid SIM opt-in (2026-07-29)
- Light-split: `admission_risk_steps.py` + `cross_trade_payload.py` (public façades preserved).
- Hybrid SIM/PAPER strict profile opt-in: env `LUMINA_HYBRID_STRICT` or `hybrid_quarantine.apply_strict_in_sim` (default false). REAL ignores; per-gate committed defaults unchanged.
- Modularization campaign waves A–C + optional polish closed for declared targets.
