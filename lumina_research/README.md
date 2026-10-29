# lumina_research

Propose-only research layer for Lumina. This is **not** Lumina-Lab and must not follow the closed `lumina-lab` project.

## Charter

Binding rules: [`RESEARCH_CHARTER.md`](../RESEARCH_CHARTER.md) (repo-root SSOT).

Every task starts with the Validation Gate. No strategy, signal, or mutant work until this gate exists and its tests pass. After that, candidates still must pass `passes_validation_gate` before they may be *proposed* to KEEP fabric.

## Phase 1 — Validation Gate

| Path | Role |
|------|------|
| `validation/walk_forward.py` | Rolling and expanding windows; minimum 6 non-overlapping OOS periods; WFE; parameter stability |
| `validation/cpcv.py` | Combinatorial Purged CV (purge on t1, embargo, φ = k/N × C(N,k) paths) |
| `validation/pbo.py` | CSCV logit PBO (Bailey et al. 2014) |
| `validation/dsr.py` | Deflated Sharpe Ratio (Bailey & López de Prado 2014); N from the trial registry only |
| `validation/cost_model.py` | Commission + half-spread + volume/vol slippage + √ impact; ES/NQ vs MES/MNQ |
| `validation/gate.py` | `passes_validation_gate(results) -> (bool, report)` — doubt = reject |
| `validation/audit.py` | Append-only JSONL: every trial, gate decision, and reject |
| `fitness.py` | Composite of median OOS Sharpe after costs + (1−PBO) + WFE + regime robustness; never IS PnL |
| `risk_core/` | Additional research Risk Core. See [`risk_core/README.md`](risk_core/README.md) |

Thresholds (`validation/gate_thresholds.toml`): DSR probability ≥ 0.95, WFE ≥ 0.5, PBO warning ≥ 0.25, PBO hard reject > 0.50, ≥ 6 OOS windows, costs required.

## Phase 2 — multi-agent research loop

| Path | Role |
|------|------|
| `agents/hypothesis.py` | `HypothesisAgent` — pluggable, seeded generators; rationale required; every variant is a `TrialRegistry` trial |
| `agents/validation_agent.py` | `ValidationAgent` — full Phase 1 `evaluate_candidate` pipeline; always publishes `ValidationResult` (OOS / DSR / PBO / WFE / reject reasons) |
| `agents/promotion.py` | `PromotionAgent` — `PromotionCandidate` only after sealed PASS + research Risk Core (`Approved` or `Scaled`) |
| `agents/experiment_log.py` | Append-only JSONL via the Phase 1 audit writer (`flock` + `fsync`) |
| `agents/loop.py` | `run_phase2_loop` on synthetic data |

Typed events `HypothesisProposed`, `ValidationResult`, `PromotionCandidate` are additive on the Event Bus / Blackboard (`research.*` topics). Existing topics are unchanged. `ValidationResult` and `PromotionCandidate` carry HMAC provenance and are issuer-guarded on the bus; a forged, edited, or replayed `ValidationResult` cannot become a `PromotionCandidate`. A `PromotionCandidate` is a **proposal**; this layer never writes the live `PromotionGate` or `lumina_core/risk`.

## Phase 3 — self-evolution within bounds

| Path | Role |
|------|------|
| `evolution/birth.py` | `BirthPhase` — open new walk-forward windows and tune parameters (propose-only) |
| `evolution/reflector.py` | `ReflectorAgent` — can only propose; apply/promote/skip-trial raise |
| `evolution/governance.py` | ADR file + HMAC-signed human review for Risk Core / threshold changes; never auto-applied |
| `evolution/regime.py` | Volatility/trend → size multiplier only; strategy switches refused |
| `evolution/loop.py` | `run_phase3_evolution` — every mutation is a `TrialRegistry` trial, then the Phase 2 event flow |
| `evolution/integrity.py` | Snapshot hashes of Risk Core, floors, and the bound Validation Gate |

Fitness remains `lumina_research/fitness.py` (median OOS Sharpe after costs, 1−PBO, WFE, regime robustness, turnover and low-DSR penalties). In-sample PnL is refused. Additive topics: `research.mutation.proposed`, `research.governance.decision`.

## Phase 4 — continuity and live monitoring

| Path | Role |
|------|------|
| `monitoring/monitor.py` | Compare live paper/shadow metrics to the sealed OOS distribution (z / percentile / CUSUM / SPRT) |
| `monitoring/registry.py` | Admit-only live book from sealed `PromotionCandidate` + `ValidationResult` |
| `monitoring/capacity.py` | Per-signal, instrument, family, and cluster caps; scale-back only |
| `monitoring/sizing.py` | Weight × capacity × regime (all ≤ 1) then research Risk Core `propose_order()` |
| `monitoring/guardian.py` | Daily/weekly Research Charter scan; violations propose suspend |
| `monitoring/replenish.py` | Floor breach → `HypothesisAgent` only; no registry shortcut |
| `monitoring/cli.py` | Scheduler entrypoint: `python -m lumina_research.monitoring daily\|weekly` |
| `monitoring/loop.py` | `ContinuityRuntime` + `run_phase4_detection` |

Staged reductions: `active → deweighted → suspended → retired`. Weights never rise. Additive topics: `research.decay.detected`, `research.signal.deweighted`, `research.signal.suspended`, `research.signal.retired`, `research.capacity.scaled`, `research.guardian.finding`, `research.replenishment.requested`. ADR-0058.

## Phase 5 — empirical proof and Fabric ports (no coupling)

| Path | Role |
|------|------|
| `proof/` | Independent P1 suite: Phase 1 gate + two-horizon FAR/TTD vs frozen Phase 4 floors. CLI: `python -m lumina_research.proof verify` |
| `cycles/` | 12 economic templates × 2 variants (24 pre-filter). First cycle: 12 MES/MNQ variants pre-registered before seeing bars. NT8 1m holdout lock (last 9 months, fail-closed). Real data or a graceful stop. Cost bands and limit-fill model. P3 SIM plan (not started). `python -m lumina_research.proof research` |
| `ports/` | Research-side Execution Fabric contracts: `SignalIntent`, `ResearchOrderIntent`, `ResearchFillEvent`, fail-closed alerts. Shadow book logs signals and CostModel hypothetical fills. `place_order` / `connect_fabric` raise. ADR-0059 |
| `monitoring/weekly.py` | Weekly hypothesis / FAR / TTD / capital-preservation report. Guardian also asserts mutation kill ≥ 0.80 and sealed gate passage |

This layer does **not** open a gRPC stream, write NinjaTrader state, expand the SIM whitelist, or set `LIVE_RELEASE`. Those remain live Risk Core + a dedicated ADR.

## This layer may only propose

`lumina_research` may generate hypotheses, reports, and Validation Gate evidence. It **must never**:

- modify or bypass the live Risk Core (`lumina_core/risk/`)
- place, size, or cancel orders
- mutate live DNA, config, or NinjaTrader/Execution Fabric state
- promote a candidate without `PromotionGate`

Promotion of a survivor is a KEEP-fabric decision (`PromotionGate` + live Risk Core + human/Twin approval). Research stops at the proposal.

## Linked KEEP surfaces (do not duplicate)

| Surface | Link |
|---------|------|
| Constitution | [`project-dna/lumina/constitution.md`](../project-dna/lumina/constitution.md) |
| Live Risk Core | [`lumina_core/risk/`](../lumina_core/risk/) (especially `risk_controller.py`) |
| Execution Fabric (gRPC) | [`docs/adr/0035-execution-fabric-grpc.md`](../docs/adr/0035-execution-fabric-grpc.md) · [`integrations/ninjatrader8/Lumina.Execution.Fabric/`](../integrations/ninjatrader8/Lumina.Execution.Fabric/) |
| Event Bus | [`lumina_core/agent_orchestration/event_bus.py`](../lumina_core/agent_orchestration/event_bus.py) |
| PromotionGate | [`lumina_core/evolution/promotion_gate.py`](../lumina_core/evolution/promotion_gate.py) |

Archived Birth-v1 experiments: [`archive/birth-v1/`](../archive/birth-v1/). Do not import them into this layer.
