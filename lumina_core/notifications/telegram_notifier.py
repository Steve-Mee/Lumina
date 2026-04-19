"""Notification-layer Telegram notifier.

This module exposes the Telegram notifier at the path requested in the
ApprovalTwinAgent prompt while reusing the production implementation.
"""

from lumina_core.evolution.telegram_notifier import TelegramNotifier

__all__ = ["TelegramNotifier"]
