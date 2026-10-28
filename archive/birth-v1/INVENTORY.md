# Phase 0 Validation Gate inventory

Binding law: [`project-dna/lumina/RESEARCH_CHARTER.md`](../../project-dna/lumina/RESEARCH_CHARTER.md).

Gate points: **WF** = walk-forward 5–8 non-overlapping OOS windows; **CPCV** = combinatorial purged CV with purge + embargo and OOS distribution; **DSR** = trial-corrected deflated Sharpe; **PBO** = probability of backtest overfitting (preferred `< 0.25`, hard reject `> 0.50`); **Costs** = commissions + half-spread + dynamic slippage + market impact; **Regime** = volatility + trend robustness.

Scope for this PR (owner): `git mv` only. No shims, no import/test/config edits, no new research layer. A component that fails the gate but cannot be moved without breaking an import or a test is left in place as **blocked: dependency**.

| Component | WF | CPCV | DSR | PBO | Costs | Regime | Decision | Notes |
|-----------|----|------|-----|-----|-------|--------|----------|-------|
| `lumina_core/risk`, `lumina_core/safety` | n/a | n/a | n/a | n/a | n/a | n/a | **KEEP** | Independent Risk Core. Untouchable. |
| Event Bus (`agent_orchestration`) | n/a | n/a | n/a | n/a | n/a | n/a | **KEEP** | Execution fabric. |
| Trading engine (`engine/`, `trading_engine/`) | tooling | tooling | tooling | tooling | tooling | partial | **KEEP** | `engine/backtest` has purged walk-forward + CPCV + PBO/DSR primitives. Not a strategy book. |
| Constitution | n/a | n/a | n/a | n/a | n/a | n/a | **KEEP** | Binding law. |
| Evolution PromotionGate / shadow / veto / rollout / Twin / DNA registry / policy DNA / canary / cutover | evidence consumer (`combinations≥5`) | consumes CPCV dict | required | max 0.40 | slippage ratio vs live | no | **KEEP** | REAL promotion fabric (ADR-0007/0032). Does not generate strategies. Incomplete vs the full charter as a *producer*; it is not a birth/evolution experiment. |
| `lumina_core/birth` (Birth phase v2, awakening, genesis, certificates) | single ~20% holdout | no | no | no | not a fee gate | curriculum stages ≠ result matrix | **blocked: dependency** | 399 external dependents (`tests/` 275, `lumina_core/` 59, `scripts/`, `lumina_launcher/`, `lumina_os/`, docs). Moving would break imports and tests. |
| Evolution strategy search (`strategy_generator`, `neuroevolution`, `genetic_operators`, `fitness_evaluator`, dream, generation_*, multi_day_sim_*, mutation_*, meta_*, orchestrator*, `research_lab`, `challenger_venue`, …) | no | optional fitness args, not run | optional | optional (defaults 0) | no | no | **blocked: dependency** | 65/65 experiment modules have importers (package `__init__.py`, KEEP fabric, engine, tests). |
| `reports/birth_cloud_run` + awakening/genesis run dumps | no | no | no | no | no | no | **blocked: dependency** | Path-read by birth runners and tests (`tests/birth/test_awakening_*`, launcher reset). Live birth code (unmoved) still writes these paths. |
| `scripts/run_birth_cloud_shadow.py` | no | no | no | no | no | no | **blocked: dependency** | `tests/birth/test_birth_cloud_runner.py`. |
| `scripts/run_birth_cloud_fault_inject.py` | no | no | no | no | no | no | **blocked: dependency** | Sibling import of `run_birth_cloud_shadow`. |
| `scripts/validation/birth_zero_human_cadence.py` | no | no | no | no | no | no | **blocked: dependency** | `tests/ops/test_birth_zero_human_cadence.py`. |
| `scripts/validation/declare_perfect_birth.py` | no | no | no | no | no | no | **blocked: dependency** | Imported from `lumina_core/birth` + tests. |
| `scripts/validation/perfect_birth_campaign.py` | no | no | no | no | no | no | **blocked: dependency** | Imported from `lumina_core/birth` + tests. |
| `scripts/extract_birth_phase_model.py`, `extract_birth_phase_orchestrator.py` | n/a | n/a | n/a | n/a | n/a | n/a | **blocked: dependency** | One-shot extractors listed in `ruff.toml` per-file ignores (config cannot be edited in this PR). |
| `scripts/verify-birth-deploy.ps1`, `scripts/validation/run_sim_birth_twin_validation.py` | n/a | n/a | n/a | n/a | n/a | n/a | **KEEP** (ops) | Deploy/harness helpers, not strategy search. |
| `scripts/install_birth_physics_stack.py`, `requirements-birth-physics.txt` | n/a | n/a | n/a | n/a | n/a | n/a | **KEEP** | Lungs / physics venv. |
| `scripts/run_awakening_grind.py` | no | no | no | no | no | no | **ARCHIVE** | No import/test dependents. |
| `scripts/run_awakening_select.py` | no | no | no | no | no | no | **ARCHIVE** | No import/test dependents. |
| `scripts/run_awakening_hole_tax.py` | no | no | no | no | no | no | **ARCHIVE** | No import/test dependents. |
| `scripts/run_genesis_cloud_ladder.py` | no | no | no | no | no | no | **ARCHIVE** | No import/test dependents. |
| `scripts/harvest_birth_exit_pi_star.py` | no | no | no | no | no | no | **ARCHIVE** | No import/test dependents. |
| `scripts/birth_runtime_fingerprint.py` | no | no | no | no | no | no | **ARCHIVE** | No import/test dependents. |
| `scripts/validation/birth_resume_exhaust_check.py` | no | no | no | no | no | no | **ARCHIVE** | No import/test dependents. |

Archived paths: `archive/birth-v1/scripts/…` (history preserved via `git mv`). No deletes. Risk Core, Event Bus, trading engine, and constitution are unchanged.
