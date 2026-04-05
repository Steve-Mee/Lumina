"""Tests for VectorContributionAPI — upload_experience and upload_batch."""
from __future__ import annotations

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from lumina_bible.vector_api import VectorContributionAPI


# ---------------------------------------------------------------------------
# Minimal collection stub
# ---------------------------------------------------------------------------

class _FakeCollection:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def add(self, documents, metadatas, ids):
        self.calls.append({"documents": documents, "metadatas": metadatas, "ids": ids})


class _BrokenCollection:
    """Collection whose add() always raises."""
    def add(self, **_):
        raise RuntimeError("db error")


# ---------------------------------------------------------------------------
# upload_experience
# ---------------------------------------------------------------------------

class TestUploadExperience:
    def test_happy_path_returns_true(self):
        col = _FakeCollection()
        api = VectorContributionAPI()
        result = api.upload_experience(col, "lost on breakout fade", {"pnl": -50})
        assert result is True
        assert len(col.calls) == 1
        assert col.calls[0]["documents"] == ["lost on breakout fade"]

    def test_injects_date_when_missing(self):
        col = _FakeCollection()
        api = VectorContributionAPI()
        api.upload_experience(col, "scalp entry", {})
        meta = col.calls[0]["metadatas"][0]
        assert "date" in meta

    def test_injects_type_when_missing(self):
        col = _FakeCollection()
        api = VectorContributionAPI()
        api.upload_experience(col, "momentum trade", {})
        meta = col.calls[0]["metadatas"][0]
        assert meta.get("type") == "community_contribution"

    def test_none_collection_returns_false(self):
        api = VectorContributionAPI()
        assert api.upload_experience(None, "text", {}) is False

    def test_collection_without_add_returns_false(self):
        api = VectorContributionAPI()
        assert api.upload_experience(object(), "text", {}) is False

    def test_broken_add_returns_false(self):
        api = VectorContributionAPI()
        assert api.upload_experience(_BrokenCollection(), "text", {}) is False


# ---------------------------------------------------------------------------
# upload_batch
# ---------------------------------------------------------------------------

class TestUploadBatch:
    def test_uploads_all_valid_rows(self):
        col = _FakeCollection()
        api = VectorContributionAPI()
        rows = [
            {"context": "trade A", "metadata": {"pnl": 100}},
            {"context": "trade B", "metadata": {"pnl": -30}},
        ]
        count = api.upload_batch(col, rows)
        assert count == 2

    def test_skips_empty_context_rows(self):
        col = _FakeCollection()
        api = VectorContributionAPI()
        rows = [{"context": "", "metadata": {}}, {"context": "  ", "metadata": {}}]
        count = api.upload_batch(col, rows)
        assert count == 0

    def test_missing_context_key_skipped(self):
        col = _FakeCollection()
        api = VectorContributionAPI()
        count = api.upload_batch(col, [{"metadata": {}}])
        assert count == 0

    def test_non_dict_metadata_converted(self):
        col = _FakeCollection()
        api = VectorContributionAPI()
        count = api.upload_batch(col, [{"context": "signal", "metadata": "raw string"}])
        assert count == 1
        meta = col.calls[0]["metadatas"][0]
        assert "raw" in meta

    def test_none_collection_returns_zero(self):
        api = VectorContributionAPI()
        assert api.upload_batch(None, [{"context": "x", "metadata": {}}]) == 0

    def test_partial_success(self):
        class _FailOnSecond:
            calls = 0
            def add(self, documents, metadatas, ids):
                _FailOnSecond.calls += 1
                if _FailOnSecond.calls % 2 == 0:
                    raise RuntimeError("intermittent")

        col = _FailOnSecond()
        api = VectorContributionAPI()
        rows = [{"context": f"t{i}", "metadata": {}} for i in range(4)]
        count = api.upload_batch(col, rows)
        # calls 1 and 3 succeed (odd calls), 2 and 4 fail
        assert count == 2
