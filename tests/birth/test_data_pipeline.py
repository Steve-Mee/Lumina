"""Unit tests for birth data_pipeline module."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.birth.data_pipeline import (
    BirthDataPipeline,
    generate_synthetic_ticks,
    train_hash,
)


@pytest.mark.unit
def test_generate_synthetic_ticks_shape() -> None:
    ticks = generate_synthetic_ticks(50, start_price=5000.0)
    assert len(ticks) == 50
    assert ticks[0]["source"] == "synthetic"
    assert ticks[0]["regime"] == "SYNTHETIC"
    assert float(ticks[0]["last"]) > 0


@pytest.mark.unit
def test_train_hash_stable_for_same_ticks() -> None:
    ticks = generate_synthetic_ticks(10, start_price=100.0)
    assert train_hash(ticks) == train_hash(ticks)
    assert train_hash([]) == ""


@pytest.mark.unit
def test_write_data_prep_progress_delegates_to_emit(tmp_path: Path) -> None:
    emitted: list[dict[str, object]] = []

    class _Host:
        workspace_root = tmp_path
        birth_start_time = 1.0

        class _Cfg:
            trade_budget_cap = 100

        birth_config = _Cfg()

        def _emit_birth_progress(self, **kwargs: object) -> None:
            emitted.append(kwargs)

    BirthDataPipeline(_Host()).write_data_prep_progress(
        phase="enriching_news",
        message="test",
        progress_pct=20.5,
        training_mode="certified",
        processed=3,
        total=10,
    )
    assert len(emitted) == 1
    assert emitted[0]["phase"] == "enriching_news"
    assert emitted[0]["stage"] == "loading_data"