# Execution Fabric — Phase 0 Success Outline

**Status:** PR-A…PR-F SIM complete (native NT Account + historical + live MD). REAL promotion still gated.  
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
| `FabricGrpcClient` + mapper | Python | Connect + auth + place/flatten via mock server (PR-B) |
| Bridge/broker wiring | Python | `attach_fabric_client`, factory injects client (PR-B) |
| C# gRPC host POC | NT8 / SimHost | `Lumina.Execution.Fabric` + SimHost PlaceOrder SIM (PR-C) |
| Basic heartbeat timeout cancel | Fabric Safety | Watchdog cancel + SAFE_MODE in C# host (PR-C) |
| Safety MVP | Fabric + Python | Audit log, StateSync, modify, chaos tests (PR-D) |
| Hardening | Fabric + Deck | Metrics, pre-trade risk, NT gateway skeleton, telemetry (PR-E) |
| PR-F SIM | NT AddOn + Brain | NtAccountOrderGateway Sim101 bind, live MD, unary auth, dual-plane |

## Automated gates (repo)

```text
python scripts/generate_fabric_proto.py
pytest tests/broker/test_fabric_proto_contract.py tests/broker/test_fabric_client.py tests/broker/test_fabric_mapper.py tests/broker/test_fabric_chaos.py -q
dotnet build integrations/ninjatrader8/Lumina.Execution.Fabric.sln -c Release
```

### Full deep-audit pack (T9)

Runs Tracks A–E unit coverage + ops status CLIs (T1–T8):

```text
python scripts/validation/run_deep_audit_gates.py
python scripts/validation/run_deep_audit_gates.py --json
python scripts/validation/run_deep_audit_gates.py --pytest-only
```

Hard fail = pytest pack. Soft ops (Perfect Birth / Phase2 unlock incomplete) do not fail CI unless `--strict-ops`.

### T1 SAFE_MODE / disconnect proof gate (Brain fail-closed)

Deep-audit residual: Brain must not place while SAFE or after disconnect.

```text
# Mock/CI (default — no NT8 required)
python scripts/validation/fabric_safe_mode_gate.py
python scripts/validation/fabric_safe_mode_gate.py --json

# Optional: reachable SIM Fabric host (token required; never REAL)
$env:LUMINA_FABRIC_TOKEN = "test-token"
python scripts/validation/fabric_safe_mode_gate.py --live
```

Covered by gate: SAFE place block, disconnect→SAFE, cancel still allowed when SAFE+connected, aperture lineage on Fabric transport, chaos SAFE reject.

Host heartbeat-timeout cancel (≥5s) remains **operator manual** (C# watchdog) — see checklist below.

### Optional SIM host E2E

```powershell
$env:LUMINA_FABRIC_TOKEN = "test-token"
# Terminal A:
dotnet run --project integrations/ninjatrader8/Lumina.Execution.Fabric.SimHost -c Release -- --port 50051
# Terminal B: Python FabricGrpcClient connect + place_order (see tests/broker/test_fabric_client.py pattern)
```

## Manual SIM gate (operator)

1. NT8 running with LUMINA Fabric AddOn enabled; gRPC bound to `127.0.0.1:50051`.
2. `LUMINA_FABRIC_TOKEN` set identically in Core env and AddOn config.
3. `broker.live_provider=ninjatrader`, `broker.ninjatrader.enabled=true`, account `Sim101`.
4. Place one market order from Python; observe fill/order event on stream.
5. Stop Brain heartbeats ≥ 5s; confirm working orders cancelled and SAFE_MODE entered.
6. Attempt place while SAFE → reject; cancel/flatten still allowed.
7. Re-auth / reconnect → SAFE clears; place works again.
8. Record p99 command→ack RTT (baseline; &lt; 5 ms target is Phase 2).
9. **Never** run this checklist against a REAL account.

## Non-goals for Phase 0

- REAL account orders
- Full modify/flatten matrix
- Prometheus dashboards
- Removing CrossTrade
