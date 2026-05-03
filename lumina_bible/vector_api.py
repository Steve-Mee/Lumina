from __future__ import annotations
import logging

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any


def stable_community_document_id(*, source: str, content: str) -> str:
    """Deterministic Chroma id for dedupe across nightly ingestion."""
    payload = f"{source}|{content[:4096]}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:48]


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
            logging.exception("Unhandled broad exception fallback in lumina_bible/vector_api.py:32")
            return False

    def upload_community_vetted(
        self,
        collection: Any,
        *,
        document: str,
        source: str,
        metadata: dict[str, Any],
    ) -> bool:
        """Store externally vetted community wisdom with stable id and provenance metadata."""
        if collection is None or not hasattr(collection, "add"):
            return False
        text = str(document).strip()
        if not text:
            return False
        payload_meta = dict(metadata)
        payload_meta.setdefault("date", datetime.now().isoformat())
        payload_meta.setdefault("type", "community_vetted_wisdom")
        payload_meta.setdefault("source", str(source))
        payload_meta.setdefault("vetting_status", "shadow_twin_ok")
        doc_id = str(payload_meta.get("document_id") or stable_community_document_id(source=source, content=text))
        payload_meta.setdefault("document_id", doc_id)
        try:
            collection.add(documents=[text], metadatas=[payload_meta], ids=[doc_id])
            return True
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_bible/vector_api.py:59")
            return False

    def query_community_layer(
        self,
        collection: Any,
        *,
        query: str,
        n_results: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Query Chroma collection; returns [] if unavailable or error."""
        if collection is None or not hasattr(collection, "query"):
            return []
        try:
            kwargs: dict[str, Any] = {"query_texts": [str(query)], "n_results": int(n_results)}
            if where:
                kwargs["where"] = where
            raw = collection.query(**kwargs)
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_bible/vector_api.py:78")
            return []
        out: list[dict[str, Any]] = []
        docs = (raw or {}).get("documents") or []
        metas = (raw or {}).get("metadatas") or []
        ids = (raw or {}).get("ids") or []
        if not docs or not docs[0]:
            return []
        for i, doc in enumerate(docs[0]):
            meta = metas[0][i] if metas and metas[0] and i < len(metas[0]) else {}
            rid = ids[0][i] if ids and ids[0] and i < len(ids[0]) else ""
            out.append({"id": str(rid), "document": str(doc), "metadata": dict(meta) if isinstance(meta, dict) else {}})
        return out

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
