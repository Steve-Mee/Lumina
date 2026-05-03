"""Provenance for PnL fed into risk / capital accounting (REAL requires broker-reconciled)."""

from __future__ import annotations

from enum import StrEnum


class PnlProvenance(StrEnum):
    """Source of a realized PnL figure."""

    BROKER_RECONCILED = "broker_reconciled"
    SIM_INTERNAL = "sim_internal"
