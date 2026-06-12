from __future__ import annotations

import pytest

from lumina_core.birth.purged_split import purged_train_holdout_split


@pytest.mark.unit
def test_purged_split_holdout_not_in_train() -> None:
    ticks = [
        {"timestamp": f"2026-01-{day:02d}T12:00:00", "last": 5000.0 + day}
        for day in range(1, 11)
        for _ in range(10)
    ]
    split = purged_train_holdout_split(ticks, holdout_pct=0.20)
    train_ts = {t["timestamp"][:10] for t in split.train}
    holdout_ts = {t["timestamp"][:10] for t in split.holdout}
    assert train_ts.isdisjoint(holdout_ts)
    assert split.holdout
