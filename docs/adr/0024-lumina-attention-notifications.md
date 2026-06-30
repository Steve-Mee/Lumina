# ADR-0024: Lumina Attention Notifications

## Status

Accepted (2026-06-27)

## Context

Birth stalls, certificate failures, REAL safety events, and evolution approvals require operator attention. Previously these surfaced only in the Tauri UI with no push notification. The plateau playbook incorrectly suggested wipe — which preserves genesis config and rarely changes learning outcomes.

Additionally, `_maybe_auto_resume_stalled_birth()` could silently restart after `plateau_evolution_exhausted`, defeating the terminal gate.

## Decision

1. **Attention SSOT** — [`lumina_core/notifications/attention_events.py`](../../lumina_core/notifications/attention_events.py) taxonomy + [`attention_notifier.py`](../../lumina_core/notifications/attention_notifier.py) dispatcher with Telegram delivery, dedupe, and waking-hours scheduling.

2. **Full-spectrum v1 wiring** — birth stall/cert/history, birth service integrity/interrupted, observability kill-switch/daily-loss/websocket alerts.

3. **Post-plateau Phase-2 remediation** — [`lumina_core/birth/stall_remediation.py`](../../lumina_core/birth/stall_remediation.py): expand → buffer curate → regime slice → meta sweep before human gate.

4. **Human gate playbook** — no wipe for plateau stall; unlock genesis settings when `needs_attention=true`; Telegram summary with actionable steps.

5. **Auto-resume block** — no auto-resume when `needs_attention`, `retryable=false`, or `plateau_evolution_exhausted` / `stall_remediation_exhausted`.

**Invariants:** Alerts are informational only; no auto-graduation; certificate v2 still gates REAL.

## Consequences

- Positive: Operator notified via Telegram when Lumina needs attention.
- Positive: Structural auto-remediation before human gate reduces silent grind.
- Negative: Telegram credential dependency; fail-closed logs when missing.
- Negative: Dedupe may suppress repeated alerts within 30 min window.

## Related ADRs

- ADR-0023: Birth plateau evolution escalator
- ADR-0017: Birth research oracle
- ADR-0013: Birth Certificate v2
