"""Windows-safe atomic text replace (temp + fsync + retried os.replace)."""

from __future__ import annotations

import os
import stat
import time
from collections.abc import Sequence
from pathlib import Path

# WinError 5 ACCESS_DENIED, 32 SHARING_VIOLATION — dest/src briefly locked
# by Defender, Search Indexer, or a concurrent reader of a large file.
_RETRY_WINERRORS = frozenset({5, 32})
_RETRY_ERRNOS = frozenset({11, 13, 16})  # EAGAIN, EACCES, EBUSY

_DEFAULT_RETRIES = 16
_DEFAULT_BASE_DELAY_SEC = 0.05
_DEFAULT_MAX_DELAY_SEC = 2.0


def is_retryable_replace_error(exc: BaseException) -> bool:
    if isinstance(exc, PermissionError):
        return True
    if not isinstance(exc, OSError):
        return False
    winerror = getattr(exc, "winerror", None)
    if winerror in _RETRY_WINERRORS:
        return True
    return getattr(exc, "errno", None) in _RETRY_ERRNOS


def unique_tmp_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.{os.getpid()}.{time.time_ns()}.tmp")


def legacy_tmp_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.tmp")


def tmp_siblings(path: Path) -> list[Path]:
    """Fixed-name leftover plus unique ``name.<pid>.<ns>.tmp`` siblings."""
    parent = path.parent
    if not parent.is_dir():
        return []
    found: list[Path] = []
    legacy = legacy_tmp_path(path)
    if legacy.is_file():
        found.append(legacy)
    prefix = f"{path.name}."
    for child in parent.iterdir():
        if not child.is_file():
            continue
        if child.name.startswith(prefix) and child.name.endswith(".tmp"):
            found.append(child)
    return found


def _clear_readonly(path: Path) -> None:
    try:
        if path.exists() and not os.access(path, os.W_OK):
            path.chmod(stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass


def write_text_fsync(path: Path, encoded: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOINHERIT"):
        flags |= os.O_NOINHERIT
    fd = os.open(str(path), flags, 0o644)
    owned = True
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            owned = False
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        if owned:
            os.close(fd)


def replace_with_retry(
    src: Path,
    dst: Path,
    *,
    retries: int = _DEFAULT_RETRIES,
    base_delay_sec: float = _DEFAULT_BASE_DELAY_SEC,
) -> None:
    _clear_readonly(dst)
    delay = max(0.01, float(base_delay_sec))
    attempts = max(1, int(retries))
    last: OSError | None = None
    for attempt in range(attempts):
        try:
            os.replace(src, dst)
            return
        except OSError as exc:
            last = exc
            if not is_retryable_replace_error(exc) or attempt + 1 >= attempts:
                raise
            time.sleep(delay)
            delay = min(delay * 2.0, _DEFAULT_MAX_DELAY_SEC)
            _clear_readonly(dst)
    if last is not None:
        raise last


def atomic_write_text(
    path: Path | str,
    encoded: str,
    *,
    retries: int = _DEFAULT_RETRIES,
    base_delay_sec: float = _DEFAULT_BASE_DELAY_SEC,
) -> None:
    """Write ``encoded`` via unique tmp + fsync + retried replace. Dest unchanged on failure."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = unique_tmp_path(dest)
    try:
        write_text_fsync(tmp_path, encoded)
        replace_with_retry(tmp_path, dest, retries=retries, base_delay_sec=base_delay_sec)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def atomic_write_text_many(
    parts: Sequence[tuple[Path | str, str]],
    *,
    retries: int = _DEFAULT_RETRIES,
    base_delay_sec: float = _DEFAULT_BASE_DELAY_SEC,
) -> None:
    """Stage every payload to a unique tmp, then replace dests in order.

    Later dests stay untouched if an earlier replace fails. Callers must put the
    commit-bit (manifest) last and the lock-sensitive dest (split cache) first.
    """
    staged: list[tuple[Path, Path]] = []
    try:
        for raw_dest, encoded in parts:
            dest = Path(raw_dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = unique_tmp_path(dest)
            write_text_fsync(tmp_path, encoded)
            staged.append((tmp_path, dest))
        for tmp_path, dest in staged:
            replace_with_retry(tmp_path, dest, retries=retries, base_delay_sec=base_delay_sec)
    except Exception:
        for tmp_path, _dest in staged:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise
