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

## After install — Operator Vault (zero-touch Fabric)

1. NinjaTrader 8 must be installed (Lumina detects it; offers official download if missing).
2. Open **Setup & connection** from Birth (or first-boot Credentials).
3. Lumina **auto-bootstraps**: token, `fabric.json`, AddOn DLL deploy to NT Custom\AddOns.
4. Click **Run fabric diagnostic** — must be **GREEN** before Genesis (fail-closed).
5. **Save & seal** unlocks Neural Genesis.
6. CrossTrade fields are **optional emergency fallback only**.

APIs:
- `POST /api/setup/fabric-bootstrap`
- `POST /api/setup/fabric-connection-test` (writes GREEN certificate)
- `GET /api/setup/fabric-link-status`
- `POST /api/setup/fabric-nt-watch` (NT update re-probe + halt)

On NinjaTrader update, Lumina re-probes Fabric; failure → **Fabric Halt** (no Birth/trading until GREEN again).

## First-time token (customers)

Use **Generate** for `LUMINA_FABRIC_TOKEN` on the Lumina first-boot **Connection Credentials** step.
That writes:

| Target | Content |
|--------|---------|
| Workspace `.env` | `LUMINA_FABRIC_TOKEN=…` (Brain / Python) |
| Windows **User** env | same value (NinjaTrader reads after **restart**) |
| `%APPDATA%\LUMINA\fabric.json` | host defaults only — **no secret value** |

Headless / operator install:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_fabric_token.ps1
```

**Single host rule:** only one process may bind `127.0.0.1:50051` (SimHost **or** NT8 AddOn, never both).

## Start SIM host (no NinjaTrader)

```powershell
$env:LUMINA_FABRIC_TOKEN = "<secret>"   # or rely on User env after install_fabric_token.ps1
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

Recommended `fabric.json` (created by onboarding / `install_fabric_token.ps1`):

```json
{
  "BindHost": "127.0.0.1",
  "BindPort": 50051,
  "AuthTokenEnv": "LUMINA_FABRIC_TOKEN",
  "AccountName": "Sim101",
  "GatewayMode": "sim",
  "HeartbeatTimeoutMs": 5000,
  "FlattenGraceMs": 15000,
  "FlattenOnTimeout": true,
  "BindLocalhostOnly": true,
  "MaxPositionSize": 2,
  "MaxOrdersPerMinute": 30,
  "DailyLossLimit": 0
}
```

- **sim** — in-memory SIM fills (default, paper validation; use even inside NT until NT gateway is bound)
- **nt** — `NtOrderGateway` skeleton; **fail-closed until NT Account is bound** (live wiring continues after PR-E)

## Brain config (concept)

```yaml
broker:
  backend: live
  live_provider: ninjatrader
  ninjatrader:
    enabled: true
    account_name: Sim101
    fabric:
      host: 127.0.0.1
      port: 50051
      auth_token_env: LUMINA_FABRIC_TOKEN
      gateway_mode: sim
```

Plus process/User env: `LUMINA_FABRIC_TOKEN`.

## REAL mode

**Not enabled in PR-E.** REAL requires a separate promotion ADR + bound NT gateway + human approval.
