"""Discover Telegram chat_id from recent bot updates (getUpdates)."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from lumina_core.notifications.telegram_notifier import TelegramNotifier


def main() -> int:
    notifier = TelegramNotifier()
    token = notifier._api_token
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not configured", file=sys.stderr)
        return 1

    url = f"https://api.telegram.org/bot{token}/getUpdates?limit=20"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        print(f"ERROR: Telegram API HTTP {exc.code}", file=sys.stderr)
        return 2
    except urllib.error.URLError as exc:
        print(f"ERROR: Network: {exc.reason}", file=sys.stderr)
        return 2

    if not payload.get("ok"):
        print(f"ERROR: {payload}", file=sys.stderr)
        return 2

    chats: dict[int, str] = {}
    for item in payload.get("result", []):
        msg = item.get("message") or item.get("edited_message") or {}
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            continue
        label = chat.get("title") or chat.get("username") or chat.get("first_name") or "unknown"
        chats[int(chat_id)] = str(label)

    if not chats:
        print("No chats found. Message your Lumina bot in Telegram first, then rerun.")
        return 3

    print("Discovered chat IDs (message the bot first if empty):")
    for cid, label in sorted(chats.items()):
        print(f"  {cid}  ({label})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
