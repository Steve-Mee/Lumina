# Trade Fill Reconciliation Runbook

## Doel

Operationele handleiding voor de WebSocket-first TradeReconciler flow in Lumina.

## Config

Belangrijkste flags (config.yaml of env override):

- reconcile_fills: true/false
- reconciliation_method: websocket (default) of polling
- reconciliation_timeout_seconds: 15
- use_real_fill_for_pnl: true
- TRADE_RECONCILER_STATUS_FILE (optional)
- TRADE_RECONCILER_AUDIT_LOG (optional)

## Runtime observability

- Reconciler statusbestand: state/trade_reconciler_status.json
- Auditlog: logs/trade_fill_audit.jsonl
- API status endpoint: GET /reconciliation-status

## Self-test

Synthetic schema/normalizer test:

```bash
python scripts/validation/trade_reconciler_self_test.py
```

Live websocket sample (als CrossTrade beschikbaar is):

```bash
python scripts/validation/trade_reconciler_self_test.py --live-window-seconds 20
```

## Incident handling

1. Check API status endpoint en kijk naar connection_state/last_error.
2. Controleer statusbestand en auditlog op laatste fill events.
3. Zet tijdelijk reconciliation_method op polling als websocket structureel faalt.
4. Laat reconciliation_timeout_seconds op 15 of hoger om false fallbacks te vermijden.

## Backward compatibility

- Paper/sim flow blijft actief.
- Close-detectie en order placement blijven ongewijzigd.
- Reconciler is een extra daemon en beïnvloedt baseline trading flow niet als disabled.
