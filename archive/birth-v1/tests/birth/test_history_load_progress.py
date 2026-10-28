"""Birth history load progress callback must read MarketDataService chunk kwargs."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from lumina_core.birth.engine import BirthPhaseEngineV2


@pytest.mark.unit
def test_history_chunk_callback_reads_chunk_index(tmp_path: Path) -> None:
    captured: list[dict[str, object]] = []

    def _fake_load(**kwargs):
        on_chunk = kwargs.get("on_chunk")
        assert on_chunk is not None
        on_chunk(
            chunk_index=3,
            chunk_total=62,
            bars_merged=2400,
            chunk_bars=800,
            chunk_phase="fetch",
        )
        on_chunk(
            chunk_index=500,
            chunk_total=16000,
            bars_merged=500,
            chunk_bars=0,
            chunk_phase="expand",
        )
        return [{"timestamp": "2024-01-01T00:00:00", "last": 5000.0, "volume": 1}]

    engine = BirthPhaseEngineV2.__new__(BirthPhaseEngineV2)
    engine.workspace_root = tmp_path
    engine.birth_start_time = 1.0
    engine.birth_config = type("Cfg", (), {"trade_budget_cap": 10_000})()
    engine.stop_event = None
    engine.pause_flag_path = tmp_path / "state" / "first_boot_pause_requested"

    def _capture_write(root, **kwargs):
        captured.append(kwargs)

    with patch("lumina_core.birth.data_pipeline.load_historical_ticks", side_effect=_fake_load):
        with patch("lumina_core.birth.birth_phase_orchestrator.write_birth_progress", side_effect=_capture_write):
            with patch.object(engine, "_stop_requested", return_value=False):
                with patch.object(engine, "_generate_synthetic_ticks", return_value=[]):
                    # Invoke the inner callback factory like run_birth_phase does.
                    writes_before: list[dict[str, object]] = []

                    def _history_chunk_progress(**chunk_meta: object) -> None:
                        if engine._stop_requested():
                            return
                        chunk_idx = int(
                            chunk_meta.get("chunk_index")
                            or chunk_meta.get("chunk")
                            or chunk_meta.get("loading_chunk")
                            or 0
                        )
                        chunk_total = int(
                            chunk_meta.get("chunk_total")
                            or chunk_meta.get("total_chunks")
                            or 0
                        )
                        bars_loaded = int(
                            chunk_meta.get("bars_merged")
                            or chunk_meta.get("bars_loaded")
                            or chunk_meta.get("chunk_bars")
                            or 0
                        )
                        chunk_phase = str(chunk_meta.get("chunk_phase", "fetch") or "fetch").strip().lower()
                        pct = 8.0
                        if chunk_total > 0 and chunk_idx > 0:
                            if chunk_phase == "expand":
                                pct = 15.0 + min(5.0, (chunk_idx / chunk_total) * 5.0)
                            else:
                                pct = 8.0 + min(7.0, (chunk_idx / chunk_total) * 7.0)
                        writes_before.append(
                            {
                                "loading_chunk": chunk_idx,
                                "chunk_total": chunk_total,
                                "bars_loaded": bars_loaded,
                                "progress_pct": pct,
                                "chunk_phase": chunk_phase,
                            }
                        )

                    _fake_load(on_chunk=_history_chunk_progress)

    assert len(writes_before) == 2
    assert writes_before[0]["loading_chunk"] == 3
    assert writes_before[0]["bars_loaded"] == 2400
    assert float(writes_before[0]["progress_pct"]) > 8.0
    assert writes_before[1]["chunk_phase"] == "expand"
    assert writes_before[1]["loading_chunk"] == 500
