# ADR-0028: Lumina Operator Notification Matrix

## Status

Accepted (2026-06-27)

## Context

ADR-0024 (attention) and ADR-0025 (birth milestones) established Telegram channels for problems and positive Birth progress. ADR-0027 added a maturation ladder SSOT in JSON, but post-birth lifecycle events (Genesis contract, SIM stability GREEN, promotion gate, REAL approval) did not reach Telegram.

Operators need **one predictable contract**: every critical milestone and every stall/failure/safety event pushes to Telegram immediately (with dedupe).

## Decision

1. **Facade:** [`lumina_core/notifications/operator_notifier.py`](../../lumina_core/notifications/operator_notifier.py)
   - `notify_maturation()` → maturation events → MilestoneNotifier (idempotent)
   - `notify_problem()` → AttentionNotifier (dedupe + quiet hours for non-critical)

2. **Maturation events:** [`lumina_core/notifications/maturation_events.py`](../../lumina_core/notifications/maturation_events.py) — builders for all maturation milestone IDs.

3. **Bridge:** [`lumina_core/maturity/milestone_hooks.py`](../../lumina_core/maturity/milestone_hooks.py) `try_record_milestone()` records JSON **and** sends Telegram.

4. **Config matrix** in `config.yaml` → `telegram.notification_matrix` toggles categories:
   - `maturation`, `birth_milestones`, `birth_attention`, `real_safety`, `evolution`, `ops`

5. **Client attention API:** `POST /api/notifications/attention` for REAL safe mode and other client-detected ops events.

6. **Reclassifications:**
   - `evolution_proof_failed` → Attention HIGH (REAL blocker), in addition to milestone log
   - `real_trading_blocked` → Attention when Command Deck REAL switch rejected

## Consequences

- Positive: Full lifecycle visibility from Genesis through REAL on Telegram.
- Positive: Category toggles prevent spam without code changes.
- Negative: More messages during long runs — mitigated by idempotency + dedupe.
- Invariant: Notifications are informational only; no auto-graduation or REAL gate bypass.

## Related ADRs

- ADR-0024: Attention notifications
- ADR-0025: Milestone notifications
- ADR-0027: Maturation ladder
