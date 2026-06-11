# 2026-06-02 — Phase 2 Deliverable 5: Risk Shadow Aperture Wired into Primary Self-Evolution Meta Path (Original SPF-003)

**Parent Hypothesis (2026-05-31 Elon first-principles analysis)**:  
Treating the capital aperture (typed Event Bus + Admission Chain + Final Arbitration + Constitution) as the single most important artifact, and ruthlessly forcing every decision that touches risk logic through an isolated, observable, hash-chained shadow path, increases survival probability by an order of magnitude while accelerating safe evolution velocity.

**This Entry Maps Directly To**:  
- 2026-05-31-elon-aperture-hardening-90-day-roadmap.md, Phase 2 Deliverable 5 (verbatim):  
  > "Extended shadow deployment: every evolution experiment that touches risk logic must run in a 'shadow aperture' mode that replays real market data but never touches the live broker."
- 2026-05-31 diagnosis SPF-003: `lumina_core/engine/meta_agent_core.py` (76 KB) identified as the primary concentration point for self-evolution orchestration + DNA mutation + promotion decisions with system-wide blast radius.

**Hypothesis for This Slice**:
By extending the already-proven official risk shadow bridge (`validate_risk_proposal_in_shadow`) into the actual factory that generates the majority of risk-affecting DNA proposals inside the primary self-evolution driver (ProposalGenerator.build_challengers + build_genetic_candidates), we close the highest-leverage remaining bypass on Deliverable 5. The change must remain best-effort and non-blocking (consistent with prior 4 sites) to preserve evolution velocity while adding the required observability/rem.

**What Was Done (Narrow, Reversible, Highest-Quality Slice)**:
- Performed fresh Plan Mode + massive parallel audit (50+ files + dedicated explore subagent) of all DNA/proposal generation surfaces.
- Confirmed that the 4 prior "automatic default" sites only covered secondary candidate flows; the real SPF-003 meta path (SelfEvolutionMetaAgent + ProposalGenerator in `lumina_core/engine/`) had zero coverage and explicitly mutates `max_risk_percent`, `drawdown_kill_percent`, fast_path thresholds under aggressive_evolution and nightly cycles.
- Added best-effort calls (exact same pattern, import-inside-try, auto_record_promotion=True, high-fidelity extraction of real hyperparam values) at the output of both `build_challengers` (including radical paths) and `build_genetic_candidates`.
- Mandatory pre-edit reviews executed: constitution-guard (9/10, all 7 rules satisfied, strong positive on "evolutie met rem" and kapitaalbehoud) + risk-safety-review (8/10, fail-closed overall aperture preserved, no optimistic assumptions, best-effort nature noted as existing pattern).
- 3 new focused tests added (`tests/engine/test_proposal_generator_risk_shadow.py`): behavioral coverage for risk hyperparam challengers + best-effort non-break + source hygiene for genetic path. All green.
- Core shadow risk evaluator suite (26 tests) remains 100% green.
- No changes to live risk math, no new god-class surface, no blocking behavior, full reversibility (single git revert of the two methods).

**Measurements / Evidence**:
- Before: Primary meta proposal factory (the exact concentration the 2026-05-31 diagnosis flagged) produced risk-affecting DNA with zero shadow aperture participation.
- After: Same factory now emits `EvolutionPromotionDecision` + rich `ShadowExperimentResult` (with recommendation + optional human_approval_request) for challengers that touch risk hyperparams. Audit trail lands in `state/risk_shadow_evolution.jsonl` and is visible to `shadow_review` CLI.
- Import hygiene + no circular imports verified (clean `python -c "from lumina_core.engine.proposal_generator import ProposalGenerator"`).
- 3/3 new tests green; 26/26 core shadow tests green; zero regressions in candidate generation paths.
- Mission Control Deliverable 5 row updated with brutal honesty (status moved from optimistic Yellow-Green to "Yellow (strong localized progress)" with explicit remaining gaps).

**Direct Mapping to Original Deliverable Wording**:
The slice makes "every evolution experiment that touches risk logic" closer to reality for the highest-blast-radius experiments (the ones the original analysis said had system-wide blast radius). It does not yet make it universal — dream_engine nudges, standalone LLM generators, and structural gating are documented open gaps.

**Honest Limitations (No Softening)**:
- Still best-effort / advisory, not a hard gate (consistent with the 4 earlier sites; gating is future work after more evidence).
- Genetic test is source-hygiene only (deep internal dependencies in the method made full behavioral stubbing high-risk for this narrow slice).
- dream_engine (direct risk param nudges) and LLM proposal surfaces remain unwired.
- "100% of risk-affecting experiments" is not yet achieved.

**Relation to North Star (2026-08-29)**:
This is the single highest-leverage move on the hardest remaining Phase 2 item. Closing the primary meta path removes the most dangerous hidden bypass between aggressive self-evolution and the isolated shadow risk aperture. It directly serves the "safe aggressive evolution" outcome required for the revolutionary aperture.

**Forcing Functions Updated**:
- `project-dna/lumina/interfaces/export/aperture-hardening-mission-control.md` (table row + highest-leverage section + last-updated).
- This log entry (public, immutable, hypothesis + evidence + mapping).
- Permanent `aperture-mission-control` skill remains active and will force re-anchoring on any future aperture/risk/evolution work.

**Next Logical Increment (Per Current Audit)**:
1. Wire dream_engine.merge_dream_hyperparam_nudges (high-volume risk injection into the already-partially-covered pipeline).
2. Add lightweight participation in strategy_generator / genetic_operators LLM paths.
3. Consider a structural safety net (test that fails on bypass, or registry-level hook) once more production evidence exists from the meta path.

**Status**: Hypothesis supported. Measurable progress on the exact 2026-05-31 text. Gap now smaller and explicitly documented. Ready for the next narrow slice on the same deliverable or Phase 3 items.

*Recorded under the permanent aperture-mission-control protocol. No context fragmentation permitted.*