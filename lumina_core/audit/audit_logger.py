from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.audit.canonical_hash import AUDIT_SCHEMA_VERSION, GENESIS_HASH, compute_entry_hash
from lumina_core.fault import FaultDomain, FaultPolicy
from lumina_core.state.state_manager import safe_append_jsonl

logger = logging.getLogger(__name__)


class AuditChainError(RuntimeError):
    """Raised when append/validation fails in fail-closed mode."""


@dataclass(slots=True)
class ChainValidationReport:
    path: Path
    valid: bool
    message: str

    @property
    def tampered(self) -> bool:
        return not self.valid


@dataclass(slots=True)
class StreamRegistry:
    root: Path = Path("state")
    _streams: dict[str, Path] = field(default_factory=dict)

    def register(self, stream: str, path: Path | str) -> None:
        self._streams[self._normalize_stream(stream)] = Path(path)

    def resolve(self, stream: str) -> Path:
        key = self._normalize_stream(stream)
        if key in self._streams:
            return self._streams[key]
        return self.root / f"{key.replace('.', '_')}.jsonl"

    def _normalize_stream(self, stream: str) -> str:
        value = str(stream).strip().lower()
        if not value:
            raise ValueError("Audit stream must be non-empty")
        return value


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, set):
        return sorted(_json_safe(item) for item in value)
    return value


def validate_hash_chain(path: Path) -> tuple[bool, str]:
    """Validate the full chain and return (ok, message)."""
    if not path.exists():
        return True, "missing_file_treated_as_empty"
    prev = GENESIS_HASH
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return False, f"io_error:{exc}"
    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            return False, f"json_parse_error_line_{idx}"
        if not isinstance(entry, dict):
            return False, f"non_object_line_{idx}"
        recorded_prev = str(entry.get("prev_hash", ""))
        recorded_hash = str(entry.get("entry_hash", ""))
        if recorded_prev != prev:
            return False, f"prev_hash_mismatch_line_{idx}"
        expected = compute_entry_hash(recorded_prev, entry)
        if recorded_hash != expected:
            return False, f"entry_hash_mismatch_line_{idx}"
        prev = recorded_hash
    return True, "ok"


@dataclass(slots=True)
class AuditLogger:
    registry: StreamRegistry = field(default_factory=StreamRegistry)

    def register_stream(self, stream: str, path: Path | str) -> None:
        self.registry.register(stream, path)

    def resolve_path(self, stream: str, *, path: Path | str | None = None) -> Path:
        if path is not None:
            resolved = Path(path)
            self.registry.register(stream, resolved)
            return resolved
        return self.registry.resolve(stream)

    def append(
        self,
        *,
        stream: str,
        payload: dict[str, Any],
        path: Path | str | None = None,
        mode: str | None = None,
        actor_id: str | None = None,
        correlation_id: str | None = None,
        severity: str | None = None,
        timestamp: str | None = None,
        fail_closed_real: bool = False,
    ) -> dict[str, Any]:
        target = self.resolve_path(stream, path=path)
        mode_key = str(mode or "sim").strip().lower()
        self._ensure_chain_integrity(
            target,
            mode=mode_key,
            fail_closed_real=bool(fail_closed_real),
            strict_validation=(mode_key == "real" or bool(fail_closed_real)),
        )

        record = dict(_json_safe(payload))
        record["schema_version"] = AUDIT_SCHEMA_VERSION
        record["stream"] = str(stream).strip().lower()
        record["timestamp"] = timestamp or datetime.now(timezone.utc).isoformat()
        if actor_id is not None:
            record["actor_id"] = str(actor_id)
        if mode is not None:
            record["mode"] = mode_key
        if correlation_id is not None:
            record["correlation_id"] = str(correlation_id)
        if severity is not None:
            record["severity"] = str(severity)

        try:
            return safe_append_jsonl(path=target, record=record, hash_chain=True)
        except OSError as exc:
            is_real_mode = bool(fail_closed_real and mode_key == "real")
            FaultPolicy.handle(
                domain=FaultDomain.AUDIT_LOGGER,
                operation="append_hash_chain",
                exc=exc,
                is_real_mode=is_real_mode,
                fault_cls=AuditChainError,
                message=f"AuditLogger append failed for stream={stream} path={target}",
                context={"stream": str(stream), "path": str(target), "mode": mode_key},
                logger_obj=logger,
            )
            raise

    def verify(self, stream: str, *, path: Path | str | None = None) -> ChainValidationReport:
        target = self.resolve_path(stream, path=path)
        ok, message = validate_hash_chain(target)
        return ChainValidationReport(path=target, valid=ok, message=message)

    def tail(
        self,
        stream: str,
        *,
        limit: int = 100,
        path: Path | str | None = None,
    ) -> list[dict[str, Any]]:
        target = self.resolve_path(stream, path=path)
        if not target.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line_number, raw in enumerate(target.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                parsed = _json_safe(json.loads(line))
            except json.JSONDecodeError as exc:
                logger.warning(
                    "AuditLogger tail skipped invalid JSON line %s in %s",
                    line_number,
                    target,
                    exc_info=exc,
                )
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
        if limit <= 0:
            return rows
        return rows[-limit:]

    def _ensure_chain_integrity(
        self,
        path: Path,
        *,
        mode: str,
        fail_closed_real: bool,
        strict_validation: bool,
    ) -> None:
        if not path.exists():
            return
        if strict_validation:
            ok, message = validate_hash_chain(path)
            report = ChainValidationReport(path=path, valid=ok, message=message)
        else:
            report = self._quick_tail_health(path)
        if report.valid:
            return
        if fail_closed_real and mode == "real":
            raise AuditChainError(f"Audit chain invalid at {path}: {report.message}")
        logger.warning("AuditLogger recovering corrupt chain at %s: %s", path, report.message)
        suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = path.with_suffix(f"{path.suffix}.corrupt.{suffix}")
        try:
            path.rename(backup)
        except OSError:
            logger.exception("AuditLogger failed to move corrupt chain file %s", path)

    def _quick_tail_health(self, path: Path) -> ChainValidationReport:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            return ChainValidationReport(path=path, valid=False, message=f"io_error:{exc}")
        for raw in reversed(lines):
            line = raw.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                return ChainValidationReport(path=path, valid=False, message="tail_json_parse_error")
            if not isinstance(parsed, dict):
                return ChainValidationReport(path=path, valid=False, message="tail_record_invalid")
            if "entry_hash" not in parsed:
                return ChainValidationReport(path=path, valid=False, message="tail_missing_hash")
            return ChainValidationReport(path=path, valid=True, message="ok")
        return ChainValidationReport(path=path, valid=True, message="empty")
