from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from lumina_launcher.services.ppo_realtime import PPORealtimeTailer


@pytest.fixture
def tailer(tmp_path: Path) -> PPORealtimeTailer:
    log_path = tmp_path / "ppo_training_log.jsonl"
    return PPORealtimeTailer(log_path=log_path)


@pytest.mark.asyncio
async def test_send_recent_lines_sends_last_n(tailer: PPORealtimeTailer) -> None:
    tailer.log_path.write_text(
        "\n".join([f'{{"step": {i}}}' for i in range(50)]),
        encoding="utf-8",
    )
    ws = AsyncMock()
    await tailer._send_recent_lines(ws, 3)
    assert ws.send_text.await_count == 3
    assert ws.send_text.await_args_list[-1].args[0] == '{"step": 49}'


@pytest.mark.asyncio
async def test_broadcast_new_line_removes_failed_clients(tailer: PPORealtimeTailer) -> None:
    ok = AsyncMock()
    bad = AsyncMock()
    bad.send_text.side_effect = RuntimeError("disconnected")
    tailer.clients = {ok, bad}

    await tailer.broadcast_new_line('{"step": 1}')

    ok.send_text.assert_awaited_once_with('{"step": 1}')
    assert bad not in tailer.clients
    assert ok in tailer.clients


@pytest.mark.asyncio
async def test_process_new_lines_advances_offset_and_broadcasts(tailer: PPORealtimeTailer) -> None:
    tailer.log_path.write_text('{"step": 1}\n', encoding="utf-8")
    tailer.last_position = tailer.log_path.stat().st_size

    with tailer.log_path.open("a", encoding="utf-8") as handle:
        handle.write('{"step": 2}\n')

    ws = AsyncMock()
    tailer.clients.add(ws)
    await tailer._process_new_lines()

    assert tailer.last_position == tailer.log_path.stat().st_size
    ws.send_text.assert_awaited_once_with('{"step": 2}')


def test_start_watching_is_idempotent(tailer: PPORealtimeTailer) -> None:
    tailer.log_path.parent.mkdir(parents=True, exist_ok=True)
    tailer.start_watching()
    observer = tailer._observer
    tailer.start_watching()
    assert tailer._observer is observer
    tailer.stop_watching()


def test_schedule_process_new_lines_requires_loop(tailer: PPORealtimeTailer) -> None:
    tailer._loop = None
    tailer._schedule_process_new_lines()  # no-op when loop unavailable
