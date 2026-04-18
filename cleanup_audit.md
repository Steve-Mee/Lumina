# Fallback Cleanup Audit

Date: 2026-04-18
Scope: lumina_core (focus: engine, evolution, rl)

## Removed fallback/legacy paths

1. lumina_core/engine/decision_graph.py
- Removed legacy supervisor fallback path (`_legacy_supervisor_loop`) at execution stage.
- Removed silent empty-handler fallback when blackboard/handler map is missing.
- Enforced fail-hard behavior with `LuminaError` for missing blackboard, missing handler map, and undefined node handlers.

2. lumina_core/evolution/evolution_orchestrator.py
- Removed `nightly_report or {}` fallback; nightly report is now required and validated.
- Removed empty generation fallbacks (`if not candidates`, `if not sim_results`) that silently returned non-promoted generation artifacts.
- Replaced summary default fallback (`max(..., default=-inf)`) with explicit non-empty validation.
- Removed metrics append swallow-failure block; metrics write now fails hard.
- Removed blackboard publish swallow-failure block; missing publish interface now fails hard.

3. lumina_core/engine/self_evolution_meta_agent.py
- Removed container dependency fallbacks in `from_container` for valuation engine and risk controller.
- Removed implicit `fine_tuning_cfg` default fallback; explicit dict is now required.
- Removed runtime mode fallback to `real`; invalid mode now fails hard.
- Removed automatic `EvolutionGuard` and `DNARegistry` creation fallbacks; both must be injected.
- Removed AB experiment exception fallback result payload (`ab-sim-failed`) and switched to direct failure semantics.
- Removed observability and proposal publish silent exception swallowing in nightly flow.
- Removed multi-generation orchestrator catch-all fallback result (`status: error`) and now fail-hard on orchestration errors.
- Removed DNA content parse fallback from raw string to synthetic payload; DNA content must be JSON object.
- Removed candidate field fallback behavior in DNA candidate extraction; required fields are enforced.
- Removed fallback-heavy `load_evolution_config` defaults for missing file/sections/keys; config schema is now required and validated.

4. lumina_core/engine/rl/rl_trading_environment.py
- Removed backward-compatible dict action parsing in `step`.
- Enforced ndarray-only action interface with explicit shape check and fail-hard `LuminaError`.
- Removed instrument and DNA-version default fallbacks from runtime context lookup.

5. lumina_core/engine/lumina_engine.py
- Removed SessionGuard initialization swallow-failure fallback (`except Exception ... self.session_guard = None`).
- Removed safe-default profile fallback logic in `_load_mode_risk_profile`.
- Enforced strict config schema (`sim`, `real`, `trading` mappings and required keys) with fail-hard `LuminaError` on invalid config.

6. lumina_core/order_gatekeeper.py
- Removed dream/agent fallback assembly paths and enforced explicit audit dependencies.
- Removed synthetic regime snapshot fallback object; snapshot provider contract is now explicit.
- Removed silent exception swallowing in observability/audit/blackboard lineage collection.
- Enforced strict tuple contracts for VaR/ES and Monte-Carlo gate methods.

7. lumina_core/engine/local_inference_engine.py
- Removed provider-chain auto-fallback execution (`fallback_order`) at runtime request dispatch.
- Removed ultimate HOLD fallback response (`All inference providers failed`).
- Removed parse-error HOLD fallback payload and enforced JSON-object payload contract.
- Removed silent provider error swallowing in vLLM/Ollama/xAI provider adapters.

8. lumina_core/runtime_context.py
- Removed implicit app-namespace compatibility path; adapter now delegates only to engine surface.
- Kept explicit engine delegation for runtime service contract compatibility.

## Total explicit fallback removals

- 45+ fallback/legacy control-flow paths removed or converted to fail-hard behavior across core runtime paths.

## Validation snapshot (second strict pass)

- Targeted strict-change suites: passing.
- Full command validation: `pytest tests/ --cov=lumina_core/evolution --cov-report=term-missing -q --tb=no` => 464 passed, 2 skipped, 89% evolution coverage.
- Runtime validation executed:
	- `python lumina_runtime.py --mode=paper --duration=300`
	- `python lumina_runtime.py --mode=sim --duration=300`
- `logs/evolution_metrics.jsonl` confirmed active with fresh generation events during runtime validation.

## Notes

- This cleanup intentionally favors explicit crashes in dev over degraded/legacy behavior.
- Any missing dependency/configuration now surfaces immediately at runtime via `LuminaError` or direct exception propagation.
