"""Notification-layer scheduler for waking-hours delivery.

This module exposes a scheduler entrypoint at the path requested in the
ApprovalTwinAgent prompt while reusing the production implementation.
"""

from lumina_core.evolution.approval_gym_scheduler import ApprovalGymScheduler


class NotificationScheduler(ApprovalGymScheduler):
    """Alias for the production waking-hours scheduler."""


__all__ = ["NotificationScheduler"]
