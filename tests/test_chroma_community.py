from __future__ import annotations

import importlib.util
from types import SimpleNamespace
from typing import Any

import pytest

from lumina_bible.chroma_community import (
    reset_community_vector_collection_cache,
    resolve_community_vector_collection,
)


class _Collection:
    def add(self, *args: Any, **kwargs: Any) -> None:
        return None


def test_resolve_uses_app_collection_first() -> None:
    reset_community_vector_collection_cache()
    coll = _Collection()
    engine = SimpleNamespace(app=SimpleNamespace(collection=coll))
    out = resolve_community_vector_collection(
        engine,
        community_cfg={"chroma_persist_path": "state/should_not_use_while_app_has_collection"},
    )
    assert out is coll


def test_resolve_returns_none_without_path_and_no_app() -> None:
    reset_community_vector_collection_cache()
    assert resolve_community_vector_collection(None, community_cfg={}) is None


@pytest.mark.skipif(importlib.util.find_spec("chromadb") is None, reason="chromadb not installed")
def test_resolve_opens_persistent_client(tmp_path) -> None:
    reset_community_vector_collection_cache()
    p = str(tmp_path / "chroma_data")
    out = resolve_community_vector_collection(
        None,
        community_cfg={"chroma_persist_path": p, "chroma_collection_name": "c_test"},
    )
    try:
        assert out is not None
        assert hasattr(out, "add")
    finally:
        reset_community_vector_collection_cache()
