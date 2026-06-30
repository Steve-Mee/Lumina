"""Send a one-off Lumina milestone or maturation Telegram test alert."""

from __future__ import annotations

import argparse
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

from lumina_core.maturity.milestone_hooks import try_record_milestone  # noqa: E402
from lumina_core.notifications.milestone_events import MilestoneCategory, MilestoneEvent  # noqa: E402
from lumina_core.notifications.milestone_notifier import get_milestone_notifier  # noqa: E402
from lumina_core.notifications.telegram_notifier import TelegramNotifier  # noqa: E402

MATURATION_IDS = (
    "genesis_contract_signed",
    "birth_started",
    "birth_certificate_issued",
    "deck_unlocked",
    "evolution_proof_passed",
    "first_sim_order_placed",
    "sim_real_guard_stable",
    "promotion_gate_passed",
    "human_real_approval",
    "real_trading_live",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Send Lumina Telegram test alert")
    parser.add_argument(
        "--maturation",
        choices=MATURATION_IDS,
        help="Send maturation ladder test milestone (records JSON + Telegram)",
    )
    args = parser.parse_args()

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

    if args.maturation:
        get_milestone_notifier(workspace_root=ROOT).reset_notified()
        try_record_milestone(ROOT, args.maturation, metadata={"test": True})
        print(f"maturation_test_recorded id={args.maturation}")
        return 0

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
