# Execution Fabric — Operator Runbook (PR-D Safety MVP)

**Audience:** operators running SIM/Paper with LUMINA Execution Fabric  
**ADR:** [0035-execution-fabric-grpc.md](../adr/0035-execution-fabric-grpc.md)

## Components

| Component | Default |
|-----------|---------|
| Fabric gRPC | `127.0.0.1:50051` |
| Auth | `LUMINA_FABRIC_TOKEN` (shared Brain + Fabric) |
| Audit log | `%APPDATA%\LUMINA\fabric-audit.jsonl` |
| Config | `%APPDATA%\LUMINA\fabric.json` |

## Start SIM host (no NinjaTrader)

```powershell
$env:LUMINA_FABRIC_TOKEN = "<secret>"
dotnet run --project integrations/ninjatrader8/Lumina.Execution.Fabric.SimHost -c Release -- --port 50051 --account Sim101
```

## Safety modes

| Mode | Behaviour |
|------|-----------|
| **NORMAL** | Accept place/modify |
| **SAFE_MODE** | Reject new place/modify; cancel/flatten allowed; non-protected cancelled on disconnect/timeout |
| **FULL_SAFE** | Operator/manual only; emergency flatten requires `emergency=true` |

### Entering SAFE_MODE

- Brain heartbeat timeout (default **5s**)
- Brain TradingStream closed (last session)
- Explicit safety policy

### Clearing SAFE_MODE

- Successful Brain re-auth clears **SAFE → NORMAL** (not FULL_SAFE)
- FULL_SAFE requires operator intervention / process restart (Phase 1)

## Disconnect matrix (operator view)

1. **Heartbeat timeout** → cancel non-protected → SAFE_MODE → after `FlattenGraceMs` emergency flatten (if enabled)
2. **Stream disconnect** → same cancel policy when no sessions remain
3. **Reconnect** → Auth + **StateSync** snapshot; Brain reconciles `state_hash`

## Protected orders

Orders with `protected=true` are **not** auto-cancelled on disconnect/timeout. Review audit log if long disconnects leave protected working orders.

## Audit log

Append-only JSONL lines: `host_start`, `auth_ok`, `place_order`, `order_event`, `disconnect_policy`, `safety_alert`, …

```powershell
Get-Content $env:APPDATA\LUMINA\fabric-audit.jsonl -Tail 50
```

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Auth fails | Token match on Brain env and Fabric host |
| Place rejected SAFE_MODE | Re-auth Brain; inspect audit for disconnect/timeout |
| Degraded on bridge | `get_safety_alerts()` / logs; reconnect Fabric client |
| Port in use | Change `--port` and `broker.ninjatrader.fabric.port` |

## Metrics (PR-E)

### Server (C# host)

On host stop, a `metrics_snapshot` line is written to the audit log. Counters include:

- `fabric_place_orders_total` / `fabric_place_rejected_total` / `fabric_place_filled_total`
- `fabric_safe_mode_entries_total` / `fabric_auth_ok_total`
- `fabric_place_latency_ms_p50|p95|p99`

### Brain (Python)

`NinjaTraderBridgeService.metrics.snapshot()` and `/ws/core/live` → `ninjatrader.metrics`:

- `fabric_client_place_*`, `fabric_client_rtt_ms_p50|p95|p99`, connect/disconnect/alerts

Command Deck **NT8** pill shows connected / SAFE / degraded and tooltip with `safe_mode` + fabric target.

## Gateway mode

`fabric.json` / config:

```json
{ "GatewayMode": "sim" }
```

- **sim** — in-memory SIM fills (default, paper validation)
- **nt** — `NtOrderGateway` skeleton; **fail-closed until NT Account is bound** (live wiring continues after PR-E)

## REAL mode

**Not enabled in PR-E.** REAL requires a separate promotion ADR + bound NT gateway + human approval.
