from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from lumina_core.state.state_manager import safe_append_jsonl

LLMCallPath = Literal["fast_rule", "llm_reasoning"]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _is_truthy(raw: str | None) -> bool:
    if raw is None:
        return False
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _default_llm_decision_log_path() -> Path:
    env_override = os.getenv("LUMINA_LLM_DECISIONS_LOG")
    if env_override:
        return Path(env_override)
    logs_dir = os.getenv("LUMINA_LOGS_DIR")
    if logs_dir:
        return Path(logs_dir) / "llm_decisions.jsonl"
    return Path("logs/llm_decisions.jsonl")


def _effective_trade_mode(engine: Any) -> str:
    env_mode = str(os.getenv("LUMINA_MODE", "")).strip().lower()
    if env_mode:
        return env_mode
    cfg = getattr(engine, "config", None)
    return str(getattr(cfg, "trade_mode", "paper") or "paper").strip().lower()


def resolve_effective_temperature(
    *,
    requested_temperature: float,
    is_real_mode: bool,
    real_mode_temperature: float = 0.35,
) -> float:
    if not is_real_mode or _is_truthy(os.getenv("LUMINA_FORCE_HIGH_TEMP")):
        return float(requested_temperature)
    bounded_real = max(0.30, min(0.40, float(real_mode_temperature)))
    return min(float(requested_temperature), bounded_real)


@dataclass(slots=True)
class LLMCallResult:
    payload_out: dict[str, Any]
    fallback: bool
    latency_ms: float
    model_version: str
    prompt_hash: str
    response_hash: str
    temperature: float
    provider: str
    decision_context_id: str
    path: LLMCallPath
    error: str | None = None


class LlmClient:
    def __init__(self, *, inference_engine: Any, engine: Any):
        self.inference_engine = inference_engine
        self.engine = engine
        self.log_path = _default_llm_decision_log_path()

    def _inference_config(self) -> dict[str, Any]:
        cfg = getattr(self.inference_engine, "config", {})
        return cfg.get("inference", {}) if isinstance(cfg, dict) else {}

    def _max_latency_ms(self) -> int:
        inf_cfg = self._inference_config()
        raw = inf_cfg.get("llm_max_latency_ms", 8000)
        try:
            return max(100, int(raw))
        except (TypeError, ValueError):
            return 8000

    def _effective_timeout_seconds(self, timeout_seconds: int) -> int:
        budget_ms = self._max_latency_ms()
        requested_ms = max(1000, int(float(timeout_seconds) * 1000))
        effective_ms = min(budget_ms, requested_ms)
        return max(1, int((effective_ms + 999) // 1000))

    @staticmethod
    def _fallback_payload(reason: str, *, decision_context_id: str) -> dict[str, Any]:
        return {
            "signal": "HOLD",
            "confidence": 0.0,
            "reason": reason,
            "decision_context_id": decision_context_id,
        }

    def _append_decision_log(self, entry: dict[str, Any]) -> None:
        safe_append_jsonl(self.log_path, entry, hash_chain=False)

    def complete_trading_json(
        self,
        *,
        payload: dict[str, Any],
        timeout_seconds: int = 20,
        context: str = "xai_json",
        max_retries: int = 1,
        decision_context_id: str | None = None,
        forced_path: LLMCallPath | None = None,
        fallback_reason: str = "llm_unavailable_fail_closed",
    ) -> LLMCallResult:
        inf_cfg = self._inference_config()
        model_version = str(payload.get("model", "unknown-model"))
        requested_temperature = float(payload.get("temperature", inf_cfg.get("temperature", 0.1)))
        real_mode_temperature = float(inf_cfg.get("llm_real_temperature", 0.35))
        mode = _effective_trade_mode(self.engine)
        effective_temperature = resolve_effective_temperature(
            requested_temperature=requested_temperature,
            is_real_mode=mode == "real",
            real_mode_temperature=real_mode_temperature,
        )
        provider = str(getattr(self.inference_engine, "active_provider", "unknown-provider"))
        prompt_hash = _sha256(payload.get("messages", payload))
        call_id = decision_context_id or f"{context}:{uuid.uuid4().hex}"
        started = time.perf_counter()

        path: LLMCallPath = "llm_reasoning" if forced_path is None else forced_path
        fallback = False
        error_text: str | None = None
        response_payload: dict[str, Any]

        if path == "fast_rule":
            fallback = True
            response_payload = self._fallback_payload(fallback_reason, decision_context_id=call_id)
        else:
            try:
                call_timeout = self._effective_timeout_seconds(timeout_seconds)
                try:
                    result = self.inference_engine.infer_json(
                        payload,
                        timeout=call_timeout,
                        context=context,
                        max_retries=max_retries,
                        temperature_override=effective_temperature,
                    )
                except TypeError:
                    # Backward compatibility for tests/adapters that still expose the old signature.
                    result = self.inference_engine.infer_json(
                        payload,
                        timeout=call_timeout,
                        context=context,
                        max_retries=max_retries,
                    )
                if isinstance(result, dict):
                    response_payload = result
                else:
                    fallback = True
                    path = "fast_rule"
                    response_payload = self._fallback_payload(fallback_reason, decision_context_id=call_id)
            except Exception as exc:  # fail-closed by design
                fallback = True
                path = "fast_rule"
                error_text = f"{type(exc).__name__}: {exc}"
                response_payload = self._fallback_payload(fallback_reason, decision_context_id=call_id)

        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
        response_hash = _sha256(response_payload)
        timestamp = datetime.now(timezone.utc).isoformat()
        self._append_decision_log(
            {
                "timestamp": timestamp,
                "decision_context_id": call_id,
                "context": context,
                "path": path,
                "fallback": fallback,
                "provider": provider,
                "model_version": model_version,
                "prompt_hash": prompt_hash,
                "response_hash": response_hash,
                "latency_ms": elapsed_ms,
                "temperature": round(effective_temperature, 4),
                "max_latency_ms": self._max_latency_ms(),
                "error": error_text,
            }
        )
        return LLMCallResult(
            payload_out=response_payload,
            fallback=fallback,
            latency_ms=elapsed_ms,
            model_version=model_version,
            prompt_hash=prompt_hash,
            response_hash=response_hash,
            temperature=effective_temperature,
            provider=provider,
            decision_context_id=call_id,
            path=path,
            error=error_text,
        )
