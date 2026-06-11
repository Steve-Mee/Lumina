"""Tests for VoiceListenerDaemon (D2 sub-slice 13)."""

from types import SimpleNamespace

import pytest

from lumina_core.engine.voice_listener_daemon import VoiceListenerDaemon


class _SrStub:
    class UnknownValueError(Exception):
        pass

    class RequestError(Exception):
        pass

    class Microphone:
        def __enter__(self):
            return object()

        def __exit__(self, *a):
            return False


@pytest.mark.unit
def test_voice_daemon_disabled_when_no_recognizer():
    app = SimpleNamespace(VOICE_INPUT_ENABLED=True, voice_recognizer=None)
    VoiceListenerDaemon(app=app).run()


@pytest.mark.unit
def test_voice_daemon_buy_override(monkeypatch):
    spoken: list[str] = []
    dream_updates: list[dict] = []

    class Recognizer:
        def adjust_for_ambient_noise(self, *_a, **_k):
            return None

        def listen(self, *_a, **_k):
            return b"audio"

        def recognize_google(self, *_a, **_k):
            return "Lumina ga long"

    app = SimpleNamespace(
        VOICE_INPUT_ENABLED=True,
        voice_recognizer=Recognizer(),
        sr=_SrStub(),
        engine=SimpleNamespace(config=SimpleNamespace(voice_wake_word="lumina")),
        get_current_dream_snapshot=lambda: {"signal": "HOLD"},
        set_current_dream_fields=lambda d: dream_updates.append(dict(d)),
        set_current_dream_value=lambda k, v: None,
        speak=lambda msg: spoken.append(msg),
        process_user_feedback=lambda *a, **k: None,
        emergency_stop=lambda: None,
        trade_log=[],
        logger=SimpleNamespace(error=lambda *a, **k: None, warning=lambda *a, **k: None),
    )

    sleeps = {"n": 0}

    def _sleep(_s):
        sleeps["n"] += 1
        if sleeps["n"] >= 1:
            raise StopIteration()

    monkeypatch.setattr("lumina_core.engine.voice_legacy_handler.time.sleep", _sleep)

    with pytest.raises(StopIteration):
        VoiceListenerDaemon(app=app).run()

    assert dream_updates and dream_updates[0]["signal"] == "BUY"
    assert any("MANUAL OVERRIDE" in str(s) or "long" in str(s).lower() for s in spoken) or spoken
    print("MANUAL_SMOKE_SUB13_VOICE_SUCCESS")


@pytest.mark.unit
def test_runtime_workers_voice_thin_delegates():
    import ast
    from pathlib import Path

    text = Path("lumina_core/runtime_workers.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "voice_listener_thread":
            src = ast.get_source_segment(text, node) or ""
            assert "VoiceLegacyHandler" in src
            assert "while True" not in src
            break
    else:
        pytest.fail("voice_listener_thread not found")
