"""SHADOW fail-closed alerts. Log + sink. Never places an order.

TelegramAlertSink journals via ADR-0043.
Research team decision (relayed by Steve 2026-10-29) item 6c:
research/alarm rejects must hit the Telegram door.
No credentials → drop_reason=no_credentials. No second poller. No network here.
"""

from __future__ import annotations

import logging
import os
from collections.abc import MutableSequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from lumina_core.notifications.telegram_journal import record_outbound

logger = logging.getLogger("lumina.research_bridge.alerts")

TelegramKind = Literal["ops", "evolution"]


class AlertSink(Protocol):
    def alert(self, *, code: str, message: str, details: dict[str, object]) -> None: ...


@dataclass
class RecordingAlertSink:
    records: MutableSequence[dict[str, object]] = field(default_factory=list)

    def alert(self, *, code: str, message: str, details: dict[str, object]) -> None:
        self.records.append({"code": code, "message": message, "details": dict(details)})
        logger.error(
            "research_bridge.alert",
            extra={
                "event_data": {
                    "event": "research_bridge.alert",
                    "code": code,
                    "message": message,
                    **dict(details),
                }
            },
        )


class LoggingAlertSink:
    def alert(self, *, code: str, message: str, details: dict[str, object]) -> None:
        logger.error(
            "research_bridge.alert",
            extra={
                "event_data": {
                    "event": "research_bridge.alert",
                    "code": code,
                    "message": message,
                    **dict(details),
                }
            },
        )


def telegram_credentials_present() -> bool:
    token = str(os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat = str(os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat:
        return False
    if token.startswith("${") or chat.startswith("${"):
        return False
    return True


@dataclass
class TelegramAlertSink:
    """ADR-0043 journal sink for research/alarm rejects. Never HTTP-sends."""

    kind: TelegramKind = "ops"
    path: Path | str | None = None
    workspace_root: Path | str | None = None
    source: str = "research_bridge"

    def alert(self, *, code: str, message: str, details: dict[str, object]) -> None:
        logger.error(
            "research_bridge.alert",
            extra={
                "event_data": {
                    "event": "research_bridge.alert",
                    "code": code,
                    "message": message,
                    **dict(details),
                }
            },
        )
        has_creds = telegram_credentials_present() is True
        record_outbound(
            text=f"{code}: {message}",
            kind=str(self.kind),
            correlation_id=str(details.get("strategy_id") or details.get("hypothesis_id") or code),
            source=self.source,
            delivered=has_creds,
            drop_reason=None if has_creds else "no_credentials",
            path=self.path,
            workspace_root=self.workspace_root,
        )
