from __future__ import annotations

import importlib.util
from types import SimpleNamespace

import pytest
import yaml  # type: ignore[import-not-found]

from lumina_core.engine.errors import LuminaError
from lumina_core.engine.local_inference_engine import LocalInferenceEngine


class _Logger:
    def info(self, *_args, **_kwargs):
        return None

    def warning(self, *_args, **_kwargs):
        return None

    def error(self, *_args, **_kwargs):
        return None


def _write_config(tmp_path, *, primary_provider="ollama", fallback_order=None):
    if fallback_order is None:
        fallback_order = ["vllm", "ollama", "grok_remote"]
    config = {
        "hardware_profile": "light",
        "inference": {
            "primary_provider": primary_provider,
            "fallback_order": fallback_order,
            "provider_calibration": {"ollama": 1.1, "vllm": 0.9, "grok_remote": 1.0},
            "provider_calibration_by_regime": {
                "TRENDING": {"ollama": 1.2, "vllm": 1.0, "DEFAULT": 1.0},
                "VOLATILE": {"ollama": 0.8, "vllm": 0.9, "DEFAULT": 1.0},
            },
            "max_tokens": 1200,
            "temperature": 0.65,
            "json_mode": True,
            "fast_path_threshold": 0.75,
        },
        "models": {
            "vision": "qwen2.5-vl:7b",
            "reasoning": "qwen2.5:7b",
            "reflector": "qwen2.5:3b",
            "meta": "qwen2.5:14b",
            "grok_trader_1b": "grok-trader-1b",
        },
        "vllm": {"host": "http://localhost:8000", "model_name": "grok-trader-1b"},
        "ollama": {"base_url": "http://localhost:11434", "temperature": 0.65, "num_ctx": 16384, "num_gpu": -1},
    }
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")


def _context():
    return SimpleNamespace(logger=_Logger(), cost_tracker={}, config=SimpleNamespace(xai_key="test-key"))


def test_local_inference_engine_fail_hard_when_primary_provider_fails(monkeypatch, tmp_path):
    _write_config(tmp_path, primary_provider="ollama", fallback_order=["vllm", "grok_remote"])
    monkeypatch.chdir(tmp_path)

    engine = LocalInferenceEngine(context=_context())
    calls: list[str] = []

    def _ollama(*_args, **_kwargs):
        calls.append("ollama")
        raise RuntimeError("ollama down")

    def _vllm(*_args, **_kwargs):
        calls.append("vllm")
        return {"signal": "BUY", "confidence": 0.82}

    monkeypatch.setattr(engine, "_is_vllm_healthy", lambda force=False: True)
    monkeypatch.setattr(engine, "_infer_via_ollama", _ollama)
    monkeypatch.setattr(engine, "_infer_via_vllm", _vllm)

    with pytest.raises(LuminaError, match="Inference provider execution failed"):
        engine.infer("test", model_type="reasoning")

    assert calls == ["ollama"]
    assert engine.get_backend() == "ollama"
    assert engine.cost_tracker["local_inference_provider_stats"]["ollama"]["failures"] == 1


def test_local_inference_engine_hot_reloads_config_without_restart(monkeypatch, tmp_path):
    _write_config(tmp_path, primary_provider="ollama", fallback_order=["vllm"])
    monkeypatch.chdir(tmp_path)

    engine = LocalInferenceEngine(context=_context())
    assert engine.get_backend() == "ollama"

    _write_config(tmp_path, primary_provider="vllm", fallback_order=["ollama"])

    calls: list[str] = []

    def _vllm(*_args, **_kwargs):
        calls.append("vllm")
        return {"signal": "HOLD", "confidence": 0.5}

    monkeypatch.setattr(engine, "_is_vllm_healthy", lambda force=False: True)
    monkeypatch.setattr(engine, "_infer_via_vllm", _vllm)
    engine.infer("reload-test", model_type="reasoning")

    assert calls == ["vllm"]
    assert engine.get_backend() == "vllm"
    assert engine.active_provider == "vllm"


def test_local_inference_engine_set_backend_overrides_config(monkeypatch, tmp_path):
    _write_config(tmp_path, primary_provider="ollama", fallback_order=["vllm"])
    monkeypatch.chdir(tmp_path)

    engine = LocalInferenceEngine(context=_context())
    assert engine.set_backend("grok_remote") == "grok_remote"
    assert engine.get_backend() == "grok_remote"


def test_local_inference_engine_tracks_latency_and_requests(monkeypatch, tmp_path):
    _write_config(tmp_path, primary_provider="ollama", fallback_order=[])
    monkeypatch.chdir(tmp_path)

    engine = LocalInferenceEngine(context=_context())

    def _ollama(*_args, **_kwargs):
        return {"signal": "SELL", "confidence": 0.77}

    monkeypatch.setattr(engine, "_infer_via_ollama", _ollama)

    result = engine.infer("metrics-test", model_type="reasoning")

    assert result["signal"] == "SELL"
    assert "harmonized_confidence" in result
    assert result["provider"] == "ollama"
    assert engine.cost_tracker["local_inference_requests"] == 1
    assert engine.cost_tracker["local_inference_last_provider"] == "ollama"
    assert engine.cost_tracker["local_inference_last_latency_ms"] >= 0.0
    assert engine.cost_tracker["local_inference_provider_stats"]["ollama"]["requests"] == 1


def test_local_inference_engine_exposes_metrics_summary(monkeypatch, tmp_path):
    _write_config(tmp_path, primary_provider="ollama", fallback_order=[])
    monkeypatch.chdir(tmp_path)

    engine = LocalInferenceEngine(context=_context())

    def _ollama(*_args, **_kwargs):
        return {"signal": "BUY", "confidence": 0.91}

    monkeypatch.setattr(engine, "_infer_via_ollama", _ollama)
    engine.infer("summary-test", model_type="reasoning")

    summary = engine.get_metrics_summary()

    assert summary["active_provider"] == "ollama"
    assert summary["requests"] == 1
    assert summary["avg_latency_ms"] >= 0.0


def test_local_inference_engine_unhealthy_vllm_fail_hard(monkeypatch, tmp_path):
    _write_config(tmp_path, primary_provider="vllm", fallback_order=["ollama", "grok_remote"])
    monkeypatch.chdir(tmp_path)

    engine = LocalInferenceEngine(context=_context())
    calls: list[str] = []

    def _vllm(*_args, **_kwargs):
        calls.append("vllm")
        raise AssertionError("vllm should be skipped when unhealthy")

    def _ollama(*_args, **_kwargs):
        calls.append("ollama")
        return {"signal": "HOLD", "confidence": 0.6}

    monkeypatch.setattr(engine, "_is_vllm_healthy", lambda force=False: False)
    monkeypatch.setattr(engine, "_infer_via_vllm", _vllm)
    monkeypatch.setattr(engine, "_infer_via_ollama", _ollama)

    with pytest.raises(LuminaError, match="INFERENCE_VLLM_UNHEALTHY"):
        engine.infer("gate-test", model_type="reasoning")

    assert calls == []


def test_local_inference_engine_reports_vllm_runtime_reason(monkeypatch, tmp_path):
    _write_config(tmp_path, primary_provider="vllm", fallback_order=["ollama"])
    monkeypatch.chdir(tmp_path)

    engine = LocalInferenceEngine(context=_context())

    original_find_spec = importlib.util.find_spec

    def _fake_find_spec(name, package=None):
        if name == "vllm._C":
            return None
        return original_find_spec(name, package)

    monkeypatch.setattr(importlib.util, "find_spec", _fake_find_spec)

    assert engine._is_vllm_healthy() is False
    assert "vllm._C" in engine.cost_tracker.get("local_inference_vllm_runtime_reason", "")
    assert engine.cost_tracker.get("local_inference_warning", "")


def test_local_inference_engine_applies_regime_aware_calibration(monkeypatch, tmp_path):
    _write_config(tmp_path, primary_provider="ollama", fallback_order=[])
    monkeypatch.chdir(tmp_path)

    ctx = _context()
    ctx.current_regime_snapshot = {"label": "TRENDING"}
    engine = LocalInferenceEngine(context=ctx)

    def _ollama(*_args, **_kwargs):
        return {"signal": "BUY", "confidence": 0.5}

    monkeypatch.setattr(engine, "_infer_via_ollama", _ollama)
    result = engine.infer("regime-calibration-test", model_type="reasoning")

    # Base 1.1 * trending 1.2 => 1.32 factor, confidence clipped to <= 1.0.
    assert result["provider"] == "ollama"
    assert result["calibration_factor"] == 1.32
    assert result["harmonized_confidence"] == 0.66


def test_local_inference_engine_grok_remote_success_path(monkeypatch, tmp_path):
    _write_config(tmp_path, primary_provider="grok_remote", fallback_order=[])
    monkeypatch.chdir(tmp_path)

    engine = LocalInferenceEngine(context=_context())

    class _Response:
        status_code = 200

        @staticmethod
        def json():
            return {"choices": [{"message": {"content": '{"signal":"BUY","confidence":0.7}'}}]}

    monkeypatch.setattr("lumina_core.engine.local_inference_engine.post_xai_chat", lambda **_kwargs: _Response())

    result = engine.infer("remote-ok", model_type="reasoning")

    assert result["signal"] == "BUY"
    assert result["provider"] == "grok_remote"
    assert result["confidence"] == 0.7


def test_local_inference_engine_grok_remote_missing_key_fail_hard(monkeypatch, tmp_path):
    _write_config(tmp_path, primary_provider="grok_remote", fallback_order=[])
    monkeypatch.chdir(tmp_path)

    ctx = _context()
    ctx.config = SimpleNamespace(xai_key="")
    engine = LocalInferenceEngine(context=ctx)

    with pytest.raises(LuminaError, match="XAI_KEY_MISSING"):
        engine.infer("remote-missing-key", model_type="reasoning")
