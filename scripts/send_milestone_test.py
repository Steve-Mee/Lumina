"""Send a one-off Lumina milestone Telegram test alert."""

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

from lumina_core.notifications.milestone_events import MilestoneCategory, MilestoneEvent  # noqa: E402
from lumina_core.notifications.milestone_notifier import get_milestone_notifier  # noqa: E402
from lumina_core.notifications.telegram_notifier import TelegramNotifier  # noqa: E402


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

    milestone = get_milestone_notifier(workspace_root=ROOT)
    milestone.reset_notified()
    test_event = MilestoneEvent(
        milestone_id=f"manual_test_{int(time.time())}",
        category=MilestoneCategory.BIRTH,
        title="Lumina milestone test",
        summary="Dit is een testbericht van Lumina Milestone Alerts. Als je dit leest, werkt Telegram.",
        dedupe_key=f"test:manual:{time.time()}",
    )
    sent = milestone.notify(test_event, workspace_root=ROOT)
    print(f"milestone_notify_sent={sent}")
    return 0 if sent else 2


if __name__ == "__main__":
    raise SystemExit(main())
