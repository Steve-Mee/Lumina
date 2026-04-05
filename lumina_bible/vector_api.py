from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class VectorContributionAPI:
    """Community contribution helpers for vector DB uploads."""

    def upload_experience(self, collection: Any, context: str, metadata: dict[str, Any]) -> bool:
        if collection is None or not hasattr(collection, "add"):
            return False
        payload_meta = dict(metadata)
        payload_meta.setdefault("date", datetime.now().isoformat())
        payload_meta.setdefault("type", "community_contribution")
        try:
            collection.add(
                documents=[context],
                metadatas=[payload_meta],
                ids=[datetime.now().isoformat()],
            )
            return True
        except Exception:
            return False

    def upload_batch(self, collection: Any, rows: list[dict[str, Any]]) -> int:
        if collection is None or not hasattr(collection, "add"):
            return 0
        uploaded = 0
        for row in rows:
            context = str(row.get("context", "")).strip()
            if not context:
                continue
            metadata = row.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {"raw": str(metadata)}
            if self.upload_experience(collection, context, metadata):
                uploaded += 1
        return uploaded
