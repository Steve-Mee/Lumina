from __future__ import annotations

from lumina_bible.vector_api import VectorContributionAPI, stable_community_document_id


def test_stable_community_document_id_is_deterministic() -> None:
    a = stable_community_document_id(source="paper", content="alpha beta")
    b = stable_community_document_id(source="paper", content="alpha beta")
    c = stable_community_document_id(source="trader", content="alpha beta")
    assert a == b
    assert a != c
    assert len(a) == 48


def test_upload_community_vetted_requires_collection() -> None:
    api = VectorContributionAPI()
    assert api.upload_community_vetted(None, document="hello", source="x", metadata={}) is False


def test_query_community_layer_empty_without_collection() -> None:
    api = VectorContributionAPI()
    assert api.query_community_layer(None, query="risk", n_results=3) == []
