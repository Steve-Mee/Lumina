"""Send a one-off Lumina Telegram test alert."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from lumina_core.notifications.attention_events import (
    AttentionCategory,
    AttentionEvent,
    AttentionSeverity,
)
from lumina_core.notifications.attention_notifier import get_attention_notifier
from lumina_core.notifications.telegram_notifier import TelegramNotifier


def main() -> int:
    notifier = TelegramNotifier()
    token_ok = bool(notifier._api_token)
    chat_ok = bool(notifier._chat_id)
    print(f"telegram_token_configured={token_ok}")
    print(f"telegram_chat_id_configured={chat_ok}")
    if not token_ok or not chat_ok:
        print(
            "ERROR: Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env or config.yaml",
            file=sys.stderr,
        )
        return 1

    attention = get_attention_notifier(workspace_root=ROOT)
    attention._dedupe_sec = 0
    event = AttentionEvent(
        category=AttentionCategory.OPS,
        severity=AttentionSeverity.INFO,
        reason_code="telegram_test",
        title="Lumina test",
        summary=(
            "Dit is een testbericht van Lumina Attention Alerts. "
            "Als je dit leest, werkt Telegram."
        ),
        recommended_actions=("Geen actie nodig — test geslaagd.",),
        dedupe_key=f"test:manual:{time.time()}",
    )
    sent = attention.notify(event, workspace_root=ROOT)
    print(f"attention_notify_sent={sent}")
    return 0 if sent else 2


if __name__ == "__main__":
    raise SystemExit(main())
