from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from lumina_core.engine.regime_detector import RegimeDetector


@pytest.mark.unit
def test_detect_handles_nullable_object_ohlcv_without_rolling_crash() -> None:
    # gegeven
    rows: list[dict[str, object]] = []
    base = datetime(2026, 5, 4, 18, 0, tzinfo=timezone.utc)
    for idx in range(80):
        close = 5000.0 + (idx * 0.2)
        rows.append(
            {
                "timestamp": (base + pd.Timedelta(minutes=idx)).isoformat(),
                "open": close - 0.2 if idx % 9 else pd.NA,
                "high": close + 0.5 if idx % 11 else pd.NA,
                "low": close - 0.5 if idx % 13 else pd.NA,
                "close": close if idx % 7 else pd.NA,
                "volume": 1200.0 + idx if idx % 10 else pd.NA,
            }
        )
    frame = pd.DataFrame(rows, dtype="object")
    detector = RegimeDetector()

    # wanneer
    snapshot = detector.detect(frame, instrument="MES JUN26", confluence_score=0.64)

    # dan
    assert isinstance(snapshot.label, str) and snapshot.label
    assert "adx" in snapshot.features
    assert snapshot.features["adx"] >= 0.0
