from __future__ import annotations

import logging
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.audit.hash_chain import validate_hash_chain
from lumina_core.state.state_manager import safe_append_jsonl

logger = logging.getLogger(__name__)

_CHAIN_VERSION = "lumina_audit_v1"


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
        include_legacy_hash: bool = False,
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
        record["chain_version"] = _CHAIN_VERSION
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
        if include_legacy_hash and "hash" not in record:
            # Placeholder: state_manager fills this with entry_hash atomically.
            record["hash"] = ""

        try:
            return safe_append_jsonl(path=target, record=record, hash_chain=True)
        except Exception as exc:
            logger.exception("AuditLogger append failed for stream=%s path=%s", stream, target)
            if fail_closed_real and mode_key == "real":
                raise AuditChainError(f"Audit append failed in REAL mode for stream '{stream}'") from exc
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
            except Exception as exc:
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
            if "entry_hash" not in parsed and "hash" not in parsed:
                return ChainValidationReport(path=path, valid=False, message="tail_missing_hash")
            return ChainValidationReport(path=path, valid=True, message="ok")
        return ChainValidationReport(path=path, valid=True, message="empty")
