"""HTTP confirm-phrase gate for named maturation wipes."""

from __future__ import annotations

from lumina_core.maturity.wipe_confirm import (
    WIPE_CONFIRM_PHRASES,
    expected_wipe_phrase,
    validate_wipe_phrase,
)


def test_phrases_are_exact_operator_tokens() -> None:
    assert WIPE_CONFIRM_PHRASES["awakening"] == "WIPE AWAKENING"
    assert WIPE_CONFIRM_PHRASES["birth"] == "WIPE BIRTH"
    assert WIPE_CONFIRM_PHRASES["full"] == "WIPE FULL"
    assert expected_wipe_phrase("wipe_all") == "WIPE FULL"


def test_validate_requires_confirm_and_exact_phrase() -> None:
    assert validate_wipe_phrase(phase="awakening", confirm=False, phrase="WIPE AWAKENING") == {
        "ok": False,
        "error": "confirm=true required",
    }
    assert validate_wipe_phrase(phase="awakening", confirm=True, phrase="wipe awakening") == {
        "ok": False,
        "error": "confirm_phrase mismatch",
    }
    assert validate_wipe_phrase(phase="awakening", confirm=True, phrase="WIPE BIRTH") == {
        "ok": False,
        "error": "confirm_phrase mismatch",
    }
    assert (
        validate_wipe_phrase(phase="awakening", confirm=True, phrase="  WIPE AWAKENING  ")
        is None
    )


def test_validate_rejects_unknown_and_genesis() -> None:
    assert validate_wipe_phrase(phase="genesis", confirm=True, phrase="WIPE FULL") == {
        "ok": False,
        "error": "unknown phase: genesis",
    }
    assert validate_wipe_phrase(phase="full", confirm=True, phrase="WIPE FULL") is None
    assert validate_wipe_phrase(phase="birth", confirm=True, phrase="WIPE BIRTH") is None
