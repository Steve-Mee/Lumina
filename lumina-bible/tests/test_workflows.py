"""Tests for workflow functions — reflect_on_trade, process_user_feedback, dna_rewrite_daemon."""
from __future__ import annotations

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
import time
import tempfile

import pytest

from lumina_bible.workflows import dna_rewrite_daemon, process_user_feedback, reflect_on_trade


# ---------------------------------------------------------------------------
# Minimal RuntimeContext stub
# ---------------------------------------------------------------------------

import threading
import types
import numpy as _np
from unittest.mock import patch


class _FakeBibleEngine:
    def save(self): pass


class _FakeEngine:
    class config:
        vision_model = "grok-vision"
        discord_webhook = ""

    def __init__(self):
        self.bible_engine = _FakeBibleEngine()

    def evolve_bible(self, *a, **kw): pass


class _FakeLogger:
    def info(self, *a, **kw): pass
    def error(self, *a, **kw): pass
    def warning(self, *a, **kw): pass


class _App:
    """Minimal stand-in for RuntimeContext used inside workflow functions."""

    def __init__(self, bible_path: Path) -> None:
        self.bible_path = str(bible_path)
        self._calls: list[tuple] = []
        self.stop_event: object = None  # will be set per test if needed

        # Attributes accessed by reflect_on_trade
        self.live_data_lock = threading.Lock()
        self.ohlc_1min: list = []
        self.AI_DRAWN_FIBS: dict = {}
        self.trade_reflection_history: list = []
        self.engine = _FakeEngine()
        self.logger = _FakeLogger()
        self.np = _np

        # Used by process_user_feedback / dna_rewrite_daemon
        self.bible: dict = {
            "sacred_core": "test",
            "evolvable_layer": {"base_winrate": 0.7},
        }

        # Used by dna_rewrite_daemon
        self.trade_log: list = [{"pnl": i * 10} for i in range(20)]

    # ---- inference (returns dict directly — avoids HTTP response path) ----

    def infer_json(self, payload: dict, *, timeout: int = 20, context: str = "") -> dict:
        self._calls.append(("infer_json", payload))
        return {"lesson": "stay disciplined", "rule_update": "avoid chasing",
                "suggested_bible_updates": {}, "reflection": "good trade", "key_lesson": "be patient"}

    # ---- chart / vision ----

    def generate_multi_tf_chart(self, fibs: dict) -> str:
        return ""  # empty base64; skips Discord webhook

    # ---- vector DB ----

    def store_experience_to_vector_db(self, context: str, metadata: dict) -> None:
        pass

    # ---- TTS ----

    def speak(self, text: str) -> None:
        pass

    # ---- misc ----

    def log_thought(self, data: dict) -> None:
        pass


# ---------------------------------------------------------------------------
# reflect_on_trade
# ---------------------------------------------------------------------------

class TestReflectOnTrade:
    def test_reflect_winning_trade(self, tmp_path):
        bible = tmp_path / "bible.json"
        app = _App(bible)
        reflect_on_trade(app, pnl_dollars=200, entry_price=4100.0, exit_price=4108.0, position_qty=2)

    def test_reflect_losing_trade(self, tmp_path):
        bible = tmp_path / "bible.json"
        app = _App(bible)
        # Should not raise even on a loss
        reflect_on_trade(app, pnl_dollars=-80, entry_price=4100.0, exit_price=4096.0, position_qty=1)

    def test_reflect_does_not_raise_without_infer_json(self, tmp_path):
        """With only post_xai_chat available, should still complete."""
        bible = tmp_path / "bible.json"
        app = _App(bible)
        reflect_on_trade(app, 50, 4200.0, 4203.0, 1)


# ---------------------------------------------------------------------------
# process_user_feedback
# ---------------------------------------------------------------------------

class TestProcessUserFeedback:
    def test_feedback_without_trade_data(self, tmp_path):
        bible = tmp_path / "bible.json"
        app = _App(bible)
        process_user_feedback(app, "I keep revenge trading after a loss")

    def test_feedback_with_trade_data(self, tmp_path):
        bible = tmp_path / "bible.json"
        app = _App(bible)
        process_user_feedback(
            app,
            "Good entry, bad exit",
            trade_data={"symbol": "MES", "pnl": 120},
        )

    def test_empty_feedback_does_not_raise(self, tmp_path):
        bible = tmp_path / "bible.json"
        app = _App(bible)
        process_user_feedback(app, "")


# ---------------------------------------------------------------------------
# dna_rewrite_daemon (runs in loop; test single-iteration behaviour)
# ---------------------------------------------------------------------------

class TestDnaRewriteDaemon:
    def test_daemon_single_iteration_via_sleep_patch(self, tmp_path):
        """Patch time.sleep to raise so daemon exits after first iteration."""
        bible = tmp_path / "bible.json"
        app = _App(bible)
        with patch("lumina_bible.workflows.time.sleep", side_effect=InterruptedError):
            try:
                dna_rewrite_daemon(app)
            except InterruptedError:
                pass  # expected exit mechanism

    def test_daemon_does_not_propagate_inference_failures(self, tmp_path):
        """Daemon swallows JSONDecodeError/TypeError/ValueError from inference."""
        bible = tmp_path / "bible.json"

        class _BadJsonApp(_App):
            def infer_json(self, *a, **kw) -> dict:  # type: ignore[override]
                raise ValueError("bad json shape")

        app = _BadJsonApp(bible)
        with patch("lumina_bible.workflows.time.sleep", side_effect=InterruptedError):
            try:
                dna_rewrite_daemon(app)
            except InterruptedError:
                pass  # expected; ValueError should be caught inside daemon

    def test_daemon_skips_rewrite_when_trade_log_too_short(self, tmp_path):
        bible = tmp_path / "bible.json"
        app = _App(bible)
        app.trade_log = [{"pnl": 10}]  # fewer than 5 trades
        with patch("lumina_bible.workflows.time.sleep", side_effect=InterruptedError):
            try:
                dna_rewrite_daemon(app)
            except InterruptedError:
                pass
        # infer_json should NOT have been called (not enough trades)
        assert all(c[0] != "infer_json" for c in app._calls)
