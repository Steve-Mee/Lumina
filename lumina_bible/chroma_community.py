"""Resolve Chroma collection for vetted community knowledge (runtime app or persistent fallback)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_cache: dict[str, Any] = {}


def reset_community_vector_collection_cache() -> None:
    """Test helper: clear cached PersistentClient collection handles."""
    _cache.clear()


def resolve_community_vector_collection(
    engine: Any | None,
    *,
    community_cfg: dict[str, Any] | None = None,
) -> Any | None:
    """
    Chroma target for :meth:`VectorContributionAPI.upload_community_vetted`.

    1) If the engine is bound to a runtime app with ``app.collection`` (Chroma
       collection with ``add`` / ``query``), use that — same store as
       :class:`lumina_core.engine.memory_service.MemoryService`.
    2) Else, if ``chroma_persist_path`` is set under ``evolution.community_knowledge``,
       use (and cache) a dedicated persistent Chroma collection so nightly evolution
       can upsert vetted snippets without a full UI runtime.
    """
    cfg = community_cfg or {}

    if engine is not None:
        app = getattr(engine, "app", None)
        if app is not None:
            coll = getattr(app, "collection", None)
            if coll is not None and hasattr(coll, "add"):
                return coll

    path = str(cfg.get("chroma_persist_path", "") or "").strip()
    if not path:
        return None
    name = str(cfg.get("chroma_collection_name", "lumina_community_vetted") or "lumina_community_vetted").strip()
    cache_key = f"{path}::{name}"
    if cache_key in _cache:
        return _cache[cache_key]

    try:
        import chromadb
        from chromadb.config import Settings
    except Exception as exc:  # pragma: no cover - optional dependency / import errors
        logger.debug("Chroma not available for community store: %s", exc)
        return None

    try:
        client = chromadb.PersistentClient(path=path, settings=Settings(anonymized_telemetry=False))
        coll = client.get_or_create_collection(
            name=name,
            metadata={"lumina_purpose": "community_vetted_wisdom"},
        )
        _cache[cache_key] = coll
        return coll
    except Exception as exc:
        logger.warning("[CHROMA_COMMUNITY] could not open persistent store path=%s: %s", path, exc)
        return None
