# Execution Fabric — Phase 0 Success Outline

**Status:** In progress (PR-A foundation)  
**Blueprint:** `project-dna/lumina/evolution/LUMINA_Execution_Fabric_Blueprint_v1.1_EN.md`  
**ADR:** [0035-execution-fabric-grpc.md](adr/0035-execution-fabric-grpc.md)

## Goal

E2E order placement from Python Brain → Fabric gRPC → NinjaTrader **SIM**, plus heartbeat and basic disconnect cancel.

## Deliverables checklist

| Item | Owner | Done when |
|------|--------|-----------|
| ADR-0035 accepted | Docs | This ADR in `docs/adr/` |
| `fabric.proto` SSOT | Contract | `protos/lumina/execution/v1/fabric.proto` |
| Python codegen | Tooling | `python scripts/generate_fabric_proto.py` produces importable stubs |
| Proto contract tests | Tests | `tests/broker/test_fabric_proto_contract.py` green |
| `FabricGrpcClient` skeleton | Python | Connect + auth + heartbeat loop (PR-B) |
| C# gRPC host POC | NT8 | PlaceOrder on Sim101 (PR-C) |
| Basic heartbeat timeout cancel | Fabric Safety | Non-protected working orders cancelled (PR-C/D) |

## Automated gates (repo)

```text
python scripts/generate_fabric_proto.py
pytest tests/broker/test_fabric_proto_contract.py -q
```

## Manual SIM gate (operator)

1. NT8 running with LUMINA Fabric AddOn enabled; gRPC bound to `127.0.0.1:50051`.
2. `LUMINA_FABRIC_TOKEN` set identically in Core env and AddOn config.
3. `broker.live_provider=ninjatrader`, `broker.ninjatrader.enabled=true`, account `Sim101`.
4. Place one market order from Python; observe fill/order event on stream.
5. Stop Brain heartbeats ≥ 5s; confirm working orders cancelled and SAFE_MODE entered.
6. Record p99 command→ack RTT (baseline; &lt; 5 ms target is Phase 2).

## Non-goals for Phase 0

- REAL account orders
- Full modify/flatten matrix
- Prometheus dashboards
- Removing CrossTrade
