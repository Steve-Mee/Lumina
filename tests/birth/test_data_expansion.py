from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumina_core.birth.data_expansion import expand_birth_data


def _ticks_for_days(days: int) -> list[dict]:
    return [
        {
            "timestamp": f"2026-01-{min(28, 1 + i % 28):02d}T12:00:00Z",
            "last": 5000.0 + i * 0.1,
            "close": 5000.0 + i * 0.1,
            "volume": 50,
            "source": "real_historical",
        }
        for i in range(days * 10)
    ]


@pytest.mark.unit
def test_data_expansion_increases_days_back(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_days: list[int] = []

    def _load(**kwargs):
        days = int(kwargs.get("days_back", 0))
        seen_days.append(days)
        return _ticks_for_days(days)

    monkeypatch.setattr("lumina_core.birth.data_expansion.load_historical_ticks", _load)

    first = expand_birth_data(
        market_data_service=SimpleNamespace(),
        runtime=SimpleNamespace(),
        current_step=0,
        expansion_steps=[90, 180, 365],
    )
    second = expand_birth_data(
        market_data_service=SimpleNamespace(),
        runtime=SimpleNamespace(),
        current_step=1,
        expansion_steps=[90, 180, 365],
    )

    assert seen_days == [90, 180]
    assert first.days_back == 90
    assert second.days_back == 180
    assert len(first.train_ticks) > 0
    assert len(second.train_ticks) > len(first.train_ticks)
