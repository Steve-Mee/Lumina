"""Birth stage graduation outcome (fail-closed constitution gate)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GraduationResult:
    ok: bool
    reason: str = ""
