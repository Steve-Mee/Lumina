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

Fields: `audit_id`, `check_phase`, `mode`, `dna_hash`, `passed`, `fatal_count`, `warn_count`, `violation_names`, `timestamp`.

This provides a complete forensic trail of every safety decision made during the organism's lifetime.

### Usage

```python
from lumina_core.safety.constitutional_guard import ConstitutionalGuard

guard = ConstitutionalGuard()

# Phase 1: before sandbox (cheap, fast).
pre = guard.check_pre_mutation(dna_content, mode="real")
if not pre.passed:
    logger.warning("Pre-mutation blocked: %s", pre.violation_names)
    continue

# Phase 2: sandboxed scoring.
scored = guard.evaluate_sandboxed(
    dna_content=dna_content, mode="real",
    pnl=pnl, max_dd=max_dd, sharpe=sharpe,
)

# Phase 3: final gate (raises on FATAL by default).
guard.check_pre_promotion(dna_content, mode="real")  # raises if violated
```

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
4. **Audit trail**: iedere rollout-beslissing wordt gelogd naar `state/evolution_rollout_history.jsonl`.

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

*Last updated: LUMINA v54 | Maintained by the LUMINA AGI Safety subsystem.*
