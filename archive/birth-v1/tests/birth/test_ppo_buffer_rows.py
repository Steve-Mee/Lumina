from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from lumina_core.ppo_trainer import PPOTrainer


@pytest.mark.unit
def test_trajectory_vector_first_element_becomes_price_row() -> None:
    trainer = PPOTrainer(engine=MagicMock())
    buffer = MagicMock()
    buffer.trajectories = [
        {
            "observation": {"vector": [5012.5, 0.1, 0.2]},
            "next_observation": {"vector": [5013.0, 0.1, 0.2]},
            "reward": 1.0,
        }
    ]

    rows = trainer._trajectory_buffer_to_rows(buffer)

    assert len(rows) >= 1
    assert rows[0]["close"] == pytest.approx(5012.5)
    assert rows[0]["last"] == pytest.approx(5012.5)


@pytest.mark.unit
def test_trajectory_direct_price_still_works() -> None:
    trainer = PPOTrainer(engine=MagicMock())
    buffer = MagicMock()
    buffer.trajectories = [
        {
            "observation": {"price": 4999.0},
            "next_observation": {"price": 5000.0},
        }
    ]

    rows = trainer._trajectory_buffer_to_rows(buffer)

    assert len(rows) == 1
    assert rows[0]["open"] == pytest.approx(4999.0)
