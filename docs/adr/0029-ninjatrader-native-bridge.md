# ADR-0029: Native NinjaTrader 8 Broker Bridge

**Status:** Accepted  
**Date:** 2026-07-11  
**Deciders:** LUMINA Engineering

## Context

LUMINA currently routes live execution through CrossTrade REST (`CrossTradeBroker`). A native NinjaTrader 8 add-on path lowers latency, improves fill reconciliation, and enables richer market-data telemetry — but introduces capital risk if orders bypass the admission chain or REAL mode guards.

The canonical mode matrix (`paper` → `broker_backend=paper`; `sim`/`sim_real_guard`/`real` → `broker_backend=live`) must not be broken. A third top-level `broker.backend=ninjatrader` value would violate existing validation and launcher setup flows.

## Decision

1. **Live provider selector** — Keep `broker.backend: paper|live`. Add `broker.live_provider: crosstrade|ninjatrader`
   (default was `crosstrade`; **ADR-0040 flips default to `ninjatrader` / Fabric-only foundation**).
2. **Bounded module** — `lumina_core/broker/ninjatrader/` implements transport (`bridge_service`), guards (`guards`, `promotion_gate`), and `NinjaTraderBroker(BrokerBridge)`.
3. **Admission invariant** — Every `submit_order` calls `run_final_arbitration` before any WS frame is sent. The bridge service has no public submit API.
4. **NT bridge promotion gate** — Separate from evolution `PromotionGate`; controls market-data ingest and order submission per `trade_mode`.
5. **Explicit opt-in** — `broker.ninjatrader.enabled=true` required before `live_provider=ninjatrader` is valid at startup.
6. **REAL safeguards** — Account name must match configured NT8 account; disconnect is fail-closed for new orders in realish modes.
7. **CrossTrade remains default** — Native path is optional indefinitely; parallel SIM shadow comparison before any deprecation.

## Consequences

### Positive

- Modular broker path without breaking existing CrossTrade or paper flows.
- Constitution-compliant admission chain preserved at the broker boundary.
- Clear promotion ladder: config enable → sim orders → sim_real_guard staging → REAL with ADR.

### Negative

- Additional config surface (`live_provider`, `ninjatrader` block).
- Operators must manage NT8 add-on deployment separately from Python Core.
- Two live providers increase test matrix size.

## Alternatives considered

1. **`BROKER_BACKEND=ninjatrader` third value** — Rejected; breaks mode matrix validation in `ConfigLoader`.
2. **Direct NT8 orders from engine** — Rejected; bypasses `BrokerBridge` and admission chain.
3. **Immediate CrossTrade removal** — Rejected; no production evidence for native bridge stability.

## Wire protocol note

The **broker façade, admission chain, and `live_provider` selector** in this ADR remain in force. The **WebSocket wire protocol** sketched here and in early integration drafts is **superseded by ADR-0035** (gRPC Execution Fabric: Fabric hosts server, Brain is client). See [0035-execution-fabric-grpc.md](0035-execution-fabric-grpc.md).

## Links

- [ninjatrader-integration.md](../ninjatrader-integration.md)
- [ADR-0035: Execution Fabric gRPC](0035-execution-fabric-grpc.md)
- [ADR-0007: PromotionGate](0007-promotion-gate-real-mode.md)
- [ADR-0003: Trading Constitution](0003-trading-constitution-sandboxed-mutation-executor.md)
- [sim_real_guard_rollout_b_staging_runbook.md](../requests/sim_real_guard_rollout_b_staging_runbook.md)
