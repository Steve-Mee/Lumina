"""Typed confirm phrases for named maturation wipes (fail-closed HTTP gate)."""

from __future__ import annotations

from typing import Any

WIPE_CONFIRM_PHRASES: dict[str, str] = {
    "awakening": "WIPE AWAKENING",
    "playground": "WIPE PLAYGROUND",
    "apprenticeship": "WIPE APPRENTICESHIP",
    "proving_ground": "WIPE PROVING GROUND",
    "birth": "WIPE BIRTH",
    "full": "WIPE FULL",
}


def expected_wipe_phrase(phase: str) -> str | None:
    key = str(phase or "").strip().lower()
    if key in {"wipe_all", "wipe-all", "all"}:
        key = "full"
    return WIPE_CONFIRM_PHRASES.get(key)


def validate_wipe_phrase(*, phase: str, confirm: bool, phrase: str) -> dict[str, Any] | None:
    """Return an error dict when the operator confirm gate fails; None when ok."""
    if not confirm:
        return {"ok": False, "error": "confirm=true required"}
    expected = expected_wipe_phrase(phase)
    if expected is None:
        return {"ok": False, "error": f"unknown phase: {phase}"}
    if str(phrase or "").strip() != expected:
        return {"ok": False, "error": "confirm_phrase mismatch"}
    return None
