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

Belangrijkste statusvelden:

- method: websocket of polling
- connection_state: idle/connecting/connected/error/polling/stopped
- status: ready/streaming/fill_received/reconciled/reconnecting/polling_error
- last_error: laatste foutmelding (null bij healthy)
- pending_count en pending_symbols: openstaande closes
- last_message_ts: laatste websocket activiteit
- last_reconciled_trade: laatste definitieve close payload

## Self-test

Synthetic schema/normalizer test:

```bash
python scripts/validation/trade_reconciler_self_test.py
```

Live websocket sample (als CrossTrade beschikbaar is):

```bash
python scripts/validation/trade_reconciler_self_test.py --live-window-seconds 20
```

## Live dry-run checklist (pre-live / post-deploy)

1. Zet TRADE_MODE op real en controleer dat reconcile_fills=true, reconciliation_method=websocket, use_real_fill_for_pnl=true.
2. Start Lumina en verifieer in statusbestand: method=websocket, connection_state=connected, status=streaming.
3. Trigger een kleine close en controleer direct een pending event in auditlog:

```text
event=pending_close
```

4. Controleer dat daarna fill events binnenkomen:

```text
event=fill_received
```

5. Controleer definitieve reconciliatie:

```text
event=reconciled
status=reconciled_fill
```

6. Verifieer dat slippage en latency worden geschreven in trade payloads en auditlog.
7. Simuleer kort netwerkverlies en bevestig reconnect flow:
	- connection_state gaat naar error/reconnecting
	- daarna terug naar connected/streaming
8. Laat een close zonder fill (of blokkeer feed kort) en controleer timeout fallback:
	- status=timeout_snapshot
	- snapshot exit wordt gebruikt volgens config
9. Controleer dat pending_count terugvalt naar 0 na reconcile of timeout.
10. Controleer TraderLeague records op broker_fill_id, commission, slippage_points, fill_latency_ms en reconciliation_status.

## Monitoring en alerts (aanbevolen)

- Alert als connection_state langer dan 60s niet connected is.
- Alert bij oplopende pending_count (bijvoorbeeld > 3 voor > 30s).
- Alert op frequente timeout_snapshot events (duidt vaak op feed/subscribe issues).
- Alert op hoge fill_latency_ms pieken t.o.v. baseline.

## Incident handling

1. Check API status endpoint en kijk naar connection_state/last_error.
2. Controleer statusbestand en auditlog op laatste fill events.
3. Zet tijdelijk reconciliation_method op polling als websocket structureel faalt.
4. Laat reconciliation_timeout_seconds op 15 of hoger om false fallbacks te vermijden.
5. Bij duplicate/event-storm: controleer auditlog op herhaalde fill_id; duplicates worden genegeerd door de reconciler.
6. Bij out-of-order fills: controleer of cumulatieve quantity binnen timeout volledig matched voordat reconcile plaatsvindt.

## Backward compatibility

- Paper/sim flow blijft actief.
- Close-detectie en order placement blijven ongewijzigd.
- Reconciler is een extra daemon en beïnvloedt baseline trading flow niet als disabled.
