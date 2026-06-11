# 2026-06-04 — Phase 3 D2 Sub-slices 13–14 (Voice + Trader League webhook extraction from runtime_workers)

**Parents**: 05-31 SPF-006 + Phase 3 D2 + MC post Sub10-12 perfection plan complete + `2026-06-04-phase3-d2-sub10-12-perfection-phase3-final-gate.md`.

**Classification**: Small (two bounded extractions + thin delegations + tests; no happy-path behavior change).

**What was executed**:
- **Sub13**: `lumina_core/engine/voice_listener_daemon.py` — `VoiceListenerDaemon.run()` owns full voice while-loop (wake-word, dream overrides, feedback, emergency_stop).
- **Sub14**: `lumina_core/engine/trader_league_webhook.py` — `TraderLeagueWebhook.push()` owns league POST (best-effort observability).
- `runtime_workers.py`: `voice_listener_thread` → thin `VoiceListenerDaemon`; `_push_trader_league_trade` → thin `TraderLeagueWebhook` (compat export preserved for real_close_detector / supervisor SM lazy imports).
- Removed unused `requests` import from runtime_workers (moved to webhook module).
- Tests: `tests/engine/test_voice_listener_daemon.py` (3 + AST thin guard + `MANUAL_SMOKE_SUB13_VOICE_SUCCESS`); `tests/engine/test_trader_league_webhook.py` (1 + `MANUAL_SMOKE_SUB14_WEBHOOK_SUCCESS`).

**Evidence**:
- `phase3_perfection_gate_verify.py`: 56 passed (prior gate) + new tests 4 passed.
- Grep: `voice_listener_thread` has no `while True` in runtime_workers; body in bounded module.

**Status impact**:
- D2 Yellow strengthened: voice + league webhook surfaces firewalled on runtime_workers god.
- **Still remaining on god**: `_compute_session_kpis`, `_publish_runtime_monitoring_snapshot`, twin bootstrap in supervisor inner, `state_persist_daemon`, supervisor wrappers — pre_dream already thin (sub7).

**Next**: Sub15 optional `RuntimeMonitoringService` (KPI + snapshot helpers) or bootstrap/twin extraction per MC.

**Reproduce**:
```bash
python -m pytest -q tests/engine/test_voice_listener_daemon.py tests/engine/test_trader_league_webhook.py
python scripts/phase3_perfection_gate_verify.py
```

---

**Protocol adherence (2026-06-11 hygiene backfill)**

**Hypothesis**: This classified entry documents a bounded change that preserves capital-path invariants when gates stay green.

**Prediction (30d)**: Relevant pytest/Guardian gates remain pass; no new FATAL aperture findings.

**Rollback**: Revert the files named in the Executed/Changes section of this log; add a superseding evolution entry if behavior changes.

