from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from lumina_core.inference.llm_client import LlmClient


class _DummyInferenceEngine:
    def __init__(self, *, response: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        self.config = {
            "inference": {
                "temperature": 0.7,
                "llm_real_temperature": 0.35,
                "llm_max_latency_ms": 1200,
            }
        }
        self.active_provider = "ollama"
        self._response = response
        self._error = error
        self.last_call: dict[str, Any] = {}

    def infer_json(
        self,
        payload: dict[str, Any],
        timeout: int = 20,
        context: str = "xai_json",
        max_retries: int = 1,
        temperature_override: float | None = None,
    ) -> dict[str, Any] | None:
        self.last_call = {
            "payload": payload,
            "timeout": timeout,
            "context": context,
            "max_retries": max_retries,
            "temperature_override": temperature_override,
        }
        if self._error is not None:
            raise self._error
        return self._response


@pytest.mark.unit
def test_timeout_error_fails_closed_to_hold(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    log_path = tmp_path / "llm_decisions.jsonl"
    monkeypatch.setenv("LUMINA_LLM_DECISIONS_LOG", str(log_path))
    engine = SimpleNamespace(config=SimpleNamespace(trade_mode="real"))
    inference = _DummyInferenceEngine(error=TimeoutError("simulated timeout"))
    client = LlmClient(inference_engine=inference, engine=engine)

    result = client.complete_trading_json(
        payload={"model": "test-model", "messages": [{"role": "user", "content": "trade"}], "temperature": 0.9},
        context="timeout_case",
        timeout_seconds=20,
    )

    assert result.fallback is True
    assert result.path == "fast_rule"
    assert result.payload_out["signal"] == "HOLD"
    assert result.payload_out["decision_context_id"] == result.decision_context_id
    assert inference.last_call["timeout"] == 2
    assert log_path.exists()
    audit = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert audit["fallback"] is True
    assert audit["path"] == "fast_rule"
    assert audit["decision_context_id"] == result.decision_context_id


@pytest.mark.unit
def test_real_mode_temperature_is_clamped_unless_force_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LUMINA_LLM_DECISIONS_LOG", str(tmp_path / "llm_temp.jsonl"))
    engine = SimpleNamespace(config=SimpleNamespace(trade_mode="real"))
    inference = _DummyInferenceEngine(response={"signal": "HOLD", "confidence": 0.2})
    client = LlmClient(inference_engine=inference, engine=engine)

    client.complete_trading_json(
        payload={"model": "test-model", "messages": [{"role": "user", "content": "trade"}], "temperature": 0.95},
        context="real_clamp",
    )
    assert inference.last_call["temperature_override"] == pytest.approx(0.35, rel=0.0, abs=1e-9)

    monkeypatch.setenv("LUMINA_FORCE_HIGH_TEMP", "1")
    client.complete_trading_json(
        payload={"model": "test-model", "messages": [{"role": "user", "content": "trade"}], "temperature": 0.95},
        context="real_override",
    )
    assert inference.last_call["temperature_override"] == pytest.approx(0.95, rel=0.0, abs=1e-9)


@pytest.mark.unit
def test_audit_trail_contains_required_hashes_and_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "llm_audit.jsonl"
    monkeypatch.setenv("LUMINA_LLM_DECISIONS_LOG", str(log_path))
    engine = SimpleNamespace(config=SimpleNamespace(trade_mode="sim"))
    inference = _DummyInferenceEngine(response={"signal": "BUY", "confidence": 0.81, "reason": "edge"})
    client = LlmClient(inference_engine=inference, engine=engine)

    result = client.complete_trading_json(
        payload={"model": "grok-test", "messages": [{"role": "user", "content": "trade now"}], "temperature": 0.42},
        context="audit_case",
        decision_context_id="ctx-001",
    )

    assert result.fallback is False
    assert result.path == "llm_reasoning"
    lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["decision_context_id"] == "ctx-001"
    assert record["model_version"] == "grok-test"
    assert record["prompt_hash"]
    assert record["response_hash"]
    assert record["latency_ms"] >= 0.0
    assert record["temperature"] == pytest.approx(0.42, rel=0.0, abs=1e-9)
    assert record["fallback"] is False
    assert record["path"] == "llm_reasoning"
