# ADR-0025: Lumina Milestone Notifications

> **Supersession (2026-08-14):** Birth Foundation pass and exit follow [ADR-0046](./0046-birth-foundation-evolvable-plant.md). Milestone copy must not treat WR gates or `stage4_polish` as current Birth graduation.

## Status

Accepted (2026-06-28)

## Context

ADR-0024 introduced attention notifications for stalls, failures, and REAL safety events. Operators receive alerts when something needs intervention, but positive Birth progress (data loaded, curriculum stage passed, certificate issued) was only visible in the Tauri UI.

The UI already defines five macro milestones in [`tauri-app/src/lib/birthPhaseModel.ts`](../../tauri-app/src/lib/birthPhaseModel.ts). The Birth engine tracks granular curriculum graduation via `StagePassReceipt` and OOS certificate evaluation.

## Decision

1. **Separate milestone channel** — [`lumina_core/notifications/milestone_events.py`](../../lumina_core/notifications/milestone_events.py) + [`milestone_notifier.py`](../../lumina_core/notifications/milestone_notifier.py), distinct from attention alerts (ADR-0024).

2. **Birth v1 milestone set** — macro milestones (birth started, history loaded, regime map ready, refinement, OOS passed, certificate issued, practice completed) plus per-curriculum-stage pass notifications (stages 1–3 via receipts; stage 4 at polish entry).

3. **Persistent idempotency** — `state/milestone_notified.json` records notified milestone IDs; checkpoint resume seeds already-achieved milestones without re-sending.

4. **Fresh run reset** — non-resume Birth runs call `reset_notified()` so a new Birth session can notify again.

5. **Telegram format** — `LUMINA MILESTONE — {title}` via `TelegramNotifier.send_milestone_alert()`; bypasses quiet hours (positive, infrequent events).

6. **Engine wiring** — [`lumina_core/birth/engine.py`](../../lumina_core/birth/engine.py) emits at phase transitions; failures remain on attention channel only.

**Invariants:** Milestone alerts are informational only; no auto-graduation; certificate v2 still gates REAL; attention alerts unchanged.

## Consequences

- Positive: Operator stays informed of Birth progress without opening Lumina.
- Positive: Idempotent resume avoids duplicate Telegram spam.
- Negative: Additional Telegram messages during long Birth runs (mitigated by dedupe + no chunk-level noise).
- Negative: Credential dependency; fail-closed log when Telegram unavailable.

## Related ADRs

- ADR-0024: Lumina attention notifications
- ADR-0013: Birth Certificate v2
- ADR-0014: Birth curriculum + OOS gate
