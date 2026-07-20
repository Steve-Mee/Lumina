# LUMINA Execution Fabric — NT8 Add-on

Native NinjaTrader 8 Add-on that hosts the **Execution Fabric** gRPC server on localhost and executes orders against the configured NT account (SIM first).

## Status

| Layer | Status |
|-------|--------|
| Proto contract | `protos/lumina/execution/v1/fabric.proto` (SSOT) |
| ADR | [0035-execution-fabric-grpc.md](../../../docs/adr/0035-execution-fabric-grpc.md) |
| C# Add-on | Skeleton → gRPC host in Phase 0 (PR-C) |
| Legacy WebSocket client | Superseded — do not implement WS to Core |

Blueprint: [LUMINA_Execution_Fabric_Blueprint_v1.1_EN.md](../../../project-dna/lumina/evolution/LUMINA_Execution_Fabric_Blueprint_v1.1_EN.md)

## Architecture (target)

```
Python Brain (gRPC client)  →  127.0.0.1:50051  →  This Add-on (gRPC server)
                                                      ├─ Order execution (NT Account API)
                                                      ├─ Market data stream
                                                      └─ Safety & Risk Engine (heartbeat watchdog)
```

Brain still enforces Final Arbitration / order gatekeeper **before** calling Fabric. Fabric enforces independent pre-trade and disconnect policies.

## Build (planned)

1. Open `LuminaNt8AddOn.csproj` in Visual Studio (net48, NT8 refs).
2. Set env `NINJATRADER8_BIN` to NT8 binary folder (for `NinjaTrader.Core.dll`).
3. Add gRPC packages compatible with .NET Framework 4.8 (Phase 0 spike: Grpc.Core or approved host).
4. Build Release; copy `.dll` to `%USERPROFILE%\Documents\NinjaTrader 8\bin\Custom\AddOns\`.
5. Restart NinjaTrader 8 and enable **LUMINA Execution Fabric** in Control Center.

## Configuration

Local config: `%APPDATA%\LUMINA\fabric.json` (not committed):

```json
{
  "bind_host": "127.0.0.1",
  "bind_port": 50051,
  "auth_token_env": "LUMINA_FABRIC_TOKEN",
  "account_name": "Sim101",
  "heartbeat_timeout_ms": 5000,
  "flatten_grace_ms": 15000
}
```

Set `LUMINA_FABRIC_TOKEN` in both the NT process environment and Core `.env`.

## Manual checklist (Phase 0)

- [ ] gRPC listens only on `127.0.0.1`
- [ ] Auth rejects wrong token (fail-closed)
- [ ] Heartbeat every 1–2s from Brain; Fabric watchdog at 5s
- [ ] `PlaceOrder` on SIM account with `client_order_id` idempotency
- [ ] Heartbeat timeout → cancel non-protected working orders + SAFE_MODE
