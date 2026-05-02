from __future__ import annotations

import json
import multiprocessing
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lumina_core.evolution.dna_registry import DNARegistry, PolicyDNA
from lumina_core.evolution.veto_registry import VetoRecord, VetoRegistry
from lumina_core.state.state_manager import (
    LockTimeoutError,
    safe_append_jsonl,
    safe_sqlite_connect,
    safe_with_file_lock,
    validate_jsonl_chain,
)


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _process_writer(path: str, writer_id: int, per_writer: int) -> int:
    target = Path(path)
    for seq in range(per_writer):
        safe_append_jsonl(
            target,
            {
                "writer_id": writer_id,
                "seq": seq,
                "ts": datetime.now(timezone.utc).isoformat(),
            },
            hash_chain=True,
        )
    return per_writer


@pytest.mark.integration
def test_safe_append_jsonl_no_corruption_under_threads(tmp_path: Path) -> None:
    path = tmp_path / "thread_no_corruption.jsonl"
    workers = 16
    per_worker = 32

    def _writer(worker_id: int) -> int:
        for seq in range(per_worker):
            safe_append_jsonl(
                path,
                {
                    "writer_id": worker_id,
                    "seq": seq,
                    "event_id": f"{worker_id}-{seq}",
                },
                hash_chain=False,
            )
        return per_worker

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(_writer, range(workers)))

    rows = _read_jsonl(path)
    assert len(rows) == workers * per_worker
    assert len({str(row["event_id"]) for row in rows}) == workers * per_worker


@pytest.mark.integration
def test_safe_append_jsonl_hash_chain_consistent_under_threads(tmp_path: Path) -> None:
    path = tmp_path / "thread_hash_chain.jsonl"
    workers = 16
    per_worker = 32

    def _writer(worker_id: int) -> int:
        for seq in range(per_worker):
            safe_append_jsonl(
                path,
                {
                    "writer_id": worker_id,
                    "seq": seq,
                    "event_id": f"{worker_id}-{seq}",
                },
                hash_chain=True,
            )
        return per_worker

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(_writer, range(workers)))

    rows = _read_jsonl(path)
    assert len(rows) == workers * per_worker
    assert len({str(row["entry_hash"]) for row in rows}) == workers * per_worker
    ok, message = validate_jsonl_chain(path)
    assert ok is True, message


@pytest.mark.slow
def test_safe_append_jsonl_no_corruption_across_processes(tmp_path: Path) -> None:
    path = tmp_path / "process_hash_chain.jsonl"
    workers = 4
    per_worker = 25

    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        pool.starmap(_process_writer, [(str(path), worker_id, per_worker) for worker_id in range(workers)])

    rows = _read_jsonl(path)
    assert len(rows) == workers * per_worker
    ok, message = validate_jsonl_chain(path)
    assert ok is True, message


@pytest.mark.integration
def test_safe_sqlite_connect_handles_concurrent_inserts(tmp_path: Path) -> None:
    db_path = tmp_path / "concurrent.sqlite3"
    workers = 12
    per_worker = 50

    with safe_sqlite_connect(db_path) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS entries (id INTEGER PRIMARY KEY AUTOINCREMENT, marker TEXT NOT NULL)")
        conn.commit()

    def _insert(worker_id: int) -> int:
        inserted = 0
        for seq in range(per_worker):
            with safe_sqlite_connect(db_path) as conn:
                conn.execute("INSERT INTO entries(marker) VALUES (?)", (f"{worker_id}-{seq}",))
                conn.commit()
                inserted += 1
        return inserted

    with ThreadPoolExecutor(max_workers=workers) as pool:
        totals = list(pool.map(_insert, range(workers)))

    assert sum(totals) == workers * per_worker
    with safe_sqlite_connect(db_path) as conn:
        count = int(conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0])
    assert count == workers * per_worker


@pytest.mark.integration
def test_dna_registry_concurrent_register_dna(tmp_path: Path) -> None:
    registry = DNARegistry(
        jsonl_path=tmp_path / "dna_registry.jsonl",
        sqlite_path=tmp_path / "dna_registry.sqlite3",
    )
    workers = 8
    per_worker = 5

    def _register(worker_id: int) -> int:
        created = 0
        for seq in range(per_worker):
            dna = PolicyDNA.create(
                prompt_id=f"prompt-{worker_id}",
                version=f"v-{worker_id}-{seq}",
                content={"rule": f"rule-{worker_id}-{seq}"},
                fitness_score=float(seq) + 0.5,
                generation=seq,
                parent_ids=[],
                mutation_rate=0.1,
                lineage_hash=f"lineage-{worker_id}",
            )
            registry.register_dna(dna)
            created += 1
        return created

    with ThreadPoolExecutor(max_workers=workers) as pool:
        totals = list(pool.map(_register, range(workers)))

    expected = sum(totals)
    rows = _read_jsonl(tmp_path / "dna_registry.jsonl")
    assert len(rows) == expected
    assert len({str(row["hash"]) for row in rows}) == expected
    with safe_sqlite_connect(tmp_path / "dna_registry.sqlite3") as conn:
        count = int(conn.execute("SELECT COUNT(*) FROM dna_entries").fetchone()[0])
    assert count == expected


@pytest.mark.integration
def test_veto_registry_concurrent_append_veto(tmp_path: Path) -> None:
    registry = VetoRegistry(
        db_path=str(tmp_path / "veto_registry.db"),
        log_path=str(tmp_path / "veto_registry.jsonl"),
    )
    workers = 8
    per_worker = 5

    def _append(worker_id: int) -> int:
        written = 0
        for seq in range(per_worker):
            registry.append_veto(
                VetoRecord(
                    veto_timestamp=datetime.now(timezone.utc).isoformat(),
                    dna_id=f"dna-{worker_id}-{seq}",
                    dna_fitness=0.5 + seq,
                    reason="concurrency_test",
                    issuer=f"tester-{worker_id}",
                    metadata={"seq": seq},
                )
            )
            written += 1
        return written

    with ThreadPoolExecutor(max_workers=workers) as pool:
        totals = list(pool.map(_append, range(workers)))

    expected = sum(totals)
    rows = _read_jsonl(tmp_path / "veto_registry.jsonl")
    assert len(rows) == expected
    with safe_sqlite_connect(tmp_path / "veto_registry.db") as conn:
        count = int(conn.execute("SELECT COUNT(*) FROM veto_records").fetchone()[0])
    assert count == expected


@pytest.mark.integration
def test_lock_timeout_raises_lock_timeout_error(tmp_path: Path) -> None:
    path = tmp_path / "locked.jsonl"
    blocker_ready = threading.Event()
    release_blocker = threading.Event()

    def _blocker() -> None:
        def _hold_lock(_: Path) -> None:
            blocker_ready.set()
            release_blocker.wait(timeout=2.0)

        safe_with_file_lock(path, _hold_lock, lock_timeout_s=1.0, retry_max_attempts=1)

    thread = threading.Thread(target=_blocker, daemon=True)
    thread.start()
    blocker_ready.wait(timeout=5.0)

    with pytest.raises(LockTimeoutError):
        safe_append_jsonl(path, {"event": "timeout"}, hash_chain=False, lock_timeout_s=0.01, retry_max_attempts=2)

    release_blocker.set()
    thread.join(timeout=5.0)
