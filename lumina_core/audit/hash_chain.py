from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.audit.audit_logger import validate_hash_chain
from lumina_core.state.state_manager import safe_append_jsonl

__all__ = ["append_hash_chained_jsonl", "validate_hash_chain"]


def append_hash_chained_jsonl(path: Path, entry: dict[str, Any]) -> dict[str, Any]:
    """Append record with prev_hash + entry_hash to a JSONL file."""
    return safe_append_jsonl(path=path, record=entry, hash_chain=True)
