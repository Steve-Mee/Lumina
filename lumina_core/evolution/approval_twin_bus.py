"""Approval Twin EventBus bind / observe / publish helpers.

Bounded modules: ``approval_twin_bus_observe``, ``approval_twin_bus_publish``.
"""
from __future__ import annotations

from lumina_core.evolution.approval_twin_bus_observe import (  # noqa: F401
    ApprovalTwinBusObserveMixin,
    _TWIN_SUBSCRIBE_TOPICS,
)
from lumina_core.evolution.approval_twin_bus_publish import ApprovalTwinBusPublishMixin  # noqa: F401


class ApprovalTwinBusMixin(ApprovalTwinBusObserveMixin, ApprovalTwinBusPublishMixin):
    """Combined bus surface kept for ApprovalTwinAgent MRO."""


__all__ = [
    "ApprovalTwinBusMixin",
    "ApprovalTwinBusObserveMixin",
    "ApprovalTwinBusPublishMixin",
    "_TWIN_SUBSCRIBE_TOPICS",
]
