from __future__ import annotations

import hashlib
import json
import os
import random
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, TypeVar

from filelock import FileLock, Timeout

_T = TypeVar("_T")

_BASE_BACKOFF_MS = 25
_MAX_BACKOFF_MS = 400


@dataclass(frozen=True, slots=True)
class StateManagerConfig:
    lock_dir: Path | None = None
    lock_timeout_s: float = 10.0
    retry_max_attempts: int = 5
    sqlite_busy_timeout_ms: int = 5000


class LockTimeoutError(RuntimeError):
    def __init__(self, path: Path, attempts: int) -> None:
        super().__init__(f"failed to acquire state lock for {path} after {attempts} attempts")
        self.path = Path(path)
        self.attempts = int(attempts)


_DEFAULT_CONFIG = StateManagerConfig()
_LOCK_CACHE: dict[str, FileLock] = {}
_LOCK_CACHE_GUARD = threading.Lock()


def _resolve_config(
    *, lock_timeout_s: float | None = None, retry_max_attempts: int | None = None
) -> StateManagerConfig:
    lock_dir_env = os.getenv("LUMINA_STATE_LOCK_DIR", "").strip()
    lock_dir = Path(lock_dir_env) if lock_dir_env else None
    timeout = float(lock_timeout_s if lock_timeout_s is not None else _DEFAULT_CONFIG.lock_timeout_s)
    attempts = int(retry_max_attempts if retry_max_attempts is not None else _DEFAULT_CONFIG.retry_max_attempts)
    return StateManagerConfig(
        lock_dir=lock_dir,
        lock_timeout_s=max(0.01, timeout),
        retry_max_attempts=max(1, attempts),
        sqlite_busy_timeout_ms=_DEFAULT_CONFIG.sqlite_busy_timeout_ms,
    )


def _lock_path_for(path: Path, *, config: StateManagerConfig) -> Path:
    target = Path(path)
    if config.lock_dir is not None:
        return config.lock_dir / f"{target.name}.lock"
    return target.parent / ".locks" / f"{target.name}.lock"


def _get_file_lock(path: Path) -> FileLock:
    lock_key = str(path.resolve())
    with _LOCK_CACHE_GUARD:
        lock = _LOCK_CACHE.get(lock_key)
        if lock is None:
            lock = FileLock(lock_key)
            _LOCK_CACHE[lock_key] = lock
        return lock


def _sleep_with_backoff(attempt: int) -> None:
    exponent = max(0, int(attempt))
    backoff_ms = min(_MAX_BACKOFF_MS, _BASE_BACKOFF_MS * (2**exponent))
    if os.getenv("LUMINA_STATE_LOCK_NO_JITTER", "").strip() == "1":
        jitter_scale = 1.0
    else:
        jitter_scale = random.uniform(0.8, 1.2)
    sleep_s = (backoff_ms * jitter_scale) / 1000.0
    time.sleep(sleep_s)


def _canonical_hash_payload(entry: dict[str, Any]) -> str:
    payload = {k: v for k, v in entry.items() if k not in {"prev_hash", "entry_hash"}}
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _latest_entry_hash(path: Path) -> str:
    if not path.exists():
        return "GENESIS"
    last_line = ""
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                last_line = stripped
    if not last_line:
        return "GENESIS"
    try:
        payload = json.loads(last_line)
    except json.JSONDecodeError:
        return "GENESIS"
    latest = payload.get("entry_hash")
    return str(latest) if latest else "GENESIS"


def _append_jsonl_payload(path: Path, payload: dict[str, Any], *, ensure_ascii: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=ensure_ascii) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def safe_with_file_lock(
    path: Path | str,
    callback: Callable[[Path], _T],
    *,
    lock_timeout_s: float | None = None,
    retry_max_attempts: int | None = None,
) -> _T:
    target = Path(path)
    config = _resolve_config(lock_timeout_s=lock_timeout_s, retry_max_attempts=retry_max_attempts)
    lock_path = _lock_path_for(target, config=config)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    file_lock = _get_file_lock(lock_path)

    for attempt in range(config.retry_max_attempts):
        try:
            with file_lock.acquire(timeout=config.lock_timeout_s):
                return callback(target)
        except Timeout as exc:
            if attempt >= config.retry_max_attempts - 1:
                raise LockTimeoutError(target, config.retry_max_attempts) from exc
            _sleep_with_backoff(attempt)

    raise LockTimeoutError(target, config.retry_max_attempts)


def safe_append_jsonl(
    path: Path | str,
    record: dict[str, Any],
    *,
    hash_chain: bool = False,
    lock_timeout_s: float | None = None,
    retry_max_attempts: int | None = None,
) -> dict[str, Any]:
    payload = dict(record)

    def _write_locked(target: Path) -> dict[str, Any]:
        next_payload = dict(payload)
        if hash_chain:
            previous_hash = _latest_entry_hash(target)
            digest = hashlib.sha256(
                f"{previous_hash}|{_canonical_hash_payload(next_payload)}".encode("utf-8")
            ).hexdigest()
            next_payload["prev_hash"] = previous_hash
            next_payload["entry_hash"] = digest
        _append_jsonl_payload(target, next_payload, ensure_ascii=bool(hash_chain))
        return next_payload

    return safe_with_file_lock(
        path=path,
        callback=_write_locked,
        lock_timeout_s=lock_timeout_s,
        retry_max_attempts=retry_max_attempts,
    )


@contextmanager
def safe_sqlite_connect(
    path: Path | str,
    *,
    busy_timeout_ms: int = 5000,
    wal: bool = True,
    retry_max_attempts: int | None = None,
) -> Iterator[sqlite3.Connection]:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    attempts = max(1, int(retry_max_attempts if retry_max_attempts is not None else _DEFAULT_CONFIG.retry_max_attempts))
    busy_timeout = max(0, int(busy_timeout_ms))

    connection: sqlite3.Connection | None = None
    for attempt in range(attempts):
        try:
            connection = sqlite3.connect(
                str(target),
                timeout=max(0.1, busy_timeout / 1000.0),
                check_same_thread=False,
            )
            connection.execute(f"PRAGMA busy_timeout={busy_timeout}")
            if wal:
                connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            break
        except sqlite3.OperationalError as exc:
            if connection is not None:
                connection.close()
            error_text = str(exc).lower()
            if "locked" not in error_text and "busy" not in error_text:
                raise
            if attempt >= attempts - 1:
                raise
            _sleep_with_backoff(attempt)

    if connection is None:
        raise RuntimeError(f"could not open sqlite connection for {target}")

    try:
        yield connection
    finally:
        connection.close()


def validate_jsonl_chain(path: Path | str) -> tuple[bool, str]:
    from lumina_core.audit.hash_chain import validate_hash_chain

    return validate_hash_chain(Path(path))
