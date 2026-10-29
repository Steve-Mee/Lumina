"""NQ templates stay closed until a new team-approved pre-register (Q-NQ-1)."""

from __future__ import annotations

from typing import Iterable

NQ_ATR_TEMPLATES_CLOSED = True
NQ_CLOSED_REASON = (
    "NQ templates stay closed until a new pre-register is explicitly approved. "
    "A reliable unclipped null is not that approval."
)


class NQTemplatesClosed(RuntimeError):
    """ATR/template grid tried to include NQ while the lock is on."""


def assert_nq_templates_closed(instruments: Iterable[str]) -> None:
    if not NQ_ATR_TEMPLATES_CLOSED:
        return
    if any(str(item) == "NQ" for item in instruments):
        raise NQTemplatesClosed(NQ_CLOSED_REASON)
