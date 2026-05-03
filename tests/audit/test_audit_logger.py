from __future__ import annotations

import logging
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lumina_core.audit import AuditLogger
from lumina_core.audit.replay_validator import DecisionReplayValidator


def _process_writer(path: str, worker_id: int, per_writer: int) -> int:
    logger = AuditLogger()
    for seq in range(per_writer):
        logger.append(
            stream="concurrency",
            path=Path(path),
            payload={"worker_id": worker_id, "seq": seq, "event_id": f"{worker_id}-{seq}"},
            mode="sim",
        )
    return per_writer


@pytest.mark.unit
def test_envelope_contains_required_fields(tmp_path: Path) -> None:
    log_path = tmp_path / "audit.jsonl"
    logger = AuditLogger()
    row = logger.append(
        stream="trade_decision",
        path=log_path,
        payload={"stage": "risk_gate", "final_decision": "allow", "reason": "ok", "mode": "sim"},
        mode="sim",
    )
    assert row["schema_version"] == "lumina_audit_v1"
    assert row["stream"] == "trade_decision"
    assert row["timestamp"]
    assert row["prev_hash"] == "GENESIS"
    assert row["entry_hash"]


@pytest.mark.unit
def test_chain_intact_single_writer(tmp_path: Path) -> None:
    path = tmp_path / "single.jsonl"
    logger = AuditLogger()
    for seq in range(100):
        logger.append(stream="single", path=path, payload={"seq": seq}, mode="sim")
    report = logger.verify("single", path=path)
    assert report.valid is True


@pytest.mark.integration
def test_chain_intact_under_threads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "threads.jsonl"
    logger = AuditLogger()
    lock_dir = tmp_path / "locks"
    monkeypatch.setenv("LUMINA_STATE_LOCK_DIR", str(lock_dir))
    monkeypatch.setenv("LUMINA_STATE_LOCK_NO_JITTER", "1")

    workers = 8
    per_worker = 50

    def _writer(worker_id: int) -> int:
        for seq in range(per_worker):
            for attempt in range(3):
                try:
                    logger.append(
                        stream="threaded",
                        path=path,
                        payload={"worker_id": worker_id, "seq": seq, "event_id": f"{worker_id}-{seq}"},
                        mode="sim",
                    )
                    break
                except PermissionError:
                    if attempt == 2:
                        raise
        return per_worker

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(_writer, range(workers)))

    report = logger.verify("threaded", path=path)
    assert report.valid is True


@pytest.mark.slow
def test_chain_intact_under_processes(tmp_path: Path) -> None:
    path = tmp_path / "processes.jsonl"
    workers = 4
    per_worker = 40
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        pool.starmap(_process_writer, [(str(path), idx, per_worker) for idx in range(workers)])

    report = AuditLogger().verify("concurrency", path=path)
    assert report.valid is True


@pytest.mark.integration
def test_parallel_streams_no_deadlock(tmp_path: Path) -> None:
    logger = AuditLogger()
    streams = [f"stream_{idx}" for idx in range(8)]
    per_stream = 50

    def _write_stream(stream: str) -> None:
        path = tmp_path / f"{stream}.jsonl"
        for seq in range(per_stream):
            logger.append(stream=stream, path=path, payload={"seq": seq}, mode="sim")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_write_stream, streams))

    for stream in streams:
        report = logger.verify(stream, path=tmp_path / f"{stream}.jsonl")
        assert report.valid is True


@pytest.mark.unit
def test_tamper_detected(tmp_path: Path) -> None:
    path = tmp_path / "tamper.jsonl"
    logger = AuditLogger()
    logger.append(stream="tamper", path=path, payload={"seq": 1}, mode="sim")
    logger.append(stream="tamper", path=path, payload={"seq": 2}, mode="sim")
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[1] = lines[1].replace('"seq": 2', '"seq": 9')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = logger.verify("tamper", path=path)
    assert report.valid is False
    assert "mismatch" in report.message


@pytest.mark.unit
def test_experimental_payload_freeform(tmp_path: Path) -> None:
    path = tmp_path / "freeform.jsonl"
    logger = AuditLogger()
    appended = logger.append(
        stream="freeform",
        path=path,
        payload={
            "experiment": {"weights": [1, 2, 3], "seen_at": datetime.now(timezone.utc)},
            "tags": {"aggressive", "creative"},
        },
        mode="sim",
    )
    assert appended["experiment"]["weights"] == [1, 2, 3]
    assert isinstance(appended["experiment"]["seen_at"], str)
    assert isinstance(appended["tags"], list)


@pytest.mark.unit
def test_chain_hash_field_still_validates(tmp_path: Path) -> None:
    path = tmp_path / "chain_hash.jsonl"
    logger = AuditLogger()
    logger.append(
        stream="agent_decision",
        path=path,
        payload={
            "agent_id": "A",
            "raw_input": {"x": 1},
            "raw_output": {"signal": "HOLD"},
            "confidence": 0.4,
            "policy_outcome": "ok",
            "decision_context_id": "ctx-1",
            "lineage": {
                "model_identifier": "m",
                "prompt_version": "p",
                "prompt_hash": "h",
                "policy_version": "pv",
                "provider_route": ["local"],
                "calibration_factor": 1.0,
            },
        },
        mode="sim",
    )
    result = DecisionReplayValidator(path=path).verify_hash_chain()
    assert result["valid"] is True


@pytest.mark.unit
def test_existing_audit_files_remain_readable(tmp_path: Path) -> None:
    path = tmp_path / "existing.jsonl"
    logger = AuditLogger()
    logger.append(
        stream="existing",
        path=path,
        payload={
            "lineage": {
                "model_identifier": "legacy",
                "prompt_version": "v1",
                "prompt_hash": "abc",
                "policy_version": "policy-v1",
                "provider_route": ["provider"],
                "calibration_factor": 1.0,
            }
        },
        mode="sim",
    )
    validator = DecisionReplayValidator(path=path)
    assert validator.verify_hash_chain()["valid"] is True
    assert validator.verify_lineage()["valid"] is True


@pytest.mark.unit
def test_tail_logs_invalid_json_lines(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    path = tmp_path / "tail_invalid.jsonl"
    path.write_text('{"ok": 1}\n{broken json\n', encoding="utf-8")
    logger = AuditLogger()

    with caplog.at_level(logging.WARNING):
        rows = logger.tail("tail-invalid", path=path, limit=0)

    assert len(rows) == 1
    assert rows[0]["ok"] == 1
    assert "AuditLogger tail skipped invalid JSON line" in caplog.text
