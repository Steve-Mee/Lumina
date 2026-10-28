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
