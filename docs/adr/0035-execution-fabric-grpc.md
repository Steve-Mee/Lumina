# ADR-0035: Execution Fabric — gRPC Transport & Independent Safety Plane

**Status:** Accepted  
**Date:** 2026-07-20  
**Deciders:** LUMINA Engineering

## Context

LUMINA needs a native, low-latency execution path to NinjaTrader 8 without CrossTrade cloud hops. ADR-0029 established the Python broker façade (`live_provider=ninjatrader`, admission chain, mode guards) and sketched a **WebSocket** wire protocol (`/ws/ninjatrader/v1`) with Core as server and the NT8 Add-on as client.

The Execution Fabric Blueprint v1.1 elevates requirements beyond a simple bridge:

1. Trading execution is stateful and capital-critical; the execution plane must operate **independently** of the AI brain on failure.
2. Disconnect/timeout handling must be fail-closed (cancel → Safe Mode → optional flatten) inside the Fabric.
3. The contract must be strongly typed and evolvable (versioned protobuf).
4. Localhost-only IPC with measurable latency is preferred over JSON WebSocket.

A WebSocket design where Core hosts the socket inverts control: if Brain dies, nothing in NT actively enforces cancel/flatten. Fabric-as-gRPC-server keeps the watchdog next to the broker API.

## Decision

1. **Wire protocol is gRPC + Protobuf** over localhost (`lumina.execution.v1`). The SSOT contract lives at `protos/lumina/execution/v1/fabric.proto`.
2. **Fabric (C# NT8 AddOn or documented companion process) hosts the gRPC server.** Brain (Python) is the gRPC client.
3. **Preserve ADR-0029 broker/admission decisions:**
   - `broker.backend: paper|live` + `broker.live_provider: crosstrade|ninjatrader`
   - Every place-order still passes `run_final_arbitration` / order gatekeeper **before** any Fabric RPC
   - **Superseded by ADR-0040:** default live provider is Fabric/`ninjatrader`;
     CrossTrade is emergency opt-in plugin only (not library default)
   - REAL requires separate promotion evidence (no capital path in Phase 0–2 without further ADR)
4. **Defense in depth:** Brain admission (Python) **and** Fabric Safety & Risk Engine (C#) are both mandatory. Fabric never trusts Brain-only limits.
5. **WebSocket JSON frames** under `docs/schemas/ninjatrader/v1/` and the planned `/ws/ninjatrader/v1` endpoint are **superseded for the wire protocol**. Existing `lumina_core/broker/ninjatrader/*` modules remain the Python façade (session state, guards, `NinjaTraderBroker`); transport becomes `FabricGrpcClient`.
6. **net48 hosting risk:** Phase 0 validates in-process Grpc.Core (or equivalent) inside the NT8 AddOn. If blocked, a localhost companion process owning gRPC is allowed only with an amendment to this ADR — still no cloud, still Fabric-owned safety.
7. **Auth:** shared secret/token from env (`LUMINA_FABRIC_TOKEN`); bind `127.0.0.1` only.
8. **Idempotency:** Brain-generated `client_order_id` (UUID); Fabric guarantees at-most-once execution.

## Consequences

### Positive

- Safety watchdog lives next to NT order APIs even when Brain crashes.
- Typed, versioned contract shared by Python and C#.
- Aligns with Blueprint v1.1 and capital-preservation defaults.
- Reuses existing NT broker façade without rewriting admission/mode matrix.

### Negative

- Supersedes earlier WS-centric integration docs and partial JSON schemas.
- gRPC hosting on .NET Framework 4.8 is a Phase 0 technical risk.
- Two live providers still expand the test matrix.

## Alternatives considered

1. **Keep WebSocket Core-as-server** — Rejected; weaker fail-closed story when Brain dies; less structure for long-term evolution.
2. **ZeroMQ** — Rejected; faster possible HFT fit but weaker typing/tooling for a production organism (Blueprint §4.2).
3. **Immediate CrossTrade removal** — Rejected; no SIM evidence for Fabric yet (ADR-0029).
4. **Orders from AddOn without Brain admission** — Rejected; violates constitution / Final Arbitration.

## Links

- Blueprint: [LUMINA_Execution_Fabric_Blueprint_v1.1_EN.md](../../project-dna/lumina/evolution/LUMINA_Execution_Fabric_Blueprint_v1.1_EN.md)
- ADR-0029: [Native NinjaTrader bridge](0029-ninjatrader-native-bridge.md) (broker façade; wire protocol superseded here)
- Integration: [ninjatrader-integration.md](../ninjatrader-integration.md)
- Proto: `protos/lumina/execution/v1/fabric.proto`
