# Integration plan: `lumina_research` → Lumina program → NinjaTrader 8

**Status:** Plan only. No runtime, execution, or Risk Core code is changed by the document that carries this plan.  
**Baseline:** `main` @ `c653cab` (merge of PR #61, Phase 4 continuity). Phases 1–4 of `lumina_research` are on `main` (PRs #58, #59, #60, #61; charter/archive cutover #57).  
**Mode of this work:** ANALYSIS + PLAN. Shadow first. No orders. No merge of execution changes.

Binding decisions (plan authors, approved by Steve), restated as implementation law:

1. **No rewrite.** `lumina_research` stays a separate propose-only layer. Integration is Event Bus + hexagonal ports.
2. **Keep** the NT8 AddOn bridge / Execution Fabric (gRPC), the independent fail-closed live Risk Core, data ingest if point-in-time correct, the order lifecycle, typed contracts, Constitution, and safety layers. **Isolate** old birth/evolution/fitness that bypasses the new gates or mixes research into the execution path.
3. **Messages:** `SignalIntent` / `OrderIntent` (`strategy_id`, `direction`, `size`, `timestamp`, `expected_horizon`) and `FillEvent` (`fill_price`, `qty`, `slippage`, `commission`). Fills feed the decay monitor and cost calibration from **one** source of truth.
4. **SIM safety:** live Risk Core rejects any account not on an **explicit SIM whitelist**. Live needs a manual, logged `LIVE_RELEASE` plus an ADR, outside research agents. That config is not agent-mutable. Tests must prove there is no bypass.
5. **Order of work:** shadow first (signals logged, hypothetical fills via `cost_model`, no orders). Real SIM orders only after **2–3 independent survivors** and the empirical monitoring thresholds.
6. **Failure:** fail-closed. Stale data or lost connection → no new orders, server-side cancel / reduce-to-flat, broker as source of truth, reconcile on reconnect. Monitor alarm with an open position → de-weight/reduce; full close only on a hard Risk Core limit. Log and alert everything.
7. **Ticks:** ES/NQ and MES/MNQ have separate costs, reported in ticks **and** dollars.

This plan names existing files, existing tests, and the exact new files each phase must add. It does not invent a second execution stack.

---

## 0. Target architecture (no rewrite)

Research already publishes sealed `PromotionCandidate` events on the KEEP Event Bus. It must never import `lumina_core.risk`, `lumina_core.evolution.promotion_gate`, or the NT broker. Isolation tests already enforce that (`tests/research/test_phase2_isolation.py`, `test_phase3_isolation.py`, `test_phase4_isolation.py`). Therefore the **adapter lives in KEEP fabric**, facing the bus:

```
lumina_research (propose-only)
  HypothesisAgent → ValidationAgent → PromotionAgent
  research.promotion.candidate  (HMAC, issuer-guarded)
           │
           ▼
KEEP ResearchBridge  (NEW, lumina_core/research_bridge/)
  S0: PromotionCandidate → SignalIntent (log only)
      → hypothetical FillEvent via lumina_research.validation.cost_model
      → observe() on LivePerformanceMonitor
      → NEVER PlaceOrderCommand / place_order()
  S3: SignalIntent → OrderIntent → AdmissionChain → FinalArbitration
      → FabricGrpcClient → ExecutionFabric → NtAccountOrderGateway
      ← OrderEvent → FillEvent (broker SSOT) → monitor + cost calibrator
```

`lumina_core` today does **not** import `lumina_research` (repo-wide grep: zero hits under `lumina_core/` and `integrations/`). The bridge is the first allowed KEEP consumer of research **events**, not of research internals except the already-public `CostModel` / `GateReport.as_promotion_fragments()` for shadow fills and evidence mapping.

NT8 filenames (binding named `LuminaNt8AddOn.cs` and `LuminaFabricHost.cs`): those exact names are **not** in the tree. Product files are:

| Binding name | Actual path |
|--------------|-------------|
| LuminaNt8AddOn.cs | `integrations/ninjatrader8/LuminaNt8AddOn/AddOn.cs` (intentional empty stub; no `AddOnBase` in the bridge DLL) |
| LuminaFabricHost.cs | NinjaScript entry `integrations/ninjatrader8/deploy/AddOns/@LuminaFabricHost.cs` (**gitignored** under `integrations/ninjatrader8/deploy/`). Runtime host: `integrations/ninjatrader8/LuminaNt8AddOn/FabricNtHost.cs` |

KEEP those files. Do not rename as part of integration.

---

## 1. Inventory of the current program

Verdict key: **KEEP** = reuse as-is (do not duplicate). **ADAPT** = keep the module, change a contract or a gate. **ISOLATE** = must not sit on the research→order path.

### 1.1 Execution path (Python Brain → NT8)

| ID | Surface | Path | Verdict | Evidence |
|----|---------|------|---------|----------|
| E1 | Trading-engine façade | `lumina_core/trading_engine/__init__.py` | KEEP | Thin BC; lazy-exports `LuminaEngine`. |
| E2 | Composition root | `lumina_core/engine/lumina_engine.py` | KEEP | Product engine. |
| E3 | Operator/engine place | `lumina_core/engine/operations_service_orders.py` `place_order()` | KEEP (product) / ISOLATE from research | Calls `enforce_pre_trade_gate` then `PolicyEngine.execute_order`. |
| E4 | Policy execute | `lumina_core/engine/policy_engine.py` `execute_order()` | KEEP | AdmissionChain block message: `"AdmissionChain blocked order: {reason}"`. |
| E5 | Supervisor auto-place | `lumina_core/engine/supervisor_tick_exec.py` `run_tick_exec()` | ISOLATE from research | On `BUY`/`SELL` + confluence, `paper` uses `PaperSimulator`; **any other `trade_mode` calls `app.place_order(signal, qty)`**. This is the live dream/confluence path. It does not read `PromotionCandidate`. Research must not be wired into `ctx.signal`. |
| E6 | Order gatekeeper | `lumina_core/order_gatekeeper/gate.py` `enforce_pre_trade_gate()` | KEEP | Canonical pre-trade admission for risk-bearing intents. |
| E7 | Admission steps | `lumina_core/order_gatekeeper/admission_steps.py` | KEEP / ADAPT in S1 | Equity snapshot: stale → `equity_snapshot_stale`. Modes requiring snapshot: `real`, `paper`, `sim_real_guard` (`engine_helpers.MODES_REQUIRING_EQUITY_SNAPSHOT`). **`sim` is not in that set.** |
| E8 | Admission chain | `lumina_core/risk/admission_chain.py` | KEEP | Steps: `session_equity_sync` → `risk_policy` → `final_arbitration` → `constitution` → `audit_write`. REAL bypass forbidden. |
| E9 | NT broker façade | `lumina_core/broker/ninjatrader/broker.py` `NinjaTraderBroker.submit_order` | KEEP | `run_final_arbitration` then Fabric RPC. |
| E10 | gRPC client | `lumina_core/broker/ninjatrader/fabric_client.py`, `fabric_client_ops.py`, `fabric_mapper.py` | KEEP / ADAPT in S2 | `place_order_sync` rejects Fabric SAFE_MODE ∈ {2,3}. Mapper `order_event_to_fill` sets **`commission=0.0`**. |
| E11 | Fill → broker `Fill` | `fabric_mapper.order_event_to_fill` | ADAPT (S2) | No slippage field; commission hardcoded 0. |
| E12 | Trade reconciler `FillEvent` | `lumina_core/engine/trade_reconciler/schemas.py` | ADAPT (message shape) | Fields: `fill_id, symbol, side, quantity, price, commission, event_ts, raw_payload, decision_context_id, prev_hash, prev_event_topic`. **No `slippage`. No `fill_price` name (uses `price`). No `qty` name (uses `quantity`).** |
| E13 | Reconcile audit SSOT | `logs/trade_fill_audit.jsonl` via `finalize_mixin` (`event: "reconciled"`) | KEEP as fill SSOT | Already consumed by `lumina_core/risk/cost_model_calibrator.py` and `lumina_core/monitoring/reality_gap_tracker.py`. Research monitor does **not** read this file. |
| E14 | Hexagonal ports | `lumina_core/ports/execution.py`, `ports/risk.py`, `ports/broker.py` | ADAPT | `ExecutionPort` is RL-decision shaped (`apply_rl_live_decision`). There is **no** research-execution port. S0 adds `ResearchExecutionPort` here, not inside `lumina_research`. |
| E15 | Order “state machine” | No Python class `OrderStateMachine` | KEEP concept | Proto `OrderState` in `fabric.proto` L160–168 (`SUBMITTED`…`REJECTED`). NT map: `NtAccountOrderGateway.MapOrderStateOut`. Do not invent a parallel Python SM. |

End-to-end product path (KEEP):

`LuminaEngine` / `OperationsOrdersMixin.place_order` → `enforce_pre_trade_gate` + `PolicyEngine.execute_order` → `NinjaTraderBroker.submit_order` → `FabricGrpcClient.place_order_sync` (`BrainMessage.place_order`) → `ExecutionFabricService.HandlePlace` → `NtAccountOrderGateway.PlaceOrder` → `Account.CreateOrder` + `Account.Submit` → `OrderEvent` on `TradingStream` → Brain fill/reconcile.

`config.yaml` today: `mode: sim`, `broker.backend: live`, `broker.live_provider: ninjatrader`, `broker.ninjatrader.account_name: Sim101`. `ConfigLoader._resolve_runtime_modes` reads `trade_mode` or `mode`. **The desk is already in a mode that may submit NT orders** from E5, independent of research.

### 1.2 gRPC / Execution Fabric / NT8 AddOn

| ID | Surface | Path | Verdict | Evidence |
|----|---------|------|---------|----------|
| G1 | Proto SSOT | `protos/lumina/execution/v1/fabric.proto` | KEEP | Service `ExecutionFabric`: `TradingStream`, `GetAccountState`, `RequestHistoricalData`, `SetRiskParameters`, `GetRiskParameters`. ADR-0035. |
| G2 | `PlaceOrderCommand` | proto L170–185 | KEEP | `client_order_id, instrument, action, quantity, order_type, price, stop_price, time_in_force, reduce_only, protected, correlation_id, mode_context`. **No `strategy_id`, no `expected_horizon`.** Those stay on Brain `OrderIntent`; correlation_id carries lineage. Additive proto fields only if S3 proves a Fabric-side need. |
| G3 | `OrderEvent` | proto L209–221 | KEEP / ADAPT optional | `filled_qty, avg_fill_price`. **No slippage, no commission.** Commission/slippage are stamped in Brain from the NT fee card + fill vs reference, not invented on the wire. |
| G4 | Generated stubs | `lumina_core/broker/ninjatrader/generated/fabric_pb2.py` | KEEP | Generated; do not hand-edit. |
| G5 | Fabric host | `integrations/ninjatrader8/Lumina.Execution.Fabric/FabricGrpcHost.cs` | KEEP | Memory → `SimOrderGateway`; NT modes outside NT process → fail-closed `NtOrderGateway`. |
| G6 | gRPC service | `.../Grpc/ExecutionFabricService.cs` | KEEP | HandlePlace: auth → FULL_SAFE reject → SAFE reject new places → idempotency → rate limit → `PreTradeRiskEngine.TryAdmitPlace` → gateway. Disconnect: `ApplyDisconnectPolicy` → SAFE + `CancelNonProtected` if watchdog armed. |
| G7 | Product gateway | `integrations/ninjatrader8/LuminaNt8AddOn/NtAccountOrderGateway.cs` | KEEP / ADAPT S1 | REAL + non-Sim name → `real_account_blocked_pending_promotion_adr`. Non-paper → `only_sim_accounts_allowed`. Paper test is **prefix**: `StartsWith("Sim")` / `Playback` / `Backtest` / `DEMO*` in paper modes (`IsSimAccountName`, `AllowsPaperOrders` ~L1168–1195). **Not an explicit whitelist.** |
| G8 | Wrong-host stub | `.../Execution/NtOrderGateway.cs` | KEEP | Rejects if Fabric is not inside NT. |
| G9 | In-memory SIM | `.../Execution/SimOrderGateway.cs` | KEEP for CI / ISOLATE from product NT | Immediate market fills. `GatewayKind=memory`. |
| G10 | Pre-trade (C#) | `.../Safety/PreTradeRiskEngine.cs` | KEEP | Independent of Brain. Size/daily-loss. Not a replacement for Python Risk Core. |
| G11 | Heartbeat | `.../Safety/HeartbeatWatchdog.cs` | KEEP | Armed only after AuthHello **and** one heartbeat. Timeout → cancel non-protected → SAFE; flatten after `FlattenGraceMs` (config default 15000). |
| G12 | Emergency flatten | `.../Safety/EmergencyFlattenPolicy.cs` | KEEP | Deny unless `armed` and `sessionTouchedCount > 0` and book not empty. Session-touched flatten, not “flatten the whole account blindly”. |
| G13 | Safe mode SM | `.../Safety/SafeModeStateMachine.cs` | KEEP | NORMAL → SAFE → FULL_SAFE. |
| G14 | NT host bind | `LuminaNt8AddOn/FabricNtHost.cs` | KEEP | Binds `NtAccountOrderGateway` inside NT. |
| G15 | AddOn stub | `LuminaNt8AddOn/AddOn.cs` | KEEP | Comments: dual-`AddOnBase` deliberately avoided. |
| G16 | Deploy entry | `@LuminaFabricHost.cs` (gitignored deploy tree) | KEEP (ops) | Must remain in the NT `Custom/AddOns` package. Not in git in this checkout. |
| G17 | Legacy WS | `LuminaNt8AddOn/LuminaWebSocketClient.cs` | ISOLATE | `[Obsolete]`; superseded by Fabric gRPC (ADR-0035/0040). |
| G18 | Fabric config | `FabricConfig.cs` | ADAPT S1 | `AccountName` default `"Sim101"`. **No whitelist collection.** Operator file: `%APPDATA%\LUMINA\fabric.json`. |
| G19 | NT capability matrix | `lumina_core/broker/ninjatrader/promotion_gate.py` | ADAPT S0/S3 | `paper`: no MD, no submit. `sim` / `sim_real_guard` / `real`: MD + submit + cancel. **There is no `shadow` mode.** Shadow as “MD yes, submit no” does not exist. |
| G20 | ADR | `docs/adr/0035-execution-fabric-grpc.md`, `0040-fabric-only-foundation-and-sentinel.md` | KEEP | Brain admission **and** Fabric safety are both mandatory. Orders from AddOn without Brain admission rejected. |

### 1.3 Live Risk Core gates

| ID | Surface | Path | Verdict | Evidence |
|----|---------|------|---------|----------|
| R1 | Live Risk Core | `lumina_core/risk/` | KEEP | Charter: untouchable. Research isolation tests ban importing it. |
| R2 | `HardRiskController` / gates | `risk_controller.py`, `risk_gates.py` | KEEP / ADAPT S3 | `check_can_trade`: **if `limits.sim_mode or not enforce_rules: return True, "OK (SIM learning mode – all caps bypassed)"**. SIM learning currently bypasses daily-loss / kill-switch / session caps inside this mixin. |
| R3 | Orchestrator enforce flag | `lumina_core/risk/orchestration.py` | ADAPT S1/S3 | `enforce_rules = trade_mode == "real"` only. `sim_real_guard` has `ModeCapabilities.risk_enforced=True` (`mode_capabilities.py`) but may not get controller-level hard enforce. |
| R4 | Modes | `lumina_core/engine/mode_capabilities.py` | ADAPT S0 | Modes: `paper`, `sim`, `sim_real_guard`, `real`. **No `shadow`.** `sim.risk_enforced=False`. `sim.capital_at_risk=False`. `sim.requires_live_broker=True`. |
| R5 | Final arbitration | `lumina_core/risk/final_arbitration.py` | KEEP | Consumes `OrderIntent` (`risk/schemas.py`). |
| R6 | Live `OrderIntent` | `lumina_core/risk/schemas.py` | ADAPT (fields) | `instrument, side (BUY/SELL), quantity, order_type, stop, target, reference_price, proposed_risk, regime, confluence_score, confidence, source_agent, disable_risk_controller, metadata.reason`. **`extra=forbid`.** Missing binding fields: `strategy_id`, `expected_horizon`, `timestamp`. |
| R7 | `propose_order` on live core | — | N/A | **Does not exist.** Live path is Admission + `check_can_trade` + FinalArbitration. Research `propose_order` is a different type in `lumina_research/risk_core/engine.py`. |
| R8 | REAL multi-gate | `lumina_core/risk/real_multi_gate.py` | KEEP | Human `approve-real` milestone. Not named `LIVE_RELEASE`. |
| R9 | Shadow aperture | `lumina_core/risk/shadow.py`, `shadow_human_approval.py` | KEEP | DNA/risk-shadow (ADR-0002). **Not** the research SHADOW execution mode of this plan. Do not overload the name in code: use `research_execution_mode=shadow`. |
| R10 | Aperture tripwire | `lumina_core/risk/aperture_guard.py` | KEEP | Constitution invariant #7: no structural bypass in `real` / `sim_real_guard`. |
| R11 | Live cost model | `lumina_core/risk/cost_model.py` `TradeExecutionCostModel` | KEEP | Fees from `lumina_core/market/nt_fees.py` (ADR-0055). Slippage is a paper/risk simulator; ADR-0055: do not add a cash tick on top of a fill price. |
| R12 | Cost calibrator | `lumina_core/risk/cost_model_calibrator.py` | ADAPT S2 | Reads `event=="reconciled"` from `logs/trade_fill_audit.jsonl`. Uses `slippage_points` + `commission` on that row. Not wired to research `observe()`. |
| R13 | NT fee card | `lumina_core/market/nt_fees.py` | KEEP | Free-plan all-in per side: ES/NQ `$2.87` (1.39+0.19+1.29), MES/MNQ `$0.94` (0.36+0.19+0.39). Separate roots. No MES fallback for unknown root. |
| R14 | Research Risk Core | `lumina_research/risk_core/` | ISOLATE (from live writes) | Additional filter. `RiskConfig` frozen (`config.py`). `propose_order` → Approved/Rejected/Scaled. Stdlib-only (AST). Survivors still face live Risk Core. |
| R15 | `LIVE_RELEASE` | — | **ABSENT** | Repo-wide search: zero matches. Closest: `real_account_blocked_pending_promotion_adr` (Python guards + C# gateway) and `evaluate_real_capital_readiness`. |

### 1.4 Account handling — does a SIM whitelist exist?

**No.** There is no `sim_whitelist`, `SIM_WHITELIST`, or `allowed_sim_accounts` anywhere in the repo.

What exists instead (KEEP as building blocks, ADAPT into an explicit list):

| ID | Surface | Path | Verdict | Evidence |
|----|---------|------|---------|----------|
| A1 | Name classifiers | `lumina_core/broker/ninjatrader/account_names.py` | KEEP helpers / ADAPT policy | `is_local_sim_name`: starts with `sim` or contains `sim101`/`playback`/`backtest`. `is_broker_demo_name`: starts with `demo`. Docstring: “The demo name is the only account the addon may bind. The real name is stored beside it and is never the bind name. REAL orders stay closed.” |
| A2 | Match guards | `lumina_core/broker/ninjatrader/guards.py` `check_account_match` | ADAPT | `sim`: connected must match configured **and** `paper_account_allowed`. A name like `LiveAcct` fails `sim_account_not_sim_named`. `real` + DEMO → `real_account_blocked_pending_promotion_adr`. Tests: `tests/broker/test_ninjatrader_guards.py`. |
| A3 | C# paper gate | `NtAccountOrderGateway.AllowsPaperOrders` | ADAPT | Prefix heuristic, not a list. **No C# test** references `only_sim_accounts_allowed` (grep under `integrations/ninjatrader8` tests: none). |
| A4 | Config account | `config.yaml` `broker.ninjatrader.account_name: Sim101` | ADAPT | Single string, not a whitelist. |
| A5 | Launcher persist | `lumina_launcher/services/nt_account_store.py` | KEEP operator path | Writes `config.yaml` + `fabric.json` `AccountName` / `RealAccountName`. |
| A6 | Pair validation | `validate_account_pair` | KEEP | Demo must be paper-shaped; real must not be paper-shaped; names must differ. |
| A7 | Agent mutability of account config | `lumina_core/code_evolution/operators.py` `FORBIDDEN_PARAMETER_KEYS` | ADAPT | Forbids risk **numeric** keys (`daily_loss_cap`, …). **Does not forbid** `account_name`, whitelist, `mode`, or a future `live_release`. `FORBIDDEN_TARGET_PREFIXES` in `code_evolution/proposal.py` covers `lumina_core/risk/`, broker, constitution, gatekeeper, `promotion_gate` — not `config.yaml` keys. Hot reload: `lumina_core/runtime_config_reloader.py` reloads `mode` / `trade_mode`. |

`sim_real_guard` additionally requires env `ENABLE_SIM_REAL_GUARD=true` (`guards._sim_real_guard_enabled`). Disabled → `sim_real_guard_disabled`.

### 1.5 Data ingest and point-in-time correctness

| ID | Surface | Path | Verdict | Evidence |
|----|---------|------|---------|----------|
| D1 | NT 1m Last SSOT | ADR-0053, `lumina_core/engine/nt_bar_ssot.py` | KEEP | Decision OHLC = NT 1-minute Last bars. Tape never writes `ohlc_1min`. Fail-closed on missing/zero high/low. |
| D2 | Closed vs forming | `lumina_core/engine/market_data_manager.py` `partition_closed_and_forming` | KEEP | “A timestamp still in the future is forming and must not enter the closed book (ADR-0053 / ADR-0054).” |
| D3 | HTF bars | ADR-0054 | KEEP | Native NT 5/15/30/60/240; no silent TradingHours fallback. |
| D4 | History fetch | `lumina_core/engine/market_data_history_fetch.py` | KEEP / ISOLATE CrossTrade | NT Fabric `RequestHistoricalData` when `live_provider=ninjatrader`. CrossTrade = “legacy emergency only”. |
| D5 | Fabric MD providers | `LuminaNt8AddOn/NtHistoricalDataProvider.cs`, `NtLiveBarProvider.cs`, `NtLiveMarketDataProvider.cs` | KEEP | Product ingest. |
| D6 | Research tapes | `lumina_research/agents/synthetic.py` `materialize()` | ISOLATE from live ingest | Deterministic gauss / planted_edge. **No network. Not NT bars.** Phase 2/3/4 tests run on this tape. There is **no** research walk-forward on NT PIT bars yet. |
| D7 | Research purge/embargo | `lumina_research/validation/purge.py`, `cpcv.py` | KEEP (research) | Validation Gate refuses missing purge/embargo. |

**PIT verdict for live ingest:** KEEP. Forming-bar split and NT Last SSOT are the correct live book. **PIT verdict for research candidates today:** they are **not** validated on that book; they are validated on synthetic series. Connecting survivors to NT without a PIT research tape is a gap (G-PIT below), not a reason to replace D1–D5.

### 1.6 Event Bus

| ID | Surface | Path | Verdict | Evidence |
|----|---------|------|---------|----------|
| B1 | Bus | `lumina_core/agent_orchestration/event_bus.py` | KEEP | In-process pub/sub. HMAC topic guards for research topics. |
| B2 | Research contracts | `schemas_research.py`, `schemas_research_continuity.py` | KEEP / ADAPT additive | Topics: `research.hypothesis.proposed`, `.validation.result`, `.promotion.candidate`, `.mutation.proposed`, `.governance.decision`, plus continuity (decay/deweight/suspend/retire/capacity/guardian/replenish). Registered in `EVENT_BUS_TOPIC_MODELS`. |
| B3 | `PromotionCandidate` | `schemas_research.py` L253–271 | KEEP | `hypothesis_id, config_id, trial_id, instrument, decision_kind, quantity, notional, validation_mac, issue_mac`. Docstring: “Proposal only. Never writes the live PromotionGate.” **No `strategy_id`, no `expected_horizon`, no `direction` (side is not on the candidate).** |
| B4 | KEEP trade signal | `schemas_trading.py` `TradeIntent` | ISOLATE from research | `signal, confidence, stop, target, …` — dream/confluence shaped. Topic `trading_engine.trade_signal.emitted`. **Not** the binding `SignalIntent`. |
| B5 | KEEP fill on bus | `ExecutionFill` topic `execution.fill.received` | ADAPT S2 | `fill_id, symbol, side, quantity, price, timestamp, commission`. **No slippage.** Lineage fields present. |
| B6 | `SignalIntent` | — | **ABSENT** | Repo-wide: zero matches except this plan. |
| B7 | Architecture doc | `docs/architecture.md` | ADAPT | Bounded contexts listed; **`lumina_research` and `research.*` topics are not in §3 / Event Bus inventory** (grep: no hits). |
| B8 | Isolation | `lumina_core` ↛ `lumina_research` | KEEP | Bridge is the first KEEP import of research **public** types. |

### 1.7 Old birth / evolution / fitness (bypass risk)

| ID | Surface | Path | Verdict | Evidence |
|----|---------|------|---------|----------|
| O1 | Archived Birth-v1 | `archive/birth-v1/` | ISOLATE | Charter: do not import. `tests/test_birth_v1_archived.py` AST-scans live trees. `pytest.ini` `norecursedirs = archive`. |
| O2 | Nightly orchestrator stub | `lumina_core/evolution/orchestrator.py` | KEEP tripwire | `GenerationResult.reason = "BIRTH_V1_ARCHIVED"`. |
| O3 | DNA promote stub | `lumina_core/engine/proposal_emit.py` `promote_winning_dna` | KEEP tripwire | Raises `LuminaError` `VALIDATION_GATE_REQUIRED`. |
| O4 | Meta apply | `lumina_core/engine/meta_agent_core.py` | KEEP tripwire | `_apply_candidate` → `VALIDATION_GATE_REQUIRED` / `BIRTH_V1_ARCHIVED`. |
| O5 | Genetic builders | `lumina_core/engine/proposal_builders.py` `build_genetic_candidates` | KEEP stub / WATCH | Returns `[], {}`. `build_challengers` still emits hyperparam challengers (A/B/C). **ISOLATE from research→order.** |
| O6 | Live `PromotionGate` | `lumina_core/evolution/promotion_gate.py` | KEEP / ADAPT | Hard REAL gate (ADR-0007). Re-implements OOS checks on an **evidence dict**. Defaults: `max_pbo=0.40`, **`min_dsr=0.0`**, windows ≥ 5. Research gate: DSR ≥ 0.95, PBO hard > 0.50, **min 6 windows** (`gate_thresholds.toml`). **Does not call `passes_validation_gate`. Does not require HMAC `GateReport`.** `GateReport.as_promotion_fragments()` exists and is unused by this class. |
| O7 | Promotion evidence mixin | `lumina_core/evolution/promotion_evidence.py` | ADAPT | Builds evidence from nightly report keys (`live_slippage`, …). Fabricate-able if callers skip research. |
| O8 | Twin / shadow DNA | `approval_twin_*`, `shadow_deployment.py` | KEEP | SIM judgment only; must not bypass REAL PromotionGate (ADR-0031/0032). |
| O9 | Code evolution | `lumina_core/code_evolution/` | KEEP sandbox | Evaluate-only; forbidden prefixes on risk/broker/constitution. |
| O10 | Research evolution | `lumina_research/evolution/` | KEEP propose-only | `ReflectorAgent.apply` raises `ReflectorRefused`. Governance records protected writes, does not apply (ADR-0057). |
| O11 | Fitness (research) | `lumina_research/fitness.py` | KEEP | Composite OOS after costs; refuses IS PnL. |
| O12 | Fitness (live leftover) | `lumina_core/evolution/genetic_operators.py` `calculate_fitness` | ISOLATE | Live helper; mutate/crossover no-ops. Not the charter fitness. |
| O13 | Maturity ledger | `lumina_core/maturity/` | ISOLATE | Birth-era milestones still importable; runners archived. |
| O14 | Playground/birth ADRs 0012–0027, 0045–0056 | `docs/adr/` | ISOLATE as implementation source | Describe archived curricula. Do not re-implement from archive. |

**Bypass residual (highest):** live DNA promotion can still `PromotionGate.evaluate` on a report dict **without** a sealed research `ValidationResult`. Research cannot place orders. The **existing supervisor path (E5) can place SIM orders without any research gate** because `config.yaml` `mode: sim`.

### 1.8 `lumina_research` Phases 1–4 (merged)

| ID | Surface | Path | Verdict | Evidence |
|----|---------|------|---------|----------|
| P1 | Validation Gate | `lumina_research/validation/gate.py` `passes_validation_gate` | KEEP | Doubt = reject. Floors in `gate_thresholds.toml`. |
| P2 | Cost model | `validation/cost_model.py` | KEEP (shadow fills) | Four legs; `ticks_for_fill` returns ticks **and** `total_usd`. Tests: `tests/research/test_cost_model.py` (ES tick_value 12.50 vs MES 1.25; MES commission_ticks > ES; both 0.25 tick). |
| P3 | Contracts | `validation/contracts.py` | KEEP | ES/NQ/MES/MNQ. Commission ticks = Free-plan USD / tick_value (`2.87/12.50` ES, `0.94/1.25` MES) — same dollars as ADR-0055, different unit. Half-spread 0.5 ticks on all four. |
| P4 | Agents | `agents/hypothesis.py`, `validation_agent.py`, `promotion.py`, `loop.py` | KEEP | Bus-wired. Promotion requires sealed PASS + research Risk Core. |
| P5 | Evolution | `evolution/` | KEEP | Propose-only. ADR-0057. |
| P6 | Monitoring | `monitoring/monitor.py` `observe(signal_id, metric)` | ADAPT input | Scalar `float` vs sealed OOS. Stages `active → deweighted → suspended → retired`. Weights only fall. **No `FillEvent`.** ADR-0058. |
| P7 | Registry | `monitoring/registry.py` | KEEP | Admit only sealed `PromotionCandidate` + `ValidationResult`. Direct insert refused (`test_phase4_bypass.py`). |
| P8 | Sizing | `monitoring/sizing.py` | KEEP | Calls research `propose_order()` only; cannot increase exposure. |
| P9 | Acceptance floors | `monitoring/acceptance.py` | KEEP (S3 gate) | FAR healthy ≤ 5%, high-vol ≤ 10%, detection ≥ 85%, TTD ≤ 15 trading days, `CONFIRM_WINDOWS=2`. Measured on **synthetic** campaigns, not broker fills. |
| P10 | Research `OrderProposal` | `risk_core/types.py` | ISOLATE from live `OrderIntent` | `side` is `"buy"|"sell"` (lower-case); live `OrderIntent.side` is `"BUY"|"SELL"`. No `expected_horizon`. |

### 1.9 Safety / Constitution / fail-closed already present

| ID | Surface | Path | Verdict | Evidence |
|----|---------|------|---------|----------|
| S1 | Constitution | `project-dna/lumina/constitution.md` | KEEP | Kapitaalbehoud; SIM vs REAL absolute; no structural bypass. |
| S2 | Machine principles | `lumina_core/safety/trading_constitution.py`, `constitution_principles.py` | KEEP | Forbids `disable_risk_controller`, gatekeeper bypass. |
| S3 | Fabric disconnect | `ExecutionFabricService.ApplyDisconnectPolicy` | KEEP | Lost Brain → SAFE + cancel non-protected (if armed). |
| S4 | Stale equity | admission `equity_snapshot_stale` | KEEP for REAL/`sim_real_guard` | Not applied in `sim` (gap vs binding “stale data → no new orders” if S3 uses `sim`). |
| S5 | Stale/bad bars | `nt_bar_ssot.validate_nt_bar` | KEEP | Fail-closed `BarRejected`. |
| S6 | Broker SSOT | `GetAccountState` / NT `Account.Positions` | KEEP | Reconcile on auth `StateSync`. |
| S7 | Monitor vs flatten | ADR-0058 + EmergencyFlattenPolicy | ADAPT (policy glue) | Research monitor **cannot** send reduce-only (isolation). Binding: alarm + open position → de-weight/reduce; full close **only** on hard Risk Core limit. That reduce must be a KEEP consumer of `research.signal.deweighted`, not the monitor placing. |

### 1.10 Message-field gap (binding vs code)

| Binding field | Exists? | Where / what exists |
|---------------|---------|---------------------|
| `SignalIntent` | No | — |
| `strategy_id` | No on intents | Research uses `hypothesis_id` / `config_id`. Regime code explicitly: “There is no strategy_id.” (`evolution/regime.py`) |
| `direction` | Partial | `OrderIntent.side`, proto `OrderAction`, research `OrderProposal.side` |
| `size` | Partial | `quantity` / proto `quantity` |
| `timestamp` | Partial | fills have `event_ts` / proto `timestamp_unix_ms`; `OrderIntent` has none |
| `expected_horizon` | No | — |
| `FillEvent.fill_price` | Name differs | `price` / `avg_fill_price` |
| `FillEvent.qty` | Name differs | `quantity` / `filled_qty` |
| `FillEvent.slippage` | No | Calibrator reads `slippage_points` off audit JSON, not the dataclass |
| `FillEvent.commission` | Yes | Often **0.0** from Fabric mapper |

---

## 2. Gap list against the binding decisions

Numbered. Each gap is a missing behavior or a contradicting behavior, with evidence. This is the work S0–S3 close.

| ID | Binding | Current fact | Severity | Closes in |
|----|---------|--------------|----------|-----------|
| G-MSG | `SignalIntent` / `OrderIntent` / `FillEvent` with named fields | `SignalIntent` absent. `OrderIntent` and `FillEvent` exist with different fields (`extra=forbid`, so adding required fields is a breaking schema change unless optional-with-default). `TradeIntent` / `ExecutionFill` / `OrderProposal` / `PromotionCandidate` are four other shapes. | Blocker for a typed bridge | S0 (add `SignalIntent` + aliases; do not fork a fifth fill type) |
| G-ADAPT | Research survivors enter the program via Event Bus | `lumina_core` does not import `lumina_research`. No subscriber of `research.promotion.candidate` outside research agents. `PromotionCandidate` never becomes a signal, order, or log line in KEEP. | Blocker | S0 |
| G-SHDW | Shadow = log signals, hypothetical fills, **no orders** | No `research_execution_mode`. `mode: sim` already allows NT submit (E5 + G19). Paper mode blocks **market data** too, so it cannot be “shadow with NT PIT bars”. | Blocker | S0 (new flag, not a rewrite of trade_mode) |
| G-WL | Explicit SIM whitelist; unknown account rejected | Prefix heuristic (`Sim*`, `DEMO*`, Playback, Backtest). Any `SimFoo` matches. Empty configured name in `sim` still returns ok if connected is non-empty (`guards.py` only mismatches when `configured` is truthy). | Safety | S1 |
| G-LIVE | Manual logged `LIVE_RELEASE` + ADR, outside agents | Flag absent. REAL is blocked by `real_account_blocked_pending_promotion_adr` + multi-gate, but there is no single logged release object, no ADR hash on the order path, and no test named for `LIVE_RELEASE`. | Safety | S1 |
| G-MUT | Config not agent-mutable; tests prove no bypass | `FORBIDDEN_PARAMETER_KEYS` does not include account/whitelist/`live_release`/`mode`. Hot reload can change `trade_mode`. Research governance cannot write Risk Core files, but that is a different config surface. | Safety | S1 |
| G-FILL | Fills → decay monitor **and** cost calibration from one SSOT | Monitor: `observe(signal_id, float)`. Calibrator: `trade_fill_audit.jsonl` `reconciled`. Fabric fill `commission=0.0`. `FillEvent` has no slippage. Two pipelines, neither is research-aware. | Blocker for honest decay | S2 |
| G-COST | One cost story; ticks and $; ES/NQ ≠ MES/MNQ | Research `CostModel` adds half-spread + slippage + √impact **as cash** on hypothetical/backtest returns. ADR-0055: slippage lives in the fill price; the card is cash commission only. Dollars on the card **match** research Free-plan commissions ($2.87 mini, $0.94 micro). The **slippage accounting disagrees**. Live `TradeExecutionCostModel` is a third object. | Truth-seeking | S2 (pick SSOT; see Q3) |
| G-SIMBYP | Independent fail-closed Risk Core on SIM orders | `risk_gates.check_can_trade` returns OK and **bypasses all caps** when `sim_mode or not enforce_rules`. Orchestrator sets `enforce_rules` only for `real`. S3 on `trade_mode=sim` would place NT orders with Brain risk caps off. Fabric `PreTradeRiskEngine` is the remaining size cap (`config.yaml` `max_position_size: 2`). | Safety | S1 policy + S3 mode = `sim_real_guard` with `enforce_rules` aligned to `risk_enforced` |
| G-PGATE | Live `PromotionGate` is the only live promotion path; research must pass Validation Gate first | Live gate does not require sealed `GateReport` / TrialRegistry. Defaults weaker on DSR (0.0 vs 0.95) and window count (5 vs 6). `as_promotion_fragments()` unused. | Skip-gate residual | S3 (AND with sealed research report); optional tighten in S0 if shadow admission should already require it |
| G-PIT | Research on point-in-time NT data | Research `materialize()` is synthetic. No NT-bar candidate pipeline. Live ingest **is** PIT-correct. | Honesty of “survivors” | S0 data note; S3 entry criterion (Q2) |
| G-ENG | Isolate old paths that mix research into execution or skip gates | E5 still auto-places on confluence. `build_challengers` still emits. Live PromotionGate evidence dict still open. Archive is isolated. Research itself is isolated. | Mix / skip | S0 isolate research from E5; S3 must not call `place_order` from supervisor |
| G-RED | Monitor alarm + open position → de-weight/reduce; flatten only on hard Risk Core limit | Monitor can publish `research.signal.deweighted` (weight falls, research `propose_order` sizes down). Nothing in KEEP turns that into a **reduce-only** Fabric order. Fabric flatten is watchdog/emergency, not decay. | Binding miss | S3 (KEEP consumer); S0 logs the intent only |
| G-CS | C# account tests | Python `test_ninjatrader_guards.py` covers prefix/mismatch. **Zero** Fabric.Tests for `only_sim_accounts_allowed`. | Bypass in AddOn | S1 |
| G-DOC | Architecture lists research | `docs/architecture.md` omits `lumina_research` / `research.*`. | Observability | S0 (docs in the implementation PRs; this plan is the spec) |
| G-HORIZ | `expected_horizon` | Nowhere in contracts. Needed for decay window alignment vs ADR-0058 rolling 20-day default. | Contract | S0 schema |
| G-SURV | 2–3 independent survivors before SIM orders | None on NT tape. Phase 2 loop produces sealed candidates from **planted_edge vs noise** synthetic series. Phase 4 floors are synthetic-campaign numbers. | Process | S3 gate (definition in §3.4) |

Gaps this plan **does not** treat as missing (already KEEP):

- gRPC Fabric + NT bind + watchdog + session-touched flatten.
- AdmissionChain + FinalArbitration + constitution on the product order path.
- Research propose-only + HMAC bus + isolation AST tests.
- NT 1m Last PIT for **live** bars.
- Separate ES/NQ vs MES/MNQ **research** contract specs and tests.

---

## 3. Phased implementation

Global rules for every phase:

- Research agents still cannot import live Risk Core / PromotionGate / broker. Isolation tests stay red-fail if they do.
- No proto rewrite. Additive fields only, and only if a phase’s acceptance requires them.
- `archive/birth-v1/` stays untouched.
- Each phase is its own PR (or two, if C# + Python). Rollback is a flag first, git revert second.
- Constitution: fail-closed; doubt = no new order.

### 3.0 Shared contracts (introduced in S0, frozen after)

Add **additive** Event Bus schemas in KEEP (new file, not a rewrite of `TradeIntent`):

`lumina_core/agent_orchestration/schemas_research_execution.py`

```
topic research.execution.signal_intent   producer research_bridge
topic research.execution.order_intent    producer research_bridge   # S0: logged, not admitted
topic research.execution.fill            producer research_bridge | fill_translator
```

Pydantic (`extra=forbid`, frozen):

**`SignalIntent`**

| Field | Type | Notes |
|-------|------|-------|
| `schema_version` | literal `research.execution.signal_intent.v1` | |
| `strategy_id` | str | `= hypothesis_id` of the sealed candidate (binding name) |
| `config_id` | str | research config |
| `trial_id` | int ≥ 1 | TrialRegistry |
| `instrument` | `ES\|NQ\|MES\|MNQ` | |
| `direction` | `BUY\|SELL` | mapped from research side |
| `size` | float > 0 | research-approved quantity (already Risk-Core-scaled) |
| `timestamp` | datetime UTC | intent time |
| `expected_horizon` | timedelta or int bars | required; refuse if missing |
| `validation_mac` | str 64 | copy from candidate |
| `issue_mac` | str 64 | copy from candidate |
| `source` | literal `research_bridge` | |

**`OrderIntent` (live schema ADAPT)** — add optional fields with defaults so existing constructors keep working:

- `strategy_id: str = ""`
- `expected_horizon_bars: int = 0`
- `submitted_at_utc: datetime | None = None`

Binding `timestamp` = `submitted_at_utc`. Binding `direction` = existing `side`. Binding `size` = existing `quantity`. S3 refuses research-originated intents with empty `strategy_id` or `expected_horizon_bars < 1`.

**`FillEvent` (reconciler dataclass ADAPT)** — add:

- `slippage_ticks: float = 0.0`
- `slippage_usd: float = 0.0`
- `commission_ticks: float = 0.0`
- `source: literal["broker","hypothetical_cost_model"] = "broker"`
- property `fill_price` → `price`, `qty` → `quantity` (binding names without renaming the SSOT fields)

Do **not** create a third fill type. Map `ExecutionFill` ↔ `FillEvent` 1:1 in the translator.

Issuer guard: only `research_bridge` (and in S2 `fill_translator`) may publish `research.execution.*`. Existing research agents must fail if they try (attack test).

---

### 3.1 S0 — Shadow wiring

**Goal.** Sealed `PromotionCandidate`s become logged `SignalIntent`s. Hypothetical fills are produced by `CostModel.ticks_for_fill` / `apply_costs`, reported in ticks and $, per root. **Zero** `PlaceOrderCommand`. **Zero** `place_order()`. Monitor `observe()` is fed from those hypothetical net returns so decay plumbing is real before SIM.

**Does not** turn off the existing dream/confluence SIM path (E5). It **must not** read research events. See Q1.

#### Files

| Action | Path |
|--------|------|
| NEW | `lumina_core/research_bridge/__init__.py` |
| NEW | `lumina_core/research_bridge/port.py` — `ResearchExecutionPort` (Protocol: `on_candidate`, `shadow_fill`, `assert_no_broker_submit`) |
| NEW | `lumina_core/research_bridge/shadow_runtime.py` — subscribe `RESEARCH_PROMOTION_TOPIC`; verify MAC via existing `ProvenanceAuthority` pattern used by monitoring; emit `SignalIntent`; call cost model; emit `FillEvent(source=hypothetical_cost_model)`; call `LivePerformanceMonitor.observe`; append JSONL |
| NEW | `lumina_core/research_bridge/horizon.py` — require `expected_horizon`; default mapping from candidate genome `oos_size` only if Steve answers Q6; otherwise refuse until field present on candidate (ADAPT `PromotionCandidate` with optional `expected_horizon_bars` default 0 = refuse) |
| NEW | `lumina_core/research_bridge/jsonl.py` — `state/research_shadow.jsonl` (UTC, strategy_id, intent, breakdown ticks+$ ) |
| NEW | `lumina_core/agent_orchestration/schemas_research_execution.py` |
| NEW | `lumina_core/ports/research_execution.py` — re-export Protocol (hexagonal; keep `ports/execution.py` unchanged) |
| ADAPT | `lumina_core/agent_orchestration/schemas.py` — register three topics in `EVENT_BUS_TOPIC_MODELS` **and** `CRITICAL_EVENT_BUS_TOPICS` |
| ADAPT | `schemas_research.py` — optional `expected_horizon_bars` on `PromotionCandidate` (default 0) |
| ADAPT | `lumina_core/risk/schemas.py` — optional OrderIntent fields listed above |
| ADAPT | `lumina_core/engine/trade_reconciler/schemas.py` — FillEvent slippage/source/aliases |
| ADAPT | `lumina_core/broker/ninjatrader/promotion_gate.py` — **do not** add submit for a fake `shadow` trade_mode in S0. Shadow is `research_execution_mode`, a separate config key. |
| NEW | `config.yaml` key `research_execution_mode: shadow` (legal values `off\|shadow\|sim`; default `shadow` in code if missing = **off** fail-closed until operator sets it) |
| NEW | `docs/adr/0059-research-bridge-shadow-first.md` — records this plan’s binding in ADR form (Steve signs) |
| ADAPT | `docs/architecture.md` — add Research context + `research.*` + bridge |
| NEW tests | see below |
| FORBIDDEN | any edit to `lumina_core/risk/risk_controller.py`, `admission_chain.py` behavior, Fabric HandlePlace, `NtAccountOrderGateway.PlaceOrder` |

`shadow_runtime` may import `lumina_research.validation.cost_model` and `lumina_research.agents.provenance` (public). It must not import `lumina_research.risk_core` for sizing (candidate already carries scaled quantity). It must not import `lumina_core.broker`.

Hypothetical fill recipe (evidence-based, uses existing API):

1. `spec = spec_for(instrument)` (`validation/contracts.py`).
2. `CostModel().ticks_for_fill(spec=spec, quantity=size, market=MarketSnapshot(...))` using the last **closed** NT bar’s volume/ATR when MD is up; if MD stale/missing → **no hypothetical fill**, log `shadow_fill_refused:stale_or_missing_market`, do not `observe()` (fail-closed, matches binding “stale data”).
3. Record `commission_ticks`, `half_spread_ticks`, `slippage_ticks`, `impact_ticks`, `total_ticks`, `total_usd` on the FillEvent + JSONL.
4. Net return for `observe()`: `-total_usd / equity` on the fill bar (shadow has no edge until a signal model is bound). Do not invent a mid-price edge. If a research signal function does not exist yet (today `materialize()` is the only tape), S0 observe-feed is **cost-only** plus an explicit `shadow_mark="cost_only"` so we do not pretend PnL is alpha.

S0 does **not** require a new strategy engine. If there is no live signal function, shadow still proves: candidate → intent log → cost ticks/$ → monitor input → no orders.

#### Tests (S0)

| Test file | What it proves |
|-----------|----------------|
| `tests/research_bridge/test_shadow_never_places.py` | With a sealed candidate, monkeypatch `FabricGrpcClient.place_order_sync`, `NinjaTraderBroker.submit_order`, `OperationsOrdersMixin.place_order`, `NtAccountOrderGateway` (if imported): **none called**. AST/import: `research_bridge` does not import `lumina_core.broker.ninjatrader.broker`. |
| `tests/research_bridge/test_signal_intent_fields.py` | Published payload has `strategy_id, direction, size, timestamp, expected_horizon`. Missing horizon → refuse, no JSONL fill. |
| `tests/research_bridge/test_hypothetical_costs_per_root.py` | Same size/market: ES vs MES vs NQ vs MNQ produce **different** `total_usd` and **different** `commission_ticks`; all report both ticks and USD; tick_size 0.25. Reuse numbers from `test_cost_model.py`. |
| `tests/research_bridge/test_stale_market_no_fill.py` | Forming-only book or empty OHLC → no FillEvent, no observe, intent still logged with `fill=refused`. |
| `tests/research_bridge/test_unsigned_candidate_refused.py` | Forged `PromotionCandidate` (same cases as `test_phase2_bypass.py` / `test_phase4_bypass.py`) does not log a SignalIntent. |
| `tests/research_bridge/test_issuer_guard.py` | `hypothesis_agent` cannot publish `research.execution.signal_intent`. |
| `tests/research_bridge/test_supervisor_unaffected.py` | `run_tick_exec` with a research candidate on the bus does not change `ctx.signal`. Research does not leak into E5. |
| `tests/agent_orchestration/test_research_execution_topics_additive.py` | Existing `research.*` and KEEP topics unchanged (copy pattern from `test_research_topics_additive.py`). |
| ADAPT `tests/research/test_phase2_isolation.py` | `lumina_research.agents` still must not import broker / live risk. Bridge is KEEP, not under `lumina_research/`. |

#### Acceptance (S0)

1. Operator can run the Phase 2 loop (synthetic) **or** replay a sealed JSONL candidate through the bridge.
2. `state/research_shadow.jsonl` contains one SignalIntent per admitted candidate and, iff closed NT (or fixture) market exists, one hypothetical FillEvent with four-leg ticks + USD per root.
3. `LivePerformanceMonitor.series(strategy_id)` grows only from bridge observe, never from supervisor fills.
4. No Fabric `place_order` in logs; Fabric tests unchanged and green.
5. `research_execution_mode=off` → bridge does not subscribe (fail-closed default if key missing).
6. ADR-0059 merged or attached.

#### Rollback (S0)

Set `research_execution_mode: off` (or delete the key: code treats missing as off). Delete `state/research_shadow.jsonl` if desired. No positions exist. Git revert of the S0 PR removes the bridge; research Phases 1–4 remain.

---

### 3.2 S1 — SIM whitelist and `LIVE_RELEASE` guard

**Goal.** Risk Core (Python) **and** Fabric (C#) reject any account not on an explicit operator list. `LIVE_RELEASE` is a logged, ADR-backed, human-only object. Agents cannot flip it. Tests include bypass/attack cases. **Still no research SIM orders.**

S1 may run in parallel with S0 once ADR-0059 exists, but must not enable S3.

#### Files

| Action | Path |
|--------|------|
| ADAPT | `config.yaml` — add frozen operator block (example below) |
| ADAPT | `lumina_core/broker/ninjatrader/guards.py` `check_account_match` — **whitelist first**; prefix helpers become diagnostics only, never allow |
| ADAPT | `lumina_core/broker/ninjatrader/account_names.py` — `account_on_sim_whitelist(name, whitelist)`; empty whitelist → deny all |
| NEW | `lumina_core/risk/sim_account_guard.py` — used as an AdmissionChain step so the **Risk Core** rejects, not only the broker façade |
| ADAPT | `lumina_core/risk/admission_chain.py` — add step id `sim_account_whitelist` to `CANONICAL_ADMISSION_STEPS` **after** `session_equity_sync`, **before** `risk_policy`. Missing step in REAL/`sim`/`sim_real_guard` = fail-closed. This is a Risk Core change: allowed in S1 because Steve’s binding requires the Core to reject non-whitelist accounts. Keep the step **pure**: list in, account in, bool out. No sizing. |
| ADAPT | `lumina_core/order_gatekeeper/admission_steps.py` — handler for the new step |
| ADAPT | `NtAccountOrderGateway.cs` — replace `AllowsPaperOrders` allow path with `SimAccountWhitelist` from `FabricConfig`; empty array → reject `sim_whitelist_empty`; name not in list → `sim_account_not_whitelisted` |
| ADAPT | `FabricConfig.cs` — `string[] SimAccountWhitelist` from `fabric.json` |
| ADAPT | `lumina_launcher/services/nt_account_store.py` — write the same list to `config.yaml` and `fabric.json` (operator UI already copies names) |
| ADAPT | `tauri-app/src/lib/ntAccountNames.ts` — UI copy: whitelist, not “starts with Sim” |
| NEW | `lumina_core/risk/live_release.py` — `LiveRelease` frozen record: `enabled: bool`, `adr_path: str`, `adr_sha256: str`, `approved_by: str`, `approved_at_utc: datetime`, `signature: str`. `enabled` true only if all fields valid **and** `enabled` is true. Missing file/key = disabled. |
| ADAPT | `guards.py` REAL branch — require `live_release.enabled`; else `live_release_required` (keep `real_account_blocked_pending_promotion_adr` as a second reason if demo name) |
| ADAPT | `NtAccountOrderGateway.PlaceOrder` REAL branch — same check from `fabric.json` `LiveRelease.enabled` (default false) |
| ADAPT | `lumina_core/code_evolution/operators.py` `FORBIDDEN_PARAMETER_KEYS` — add `live_release`, `sim_account_whitelist`, `account_name`, `RealAccountName`, `research_execution_mode`, `mode`, `trade_mode` |
| ADAPT | `lumina_core/code_evolution/proposal.py` `FORBIDDEN_TARGET_PREFIXES` — add `config.yaml`, `fabric.json`, `lumina_core/risk/live_release`, `lumina_core/risk/sim_account_guard` |
| ADAPT | `lumina_core/runtime_config_reloader.py` — refuse hot-reload of whitelist / `live_release` / `research_execution_mode` / `trade_mode` (log `config_reload_refused:protected_key`). Operator change requires process restart. |
| ADAPT | `lumina_core/risk/orchestration.py` — `enforce_rules = resolve_mode_capabilities(trade_mode).risk_enforced` (closes G-SIMBYP for `sim_real_guard`). **Do not** turn `sim` into risk_enforced in this step (that would change current learning mode). S3 will not use `sim` for research orders. |
| NEW | `docs/adr/0060-sim-whitelist-and-live-release.md` |
| NEW tests | below |
| FORBIDDEN | enabling REAL orders; setting `LiveRelease.enabled: true` in repo `config.yaml` (must stay false) |

Config shape (operator-owned; committed default is deny-open):

```yaml
broker:
  ninjatrader:
    account_name: Sim101
    sim_account_whitelist:
      - Sim101
live_release:
  enabled: false
  adr_path: ""
  adr_sha256: ""
  approved_by: ""
  approved_at_utc: ""
  signature: ""
research_execution_mode: shadow
```

Empty `sim_account_whitelist:` (or omitted) **denies** every account. That is the opposite of today’s “configured empty → skip match”.

#### Tests (S1) — including bypass / attack

Python:

| Test | Proves |
|------|--------|
| `tests/broker/test_sim_whitelist.py` | `Sim101` on list + match → ok. `Sim202` not on list → reject even though `is_local_sim_name` is true (prefix bypass dead). `DEMO5042070` not on list → reject. |
| `tests/broker/test_sim_whitelist_empty_denies.py` | `whitelist=[]` + `Sim101` → deny. Missing key → deny. |
| `tests/broker/test_sim_whitelist_case.py` | Exact NT name; document casefold policy (recommend casefold match, store canonical). |
| `tests/risk/test_admission_whitelist_step.py` | AdmissionChain without the step fails closed in `sim`/`sim_real_guard`/`real`. Step sees connected account `LiveAcct` → reject. |
| `tests/risk/test_live_release.py` | `enabled=false` → REAL submit denied. `enabled=true` but empty `adr_sha256` / signature → denied. Valid record → Python gate returns ok **only** for the live-release check (other REAL gates still apply). |
| `tests/risk/test_live_release_attack.py` | (1) env `TRADE_MODE=real` without live_release → deny. (2) hot-reload payload flipping `live_release.enabled` → `config_reload_refused`. (3) code-evolution parameter tweak `live_release` → `forbidden_parameter_key`. (4) research `GovernanceGate.apply_protected` still `refuse_protected_write`. (5) agent publishes Event Bus event `runtime.config.reload_requested` with live_release true → reloader refuses. |
| `tests/code_evolution/test_forbidden_whitelist_keys.py` | `FORBIDDEN_PARAMETER_KEYS` contains the new names; sandbox worker copy in `sandboxed_code_worker.py` updated to match. |
| `tests/risk/test_orchestrator_enforce_rules_follows_capabilities.py` | `sim_real_guard` ⇒ `enforce_rules True`; `sim` ⇒ False; `real` ⇒ True. |
| ADAPT `tests/broker/test_ninjatrader_guards.py` | Old “DEMO allowed in sim when names match” **fails** unless DEMO is on the whitelist. Update tests to the new law; do not keep the prefix allow. |

C# (new; gap G-CS):

| Test | Proves |
|------|--------|
| `integrations/ninjatrader8/Lumina.Execution.Fabric.Tests/SimWhitelistTests.cs` | Empty whitelist → reject. Name not in list → `sim_account_not_whitelisted`. `Sim101` in list → admit past **this** check (other gates still run). Prefix `Sim999` not in list → reject. |
| `LiveReleaseTests.cs` | `ModeContext=real` and `LiveRelease.enabled=false` → reject even on a Sim name. `enabled=true` still does not bind a live brokerage name in S1 (keep `real_account_blocked` until a later live ADR). |

#### Acceptance (S1)

1. A SIM order attempt (from the **existing** engine path or a unit-level `check_account_match`) to an account not on the list is rejected in Python **and** C#.
2. Empty list denies `Sim101`.
3. `LIVE_RELEASE` cannot be enabled by hot reload, code evolution, or research governance.
4. Repo `config.yaml` remains `live_release.enabled: false`.
5. Isolation tests still pass.
6. ADR-0060 exists.

#### Rollback (S1)

**Do not** roll back to prefix-allow (that re-opens G-WL). Rollback = git revert **forward** to “deny all SIM submits except the previous explicit list” by restoring the last known good whitelist in operator `fabric.json`, or set whitelist to `[]` (desk stops). Flag `research_execution_mode` stays `shadow`/`off`.

---

### 3.3 S2 — Fill feedback to monitor and cost calibration

**Goal.** One fill SSOT. Broker fills (and S0 hypothetical fills) share `FillEvent`. Decay monitor and cost calibrator both consume that type. Commission and slippage are non-zero when the card/model says they are. Ticks and $ are both logged per root.

#### Files

| Action | Path |
|--------|------|
| NEW | `lumina_core/research_bridge/fill_translator.py` — `FillEvent` / `ExecutionFill` / reconciler row → `observe(signal_id, metric)` **and** calibrator row. `strategy_id` from order metadata / `correlation_id` map. Unmapped fills still go to calibrator (desk-level costs) but **not** to a random signal’s decay series. |
| NEW | `lumina_core/research_bridge/fill_index.py` — `client_order_id → strategy_id` (S0: hypothetical ids; S3: real client_order_id). |
| ADAPT | `lumina_core/broker/ninjatrader/fabric_mapper.py` `order_event_to_fill` — stamp `commission` from `lumina_core.market.nt_fees.fee_components` (Free-plan all-in × qty). Do not leave `0.0`. Slippage: `slippage_ticks = (fill_price - reference_price) / tick_size` when reference is on the originating `OrderIntent`; else omit (do not invent). |
| ADAPT | `lumina_core/engine/trade_reconciler/fill_normalization_mixin.py` — copy slippage/commission onto `FillEvent`. |
| ADAPT | `lumina_core/engine/trade_reconciler/finalize_mixin.py` — `reconciled` JSONL includes `slippage_ticks`, `slippage_usd`, `commission_ticks`, `commission`, `fill_price`, `qty`, `strategy_id`, `source`. |
| ADAPT | `lumina_core/risk/cost_model_calibrator.py` — read those fields; group **by root** (ES vs MES separate running bias). Do not mix mini and micro in one `instrument` bucket. |
| ADAPT | `lumina_research/monitoring/loop.py` / KEEP bridge — **KEEP calls `observe`**. Monitoring still does not import broker (isolation). Bridge is the anti-corruption layer. |
| ADAPT | `ExecutionFill` — optional `slippage` / `commission_ticks` with defaults 0; `extra=forbid` so add fields, don’t allow unknown. |
| ADAPT | `scripts/validation/run_cost_model_calibration.py` — pass-through; assert per-root output. |
| NEW tests | below |
| FORBIDDEN | research importing `lumina_core.broker`; changing ADR-0055 card formula; Fabric proto commission field (stamp in Brain) |

Hypothetical S0 fills already have `source=hypothetical_cost_model`. S2 translator accepts both sources. Calibrator **must** tag hypothetical vs broker so we never calibrate the live card against cost-model fiction. Two state files:

- `state/cost_model_calibration.json` — **broker** fills only (KEEP meaning).
- `state/research_shadow_cost.json` — hypothetical vs later broker, for S3 promotion evidence (reality gap).

#### Tests (S2)

| Test | Proves |
|------|--------|
| `tests/research_bridge/test_fill_ssot.py` | One `FillEvent` fixture fans out to monitor `series()` **and** calibrator `load_reconciled_rows`; mutating only JSONL without FillEvent is not sufficient (translator is the API). |
| `tests/research_bridge/test_unmapped_fill_not_observed.py` | Fill without `strategy_id` updates calibrator, not monitor. |
| `tests/broker/test_fabric_mapper_commission.py` | MES qty 1 commission = 0.94; ES qty 1 = 2.87; MNQ ≠ NQ. Not 0.0. |
| `tests/broker/test_fill_slippage_ticks.py` | BUY fill 1 tick above reference → `slippage_ticks=1`, `slippage_usd=tick_value`. |
| `tests/risk/test_cost_model_calibration_per_root.py` | ES and MES rows do not share a rolling mean. |
| `tests/research_bridge/test_hypothetical_excluded_from_live_calibration.py` | `source=hypothetical_cost_model` never writes `state/cost_model_calibration.json`. |
| `tests/research/test_phase4_isolation.py` | still no broker import from `lumina_research/monitoring`. |
| ADAPT `tests/risk/test_cost_model_calibration.py` | new fields. |

#### Acceptance (S2)

1. A fixture broker fill with known price/qty produces identical `(fill_price, qty, slippage, commission)` in JSONL, `FillEvent`, calibrator input, and (if mapped) monitor observe.
2. Commission is the ADR-0055 Free-plan all-in, per root, in $; ticks = `$ / tick_value_usd`.
3. Hypothetical fills never pollute live calibration.
4. Isolation tests green.

#### Rollback (S2)

Stop the translator subscription; monitor can still be fed by S0 hypothetical path only; calibrator reverts to previous JSONL fields (backward compatible if new keys are optional). Git revert S2 PR.

---

### 3.4 S3 — SIM orders, gated

**Goal.** Research-originated `OrderIntent`s may reach Fabric **only if** all gates below pass. Still **not** LIVE. `LIVE_RELEASE.enabled` remains false. Account must be on the S1 whitelist.

#### Entry criteria (machine-checkable)

All must be true; missing evidence = reject (`research_sim_gated`):

1. `research_execution_mode: sim` set by operator **restart** (not hot reload).
2. `live_release.enabled: false` (S3 is SIM; if this is true, refuse research S3 until a later live ADR — do not mix).
3. Connected NT account ∈ `sim_account_whitelist`.
4. Trade mode is **`sim_real_guard`** (not `sim`), with `ENABLE_SIM_REAL_GUARD=true`, so Brain risk caps are on (G-SIMBYP closed). Session guard + equity snapshot apply (`MODES_REQUIRING_EQUITY_SNAPSHOT`).
5. **Survivors:** ≥ 2 and ≤ N (operator cap) **independent** signals in `LiveSignalRegistry` with `stage in {active, deweighted}` (not suspended/retired), each with:
   - sealed `PromotionCandidate` + `ValidationResult` (`passes_validation_gate` true);
   - distinct `hypothesis_id`;
   - pairwise correlation of shadow observe series below a fixed cap (reuse research cluster: ES family vs NQ family counts as independent; two MES clones of the same `config_id` do not);
   - shadow fill history ≥ `expected_horizon` and ≥ ADR-0058 window (`CONFIRM_WINDOWS` and monitor `window`, default 20) **from FillEvent SSOT** (hypothetical allowed for the first S3 enable only if Q2 says so; default recommendation: **NT-tape or NT-bar replay PIT**, not planted_edge gauss).
6. Empirical monitoring thresholds **on that shadow series** (not only the synthetic campaign in `tests/research/test_phase4_campaign.py`): FAR and detection floors from `lumina_research/monitoring/acceptance.py` either (a) still hold on the campaign harness **and** (b) live/shadow FAR on healthy control signals ≤ 5%. If (b) cannot be measured yet, **do not enable** S3 (doubt = reject).
7. Live `PromotionGate.evaluate` on `GateReport.as_promotion_fragments()` **plus** HMAC verification of the same `ValidationResult` used by the registry. Fail if fragments and MAC disagree.
8. Twin/human: existing `sim_real_guard` approval_required in `config.yaml` (`sim.approval_required: true`) stays on.

If any check fails, bridge stays in shadow behavior even if the yaml says `sim`.

#### Files

| Action | Path |
|--------|------|
| ADAPT | `lumina_core/research_bridge/shadow_runtime.py` → split `sim_runtime.py` or mode switch inside bridge: `shadow` logs; `sim` builds live `OrderIntent` and calls **existing** `enforce_pre_trade_gate` + `FinalArbitration` + `NinjaTraderBroker.submit_order`. No new broker. |
| ADAPT | `operations_service_orders.py` / policy — research orders enter **only** through the bridge, with `source_agent="research_bridge"` and `strategy_id` set. Supervisor E5 **must refuse** `source_agent=research_bridge` if somehow invoked (defense). |
| NEW | `lumina_core/research_bridge/sim_gate.py` — implements entry criteria 1–8; returns `(ok, reason)`. |
| ADAPT | `lumina_core/evolution/promotion_gate.py` — **require** optional `validation_mac` / `report_sha256` when `source=research`. Dictionary-only evidence without MAC **rejects** for research-sourced DNA. Do not silently accept nightly report dicts for research strategies. |
| NEW | `lumina_core/research_bridge/reduce_on_decay.py` — subscribe `RESEARCH_DEWEIGHT_TOPIC` / `SUSPEND` / `RETIRE`; if open position for `strategy_id`, submit **reduce-only** `OrderIntent` through the same AdmissionChain. Suspend/retire → flatten **that strategy’s** qty, not the whole account, unless Risk Core hard limit fires (kill switch / daily loss / Fabric daily loss). Emergency account flatten remains Fabric watchdog (KEEP). |
| ADAPT | `fabric_mapper.order_to_place_command` — set `reduce_only` true for decay reduces; `mode_context=sim_real_guard`; `correlation_id` = strategy_id + client_order_id. |
| ADAPT | `config.yaml` — do not commit `research_execution_mode: sim`; operator sets it locally after the gate script passes. |
| NEW | `scripts/research/check_sim_entry.py` — prints survivors, FAR, whitelist, live_release, mode; exit 0 only if criteria pass. |
| NEW tests | below |
| FORBIDDEN | `LIVE_RELEASE.enabled: true`; `trade_mode: real`; relaxing `risk_gates` SIM bypass for `sim` mode “to make S3 easier”; importing archive birth. |

#### Tests (S3)

| Test | Proves |
|------|--------|
| `tests/research_bridge/test_sim_gate_requires_survivors.py` | 0 or 1 survivor → no `place_order`. 2 independent → gate ok **in fixture**. Two clones same `config_id` → not independent. |
| `tests/research_bridge/test_sim_gate_mode.py` | `trade_mode=sim` (learning, caps bypassed) → refuse research orders. `sim_real_guard` + env → ok. `real` → refuse (`live_release` false). |
| `tests/research_bridge/test_sim_still_shadow_when_yaml_lies.py` | yaml `sim` but survivors < 2 → still no Fabric call. |
| `tests/research_bridge/test_research_order_hits_admission.py` | Mock chain: whitelist, constitution, arbitration all invoked; a reject anywhere → no Fabric. |
| `tests/research_bridge/test_promotion_gate_requires_mac.py` | Research-sourced evidence dict without MAC → reject. |
| `tests/research_bridge/test_decay_reduce_only.py` | Deweight with open qty → one reduce-only order, not flatten-all. Retire → qty to 0 for that strategy. Kill-switch → existing Risk Core path (full block / flatten policy unchanged). |
| `tests/research_bridge/test_disconnect_no_new_orders.py` | Reuse `check_disconnect_policy` / SAFE_MODE: research bridge does not retry place while disconnected. |
| `tests/research_bridge/test_stale_equity_blocks_sim.py` | `sim_real_guard` + stale snapshot → no new research order (reduce-only still allowed if `is_risk_reducing_side`). |
| C# | Existing heartbeat/flatten tests still pass; whitelist tests from S1 still pass. |

#### Acceptance (S3)

1. `python scripts/research/check_sim_entry.py` exit 0 on the operator desk.
2. First research order is on a **whitelisted SIM** account, `mode_context=sim_real_guard`, `LIVE_RELEASE` false.
3. Fills return on `TradingStream`, become `FillEvent(source=broker)`, update monitor and live calibrator (S2).
4. Kill NT or Brain: Fabric SAFE + cancel non-protected; no new places; reconcile on reconnect (`GetAccountState`).
5. Decay: size down, not account-wide flatten, unless a hard Risk Core / Fabric daily-loss limit fires.
6. Logs/alerts: every reject (`sim_gate`, admission, Fabric) in JSONL + existing Telegram `real_safety` matrix **not** spammed; use `ops` / `evolution` channels (`config.yaml` notification_matrix).

#### Rollback (S3)

1. Immediate: `research_execution_mode: shadow` + restart. Bridge stops placing. Open research positions: operator or `reduce_on_decay` on a synthetic “retire all research” guardian finding — **prefer reduce-only per strategy**. Account-wide flatten only if Risk Core kill switch engages.
2. Git revert S3 PR. S0–S2 remain.
3. Fabric watchdog unchanged.

---

### 3.5 What this plan never does

- Rewrite `lumina_research` into the engine.
- Point research agents at `place_order`.
- Enable REAL / `LIVE_RELEASE`.
- Use `archive/birth-v1/` fitness or curricula.
- Trust prefix `Sim*` as a whitelist.
- Calibrate live costs on hypothetical fills.
- Flatten the whole book because a monitor z-test fired.

---

## 4. Risks and open questions for Steve

### 4.1 Risks (real)

| Risk | Why it is real | Mitigation |
|------|----------------|------------|
| Existing `mode: sim` already submits NT orders from `supervisor_tick_exec` | Desk can trade **without** research gates while we “start in SHADOW” for research only | Q1. Bridge isolation test `test_supervisor_unaffected`. Do not claim the desk is shadow-only unless E5 is frozen. |
| Two cost theories (research four-leg cash vs ADR-0055 “slippage in the fill”) | Shadow PnL and live calibration will disagree if both run unlabeled | S2 splits state files; Q3. |
| Live `PromotionGate` DSR floor 0.0 vs research 0.95 | A research survivor could be re-judged by a weaker live gate, or the reverse | S3 requires MAC **and** research floors; do not lower `gate_thresholds.toml`. |
| `sim` Risk Core cap bypass | S3 on `sim` would be NT orders with Brain caps off | S3 hard-requires `sim_real_guard`. |
| `@LuminaFabricHost.cs` gitignored | S1 C# whitelist lives in `fabric.json`; a stale AddOn build could skip new checks | Operator rebuild/heal after S1; add a Fabric version/capability ping if missing. |
| Synthetic “survivors” look like 2–3 | Phase 2 planted_edge will pass the gate on gauss tapes without NT PIT | Q2; default S3 refuse synthetic-only. |
| Reduce-on-decay vs session-touched flatten | Mis-wiring could flatten the operator’s manual SIM trades | Reduce only client_order_ids in `fill_index`; EmergencyFlattenPolicy stays session-touched for **Brain disconnect**, not decay. |
| AdmissionChain step add is a Risk Core change | Binding said “no Risk Core code” for **this** docs PR; S1 **will** touch it | Separate S1 PR, human review, ADR-0060, tests above. This plan PR does not apply that change. |

### 4.2 Open questions (only real ones; the plan cannot honestly choose)

**Q1.** While research is in SHADOW, should the **existing** confluence/`place_order` path (`supervisor_tick_exec`, `config.yaml` `mode: sim`) keep sending SIM orders to NT, or freeze it (`research_execution_mode=shadow` also sets a desk-level `execution_hold` except flatten/cancel)?

This plan cannot call the desk “shadow first” if E5 still fires. Recommendation if you do not answer: **leave E5 as-is** (KEEP product), document it as a parallel path, and do not advertise SHADOW as “no NT orders from Lumina”.

**Q2.** What is an “independent survivor”? Specifically: may S3 enable on **synthetic** planted_edge candidates that passed Phases 1–4, or only on candidates whose Validation Gate ran on **NT closed bars** (PIT, ADR-0053)?

Default if unanswered: **NT PIT bars required**. That implies a research data adapter (read-only closed book → `materialize` replacement) **before** S3, which is a new slice between S0 and S3 (call it S2.5 if needed). It is not in S0 because S0 can prove wiring on cost-only hypothetical fills without claiming alpha.

**Q3.** For hypothetical S0 fills and for live calibration, which cost SSOT wins when they disagree: `lumina_research.validation.cost_model` (commission + half-spread + slippage + impact as cash) or ADR-0055 `nt_fees` (commission cash; slippage in fill price)?

Recommendation: **broker/live calibration = ADR-0055 card + observed fill slippage**. **Research Validation Gate** keeps the four-leg model (charter). Shadow JSONL stores **both** breakdowns. Do not silently replace the charter model.

**Q4.** `LIVE_RELEASE` signature: reuse research `SignedReview` HMAC (`schemas_research.py`) with `reviewer_id` not an agent, or a separate operator file under `%APPDATA%\LUMINA\live_release.json` plus ADR-0060 hash only?

Either is fail-closed. Need one so S1 tests have a golden fixture. Recommendation: **file + ADR hash + human name + UTC**, HMAC optional (launcher already writes `fabric.json` without HMAC).

**Q5.** First SIM instrument for S3: MES/MNQ (micro, $0.94/side) or ES/NQ (mini, $2.87/side, 10× tick value on ES vs MES)? Binding only says **separate** costs. Recommendation: **MES or MNQ** on Sim101 until survivors exist, because Fabric `max_position_size: 2` still hurts more on ES.

**Q6.** `expected_horizon`: who sets it? PromotionCandidate today has no field. Options: (a) refuse until the hypothesis carries bars/time, (b) default to monitor window 20, (c) default to genome `oos_size` (30 in the schema default).

Recommendation: **(a) refuse in S0 if missing**; ADAPT `HypothesisProposed` / `PromotionCandidate` with required `expected_horizon_bars ≥ 1` in the same S0 PR. That is a research schema change but not a Risk Core change.

No other questions are blocking. Dual Event Bus vs gRPC, “rewrite the AddOn”, and “merge research into `lumina_core/engine`” are already decided (no).

---

## 5. Implementation PR sequence (after this docs PR)

| PR | Content | Touches Risk Core / Fabric? |
|----|---------|------------------------------|
| This PR | `docs/plans/INTEGRATION_PLAN_research_to_nt8.md` only | No |
| S0 | Bridge + schemas + ADR-0059 + tests | No (config key only) |
| S1 | Whitelist + LIVE_RELEASE + admission step + C# + ADR-0060 + attack tests | **Yes** (admission step, guards, C# place reject). Human review required. |
| S2 | Fill translator + mapper commission/slippage + per-root calibrator | Mapper/reconciler only; not risk limits |
| S2.5 (if Q2 = NT PIT) | Research tape from closed NT bars | Read-only MD |
| S3 | sim_runtime + sim_gate + reduce-on-decay + PromotionGate MAC | Order path via **existing** admission; no LIVE_RELEASE |

Each PR: `ruff` + `mypy --strict` + `pyright` + targeted pytest; C# `dotnet test` on Fabric.Tests when G/S1/S3.

---

## 6. Traceability

| Binding sentence | Plan section |
|------------------|--------------|
| No rewrite; Event Bus/ports | §0, E14, B1, S0 files |
| Keep NT8 / Fabric / Risk Core / PIT ingest / order lifecycle / contracts / Constitution | §1 KEEP rows |
| Isolate old birth/evolution | §1.7, G-ENG, O1–O14 |
| SignalIntent / OrderIntent / FillEvent fields | §1.10, §3.0, G-MSG |
| Fills → monitor + calibration, one SSOT | §3.3, E13, G-FILL |
| Explicit SIM whitelist; LIVE_RELEASE; not agent-mutable; bypass tests | §1.4, §3.2, G-WL, G-LIVE, G-MUT |
| Shadow first; SIM after 2–3 survivors + empirical floors | §3.1, §3.4, G-SURV, P9 |
| Fail-closed stale/disconnect; broker SSOT; reduce vs hard flatten | G11–G13, S3–S6, G-RED, §3.4 reduce_on_decay |
| ES/NQ vs MES/MNQ ticks and $ | P2, P3, R13, S0 cost tests, S2 mapper tests |

*End of plan. No runtime behavior changes in the commit that adds this file.*
