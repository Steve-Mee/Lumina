"""Tests for BibleEngine — load, save, evolve, export_public_bible."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lumina_bible.bible_engine import DEFAULT_BIBLE, BibleEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tmp_bible(tmp_path: Path, content: dict | None = None) -> Path:
    p = tmp_path / "bible.json"
    if content is not None:
        p.write_text(json.dumps(content), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# BibleEngine: construction / load
# ---------------------------------------------------------------------------

class TestBibleEngineLoad:
    def test_creates_default_file_when_missing(self, tmp_path):
        p = _tmp_bible(tmp_path)
        engine = BibleEngine(file_path=p)
        assert p.exists()
        data = json.loads(p.read_text())
        assert "evolvable_layer" in data

    def test_loads_existing_file(self, tmp_path):
        payload = {"sacred_core": "test", "evolvable_layer": {"key": "val"}}
        p = _tmp_bible(tmp_path, payload)
        engine = BibleEngine(file_path=p)
        assert engine.bible is not None
        assert engine.bible["evolvable_layer"]["key"] == "val"

    def test_file_path_coerced_to_path_object(self, tmp_path):
        p = _tmp_bible(tmp_path)
        engine = BibleEngine(file_path=p)  # Path object
        assert isinstance(engine.file_path, Path)

    def test_default_bible_has_sacred_core(self):
        assert "sacred_core" in DEFAULT_BIBLE
        assert "scalp" in DEFAULT_BIBLE["sacred_core"].lower() or "playbook" in DEFAULT_BIBLE["sacred_core"].lower()

    def test_default_bible_has_evolvable_layer(self):
        assert "evolvable_layer" in DEFAULT_BIBLE
        assert "probability_model" in DEFAULT_BIBLE["evolvable_layer"]


# ---------------------------------------------------------------------------
# BibleEngine: save / persist
# ---------------------------------------------------------------------------

class TestBibleEngineSave:
    def test_save_persists_changes(self, tmp_path):
        p = _tmp_bible(tmp_path)
        engine = BibleEngine(file_path=p)
        assert engine.bible is not None
        engine.bible["custom_key"] = "hello"
        engine.save()
        reloaded = json.loads(p.read_text())
        assert reloaded["custom_key"] == "hello"


# ---------------------------------------------------------------------------
# BibleEngine: evolve
# ---------------------------------------------------------------------------

class TestBibleEngineEvolve:
    def test_evolve_updates_evolvable_layer(self, tmp_path):
        p = _tmp_bible(tmp_path)
        engine = BibleEngine(file_path=p)
        engine.evolve({"new_signal": "RSI_divergence"})
        assert engine.evolvable_layer["new_signal"] == "RSI_divergence"

    def test_evolve_persists_to_disk(self, tmp_path):
        p = _tmp_bible(tmp_path)
        engine = BibleEngine(file_path=p)
        engine.evolve({"win_rate": 0.85})
        reloaded = json.loads(p.read_text())
        assert reloaded["evolvable_layer"]["win_rate"] == 0.85

    def test_evolve_partial_update_preserves_other_keys(self, tmp_path):
        p = _tmp_bible(tmp_path)
        engine = BibleEngine(file_path=p)
        original_tf = engine.evolvable_layer.get("mtf_matrix")
        engine.evolve({"extra_rule": "no_fomo"})
        assert engine.evolvable_layer.get("mtf_matrix") == original_tf


# ---------------------------------------------------------------------------
# BibleEngine: export_public_bible
# ---------------------------------------------------------------------------

class TestExportPublicBible:
    def test_sacred_core_hidden_by_default(self, tmp_path, monkeypatch):
        monkeypatch.delenv("LUMINA_BIBLE_EXPOSE_SACRED_CORE", raising=False)
        p = _tmp_bible(tmp_path)
        engine = BibleEngine(file_path=p)
        pub = engine.export_public_bible()
        assert pub["sacred_core"].startswith("<private")

    def test_sacred_core_hidden_when_flag_false(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LUMINA_BIBLE_EXPOSE_SACRED_CORE", "false")
        p = _tmp_bible(tmp_path)
        engine = BibleEngine(file_path=p)
        pub = engine.export_public_bible()
        assert pub["sacred_core"].startswith("<private")

    def test_sacred_core_exposed_when_flag_true(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LUMINA_BIBLE_EXPOSE_SACRED_CORE", "true")
        p = _tmp_bible(tmp_path)
        engine = BibleEngine(file_path=p)
        pub = engine.export_public_bible()
        # actual sacred core content should be present
        assert not pub["sacred_core"].startswith("<private")

    def test_export_does_not_mutate_original(self, tmp_path, monkeypatch):
        monkeypatch.delenv("LUMINA_BIBLE_EXPOSE_SACRED_CORE", raising=False)
        p = _tmp_bible(tmp_path)
        engine = BibleEngine(file_path=p)
        assert engine.bible is not None
        original_core = engine.bible["sacred_core"]
        engine.export_public_bible()
        assert engine.bible["sacred_core"] == original_core
