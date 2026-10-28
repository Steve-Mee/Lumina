# Integration plan: `lumina_research` → Lumina program → NinjaTrader 8

**Status:** Plan only. No runtime, execution, or Risk Core code is changed by the document that carries this plan.  
**Baseline:** `main` @ `c653cab` (merge of PR #61, Phase 4 continuity). Phases 1–4 of `lumina_research` are on `main` (PRs #58, #59, #60, #61; charter/archive cutover #57).  
**Mode of this work:** ANALYSIS + PLAN. Shadow first. No orders. No merge of execution changes.

Binding decisions (plan authors, approved by Steve), restated as implementation law:

1. **No rewrite.** `lumina_research` stays a separate propose-only layer. Integration is Event Bus + hexagonal ports.
2. **Keep** the NT8 AddOn bridge / Execution Fabric (gRPC), the independent fail-closed live Risk Core, data ingest if point-in-time correct, the order lifecycle, typed contracts, Constitution, and safety layers. **Isolate** old birth/evolution/fitness that bypasses the new gates or mixes research into the execution path.
3. **Messages:** `SignalIntent` / `OrderIntent` (`strategy_id`, `direction`, `size`, `timestamp`, `expected_horizon`) and `FillEvent` (`fill_price`, `qty`, `slippage`, `commission`). Fills feed the decay monitor and cost calibration from **one** source of truth.
4. **SIM safety:** live Risk Core rejects any account not on an **explicit SIM whitelist**. Live needs `LIVE_RELEASE` (HMAC-signed review/token + human-reviewed logged ADR; see D4), outside research agents. That config is not agent-mutable. Tests must prove there is no bypass.
5. **Order of work:** shadow first (signals logged, hypothetical fills calibrated to ADR-0055, no orders). Real SIM orders only after **2–3 independent survivors** whose Validation Gate ran on **point-in-time NT bars** (D2, D11), first on **MES/MNQ** (D5).
6. **Failure:** fail-closed. Stale data or lost connection → no new orders, server-side cancel / reduce-to-flat, broker as source of truth, reconcile on reconnect. Monitor alarm with an open position: research **proposes** de-weight/reduce; Risk Core or Position Manager **executes** (D7, D9, D10). Log and alert everything.
7. **Ticks:** ES/NQ and MES/MNQ have separate costs, reported in ticks **and** dollars. Cost SSOT is ADR-0055 (D3).

This plan names existing files, existing tests, and the exact new files each phase must add. It does not invent a second execution stack.

---

## Decisions (Steve, 2026-10-28)

Plan authors, approved by Steve. These close the six questions in the first draft of this plan, the seventh (alarm authority), and the four follow-ups (OQ1–OQ4). They are implementation law for S0–S3. A config flag **alone** is never a control.

| ID | Decision |
|----|----------|
| **D1** | **Hard-freeze / hard-block** `supervisor_tick_exec` and **every equivalent path that can place orders without the Validation Gate** during S0 and S1. A `research_execution_mode` (or `mode: sim`) yaml key is **not** enough. This is an **S0 prerequisite**. Tests must prove there is no parallel order path. Flatten / cancel / emergency reduce remain allowed. **D8** extends this: research signals never use `supervisor_tick_exec`. |
| **D2** | S3 survivors come **only** from `passes_validation_gate` on **real point-in-time NT closed bars** (ADR-0053/0054). Synthetic `materialize()` / planted_edge tapes are for **acceptance tests, calibration, and unit tests only**. They cannot count as S3 survivors. |
| **D3** | Cost source of truth is **ADR-0055**: commission from `lumina_core/market/nt_fees.py`; **slippage lives in the fill price**. The research `CostModel` **calibrates to** that card. On discrepancy, **execution-side wins** (broker fill + NT card), not the four-leg research estimate. |
| **D4** | `LIVE_RELEASE` is an **HMAC-signed review/token**. The HMAC secret is **outside agent reach**. A human-reviewed, logged ADR is required. The **live Risk Core verifies the signature**. Invalid or missing signature → reject. A plain file plus hash **without** HMAC is too weak and is refused. |
| **D5** | First S3 instruments are **MES and MNQ**. Scale to **ES/NQ only after stability** on micros (separate costs, ticks and $). |
| **D6** | Refuse a `SignalIntent` (and the hypothesis that would produce it) **without `expected_horizon`**. No silent default (not 20, not `oos_size`). `HypothesisAgent` **may set one explicitly**; that value is **logged and gated**. |
| **D7** | Alarm with an open position: research **only proposes** de-weight/reduce. The **live Risk Core or a Position Manager executes**. Act within **1–5 minutes or the next bar**, depending on severity. Size and SLA-miss policy: **D9** and **D10**. Log and escalate everything. Broker is SSOT; reconcile on reconnect. |
| **D8** | `supervisor_tick_exec` stays **permanently closed for research signals**. S3 does **not** re-arm confluence auto-place. Non-research orders (manual / legacy) are **default closed**. They may place **only** via an **explicit logged release outside the agents**, always through the live Risk Core (SIM whitelist **or** a valid `LIVE_RELEASE`). Reopening that path requires **ADR + human approval**. |
| **D9** | ADR-0058 mapping: **suspend / de-weight** → reduce **50% of that strategy’s position** within the D7 reaction time. **Disable / critical / hard limit** (including `retired`, guardian disable, `GuardianSeverity` critical, hard drawdown, prolonged disconnect) → **flatten 100%** of that strategy. Research **proposes**; Risk Core / Position Manager **executes**. Account-wide flatten only if Core kill-switch / Fabric emergency fires. |
| **D10** | SLA miss: **first miss** → log + alarm + **one retry**. **Second miss** or **timeout > 10 minutes** → escalate to Risk Core action **for that strategy** (reduce or flatten by D9 severity). **No infinite silent retry**. Broker is SSOT; reconcile on reconnect. |
| **D11** | Survivors count as **independent** only if **both** apply: (1) a **different economic hypothesis and family**, and (2) pairwise return (or residual return) **correlation < 0.5** over the evaluation period. Distinct `hypothesis_id` alone is not enough. Same `config_id` clones never count. |

Closed questions: former Q1→D1, Q2→D2, Q3→D3, Q4→D4, Q5→D5, Q6→D6, alarm authority→D7, OQ1→D8, OQ2→D9, OQ3→D10, OQ4→D11. §4.2 has **no remaining blocking questions**. Inventory market-data rows are **MD1–MD7**; live Risk Core inventory rows stay **R1–R15**.

**This revision (2026-10-28, docs-only):** adds D8–D11 (Steve-approved OQ answers) and retunes S0–S3. It does not change runtime, Risk Core, or Fabric code.

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
  S0 prerequisite: hard-block ungated place_order paths (D1); supervisor stays closed for research (D8)
  S0: PromotionCandidate → SignalIntent (log only; expected_horizon required)
      → hypothetical FillEvent using ADR-0055 commission + fill-price slippage (D3)
      → observe() on LivePerformanceMonitor
      → NEVER PlaceOrderCommand / place_order()
  S3: SignalIntent → OrderIntent → AdmissionChain → FinalArbitration
      → FabricGrpcClient → ExecutionFabric → NtAccountOrderGateway
      ← OrderEvent → FillEvent (broker SSOT) → monitor + cost calibrator
      MES/MNQ first (D5). Independent survivors per D11.
      Alarm: research proposes; Risk Core / Position Manager executes (D7, D9, D10).
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
| E5 | Supervisor auto-place | `lumina_core/engine/supervisor_tick_exec.py` `run_tick_exec()` | **HARD-BLOCK in S0/S1 (D1); permanently closed for research (D8)** | On `BUY`/`SELL` + confluence, `paper` uses `PaperSimulator`; **any other `trade_mode` calls `app.place_order(signal, qty)`**. Ungated vs Validation Gate. S0 must tripwire this path in code, not via yaml. S3 does **not** re-arm it for research. Equivalent callers: `operations_service_orders.place_order`, `policy_engine.execute_order`, `reasoning_service.submit_order`/`execute_order`, `trade_workers.submit_order_with_risk_check`, `paper_trade_executor` broker submit, `PaperSimulator.try_open`. Emergency flatten (`lumina_os/backend/emergency_order_endpoints.py`) stays allowed. Non-research reopen: ADR + human, through Risk Core (D8). |
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

`config.yaml` today: `mode: sim`, `broker.backend: live`, `broker.live_provider: ninjatrader`, `broker.ninjatrader.account_name: Sim101`. `ConfigLoader._resolve_runtime_modes` reads `trade_mode` or `mode`. **The desk is already in a mode that may submit NT orders** from E5, independent of research. D1 forbids leaving that path live during S0/S1. D8 forbids using it for research signals at any later phase; non-research stays default-closed.

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
| R11 | Live cost model | `lumina_core/risk/cost_model.py` `TradeExecutionCostModel` | KEEP (execution SSOT with R13) | Fees from `lumina_core/market/nt_fees.py` (ADR-0055). Slippage is a paper/risk simulator; ADR-0055: do not add a cash tick on top of a fill price. D3: this side wins on discrepancy. |
| R12 | Cost calibrator | `lumina_core/risk/cost_model_calibrator.py` | ADAPT S2 | Reads `event=="reconciled"` from `logs/trade_fill_audit.jsonl`. Uses `slippage_points` + `commission` on that row. Not wired to research `observe()`. S2 also calibrates research `CostModel` **toward** this SSOT. |
| R13 | NT fee card | `lumina_core/market/nt_fees.py` | KEEP — **cost SSOT (D3)** | Free-plan all-in per side: ES/NQ `$2.87` (1.39+0.19+1.29), MES/MNQ `$0.94` (0.36+0.19+0.39). Separate roots. No MES fallback for unknown root. |
| R14 | Research Risk Core | `lumina_research/risk_core/` | ISOLATE (from live writes) | Additional filter. `RiskConfig` frozen (`config.py`). `propose_order` → Approved/Rejected/Scaled. Stdlib-only (AST). Survivors still face live Risk Core. |
| R15 | `LIVE_RELEASE` | — | **ABSENT** — S1 must add HMAC token (D4), not a bare flag | Repo-wide search: zero matches. Closest: `real_account_blocked_pending_promotion_adr` and `evaluate_real_capital_readiness`. Research `SignedReview` HMAC (`schemas_research.py`) is the pattern to reuse; the secret must not live in `config.yaml` or agent-writable state. |

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
| MD1 | NT 1m Last SSOT | ADR-0053, `lumina_core/engine/nt_bar_ssot.py` | KEEP | Decision OHLC = NT 1-minute Last bars. Tape never writes `ohlc_1min`. Fail-closed on missing/zero high/low. |
| MD2 | Closed vs forming | `lumina_core/engine/market_data_manager.py` `partition_closed_and_forming` | KEEP | “A timestamp still in the future is forming and must not enter the closed book (ADR-0053 / ADR-0054).” |
| MD3 | HTF bars | ADR-0054 | KEEP | Native NT 5/15/30/60/240; no silent TradingHours fallback. |
| MD4 | History fetch | `lumina_core/engine/market_data_history_fetch.py` | KEEP / ISOLATE CrossTrade | NT Fabric `RequestHistoricalData` when `live_provider=ninjatrader`. CrossTrade = “legacy emergency only”. |
| MD5 | Fabric MD providers | `LuminaNt8AddOn/NtHistoricalDataProvider.cs`, `NtLiveBarProvider.cs`, `NtLiveMarketDataProvider.cs` | KEEP | Product ingest. |
| MD6 | Research tapes | `lumina_research/agents/synthetic.py` `materialize()` | ISOLATE from live ingest | Deterministic gauss / planted_edge. **No network. Not NT bars.** Phase 2/3/4 tests run on this tape. There is **no** research walk-forward on NT PIT bars yet. |
| MD7 | Research purge/embargo | `lumina_research/validation/purge.py`, `cpcv.py` | KEEP (research) | Validation Gate refuses missing purge/embargo. |

**PIT verdict for live ingest:** KEEP. Forming-bar split and NT Last SSOT are the correct live book. **PIT verdict for research candidates today:** they are **not** validated on that book; they are validated on synthetic series. Decision **D2**: S3 survivors **require** a PIT NT-bar Validation Gate (mandatory S2.5). Synthetic tapes remain test-only (inventory **MD6** `materialize()`, not decision D6).

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
| P2 | Cost model | `validation/cost_model.py` | ADAPT S2 (calibrate to ADR-0055) | Four legs today; `ticks_for_fill` returns ticks **and** `total_usd`. Tests: `tests/research/test_cost_model.py`. D3: commission must match the NT card; extra legs are estimates that calibrate to execution fills; they must not undercut ADR-0055. |
| P3 | Contracts | `validation/contracts.py` | KEEP | ES/NQ/MES/MNQ. Commission ticks = Free-plan USD / tick_value (`2.87/12.50` ES, `0.94/1.25` MES) — same dollars as ADR-0055, different unit. Half-spread 0.5 ticks on all four. |
| P4 | Agents | `agents/hypothesis.py`, `validation_agent.py`, `promotion.py`, `loop.py` | KEEP / ADAPT D6 | Bus-wired. Promotion requires sealed PASS + research Risk Core. `HypothesisProposed` has **no** `expected_horizon` today (`schemas_research.py` L131–156). D6: HypothesisAgent sets `expected_horizon` explicitly; missing → `HypothesisRefused`; logged; ValidationAgent refuses if absent. |
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
| S7 | Monitor vs flatten | ADR-0058 + EmergencyFlattenPolicy | ADAPT S3 per **D7, D9, D10** | Research monitor **cannot** send reduce-only (isolation). It **proposes**. Live Risk Core or Position Manager **executes**: deweight/suspend → 50% of that strategy; disable/critical/hard limit → flatten 100% (D9). SLA miss: one logged retry, then Core action; no silent loop (D10). Broker SSOT. |

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
| G-SHDW | Shadow = log signals, hypothetical fills, **no orders** | No `research_execution_mode`. `mode: sim` already allows NT submit (E5 + G19). Paper mode blocks **market data** too. | Blocker | **S0 prerequisite D1** (hard-block) plus shadow bridge |
| G-WL | Explicit SIM whitelist; unknown account rejected | Prefix heuristic (`Sim*`, `DEMO*`, Playback, Backtest). Any `SimFoo` matches. Empty configured name in `sim` still returns ok if connected is non-empty (`guards.py` only mismatches when `configured` is truthy). | Safety | S1 |
| G-LIVE | HMAC `LIVE_RELEASE` + ADR, Risk Core verifies, secret outside agents (D4) | Flag absent. A yaml `enabled: true` plus SHA would be **too weak** (D4). | Safety | S1 |
| G-MUT | Config not agent-mutable; tests prove no bypass | `FORBIDDEN_PARAMETER_KEYS` does not include account/whitelist/`live_release`/`mode`. Hot reload can change `trade_mode`. HMAC secret must never be in agent-writable config. | Safety | S1 |
| G-FILL | Fills → decay monitor **and** cost calibration from one SSOT | Monitor: `observe(signal_id, float)`. Calibrator: `trade_fill_audit.jsonl` `reconciled`. Fabric fill `commission=0.0`. `FillEvent` has no slippage. Two pipelines, neither is research-aware. | Blocker for honest decay | S2 |
| G-COST | ADR-0055 is SSOT; research calibrates to it; execution wins (D3) | Research `CostModel` adds half-spread + slippage + √impact **as cash**. ADR-0055: slippage lives in the fill price; card is cash commission. Dollars on the card **match** Free-plan commissions ($2.87 mini, $0.94 micro). Accounting disagrees. | Truth-seeking | S2 (calibrate; do not let research undercut the card) |
| G-SIMBYP | Independent fail-closed Risk Core on SIM orders | `risk_gates.check_can_trade` returns OK and **bypasses all caps** when `sim_mode or not enforce_rules`. Orchestrator sets `enforce_rules` only for `real`. S3 on `trade_mode=sim` would place NT orders with Brain risk caps off. Fabric `PreTradeRiskEngine` is the remaining size cap (`config.yaml` `max_position_size: 2`). | Safety | S1 policy + S3 mode = `sim_real_guard` with `enforce_rules` aligned to `risk_enforced` |
| G-PGATE | Live `PromotionGate` is the only live promotion path; research must pass Validation Gate first | Live gate does not require sealed `GateReport` / TrialRegistry. Defaults weaker on DSR (0.0 vs 0.95) and window count (5 vs 6). `as_promotion_fragments()` unused. | Skip-gate residual | S3 (AND with sealed research report on **NT PIT** evidence) |
| G-PIT | S3 survivors only from Validation Gate on real NT closed bars (D2) | Research `materialize()` is synthetic. No NT-bar candidate pipeline. Live ingest **is** PIT-correct. | Honesty of “survivors” | **S2.5 mandatory** then S3 |
| G-ENG | Isolate / hard-block ungated order paths (D1, D8) | E5 still auto-places on confluence. Also: `reasoning_service`, `trade_workers`, `paper_trade_executor`, `PaperSimulator.try_open`. Archive is isolated. | Mix / skip | **S0 prerequisite**; supervisor stays closed for research **after S3** (D8) |
| G-RED | Alarm + open position: research proposes; Risk Core/Position Manager executes (D7, D9, D10) | Monitor can publish `research.signal.deweighted`. Nothing in KEEP executes a reduce-only or timed flatten. Fabric flatten is watchdog/emergency, not decay. | Binding miss | S3 executor + D9 size map + D10 SLA tests; S0/S1 only log proposals (no open research positions if D1 holds) |
| G-CS | C# account tests | Python `test_ninjatrader_guards.py` covers prefix/mismatch. **Zero** Fabric.Tests for `only_sim_accounts_allowed`. | Bypass in AddOn | S1 |
| G-DOC | Architecture lists research | `docs/architecture.md` omits `lumina_research` / `research.*`. | Observability | S0 (docs in the implementation PRs; this plan is the spec) |
| G-HORIZ | No silent default for `expected_horizon` (D6) | Nowhere on `HypothesisProposed` / `PromotionCandidate` / `SignalIntent`. CPCV `label_horizon` is a different concept (purge t1). | Contract | S0 schema + HypothesisAgent + gate |
| G-SURV | 2–3 independent **NT-PIT** survivors before SIM orders (D2, D5, D11) | None on NT tape. Phase 2 loop produces sealed candidates from **planted_edge vs noise**. Phase 4 floors are synthetic-campaign numbers. No pairwise correlation cap. | Process | S2.5 + S3; synthetics never count; D11 both-clauses |

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
- Decisions D1–D11 override earlier draft recommendations in this file.

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
| `expected_horizon` | int bars ≥ 1 | **required (D6)**. No default. Missing → schema/refuse, no log fill. |
| `validation_mac` | str 64 | copy from candidate |
| `issue_mac` | str 64 | copy from candidate |
| `source` | literal `research_bridge` | |

**`OrderIntent` (live schema ADAPT)** — add optional fields with defaults so existing constructors keep working:

- `strategy_id: str = ""`
- `expected_horizon_bars: int = 0`
- `submitted_at_utc: datetime | None = None`

Binding `timestamp` = `submitted_at_utc`. Binding `direction` = existing `side`. Binding `size` = existing `quantity`. Research-originated intents with empty `strategy_id` or `expected_horizon_bars < 1` are refused in S0 and S3 (D6). Do not copy `oos_size` or the monitor window of 20 into this field.

**`FillEvent` (reconciler dataclass ADAPT)** — add:

- `slippage_ticks: float = 0.0`
- `slippage_usd: float = 0.0`
- `commission_ticks: float = 0.0`
- `source: literal["broker","hypothetical_adr0055"] = "broker"`
- property `fill_price` → `price`, `qty` → `quantity` (binding names without renaming the SSOT fields)

Do **not** create a third fill type. Map `ExecutionFill` ↔ `FillEvent` 1:1 in the translator.

Issuer guard: only `research_bridge` (and in S2 `fill_translator`) may publish `research.execution.*`. Existing research agents must fail if they try (attack test).

---

### 3.1 S0 — Shadow wiring (D1 freeze is a prerequisite)

**Goal.** (1) **Hard-block every ungated order path** so SHADOW means no NT/paper/SIM orders except flatten/cancel. (2) Sealed `PromotionCandidate`s become logged `SignalIntent`s with a required `expected_horizon`. (3) Hypothetical fills use **ADR-0055 commission** and **slippage in the fill price** (D3), reported in ticks and $. **Zero** `PlaceOrderCommand`. **Zero** risk-increasing `place_order()`. Monitor `observe()` may be fed from those hypothetical net returns so decay plumbing is real before SIM.

A yaml `research_execution_mode: shadow` is **not** the control. The freeze is a **code tripwire** that fails closed even if `mode: sim` and even if the yaml key is missing or set to `sim`.

#### S0 prerequisite — ungated order freeze (D1)

Must land in the same S0 PR as the bridge (or a stacked PR that **merges before** the bridge is enabled). If the freeze tests are red, the bridge must not subscribe.

Block **new risk-increasing orders** from these product callers (evidence in §1.1 / grep):

| Path | Symbol |
|------|--------|
| `lumina_core/engine/supervisor_tick_exec.py` | `run_tick_exec` → `app.place_order` |
| `lumina_core/engine/operations_service_orders.py` | `place_order` |
| `lumina_core/engine/policy_engine.py` | `execute_order` → `broker.submit_order` |
| `lumina_core/engine/reasoning_service.py` | `submit_order` / `execute_order` |
| `lumina_core/trade_workers.py` | `submit_order_with_risk_check` |
| `lumina_core/engine/paper_trade_executor.py` | `broker.submit_order` |
| `lumina_core/engine/paper_simulator.py` | `try_open` |

**Allow** during the freeze (do not break fail-closed exits):

- Fabric watchdog cancel / session-touched flatten (`HeartbeatWatchdog`, `EmergencyFlattenPolicy`).
- Operator emergency flatten/cancel: `lumina_os/backend/emergency_order_endpoints.py`.
- Risk-reducing / flatten intents tagged `reduce_only` or emergency (Admission `is_risk_reducing_side`).

Implementation shape: NEW `lumina_core/order_gatekeeper/ungated_place_block.py` with `assert_validation_gate_or_block(source, *, reduce_only) -> tuple[bool, str]`. Call it at the **start** of `OperationsOrdersMixin.place_order` and `PolicyEngine.execute_order` (the two funnels). Supervisor and reasoning go through those funnels today; still add an explicit guard in `run_tick_exec` so a future bypass of `place_order` cannot skip it. Reason code: `UNGATED_PLACE_BLOCKED_S0`. S3 later allows `source_agent="research_bridge"` **only** when `sim_gate` passes; that allow-list is **empty** in S0/S1. **D8:** `run_tick_exec` is never added to the research allow-list. Non-research `place_order` stays denied unless a later ADR + human logged release exists; even then AdmissionChain (SIM whitelist or valid `LIVE_RELEASE`) must pass.

AST inventory test: every production (non-`tests/`, non-`archive/`) call to `place_order` / `execute_order` / `submit_order` / `try_open` is either behind this block or on the emergency/flatten allow-list. New callers without the block fail CI.

#### Files (bridge + freeze)

| Action | Path |
|--------|------|
| NEW | `lumina_core/order_gatekeeper/ungated_place_block.py` — D1 tripwire |
| ADAPT | `operations_service_orders.py`, `policy_engine.py`, `supervisor_tick_exec.py`, `reasoning_service.py`, `trade_workers.py`, `paper_trade_executor.py`, `paper_simulator.py` — call the tripwire |
| NEW | `lumina_core/research_bridge/__init__.py` |
| NEW | `lumina_core/research_bridge/port.py` — `ResearchExecutionPort` (Protocol: `on_candidate`, `shadow_fill`, `assert_no_broker_submit`) |
| NEW | `lumina_core/research_bridge/shadow_runtime.py` — subscribe `RESEARCH_PROMOTION_TOPIC`; verify MAC; emit `SignalIntent`; hypothetical fill per D3; `observe`; JSONL |
| NEW | `lumina_core/research_bridge/horizon.py` — require `expected_horizon_bars ≥ 1`; **no default**; missing → refuse (D6) |
| NEW | `lumina_core/research_bridge/jsonl.py` — `state/research_shadow.jsonl` |
| NEW | `lumina_core/agent_orchestration/schemas_research_execution.py` |
| NEW | `lumina_core/ports/research_execution.py` |
| ADAPT | `schemas.py` — register three topics in `EVENT_BUS_TOPIC_MODELS` **and** `CRITICAL_EVENT_BUS_TOPICS` |
| ADAPT | `schemas_research.py` — **`expected_horizon_bars: int` required ≥ 1** on `HypothesisProposed` and `PromotionCandidate` (no default). `HypothesisAgent._accept` refuses if the generator did not set it; log the value. |
| ADAPT | `lumina_research/agents/hypothesis.py`, `agents/generators.py` — generators must supply horizon explicitly; ValidationAgent rejects missing/zero. |
| ADAPT | `lumina_core/risk/schemas.py` — optional OrderIntent fields listed in §3.0 |
| ADAPT | `lumina_core/engine/trade_reconciler/schemas.py` — FillEvent slippage/source/aliases |
| ADAPT | `lumina_core/broker/ninjatrader/promotion_gate.py` — do **not** add submit for a fake `shadow` trade_mode |
| NEW | `config.yaml` key `research_execution_mode: shadow` (legal `off\|shadow\|sim`; **missing = off**). This key is **observability**, not the freeze. |
| NEW | `docs/adr/0059-research-bridge-shadow-first.md` |
| ADAPT | `docs/architecture.md` — Research context + freeze + bridge |
| NEW tests | see below |
| FORBIDDEN | relaxing `risk_gates` SIM bypass; Fabric `HandlePlace` allow; `NtAccountOrderGateway.PlaceOrder` allow; silent horizon defaults; counting synthetic candidates as live survivors; re-arming `supervisor_tick_exec` for research (D8) |

`shadow_runtime` may import `lumina_research.agents.provenance` and `lumina_core.market.nt_fees` (ADR-0055). It may import research `CostModel` **only** to record the research estimate **beside** the execution-side numbers for later calibration (D3). Hypothetical **FillEvent** fields that feed the monitor/calibrator-preview must be execution-side: commission from `nt_fees.fee_components`, slippage from (hypothetical fill price − reference) / tick_size, **not** an added cash tick. If the two disagree, log `cost_discrepancy` and **keep execution-side**. Stale/missing closed NT bar → no hypothetical fill, log `shadow_fill_refused:stale_or_missing_market`.

S0 does **not** require a new strategy engine. Synthetic Phase 2 loops remain valid **unit/acceptance** wiring tests (D2). They must tag `tape=synthetic` so they cannot be mistaken for S3 survivors.

#### Tests (S0)

| Test file | What it proves |
|-----------|----------------|
| `tests/order_gatekeeper/test_ungated_place_block.py` | `run_tick_exec` with `BUY`/`SELL` + high confluence **does not** call `place_order` / Fabric / `PaperSimulator.try_open`. `OperationsOrdersMixin.place_order("BUY", 1)` returns false / blocked with `UNGATED_PLACE_BLOCKED_S0`. `policy_engine.execute_order` same. `submit_order_with_risk_check` same. Flatten/cancel/`reduce_only` still reaches broker mock. |
| `tests/order_gatekeeper/test_ungated_place_inventory.py` | AST scan of `lumina_core/**/*.py` and `lumina_os/**/*.py`: every `place_order`/`execute_order`/`submit_order`/`try_open` is either the block helper, emergency flatten, or a listed allow. Fail on a new caller. |
| `tests/order_gatekeeper/test_yaml_mode_is_not_enough.py` | `research_execution_mode=sim` **and** `mode=sim` in a fixture config still blocks ungated place (D1: config alone is not enough). |
| `tests/research_bridge/test_shadow_never_places.py` | Sealed candidate: Fabric `place_order_sync` / `NinjaTraderBroker.submit_order` not called. |
| `tests/research_bridge/test_signal_intent_fields.py` | Payload has `strategy_id, direction, size, timestamp, expected_horizon`. Missing horizon → refuse, no JSONL fill. `oos_size=30` without horizon still refuses. |
| `tests/research/test_hypothesis_horizon_required.py` | HypothesisAgent without explicit horizon raises `HypothesisRefused`. With horizon, experiment JSONL contains the value. |
| `tests/research_bridge/test_hypothetical_costs_adr0055.py` | MES qty 1 commission_usd = 0.94; ES = 2.87; MNQ ≠ NQ. Slippage_usd comes from fill vs reference, not a fourth cash leg. Research four-leg total if higher is logged as discrepancy; FillEvent uses execution-side. |
| `tests/research_bridge/test_stale_market_no_fill.py` | Forming-only book → no FillEvent, no observe, intent logged `fill=refused`. |
| `tests/research_bridge/test_unsigned_candidate_refused.py` | Forged candidate does not log a SignalIntent. |
| `tests/research_bridge/test_issuer_guard.py` | `hypothesis_agent` cannot publish `research.execution.signal_intent`. |
| `tests/research_bridge/test_supervisor_cannot_place.py` | Replaces former `test_supervisor_unaffected`: supervisor cannot place **and** cannot change `ctx.signal` into a research order. |
| `tests/agent_orchestration/test_research_execution_topics_additive.py` | Existing topics unchanged. |
| ADAPT `tests/research/test_phase2_isolation.py` | Agents still must not import broker / live risk. |

#### Acceptance (S0)

1. Ungated BUY/SELL from supervisor, ops `place_order`, policy, reasoning, trade_workers, and paper open **cannot** reach NT or paper simulator. Emergency flatten still can.
2. Setting yaml to `sim` does not lift the freeze.
3. `state/research_shadow.jsonl` contains SignalIntents with explicit `expected_horizon`; missing horizon produces zero fills.
4. Hypothetical FillEvent commission matches ADR-0055 per root; ticks and $ both present.
5. Synthetic Phase 2 loop may still run as a **test**; its candidates are labeled synthetic and are not S3 survivors.
6. ADR-0059 merged or attached.

#### Rollback (S0)

Revert the S0 PR: freeze lifts **and** bridge unsubscribes together (do not lift freeze while leaving a half-wired bridge). `research_execution_mode: off`. No research positions should exist if D1 held. Research Phases 1–4 remain. D8 still forbids treating a revert as a license to auto-place research from `supervisor_tick_exec` in a later PR without ADR + human.

---

### 3.2 S1 — SIM whitelist and `LIVE_RELEASE` guard

**Goal.** Risk Core (Python) **and** Fabric (C#) reject any account not on an explicit operator list. `LIVE_RELEASE` is an **HMAC-signed review/token** (D4) plus a human-reviewed logged ADR; the live Risk Core verifies the signature; invalid or missing → reject. Agents cannot mint, rotate, or read the HMAC secret. Tests include bypass/attack cases. **Still no research SIM orders.** D1 freeze **stays on**.

S1 may follow S0 once ADR-0059 exists. It must not enable S3 and must not lift the ungated-place block.

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
| NEW | `lumina_core/risk/live_release.py` — `LiveRelease` frozen record verified **inside the live Risk Core**: `enabled: bool`, `adr_path: str`, `adr_sha256: str`, `approved_by: str` (must not be a research/agent id), `approved_at_utc: datetime`, `mac: str` (HMAC-SHA256 hex, 64 chars). `verify(secret) -> (ok, reason)`. Missing record, missing/short mac, wrong mac, agent `approved_by`, or `enabled` false → reject. **A file that has `adr_sha256` but no mac is refused** (`live_release_hmac_required`) — D4 forbids plain file+hash. |
| NEW | HMAC secret: env `LUMINA_LIVE_RELEASE_SECRET` (same class as `LUMINA_FABRIC_TOKEN`). Not in `config.yaml`, not in `fabric.json`, not in the Event Bus, not readable from `lumina_research/**`. Empty/missing secret → every REAL check fails closed (`live_release_secret_missing`). |
| ADAPT | `lumina_core/risk/final_arbitration.py` or a dedicated admission step `live_release` — Risk Core calls `LiveRelease.verify`. Do not verify only in the broker façade. |
| ADAPT | `guards.py` REAL branch — require Core-verified live_release; else `live_release_required`. Keep `real_account_blocked_pending_promotion_adr` as a second reason if demo name. |
| ADAPT | `NtAccountOrderGateway.PlaceOrder` REAL branch — defense in depth: reject `ModeContext=real` unless Fabric has seen a **Brain-attested** live-release ok (do not duplicate the secret into C# if that would copy it into `%APPDATA%`). Prefer: Brain never sends REAL `mode_context` unless Core verified; Fabric rejects REAL when `LiveReleaseEnabled` is false (operator boolean **is not** sufficient without Brain attestation). |
| ADAPT | `lumina_core/code_evolution/operators.py` `FORBIDDEN_PARAMETER_KEYS` — add `live_release`, `sim_account_whitelist`, `account_name`, `RealAccountName`, `research_execution_mode`, `mode`, `trade_mode` |
| ADAPT | `lumina_core/code_evolution/proposal.py` `FORBIDDEN_TARGET_PREFIXES` — add `config.yaml`, `fabric.json`, `lumina_core/risk/live_release`, `lumina_core/risk/sim_account_guard`, `order_gatekeeper/ungated_place_block` |
| ADAPT | `lumina_core/runtime_config_reloader.py` — refuse hot-reload of whitelist / `live_release` / `research_execution_mode` / `trade_mode` / freeze (log `config_reload_refused:protected_key`). Operator change requires process restart. |
| ADAPT | Isolation AST: `lumina_research/**` must not reference `LUMINA_LIVE_RELEASE_SECRET` or `live_release.py`. |
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
  mac: ""
research_execution_mode: shadow
```

Committed `mac` must stay empty. The operator stores the HMAC secret only in the environment (or OS secret store). Launchers must not write the secret into `config.yaml` or `fabric.json`.

Empty `sim_account_whitelist:` (or omitted) **denies** every account. That is the opposite of today’s “configured empty → skip match”.

#### Tests (S1) — including bypass / attack

Python:

| Test | Proves |
|------|--------|
| `tests/broker/test_sim_whitelist.py` | `Sim101` on list + match → ok. `Sim202` not on list → reject even though `is_local_sim_name` is true (prefix bypass dead). `DEMO5042070` not on list → reject. |
| `tests/broker/test_sim_whitelist_empty_denies.py` | `whitelist=[]` + `Sim101` → deny. Missing key → deny. |
| `tests/broker/test_sim_whitelist_case.py` | Exact NT name; document casefold policy (recommend casefold match, store canonical). |
| `tests/risk/test_admission_whitelist_step.py` | AdmissionChain without the step fails closed in `sim`/`sim_real_guard`/`real`. Step sees connected account `LiveAcct` → reject. |
| `tests/risk/test_live_release.py` | `enabled=false` → REAL denied. `enabled=true` with `adr_sha256` but **empty mac** → `live_release_hmac_required` (D4). Wrong mac → reject. Missing secret env → reject. Valid HMAC + human `approved_by` + ADR hash → this check ok (other REAL gates still apply). Agent id as `approved_by` → reject. |
| `tests/risk/test_live_release_attack.py` | (1) env `TRADE_MODE=real` without live_release → deny. (2) hot-reload flipping `enabled` → refused. (3) code-evolution tweak → `forbidden_parameter_key`. (4) research governance cannot write. (5) bus reload request → refused. (6) research AST forbids the secret name. (7) truncated/flipped mac → reject. (8) `ungated_place_block` still on: even a valid LIVE_RELEASE does **not** allow S0/S1 SIM research orders. |
| `tests/code_evolution/test_forbidden_whitelist_keys.py` | `FORBIDDEN_PARAMETER_KEYS` contains the new names; sandbox worker copy in `sandboxed_code_worker.py` updated to match. |
| `tests/risk/test_orchestrator_enforce_rules_follows_capabilities.py` | `sim_real_guard` ⇒ `enforce_rules True`; `sim` ⇒ False; `real` ⇒ True. |
| ADAPT `tests/broker/test_ninjatrader_guards.py` | Old “DEMO allowed in sim when names match” **fails** unless DEMO is on the whitelist. Update tests to the new law; do not keep the prefix allow. |

C# (new; gap G-CS):

| Test | Proves |
|------|--------|
| `integrations/ninjatrader8/Lumina.Execution.Fabric.Tests/SimWhitelistTests.cs` | Empty whitelist → reject. Name not in list → `sim_account_not_whitelisted`. `Sim101` in list → admit past **this** check (other gates still run). Prefix `Sim999` not in list → reject. |
| `LiveReleaseTests.cs` | `ModeContext=real` without Brain-attested live-release → reject even on a Sim name. A Fabric boolean without HMAC attestation is not sufficient. S1 still does not bind a live brokerage name (`real_account_blocked`). |

#### Acceptance (S1)

1. A SIM order attempt to an account not on the list is rejected in Python **and** C#. Empty list denies `Sim101`.
2. Prefix `Sim999` not on the list is rejected.
3. `LIVE_RELEASE` without HMAC, with a wrong HMAC, or with a missing secret is rejected by the **Risk Core**. File+hash without mac is rejected.
4. Repo `config.yaml` remains `live_release.enabled: false` and `mac: ""`. Secret is not in git.
5. D1 freeze still blocks ungated places (including with yaml `mode: sim`). D8: supervisor cannot place research even if a later PR sets `research_execution_mode: sim`.
6. Isolation tests still pass. ADR-0060 exists.

#### Rollback (S1)

**Do not** roll back to prefix-allow (that re-opens G-WL). Rollback = git revert **forward** to “deny all SIM submits except the previous explicit list” by restoring the last known good whitelist in operator `fabric.json`, or set whitelist to `[]` (desk stops). Flag `research_execution_mode` stays `shadow`/`off`.

---

### 3.3 S2 — Fill feedback to monitor and cost calibration

**Goal.** One fill SSOT. Broker fills (and S0 hypothetical fills) share `FillEvent`. Decay monitor and cost calibrator both consume that type. **ADR-0055 is SSOT** (D3): commission from the NT card; slippage from fill price vs reference. The research `CostModel` **calibrates to** those broker fills. On discrepancy, **execution-side wins**. Ticks and $ are both logged per root. MES/MNQ are calibrated **separately** from ES/NQ.

#### Files

| Action | Path |
|--------|------|
| NEW | `lumina_core/research_bridge/fill_translator.py` — `FillEvent` / `ExecutionFill` / reconciler row → `observe(signal_id, metric)` **and** calibrator row. `strategy_id` from order metadata / `correlation_id` map. Unmapped fills still go to calibrator (desk-level costs) but **not** to a random signal’s decay series. |
| NEW | `lumina_core/research_bridge/fill_index.py` — `client_order_id → strategy_id` (S0: hypothetical ids; S3: real client_order_id). |
| ADAPT | `lumina_core/broker/ninjatrader/fabric_mapper.py` `order_event_to_fill` — stamp `commission` from `lumina_core.market.nt_fees.fee_components` (Free-plan all-in × qty). Do not leave `0.0`. Slippage: `slippage_ticks = (fill_price - reference_price) / tick_size` when reference is on the originating `OrderIntent`; else omit (do not invent). |
| ADAPT | `lumina_core/engine/trade_reconciler/fill_normalization_mixin.py` — copy slippage/commission onto `FillEvent`. |
| ADAPT | `lumina_core/engine/trade_reconciler/finalize_mixin.py` — `reconciled` JSONL includes `slippage_ticks`, `slippage_usd`, `commission_ticks`, `commission`, `fill_price`, `qty`, `strategy_id`, `source`. |
| ADAPT | `lumina_core/risk/cost_model_calibrator.py` — read those fields; group **by root** (ES vs MES separate). Do not mix mini and micro. |
| NEW | `lumina_research/validation/cost_calibrate.py` (or KEEP-side writer that **does not** let agents mutate `limits.toml`) — compare research four-leg estimate to ADR-0055 + observed fill slippage; write `state/research_cost_calibration.json`. Research coefficients may **tighten** (never cheapen commission below the card). Execution-side numbers remain the FillEvent SSOT. |
| ADAPT | `lumina_research/monitoring/loop.py` / KEEP bridge — **KEEP calls `observe`**. Monitoring still does not import broker. |
| ADAPT | `ExecutionFill` — optional `slippage` / `commission_ticks` with defaults 0; `extra=forbid`. |
| ADAPT | `scripts/validation/run_cost_model_calibration.py` — per-root; assert research estimate ≥ execution commission (never undercut the card). |
| NEW tests | see below |
| FORBIDDEN | research importing `lumina_core.broker`; changing ADR-0055 card formula; using research four-leg cash as FillEvent commission; Fabric proto commission field |

`source=hypothetical_adr0055` (S0) vs `source=broker` (S2/S3). Live calibrator **`state/cost_model_calibration.json`** is **broker fills only**. Research calibration file is separate. Hypothetical fills never write the live calibrator.

On discrepancy (research total_usd ≠ commission_card + fill_slippage): log `cost_discrepancy`; **FillEvent and live calibrator keep execution-side**; research file records the delta for honesty.

#### Tests (S2)

| Test | Proves |
|------|--------|
| `tests/research_bridge/test_fill_ssot.py` | One `FillEvent` fixture fans out to monitor `series()` **and** calibrator `load_reconciled_rows`; mutating only JSONL without FillEvent is not sufficient (translator is the API). |
| `tests/research_bridge/test_unmapped_fill_not_observed.py` | Fill without `strategy_id` updates calibrator, not monitor. |
| `tests/broker/test_fabric_mapper_commission.py` | MES qty 1 commission = 0.94; ES qty 1 = 2.87; MNQ ≠ NQ. Not 0.0. |
| `tests/broker/test_fill_slippage_ticks.py` | BUY fill 1 tick above reference → `slippage_ticks=1`, `slippage_usd=tick_value`. |
| `tests/risk/test_cost_model_calibration_per_root.py` | ES and MES rows do not share a rolling mean. |
| `tests/research_bridge/test_hypothetical_excluded_from_live_calibration.py` | `source=hypothetical_adr0055` never writes `state/cost_model_calibration.json`. |
| `tests/research/test_cost_model_does_not_undercut_card.py` | After calibration, research commission_usd ≥ ADR-0055 all-in for that root; slippage is not added as a second cash ticket on a fill that already moved. |
| `tests/research_bridge/test_discrepancy_execution_wins.py` | Fixture where research four-leg > card: FillEvent.commission stays card; discrepancy logged. |
| `tests/research/test_phase4_isolation.py` | still no broker import from `lumina_research/monitoring`. |
| ADAPT `tests/risk/test_cost_model_calibration.py` | new fields; per-root MES vs ES. |

#### Acceptance (S2)

1. A fixture broker fill with known price/qty produces identical `(fill_price, qty, slippage, commission)` in JSONL, `FillEvent`, live calibrator input, and (if mapped) monitor observe.
2. Commission is the ADR-0055 Free-plan all-in, per root, in $; ticks = `$ / tick_value_usd`; slippage is fill vs reference, not a cash tick on the card.
3. Research four-leg estimate cannot undercut the card; execution-side wins on discrepancy.
4. Hypothetical fills never pollute live calibration.
5. Isolation tests green.

#### Rollback (S2)

Stop the translator subscription; monitor can still be fed by S0 hypothetical path only; calibrator reverts to previous JSONL fields (backward compatible if new keys are optional). Git revert S2 PR.

---

### 3.3.1 S2.5 — PIT NT-bar tape for the Validation Gate (mandatory, D2)

**Goal.** Research candidates that might become S3 survivors are evaluated with `passes_validation_gate` on **closed NT Last bars** (ADR-0053/0054), not on `lumina_research/agents/synthetic.py`. Synthetic tapes remain for unit, campaign, mutation, and calibration tests only.

| Action | Path |
|--------|------|
| NEW | `lumina_research/validation/nt_tape.py` — read-only adapter: closed-book OHLC from KEEP `MarketDataManager` / fixture replay → returns series for `evaluate_candidate`. Forming bars refused. Look-ahead = reject. |
| ADAPT | `ValidationAgent` — production/survivor path requires `tape_kind="nt_pit"` provenance on `ValidationResult` (new required field or fail-closed default `synthetic`). |
| ADAPT | `PromotionAgent` — refuse candidate if validation `tape_kind != "nt_pit"` when `admit_for_sim=true`. Tests may still promote synthetic **only** into test registries. |
| NEW tests | `tests/research/test_nt_tape_no_lookahead.py`, `tests/research/test_synthetic_cannot_be_survivor.py` |
| FORBIDDEN | downloading vendor CSV as a silent substitute for NT closed bars; using planted_edge gauss as `nt_pit`. |

Acceptance: a fixture of NT closed MES/MNQ bars produces a `ValidationResult` with `tape_kind=nt_pit`; the same candidate on `materialize()` is `tape_kind=synthetic` and `check_sim_entry.py` will not count it.

Rollback: revert S2.5; S3 cannot enable (gate fails closed with `survivors_not_nt_pit`).

---

### 3.4 S3 — SIM orders, gated

**Goal.** Research-originated `OrderIntent`s may reach Fabric **only if** all gates below pass. Still **not** LIVE (`LIVE_RELEASE` HMAC must verify as disabled / not valid for REAL). Account on the S1 whitelist. First instruments **MES and MNQ only** (D5). **D8:** `supervisor_tick_exec` stays **permanently closed for research**; S3 does not re-arm confluence. The **only** new allow is `source_agent="research_bridge"` after `sim_gate`. Non-research (manual/legacy) stays default-closed unless ADR + human logged release, then Risk Core.

#### Entry criteria (machine-checkable)

All must be true; missing evidence = reject (`research_sim_gated`):

1. `research_execution_mode: sim` set by operator **restart** (not hot reload). Yaml alone does not lift D1 for ungated paths.
2. `live_release.enabled` is false **or** HMAC does not verify as a REAL release. S3 is SIM; mixing REAL release with first SIM is refused.
3. Connected NT account ∈ `sim_account_whitelist`.
4. Trade mode is **`sim_real_guard`** (not `sim`), with `ENABLE_SIM_REAL_GUARD=true`. Session guard + equity snapshot apply.
5. Instrument ∈ **{MES, MNQ}**. ES/NQ `OrderIntent` → `sim_instrument_not_yet_released` until a later stability ADR.
6. **Survivors:** ≥ 2 and ≤ N **independent** signals in `LiveSignalRegistry` with `stage in {active, deweighted}`, each with:
   - sealed `PromotionCandidate` + `ValidationResult` with `passes_validation_gate` true;
   - **`tape_kind="nt_pit"`** (D2). `tape_kind="synthetic"` never counts, even if the gate passed in a unit test;
   - **D11 independence — both clauses required:**
     - different economic hypothesis **and** family (distinct `hypothesis_id` is necessary but not sufficient; two clones of the same `config_id` never count; MES+MNQ of the **same** family count as one);
     - pairwise return (or residual return) correlation **< 0.5** over the evaluation period. Missing corr series → not independent (`survivors_corr_unavailable`);
   - explicit `expected_horizon_bars ≥ 1` (D6);
   - shadow/PIT fill history ≥ `expected_horizon` and ≥ ADR-0058 window from **FillEvent SSOT** (broker or S0 hypothetical **on NT bars**, not gauss).
7. Empirical monitoring thresholds on that **NT-bar** shadow series (synthetic campaign in `test_phase4_campaign.py` is necessary but **not sufficient**). If live/shadow FAR on healthy NT-tape controls cannot be measured, **do not enable** S3.
8. Live `PromotionGate.evaluate` on `GateReport.as_promotion_fragments()` **plus** HMAC of the same NT-PIT `ValidationResult`. Dictionary-only evidence → reject.
9. Twin/human: `sim.approval_required: true` stays on.

If any check fails, bridge stays in shadow behavior even if the yaml says `sim`.

#### Files

| Action | Path |
|--------|------|
| ADAPT | `ungated_place_block.py` — allow-list **only** `source_agent="research_bridge"` after `sim_gate` ok. **Never** allow `supervisor_tick_exec` / confluence for research (D8). Non-research sources stay denied unless an ADR + human logged release is present; then still AdmissionChain. |
| ADAPT | `lumina_core/research_bridge/shadow_runtime.py` → `sim_runtime.py`: `sim` builds live `OrderIntent` (MES/MNQ only) and calls **existing** `enforce_pre_trade_gate` + `FinalArbitration` + `NinjaTraderBroker.submit_order`. No new broker. |
| NEW | `lumina_core/research_bridge/sim_gate.py` — entry criteria 1–9 including D11 corr; returns `(ok, reason)`. |
| NEW | `lumina_core/research_bridge/independence.py` — pairwise return / residual-return correlation; threshold **< 0.5**; fail-closed if series too short. |
| ADAPT | `lumina_core/evolution/promotion_gate.py` — require `validation_mac` / `report_sha256` / `tape_kind=nt_pit` when `source=research`. |
| NEW | `lumina_core/risk/alarm_executor.py` — **D7/D9/D10 executor** in the Risk Core context (not in `lumina_research`). Subscribes to `research.signal.deweighted` / `suspended` / `retired` / `research.guardian.finding`. Research still only **proposes**. This module (with `LivePositionManager` for book qty) **executes** through AdmissionChain. **D9 size:** deweight/suspend → **50% of that strategy’s qty** (`reduce_only`); disable/retired/critical/hard DD/prolonged disconnect → **flatten 100%** of that strategy (account flatten only if Core kill-switch / Fabric emergency). **D7 SLA:** default → next bar or ≤ 5 min; critical → ≤ 1 min. **D10 miss:** first miss → log + alarm + **one retry**; second miss **or** wall time **> 10 min** → Core action for that strategy (reduce or flatten by D9); **no infinite silent retry**. Broker `GetAccountState` is SSOT after; reconcile on reconnect. |
| ADAPT | `lumina_core/engine/live_position_manager.py` — book qty for the executor; does not decide severity. |
| ADAPT | `fabric_mapper.order_to_place_command` — `reduce_only` true for D9 50% reduces; flatten is close-to-flat of that strategy; `mode_context=sim_real_guard`; `correlation_id` = strategy_id + client_order_id. |
| ADAPT | `config.yaml` — do not commit `research_execution_mode: sim`. |
| NEW | `scripts/research/check_sim_entry.py` — survivors with `tape_kind=nt_pit`, D11 independence (family **and** corr < 0.5), FAR, whitelist, live_release HMAC disabled, MES/MNQ, supervisor still blocked; exit 0 only if criteria pass. |
| NEW tests | below |
| FORBIDDEN | `LIVE_RELEASE` HMAC valid for REAL; `trade_mode: real`; ES/NQ research orders; synthetic survivors; research calling `place_order`; relaxing SIM cap bypass; archive birth; re-arming `supervisor_tick_exec` for research; counting correlated clones as two survivors. |

#### Tests (S3)

| Test | Proves |
|------|--------|
| `tests/research_bridge/test_sim_gate_requires_survivors.py` | 0 or 1 survivor → no `place_order`. 2 **D11-independent nt_pit** → gate ok in fixture. Two clones same `config_id` → not independent. Two **synthetic** gate-passes → still refuse. |
| `tests/research_bridge/test_survivor_independence.py` | Same family, corr 0.2 → not independent. Different family, corr 0.7 → not independent. Different family, corr 0.3 → independent. Missing series → `survivors_corr_unavailable`. Threshold is **strictly < 0.5** (0.5 is not independent). |
| `tests/research_bridge/test_sim_gate_mes_mnq_only.py` | ES/NQ OrderIntent refused with `sim_instrument_not_yet_released`. MES/MNQ allowed when other gates pass. |
| `tests/research_bridge/test_sim_gate_mode.py` | `trade_mode=sim` → refuse research orders. `sim_real_guard` + env → ok. `real` → refuse. |
| `tests/research_bridge/test_sim_still_shadow_when_yaml_lies.py` | yaml `sim` but survivors < 2 or synthetic-only → no Fabric call. D1/D8 still block supervisor. |
| `tests/research_bridge/test_supervisor_stays_closed_after_sim_gate.py` | After `sim_gate` ok, `run_tick_exec` BUY/SELL still cannot `place_order`. Research bridge can. (D8) |
| `tests/research_bridge/test_non_research_default_closed.py` | Manual/legacy `place_order` without logged ADR+human release is denied even when `sim_gate` is ok. With a fixture release, still requires Risk Core whitelist / LIVE_RELEASE. |
| `tests/research_bridge/test_research_order_hits_admission.py` | Whitelist, constitution, arbitration invoked; reject anywhere → no Fabric. |
| `tests/research_bridge/test_promotion_gate_requires_mac.py` | Evidence dict without MAC or without `nt_pit` → reject. |
| `tests/risk/test_alarm_executor_default_reduce.py` | Deweight **or suspend** proposal + open qty 2 → executor submits reduce-only qty 1 (50%) through AdmissionChain. Research modules are not in the stack trace of `submit_order`. (D9) |
| `tests/risk/test_alarm_executor_critical_flatten.py` | Retired / disable / hard DD / prolonged disconnect / critical guardian finding → flatten that strategy (qty to 0). Account-wide flatten only if Core kill-switch / Fabric emergency fires. (D9) |
| `tests/risk/test_alarm_executor_sla.py` | Default proposal executed by next bar or ≤ 5 min in the fake clock. Critical ≤ 1 min. **First miss:** log + alarm + exactly one retry, no flatten yet. **Second miss** or **t > 10 min:** Core action for that strategy (50% or flatten by D9). Third miss does not retry forever. (D10) |
| `tests/research_bridge/test_disconnect_no_new_orders.py` | SAFE_MODE / disconnect: no new research places; reconcile on reconnect. |
| `tests/research_bridge/test_stale_equity_blocks_sim.py` | Stale snapshot → no **new** research order; reduce-only still allowed if `is_risk_reducing_side`. |
| `tests/research/test_monitor_cannot_place.py` | AST: `lumina_research/monitoring` still has no broker/`place_order` import. |
| C# | Heartbeat/flatten + S1 whitelist tests still pass. |

#### Acceptance (S3)

1. `python scripts/research/check_sim_entry.py` exit 0: ≥2 **D11-independent nt_pit** survivors, MES/MNQ, whitelist, `sim_real_guard`, LIVE_RELEASE HMAC not enabling REAL, supervisor still blocked.
2. First research order is MES or MNQ on a **whitelisted SIM** account. ES/NQ research orders are rejected. `run_tick_exec` still cannot place.
3. Fills return on `TradingStream`, become `FillEvent(source=broker)` with ADR-0055 commission, update monitor and live calibrator.
4. Kill NT or Brain: Fabric SAFE + cancel non-protected; no new places; reconcile on reconnect (`GetAccountState`).
5. Alarm: research JSONL shows a **proposal**; Risk Core `alarm_executor` JSONL shows the **execution** (D9: 50% on deweight/suspend, flatten on disable/critical) within SLA. First SLA miss retries once; second miss or >10 min → Core action (D10). Research did not call Fabric.
6. Logs/alerts: every reject, every alarm execution, every SLA miss; Telegram `ops` / `evolution`, not a `real_safety` spam path.

#### Rollback (S3)

1. Immediate: `research_execution_mode: shadow` + restart. Bridge allow-list empties (D1 freeze fully on again; D8 supervisor stays closed). Open research positions: `alarm_executor` on a retire-all **proposal** (D9: flatten 100% of those strategies), or operator emergency flatten. Account-wide flatten only if Core kill-switch / Fabric emergency.
2. Git revert S3 PR. S0–S2.5 remain.
3. Fabric watchdog unchanged.

---

### 3.5 What this plan never does

- Rewrite `lumina_research` into the engine.
- Point research agents at `place_order`.
- Enable REAL / `LIVE_RELEASE`.
- Use `archive/birth-v1/` fitness or curricula.
- Trust prefix `Sim*` as a whitelist.
- Calibrate live costs on hypothetical fills.
- Flatten the whole book because a monitor z-test fired (D9: deweight/suspend is 50% of **that strategy**; flatten 100% of that strategy on disable/critical; account flatten is Core/Fabric emergency only).
- Count synthetic planted_edge candidates as S3 survivors (D2).
- Count two correlated or same-family hypotheses as independent survivors (D11).
- Accept `LIVE_RELEASE` as a yaml flag or file+SHA without HMAC (D4).
- Silent-default `expected_horizon` from `oos_size` or 20 (D6).
- First-wave ES/NQ research SIM orders (D5).
- Let research execute de-weight (D7).
- Re-arm `supervisor_tick_exec` for research signals (D8).
- Infinite silent SLA retries (D10).

---

## 4. Risks and remaining questions

### 4.1 Risks (real)

| Risk | Why it is real | Mitigation |
|------|----------------|------------|
| Ungated `mode: sim` path | E5 and siblings can submit without the Validation Gate **today** | D1 hard-block in S0; D8 keeps supervisor closed for research after S3; AST inventory test; yaml cannot lift it |
| S0 freeze touches the order funnel | `place_order` / `execute_order` wrappers change in S0 | Separate review of the freeze diff; flatten/emergency remain allowed; this docs PR does not apply it |
| Dual cost numbers until S2 calibrates | Research four-leg vs ADR-0055 | D3: FillEvent is execution-side; log discrepancy; never undercut the card |
| Live `PromotionGate` DSR floor 0.0 vs research 0.95 | Weaker live gate on dict evidence | S3 requires MAC + `nt_pit` + research floors |
| `sim` Risk Core cap bypass | S3 on `sim` would be NT orders with Brain caps off | S3 requires `sim_real_guard` |
| `@LuminaFabricHost.cs` gitignored | Stale AddOn could skip S1 whitelist | Operator rebuild after S1 |
| Synthetic candidates look like survivors | Phase 2 planted_edge will PASS on gauss | D2 + `tape_kind`; `check_sim_entry.py` refuses synthetic |
| Alarm executor vs session-touched flatten | Wrong wiring could flatten operator SIM trades | D7 executes **per strategy_id** in `fill_index`; Fabric emergency stays session-touched for Brain death |
| HMAC secret handling | Secret in env can leak via logs/debug | Never log secret; AST ban in research; missing secret = reject |
| S1 AdmissionChain step is a Risk Core change | Required by whitelist + LIVE_RELEASE verify | S1 PR + ADR-0060 + human review; not this docs PR |
| Correlated “survivors” | Two clones or high-corr MES/MNQ pair could count as 2 | D11 both-clauses; `check_sim_entry.py` fail-closed if corr missing |
| Silent SLA retry loop | Executor could retry forever on a stuck reduce | D10: one logged retry, then Core action; >10 min cap |

### 4.2 Remaining questions

Former Q1–Q6 are **closed** (D1–D6). Alarm authority is **D7**. Former OQ1–OQ4 are **closed** (D8–D11). Nothing in that set is still unspecified.

Not blocking for S0–S3 (later ADR, not a gate on this plan): Event Bus vs gRPC (keep both), rewrite AddOn (no), merge research into `lumina_core/engine` (no), LIVE_RELEASE secret store (use env `LUMINA_LIVE_RELEASE_SECRET` like `LUMINA_FABRIC_TOKEN`), horizon unit (bars, `expected_horizon_bars ≥ 1`), numeric “stability” gate to scale MES/MNQ → ES/NQ (D5).

---

## 5. Implementation PR sequence (after this docs PR)

| PR | Content | Touches Risk Core / Fabric? |
|----|---------|------------------------------|
| This PR | `docs/plans/INTEGRATION_PLAN_research_to_nt8.md` only | No |
| S0 | **D1 freeze** + bridge + horizon schema + ADR-0059 + parallel-path tests (D8: supervisor never on the research allow-list) | **Yes** (order-funnel tripwire). Flatten/emergency remain. Human review. |
| S1 | Whitelist + HMAC `LIVE_RELEASE` in Risk Core + C# + ADR-0060 + attack tests. Freeze stays on. | **Yes** (admission step, Core verify, C# reject). Human review. |
| S2 | Fill translator + ADR-0055 stamp + research calibrates to execution | Mapper/reconciler/calibrator; not risk limits |
| S2.5 | **Mandatory** NT-PIT tape for Validation Gate (D2) | Read-only MD |
| S3 | sim_runtime + sim_gate (MES/MNQ, nt_pit, **D11 independence**) + `alarm_executor` (D7/D9/D10) + PromotionGate MAC. Supervisor stays closed (D8). | Order path via **existing** admission; research still propose-only on alarms |

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
| Explicit SIM whitelist; HMAC LIVE_RELEASE; not agent-mutable; bypass tests | §1.4, §3.2, D4, G-WL, G-LIVE, G-MUT |
| Shadow first; hard-block ungated places (D1); supervisor closed for research (D8); SIM after 2–3 **nt_pit** D11-independent survivors | Decisions, §3.1, §3.3.1, §3.4, G-SURV, G-ENG |
| Fail-closed stale/disconnect; broker SSOT; research proposes, Core executes (D7, D9, D10) | Decisions D7–D10, G11–G13, S7, G-RED, `alarm_executor` |
| ES/NQ vs MES/MNQ ticks and $; ADR-0055 SSOT (D3); MES/MNQ first (D5) | D3, D5, P2, P3, R13, S0/S2 tests |
| `expected_horizon` required, no silent default (D6) | Decisions D6, G-HORIZ, HypothesisAgent, SignalIntent |
| Independent = different family **and** corr < 0.5 (D11) | Decisions D11, `independence.py`, `check_sim_entry.py` |

*End of plan. No runtime behavior changes in the commit that updates this file.*
