from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from lumina_core.evolution.evolution_dashboard import _load_metrics, render_evolution_dashboard


def _write_metrics(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def _complete_cycle(cycle_idx: int = 1, promoted: bool = False) -> dict:
    return {
        "status": "complete",
        "timestamp": f"2026-04-1{cycle_idx}T10:00:00+00:00",
        "generations_run": 3,
        "total_candidates_evaluated": 15,
        "promotions": 1 if promoted else 0,
        "best_fitness": 1.23,
        "generations": [
            {"generation": 0, "candidates": 5, "winner_hash": "abc123", "winner_fitness": 1.0, "promoted": False},
            {"generation": 1, "candidates": 5, "winner_hash": "def456", "winner_fitness": 1.23, "promoted": promoted},
            {"generation": 2, "candidates": 5, "winner_hash": "def456", "winner_fitness": 1.10, "promoted": False},
        ],
    }


# ── _load_metrics ────────────────────────────────────────────────────────────


def test_load_metrics_returns_empty_when_file_absent() -> None:
    assert _load_metrics(Path("/nonexistent/path.jsonl")) == []


def test_load_metrics_skips_non_complete_events() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as fh:
        fh.write(json.dumps({"event": "evolution_cycle_started", "timestamp": "x"}) + "\n")
        fh.write(json.dumps({"event": "generation_completed", "generation": 0}) + "\n")
        fh.write(json.dumps({"status": "complete", "generations_run": 1, "generations": []}) + "\n")
        path = Path(fh.name)

    try:
        rows = _load_metrics(path)
        assert len(rows) == 1
        assert rows[0]["status"] == "complete"
    finally:
        path.unlink(missing_ok=True)


def test_load_metrics_skips_corrupt_json_lines() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as fh:
        fh.write("{not valid json\n")
        fh.write(json.dumps({"status": "complete", "generations_run": 2, "generations": []}) + "\n")
        path = Path(fh.name)

    try:
        rows = _load_metrics(path)
        assert len(rows) == 1
    finally:
        path.unlink(missing_ok=True)


def test_load_metrics_skips_blank_lines() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as fh:
        fh.write("\n")
        fh.write("   \n")
        fh.write(json.dumps({"status": "complete", "generations_run": 1, "generations": []}) + "\n")
        path = Path(fh.name)

    try:
        rows = _load_metrics(path)
        assert len(rows) == 1
    finally:
        path.unlink(missing_ok=True)


# ── render_evolution_dashboard ───────────────────────────────────────────────


def _make_st_mock() -> MagicMock:
    """Return a MagicMock that accepts any st.* call without error."""
    mock = MagicMock()
    mock.pivot_table = MagicMock(return_value=MagicMock())
    return mock


def test_render_shows_no_data_info_when_empty() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as fh:
        path = Path(fh.name)

    try:
        with patch("lumina_core.evolution.evolution_dashboard.st") as mock_st:
            render_evolution_dashboard(path)
            mock_st.info.assert_called_once()
            mock_st.metric.assert_not_called()
    finally:
        path.unlink(missing_ok=True)


def test_render_shows_metrics_from_complete_cycle() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as fh:
        fh.write(json.dumps(_complete_cycle(cycle_idx=1)) + "\n")
        path = Path(fh.name)

    try:
        with patch("lumina_core.evolution.evolution_dashboard.st") as mock_st:
            with patch("lumina_core.evolution.evolution_dashboard.pd") as mock_pd:
                mock_df = MagicMock()
                mock_df.pivot_table.return_value = mock_df
                mock_df.tail.return_value = mock_df
                mock_pd.DataFrame.return_value = mock_df

                render_evolution_dashboard(path)

                # Metrics for generations, candidates, promotions must be rendered.
                metric_calls = [call.args[0] for call in mock_st.metric.call_args_list]
                assert "Generations" in metric_calls
                assert "Candidates" in metric_calls
                assert "Promotions" in metric_calls
    finally:
        path.unlink(missing_ok=True)


def test_render_shows_top_dna_hash_caption() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as fh:
        fh.write(json.dumps(_complete_cycle(cycle_idx=1)) + "\n")
        path = Path(fh.name)

    try:
        with patch("lumina_core.evolution.evolution_dashboard.st") as mock_st:
            with patch("lumina_core.evolution.evolution_dashboard.pd") as mock_pd:
                mock_df = MagicMock()
                mock_df.pivot_table.return_value = mock_df
                mock_df.tail.return_value = mock_df
                mock_pd.DataFrame.return_value = mock_df

                render_evolution_dashboard(path)

                # st.caption must be called with a string containing "Top DNA hash".
                caption_texts = [str(call.args[0]) for call in mock_st.caption.call_args_list]
                assert any("Top DNA hash" in text for text in caption_texts), (
                    f"Expected 'Top DNA hash' in caption, got: {caption_texts}"
                )
    finally:
        path.unlink(missing_ok=True)
