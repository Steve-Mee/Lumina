# ADR-0043: Telegram I/O SSOT — one door, one journal, no Twin diary spam

**Status:** Accepted
**Date:** 2026-08-13
**Deciders:** LUMINA Engineering (Steve + Grok Captain)
**Relates:** [ADR-0028](./0028-lumina-operator-notification-matrix.md), [ADR-0044](./0044-twin-base-curriculum-and-escalation.md)

## Context

Telegram is one physical channel. Lumina had many writers (Twin decision feed, escalations, freeze, attention, milestones, ACKs) and competing `getUpdates` pollers with ephemeral `TelegramNotifier()` instances. Twin birth ticks called `evaluate_dna_promotion` on every rollout; `decision_notify.min_interval_sec: 0` plus low-conf force-bypass pushed every judgment to the phone.

First principles: Telegram is for **human decisions**, not the Twin's diary. Operator comms must be listable (timestamp, text, direction, linked reply) without becoming a capital hash-chain.

Elon protocol: one door, measure everything that passes (or is refused), stop the fire at the source.

## Decision

1. **Journal SSOT** — `lumina_core/notifications/telegram_journal.py` appends `state/monitoring_telegram_messages.jsonl` (`safe_append_jsonl`, no hash-chain). Every in/out row has `ts`, `direction`, `kind`, `text`, `correlation_id`, `expects_reply`, `delivered`, `drop_reason`. Twin/Deck answers append `telegram.thread.resolved` so a list shows Q+A.

2. **Single door** — `TelegramGateway` owns disk-backed outbound quota (`state/telegram_outbound_gate.json`) and poll offset (`state/telegram_poll_offset.json`). `TelegramNotifier._send_telegram_message` / `poll_for_replies` go through it. Bypass kinds: `promotion`, `freeze`, `real_safety` (never dropped by quota).

3. **Twin diary off Telegram** — `evolution.approval_twin.decision_notify.telegram: false`. Judgments still journal locally (`drop_reason=policy_shadow_diary`) and remain trainable via Deck/API.

4. **Escalation dedup** — `TwinPendingStore.find_open(kind, dna_hash)`: one open question per DNA; no new Telegram push.

5. **Freeze one channel** — attention ACCEPT/WIPE card only; Twin MC for freeze is deck-side (`notify_telegram=False`).

6. **No ACK spam** — feedback/escalation/micro resolve journals the answer; no extra Telegram ACK.

7. **List API** — `GET /api/notifications/telegram-log`.

Invariants: REAL promotion APPROVE/VETO and REAL-safety attention are fail-open on quota. Notifications never bypass constitution, sandbox, or PromotionGate.

## Consequences

### Positive

- Birth/SIM Twin ticks no longer flood Telegram.
- Operator can export a complete message list with answers attached.
- Competing pollers share one `getUpdates` offset.

### Negative

- Post-hoc Twin judgments are not on the phone (Deck/journal only). Re-enable `decision_notify.telegram` only with `min_interval_sec` ≥ 300 and `force_low_conf: false`.
- Quota is disk-best-effort; a lock timeout fail-closes non-bypass sends.

## Alternatives considered

1. Throttle Twin diary to 1/45s — still spam during birth loops; rejected.
2. Hash-chain the chat log — wrong audit class; rejected.
3. Command Deck UI in the same change — scope; API+file is the list.

## Links

- `lumina_core/notifications/telegram_journal.py`
- `lumina_core/notifications/telegram_gateway.py`
- `docs/adr/0028-lumina-operator-notification-matrix.md`
- `docs/adr/0044-twin-base-curriculum-and-escalation.md`
