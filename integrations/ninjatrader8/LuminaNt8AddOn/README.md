# LUMINA Execution Fabric — NT8 Add-on + SIM host

Native execution plane for LUMINA Brain (ADR-0035 / Blueprint v1.1).

## Projects

| Project | Role |
|---------|------|
| `Lumina.Execution.Fabric` | gRPC server, safety watchdog, SIM order gateway, idempotency |
| `Lumina.Execution.Fabric.SimHost` | Standalone console host for Phase 0 E2E **without** NT8 |
| `LuminaNt8AddOn` | NT8 `AddOnBase` entry; starts Fabric on `State.Active` |

## Build

```powershell
cd integrations\ninjatrader8
dotnet build Lumina.Execution.Fabric.sln -c Release
```

Optional NT8 reference (live AddOn against real `NinjaTrader.Core`):

```powershell
$env:NINJATRADER8_BIN = "C:\Program Files\NinjaTrader 8\bin"
dotnet build LuminaNt8AddOn\LuminaNt8AddOn.csproj -c Release
```

Without `NINJATRADER8_BIN`, the AddOn compiles with `FABRIC_STANDALONE` (lifecycle stub). Use **SimHost** for gRPC E2E.

## Run SIM Fabric (Phase 0)

```powershell
$env:LUMINA_FABRIC_TOKEN = "test-token"
.\Lumina.Execution.Fabric.SimHost\bin\Release\net48\Lumina.Execution.Fabric.SimHost.exe --port 50051 --account Sim101
```

Python Brain (after `pip install grpcio`):

```powershell
$env:LUMINA_FABRIC_TOKEN = "test-token"
# broker.live_provider=ninjatrader, fabric host 127.0.0.1:50051
```

Or use unit tests with an in-process mock server (`tests/broker/test_fabric_client.py`).

## Configuration

`%APPDATA%\LUMINA\fabric.json` (not committed):

```json
{
  "BindHost": "127.0.0.1",
  "BindPort": 50051,
  "AuthTokenEnv": "LUMINA_FABRIC_TOKEN",
  "AccountName": "Sim101",
  "HeartbeatTimeoutMs": 5000,
  "FlattenGraceMs": 15000,
  "FlattenOnTimeout": true,
  "BindLocalhostOnly": true,
  "MaxPositionSize": 10
}
```

## Safety (server-side) — PR-D MVP

- Heartbeat timeout (default 5s) → cancel non-protected working orders → **SAFE_MODE**
- After flatten grace (default 15s) → emergency flatten (SIM gateway)
- Brain stream close (last session) → same disconnect policy
- Auth success → **StateSync** snapshot (`state_hash`) for reconciliation
- Limit/stop orders stay WORKING; market fills immediately (SIM)
- Protected orders skipped by cancel-on-disconnect; reduce-only enforced on SIM
- Order rate limit (`MaxOrdersPerMinute`) + max position size
- Append-only audit: `%APPDATA%\LUMINA\fabric-audit.jsonl`
- Operator runbook: [execution-fabric-operator.md](../../../docs/runbooks/execution-fabric-operator.md)
- Localhost-only bind enforced when `BindLocalhostOnly=true`

## Token + fabric.json (customers)

```powershell
# Preferred: Lumina first-boot Credentials step → Generate "NinjaTrader Fabric Token"
# Or headless:
powershell -ExecutionPolicy Bypass -File scripts\install_fabric_token.ps1
```

Installs User env `LUMINA_FABRIC_TOKEN`, workspace `.env`, and `%APPDATA%\LUMINA\fabric.json` (`GatewayMode: sim`).  
**Restart NinjaTrader** after setting User env. Run **either** SimHost **or** this AddOn on port 50051 — not both.

## Deploy to NinjaTrader 8

1. Build Release with `NINJATRADER8_BIN` set:

```powershell
$env:NINJATRADER8_BIN = "C:\Program Files\NinjaTrader 8\bin"
dotnet build integrations\ninjatrader8\Lumina.Execution.Fabric.sln -c Release
```

2. Copy `LuminaNt8AddOn.dll`, `Lumina.Execution.Fabric.dll`, and Grpc/Protobuf dependencies into  
   `%USERPROFILE%\Documents\NinjaTrader 8\bin\Custom\AddOns\`  
   (or merge per NT dependency policy).
3. Restart NT8; enable **LUMINA Execution Fabric**.
4. Confirm NinjaScript Output shows `gRPC listening` and `AuthToken set = YES`.

AddOn starts real `FabricGrpcHost` with `GatewayMode` from `fabric.json` (default **sim** / `SimOrderGateway`).  
Switch to `nt` only after `NtOrderGateway` is bound to a live Account.

## Checklist

- [x] gRPC listens only on `127.0.0.1` (default)
- [x] Auth rejects wrong token
- [x] PlaceOrder + GetAccountState (SIM)
- [x] Heartbeat watchdog → SAFE_MODE + cancel
- [x] Metrics + pre-trade risk + StateSync + chaos tests (PR-D/E)
- [x] `NtOrderGateway` skeleton (`GatewayMode=nt`, fail-closed until Account bound)
- [ ] Live NT Account bind + order API (post PR-E)
- [ ] REAL promotion ADR
