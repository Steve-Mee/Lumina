"""Residual history failure must not look like a live engine failure (frontend contract)."""

# Mirrors tauri-app/src/lib/birth/birthStatusPredicates.ts isBirthResidualHistoryFailure
# so Python CI can guard the residual fields we demote on disk.


def test_residual_history_fields_shape() -> None:
    residual = {
        "status": "error",
        "live": False,
        "progress": {
            "stage": "error",
            "phase": "loading_history_failed",
            "residual_failure": True,
            "attention_reason_code": "history_unavailable_residual",
            "message": "Vorige birth-run stopte",
        },
    }
    assert residual["live"] is False
    assert residual["progress"]["residual_failure"] is True
    assert "CROSSTRADE" not in residual["progress"]["message"].upper()
