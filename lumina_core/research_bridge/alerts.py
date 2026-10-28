"""SHADOW fail-closed alerts. Log + sink. Never places an order."""

from __future__ import annotations

import logging
from collections.abc import MutableSequence
from dataclasses import dataclass, field
from typing import Protocol

logger = logging.getLogger("lumina.research_bridge.alerts")


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
