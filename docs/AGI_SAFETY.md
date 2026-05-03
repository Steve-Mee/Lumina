# LUMINA AGI Safety System

> **"Kapitaalbehoud is heilig."** — LUMINA .cursorrules

LUMINA is a self-learning, self-evolving AI organism that mutates its own trading DNA thousands of times per year. Without hard, machine-enforced safety boundaries, this evolutionary power becomes an existential risk to the capital it is entrusted to protect.

This document describes the three-layer AGI Safety architecture that makes LUMINA's evolution safe by construction — not by convention.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                    EvolutionOrchestrator                          │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              ConstitutionalGuard                             │ │
│  │  ┌─────────────────────┐  ┌───────────────────────────────┐ │ │
│  │  │  TradingConstitution│  │  SandboxedMutationExecutor    │ │ │
│  │  │  15 Principles      │  │  Subprocess isolation         │ │ │
│  │  │  Fail-closed        │  │  Secret stripping             │ │ │
│  │  │  Mode-aware         │  │  Hard timeout                 │ │ │
│  │  └─────────────────────┘  └───────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  Phase 1: check_pre_mutation()  ─── before any code executes     │
│  Phase 2: evaluate_sandboxed()  ─── isolated fitness scoring     │
│  Phase 3: check_pre_promotion() ─── final gate before live DNA   │
└──────────────────────────────────────────────────────────────────┘
```

All three layers are **fail-closed**: any unexpected error blocks the mutation/promotion rather than allowing it through.

---

## Canonical Audit & Hash Chain (lumina_audit_v1)

LUMINA now uses one canonical audit integrity system across safety-critical paths.

- **Facade:** `lumina_core/audit/audit_logger.py` (`AuditLogger`, `StreamRegistry`)
- **Canonical chain fields:** `schema_version="lumina_audit_v1"`, `prev_hash`, `entry_hash`
- **Write primitive:** `safe_append_jsonl(..., hash_chain=True)` with cross-process file locks
- **REAL mode:** fail-closed (`AuditChainError`) on corruption or append failure
- **SIM/PAPER:** corrupt files rotate to `*.corrupt.*` and a new chain segment starts from `GENESIS`

Canonical streams:

- `trade_decision`
- `agent_decision`
- `evolution_meta`
- `agent_thought`
- `security`
- `governance.real_promotion`
- `evolution.decisions`
- `safety.constitution`
- `trade_reconciler`
- `lumina_bible`

Legacy `hash` is dual-written temporarily on selected migrated streams for backward compatibility.
Historical `lumina_bible` entries written before this migration use a different legacy formula and are not
guaranteed to validate under `validate_hash_chain`; all new writes use the canonical chain.

## Typed FaultPolicy (decision & audit paths)

LUMINA now enforces one explicit fault policy for decision/audit integrity paths:

- **Module:** `lumina_core/fault/fault_policy.py` (`FaultDomain`, `FaultPolicy`, `LuminaFault`)
- **Coverage:** agent contract decision mirroring, agent decision log, audit logger/service, evolution audit writers, veto read/write paths, and reasoning decision-log writes
- **Alarming:** every handled fault writes a structured entry to `logs/structured_errors.jsonl` with `fault_id`, `domain`, `operation`, and `cause_*` fields
- **REAL mode:** fail-closed by default for critical writes; faults raise typed exceptions immediately after structured logging
- **SIM/PAPER mode:** tolerant where exploration requires continuity, but faults remain visible and traceable via structured logs and stack traces

This removes silent broad-exception behavior from decision/audit write paths and keeps every integrity fault attributable.

---

## Economic PnL vs training reward (capital path)

- **`economic_pnl`** (broker-confirmed fills → commissions → realized net) is the **only** input for REAL capital reporting, risk accumulation (`HardRiskController.record_trade_result` in REAL accepts `PnlProvenance.BROKER_RECONCILED` only), and governance metrics that claim economic truth.
- **`training_reward`** and Gym **`reward`** exist **only** in RL training modules: [`lumina_core/rl/`](../lumina_core/rl/) (canonical Gym env) and [`lumina_core/engine/rl/`](../lumina_core/engine/rl/) (Meta-RL / engine-attached env). They may include reward shaping, heuristic VaR penalties, and other **non-broker** terms. They must **never** be labeled as economic PnL or fed into REAL risk totals.
- **RL rollout metrics:** keys such as `shadow_total_training_reward` (Gym reward sums from [`ppo_trainer`](../lumina_core/ppo_trainer.py)) are training signals only, not broker `economic_pnl`.
- **Central enforcement:** [`EconomicPnLService`](../lumina_core/engine/economic_pnl_service.py) wraps the golden ledger formulas and **rejects** payloads that carry RL-only keys (e.g. `training_reward`). SIM and evolution layers may experiment freely; REAL stays fail-closed on provenance.

---

## LLM As Powerful Advisor, Never Sole Ruler

LUMINA treats the LLM as a high-bandwidth reasoning engine, not as an execution authority:

- The LLM may always generate creative hypotheses, counterfactuals, dreams, and mutation proposals in SIM, PAPER, and REAL.
- Any capital-relevant output is routed through `LLMDecisionRouter` and only becomes executable after deterministic checks.
- In REAL mode, no order intent is executable on LLM output alone; it must pass `FinalArbitration`, which already enforces both `RiskPolicy` and `TradingConstitution`.
- Final Arbitration beschermt het organisme, maar beperkt zijn creatieve ziel niet.
- Timeout/error paths degrade deterministically to conservative behavior (`HOLD`) and are logged as `rule_based_fallback` for audit transparency.
- Every routed LLM payload includes `llm_confidence` (0..1). Low confidence increases rule weight and blocks direct order execution in REAL mode.
- REAL temperature is clamped to 0.30-0.40 by default to reduce stochastic drift; higher temperature requires an explicit audit identifier (`real_temperature_override_audit_id`) so overrides are attributable.

This preserves radical creativity in the advisory layer while making the capital path deterministic, reviewable, and constitutionally constrained.

## Typed Event Contract Balance: Safety and Emergence

LUMINA keeps a deliberate two-tier contract strategy in `lumina_core/agent_orchestration/schemas.py`:

- **Tier A (strict, `extra="forbid"`):** `TradeIntent`, `RiskVerdict`, `FinalArbitrationResult`, `ConstitutionAudit`, `ShadowResult`, `EvolutionPromotionDecision`.
- **Tier B (flexible, `extra="allow"`):** `EvolutionProposal`, `AgentReflection`, `DreamState`, `MetaAgentThought`, `CommunityKnowledgeSnippet`, `LLMDecisionContext`.

Why this split is safety-aligned:

- Tier A protects REAL execution and governance boundaries against schema drift; unknown fields are hard-rejected so critical decisions remain deterministic and auditable.
- Tier B preserves Lumina's experimental soul: agents and LLM layers can surface novel features and emergent structure while contracts are still being discovered.
- Flexible Tier B payloads never bypass deterministic execution gates; REAL capital paths still require admission-chain checks, constitution checks, and `FinalArbitration`.

This gives Lumina a controlled organism pattern: strict where capital is exposed, flexible where learning happens.

---

## Layer 1: TradingConstitution — 15 Hard Principles

**File:** `lumina_core/safety/trading_constitution.py`

The `TradingConstitution` is the machine-readable encoding of the LUMINA Noordster. It contains 15 immutable principles that every DNA mutation must satisfy before it can be executed, scored, or promoted.

### Principles

| # | Name | Severity | Mode | Description |
|---|------|----------|------|-------------|
| 1 | `capital_preservation_in_real` | FATAL | REAL | `max_risk_percent` ≤ 3% |
| 2 | `no_naked_orders` | FATAL | ANY | Risk controller & gatekeeper must never be disabled |
| 3 | `max_mutation_depth_enforced` | FATAL | REAL | Only `conservative`/`moderate` mutations in live mode |
| 4 | `approval_required_in_real` | FATAL | REAL | Human approval gate cannot be bypassed |
| 5 | `no_synthetic_data_in_real_neuro` | FATAL | REAL | Neuroevolution must use real OHLC data |
| 6 | `drawdown_kill_percent_bounded` | FATAL | ANY | `drawdown_kill_percent` ≤ 25% |
| 7 | `no_aggressive_evolution_in_real` | FATAL | REAL | `aggressive_evolution` forbidden in live mode |
| 8 | `kelly_fraction_cap` | FATAL | REAL | `kelly_fraction` ≤ 0.25 (quarter-Kelly) |
| 9 | `daily_loss_hard_stop_required` | FATAL | REAL | Daily loss cap must be active (negative value) |
| 10 | `no_leverage_explosion` | FATAL | REAL | `leverage_multiplier` ≤ 2× |
| 11 | `minimum_backtest_quality_for_real` | FATAL | REAL | `backtest_sharpe_ratio` ≥ 0.3 when present |
| 12 | `no_circuit_breaker_disable` | FATAL | ANY | Emergency halt cannot be disabled |
| 13 | `no_session_guard_bypass` | FATAL | REAL | Session guard cannot be bypassed |
| 14 | `concentration_risk_limit` | WARN | REAL/PAPER | Single-instrument exposure ≤ 80% |
| 15 | `trade_frequency_guard` | WARN | ANY | Daily trade frequency ≤ 200 trades/day |

### Severity

- **FATAL**: Blocks the mutation/promotion immediately. Logged as `ERROR`. The evolution cycle is halted for this candidate.
- **WARN**: Logged as `WARNING`. The candidate is allowed to proceed but the violation is recorded in the audit trail.

### Fail-Closed Design

If a check function raises an exception (e.g., due to a malformed DNA payload), the exception is caught and the principle is treated as **violated** with FATAL severity. This prevents adversarially crafted DNA from exploiting errors to bypass checks.

### Mode Awareness

Principles are mode-aware: REAL mode is the strictest, followed by PAPER, then SIM. In SIM mode, experimentation is allowed within physical bounds (principles 2, 6, 12 still apply in SIM).

### Usage

```python
from lumina_core.safety.trading_constitution import TRADING_CONSTITUTION

# Audit a DNA candidate.
violations = TRADING_CONSTITUTION.audit(dna_content, mode="real", raise_on_fatal=False)
fatals = [v for v in violations if v.severity == "fatal"]

# Quick boolean check.
is_safe = TRADING_CONSTITUTION.is_clean(dna_content, mode="real")

# Red-team probe (for tests).
result = TRADING_CONSTITUTION.probe_attack(
    evil_dna, mode="real",
    expected_violations=["no_naked_orders", "capital_preservation_in_real"],
)
assert result["blocked"] and result["expected_hit"]
```

---

## Layer 2: SandboxedMutationExecutor — Process Isolation

**File:** `lumina_core/safety/sandboxed_executor.py`

Every DNA candidate is scored in a **subprocess** with the following guarantees:

### Isolation Properties

| Property | Mechanism |
|----------|-----------|
| **State isolation** | `LUMINA_STATE_DIR` and `LUMINA_LOGS_DIR` redirected to a private `tmpdir` |
| **Process isolation** | Separate Python process — a crash cannot affect the parent |
| **Network isolation** | `socket.setdefaulttimeout(0.001)` blocks all outbound network calls |
| **Secret isolation** | All `API_KEY`, `TOKEN`, `PASSWORD` env vars stripped before subprocess fork |
| **Hard timeout** | Subprocess killed after 45s; timeout = failed evaluation |
| **I/O protocol** | JSON stdin/stdout only — no pickle, no shared memory |

### Audit Trail

Every evaluation produces a `SandboxedResult` with:
- `input_hash`: SHA-256 of the full input payload (deterministic, reproducible)
- `output_hash`: SHA-256 of the subprocess stdout (for forensic verification)
- `dna_hash`: First 16 chars of the DNA content hash
- `violations`: List of constitutional violation names
- `score`: Fitness score (0.0 on any failure)
- `sandbox_used`: `True` when subprocess mode was used

The `to_audit_record()` method produces a dict suitable for appending to `logs/evolution_metrics.jsonl`.
Safety-critical evolution decisions are additionally persisted through the canonical `lumina_audit_v1` chain.

### When Is Sandboxing Used?

- **REAL mode**: Always sandboxed (cannot be disabled).
- **SIM/PAPER mode**: Sandboxed by default; can be disabled via `config.yaml` → `evolution.sandbox_mutations: false` for development speed.

### Usage

```python
from lumina_core.safety.sandboxed_executor import SandboxedMutationExecutor

executor = SandboxedMutationExecutor(timeout_s=45)
result = executor.evaluate(
    dna_content=dna_json,
    mode="real",
    pnl=500.0,
    max_dd=200.0,
    sharpe=1.2,
)

if result.passed:
    # Safe to register as candidate.
    registry.register_dna(candidate)
else:
    logger.error("Candidate blocked: %s", result.violations)
```

---

## Layer 3: ConstitutionalGuard — Top-Level Integration Point

**File:** `lumina_core/safety/constitutional_guard.py`

The `ConstitutionalGuard` is the single integration point for all safety checks in the evolution loop. It composes `TradingConstitution` and `SandboxedMutationExecutor` behind a clean API.

### Two Enforcement Phases

```
DNA mutant created
       │
       ▼
┌─────────────────────┐
│  check_pre_mutation  │  Fast (in-process). Blocks before sandbox investment.
│  (TradingConstitution│
│  check only)         │
└──────────┬──────────┘
           │ passed
           ▼
┌────────────────────────┐
│  evaluate_sandboxed     │  Subprocess. Scores fitness + constitutional check.
│  (SandboxedMutationExec│
│  utor)                 │
└──────────┬─────────────┘
           │ scored
           ▼
┌─────────────────────┐
│  check_pre_promotion │  Final gate. Raises on FATAL by default.
│  (TradingConstitution│
│  check only)         │
└─────────────────────┘
           │ passed
           ▼
     DNA promoted to active
```

### Audit Logging

Every `check_pre_mutation` and `check_pre_promotion` call appends a structured JSON record to:

```
$LUMINA_STATE_DIR/constitutional_audit.jsonl
```

Fields include canonical chain metadata (`schema_version`, `stream`, `prev_hash`, `entry_hash`) plus guard fields (`audit_id`, `check_phase`, `mode`, `dna_hash`, `passed`, `fatal_count`, `warn_count`, `violation_names`, `timestamp`).

This provides a complete forensic trail of every safety decision made during the organism's lifetime.

### Integrity vs Experimentation (SIM/REAL)

LUMINA now enforces a strict rule on decision and audit chains: silent exceptions are forbidden on critical log paths.

- `AgentDecisionLog`, `AuditLogService`, `EvolutionAuditWriter`, and `agent_contracts` now use the canonical `AuditLogger` chain and log write/read failures with stack traces.
- **SIM/PAPER behavior:** experimental layers remain permissive. Failures are visible in logs, but non-capital simulation workflows continue where safe.
- **REAL behavior:** fail-closed remains active on capital paths (`order_gatekeeper` blocks when trade-decision audit logging fails), and contract mirror failures in REAL now raise explicitly instead of being silently ignored.
- Hash-chain read corruption in `AgentDecisionLog` is tolerated in SIM (with error logging) but treated as a hard failure in REAL to protect audit integrity.

---

## Layer 4: FinalArbitration — Runtime Order Enforcement

**Files:** `lumina_core/risk/risk_policy.py`, `lumina_core/risk/final_arbitration.py`

`FinalArbitration` is the final fail-closed runtime gate before broker submission. It evaluates each order intent against:

1. **Input integrity** (symbol, side, quantity, state completeness)
2. **TradingConstitution** (fatal violations reject immediately)
3. **RiskPolicy** (daily loss, per-instrument risk, total open risk, Kelly cap, VaR/ES limits)
4. **Live account state** (equity sanity, margin availability, drawdown kill threshold)

### Hard guarantee

No agent proposal can bypass this layer through supervisor flow, operations/reasoning services, or direct broker submit paths. Any arbitration error is treated as `REJECTED` (fail-closed). Final runtime decisions are persisted via the canonical `trade_decision` stream.

### Mode behavior

- **REAL:** strictest thresholds; capital preservation is sacred.
- **PAPER:** realistic enforcement close to REAL.
- **SIM:** learning-friendly but still bounded by physical risk constraints.

### REAL equity snapshot gate

- REAL order intents that increase risk now require a **fresh (<= 30s) equity snapshot** from the active broker path.
- Snapshot data is resolved via `EquitySnapshotProvider` (`lumina_core/risk/equity_snapshot.py`) and consumed by `build_current_state_from_engine`.
- If broker equity/margin data is missing, stale, or fetch fails, the runtime gate is **fail-closed**: no new risk-increasing trades are allowed.
- Risk-reducing exits (flatten direction) remain allowed so the system can still de-risk under degraded broker telemetry.
- Final Arbitration is de ultieme, niet-omzeilbare poort in REAL. EquitySnapshot is een harde pre-conditie.
- EquitySnapshot staat vóór Final Arbitration in de admission chain om kapitaalbehoud af te dwingen: zonder verse account-equity en margin-context kan het systeem geen betrouwbare risico-inschatting doen, dus wordt de order fail-closed afgewezen.

### Usage

```python
from lumina_core.risk.final_arbitration import (
    FinalArbitration,
    build_current_state_from_engine,
    build_order_intent_from_order,
)
from lumina_core.risk.risk_policy import load_risk_policy

policy = load_risk_policy(mode="real")
arb = FinalArbitration(policy)

intent = build_order_intent_from_order(order, dream_snapshot=engine.get_current_dream_snapshot())
state = build_current_state_from_engine(engine)
result = arb.check_order_intent(intent, state)

if result.status != "APPROVED":
    logger.warning("FinalArbitration blocked order: %s", result.reason)
    return

broker.submit_order(order)
```

---

## Layer 5: PromotionGate — Non-Negotiable REAL Promotion Gate

**File:** `lumina_core/evolution/promotion_gate.py`

Promotion to REAL is now blocked unless **all** of the following criteria pass in one fail-closed evaluation:

1. **Out-of-sample robustness**: Purged walk-forward + combinatorial purged CV evidence must meet minimum Sharpe consistency and overfitting controls.
2. **Reality gap**: live/paper execution must stay within allowed gap bands for slippage and fill-rate degradation versus backtest.
3. **Stress drawdown ceiling**: deterministic stress overlays must remain under the configured maximum drawdown percentage of equity.
4. **Statistical significance**: minimum trade sample plus Welch p-value (`p < 0.05`) and Cohen's d (`d > 0.3`) thresholds.

### Hard rule

- This gate is **non-negotiable** for REAL promotions.
- Any missing or invalid evidence is treated as **reject** (fail-closed).
- `mean_pnl > 0` is no longer sufficient for REAL promotion.

### Integration point

The gate is enforced in `PromotionPolicy.run_shadow_validation_gate()` after shadow validation passes and before the rollout/human approval decision path proceeds.

`ShadowDeploymentTracker.compute_shadow_verdict()` in `lumina_core/evolution/shadow_deployment.py` is a legacy/experiment heuristic and is not used as the REAL promotion authority.

---

## Evolution Loop Integration

The `ConstitutionalGuard` is wired into `EvolutionOrchestrator` at two points:

1. **`_generate_candidates()`**: `check_pre_mutation()` is called for every generated candidate. Candidates that fail are discarded without being registered in the DNA registry.

2. **`_run_single_generation()`**: `check_pre_promotion()` is called as the final gate before a winner DNA is promoted to `"active"` status. This replaces the previous inline `ConstitutionalChecker()` call.

### Rollout Safety Layer (Shadow + Human Approval)

**Files:** `lumina_core/evolution/rollout.py`, `lumina_core/evolution/evolution_orchestrator.py`

LUMINA voegt een extra promotion gate toe via `EvolutionRolloutFramework`:

1. **Shadow-first in REAL mode**: geen REAL promotie zonder geslaagde shadow-validatie.
2. **Radicale mutaties**: verplicht expliciete human approval in REAL/PAPER.
3. **A/B context**: geselecteerde variant wordt vergeleken met de A/B baseline.
4. **Audit trail**: iedere rollout-beslissing wordt gelogd naar `state/evolution_rollout_history.jsonl`; governance/security-critical approvals additionally flow through canonical hash-chained streams.

Deze laag is fail-closed: als shadow of human approval niet voldoet, wordt promotie geblokkeerd.

---

## Red-Team Testing

**File:** `tests/safety/test_redteam_attacks.py`

The red-team test suite simulates adversarial DNA attack vectors:

| Attack Category | Tests |
|----------------|-------|
| Gatekeeper bypass flags | 4 |
| Capital destruction (risk amplification) | 6 |
| Approval gate bypass | 4 |
| Type confusion (string/None/bool injection) | 5 |
| Unicode/encoding tricks | 3 |
| Extreme value injection | 6 |
| Multi-vector combined attacks | 2 |
| ConstitutionalGuard integration | 8 |

**A passing red-team test means the attack was BLOCKED.** The goal is 100% attack-blocked coverage.

### Running the Safety Tests

```bash
# All safety tests (unit + subprocess)
pytest tests/safety/ -v

# Unit tests only (fast, no subprocess)
pytest tests/safety/ -m unit -v

# Subprocess isolation tests (slow)
pytest tests/safety/ -m slow -v

# Full safety gate with mypy
mypy lumina_core/safety/ --ignore-missing-imports
pytest tests/safety/ -v --tb=short
```

---

## ADR Reference

Architecture decisions live under `docs/adr/`. **Prefer the canonical `000x` series** ([index](adr/README.md)); the `ADR-00x-*` filenames remain for bookmarks and older references.

| Topic | Canonical ADR | Legacy ADR (historical filename) |
|-------|---------------|----------------------------------|
| Trading constitution, sandboxed mutation executor, constitutional guardrails | [0003](adr/0003-trading-constitution-sandboxed-mutation-executor.md) | [ADR-001](adr/ADR-001-constitutional-principles.md) · [ADR-004](adr/ADR-004-agi-safety-system.md) |
| Shadow deployment + mandatory human approval for radical mutations | [0002](adr/0002-shadow-deployment-human-approval.md) | — |
| Canonical audit/hash-chain unification | [ADR-0042](adr/ADR-0042-canonical-audit-logger.md) | — |

---

## Principles of Constitutional Design

1. **Fail-closed**: An error in a check blocks execution. Never fail-open.
2. **Immutable**: Principles cannot be modified at runtime. The constitution is a tuple, not a list.
3. **Mode-aware**: REAL > PAPER > SIM in terms of strictness.
4. **Auditable**: Every check is logged with a unique ID, timestamp, and DNA hash.
5. **Layered**: Pre-mutation → sandbox → pre-promotion forms a defence-in-depth.
6. **Testable**: Every principle has at least 3 unit tests (pass, fail, mode-skip).
7. **Human-readable**: Every principle has a `rationale` field explaining *why* it exists.

---

## Threat Model

| Threat | Mitigation |
|--------|-----------|
| Adversarial DNA with bypass flags | `no_naked_orders`, `no_circuit_breaker_disable` principles |
| Capital blowup via excessive risk | `capital_preservation_in_real`, `kelly_fraction_cap`, `no_leverage_explosion` |
| Approval gate bypass | `approval_required_in_real` principle |
| Synthetic data overfitting | `no_synthetic_data_in_real_neuro` principle |
| Runaway loss without stop | `daily_loss_hard_stop_required`, `drawdown_kill_percent_bounded` |
| Sandbox escape via env vars | Secret stripping, `socket.setdefaulttimeout(0.001)`, tmpdir isolation |
| Subprocess state corruption | Private tmpdir, LUMINA_STATE_DIR/LUMINA_LOGS_DIR redirect |
| Infinite loop / DoS | Hard 45-second subprocess timeout |
| Type confusion attacks | All `float()` / `int()` conversions wrapped in try/except |

---

## LLM Runtime Safeguards (Live Loop)

LUMINA now enforces a dedicated LLM discipline layer for every live-loop reasoning call:

- **Central wrapper**: `lumina_core/inference/llm_client.py` provides one fail-closed gateway around local/remote providers (`ollama`, `vllm`, `grok_remote` and future providers).
- **Hard latency budget**: each call is capped by `inference.llm_max_latency_ms`. Effective timeout is the strict minimum of request timeout and budget.
- **Automatic fail-closed fallback**: timeout, provider errors, or empty/malformed LLM responses produce deterministic fallback (`signal=HOLD`) instead of propagating an order-intent.
- **REAL-mode temperature discipline**: in REAL mode, temperature is clamped to a safe low band (`llm_real_temperature`, bounded to 0.30-0.40) unless explicitly overridden via `LUMINA_FORCE_HIGH_TEMP`.
- **Path-level audit trail**: `logs/llm_decisions.jsonl` records `path` (`fast_rule` or `llm_reasoning`) plus `decision_context_id`, prompt/response hashes, model version, latency, provider, temperature, and fallback status.
- **Trade traceability**: every call receives a unique `decision_context_id`, so each trade decision can be traced back to the exact LLM invocation or deterministic fast-rule fallback.

Environment flags:

- `LUMINA_FORCE_HIGH_TEMP=1` allows bypassing REAL-mode temperature clamp (intended for explicit operator override only).
- `LUMINA_LLM_DECISIONS_LOG=/path/to/file.jsonl` overrides the default LLM decision log location.

---

## ApprovalChain (REAL Promotion)

REAL promotion now has an additional non-bypassable governance gate: `ApprovalChain`.

- **Cryptographic approvals only**: each REAL promotion payload is signed with Ed25519 and verified against an allowlist of public keys (`governance.real_approval_public_keys_hex`).
- **Multi-party threshold**: promotion is allowed only when a configured threshold (`governance.real_approval_threshold`) is met (e.g., 2-of-3).
- **Payload binding**: signatures are bound to canonical payload bytes, including DNA hash and DNA content digest, preventing replay on modified DNA.
- **Fail-closed by design**: missing policy, expired payload, malformed signatures, unauthorized signers, or threshold shortfall block promotion.
- **Hash-chained audit trail**: every approval event writes timestamp, approver, DNA hash, reason, and verification result to canonical stream `governance.real_promotion` (`state/real_promotion_approval_audit.jsonl`) with `schema_version`, `prev_hash`, `entry_hash`.
- **No REAL bypass flag**: for `mode=real`, disabling `require_human_approval` is treated as unsafe and promotion is rejected.

This gate complements (not replaces) `PromotionGate`, `EvolutionRolloutFramework`, and `ConstitutionalGuard`. A candidate must pass all layers before becoming active in REAL.

---

*Last updated: LUMINA v55 | Maintained by the LUMINA AGI Safety subsystem.*
