from __future__ import annotations

import importlib.util
import json
import logging
import platform
import time
from pathlib import Path
from typing import Any, Dict, Optional

import ollama
import requests

from lumina_core.engine.errors import ErrorSeverity, LuminaError
from lumina_core.runtime_context import RuntimeContext
from lumina_core.xai_client import post_xai_chat
from .provider_normalization import ProviderNormalizationLayer

_DEFAULT_LOGGER = logging.getLogger("lumina.local_inference")


class LocalInferenceEngine:
    """Drop-in + geoptimaliseerde inference engine met Grok-Trader-1B support."""

    def __init__(self, context: RuntimeContext | Any = None, engine: Any = None):
        if context is None and engine is not None:
            context = engine
        if context is None:
            raise ValueError("LocalInferenceEngine requires a RuntimeContext or engine")

        self.context = context
        self.config_path = Path("config.yaml")
        self.config_mtime = 0.0
        self.config = self._load_config()
        self.logger = getattr(context, "logger", _DEFAULT_LOGGER)
        self.profile = self.config["hardware_profile"]
        self.backend_override: str | None = None
        self.active_provider = str(self.config.get("inference", {}).get("primary_provider", "ollama"))
        self.session = requests.Session()
        self.normalization_layer = ProviderNormalizationLayer()

        tracker = getattr(context, "COST_TRACKER", None)
        if tracker is None:
            tracker = getattr(context, "cost_tracker", None)
        if not isinstance(tracker, dict):
            tracker = {}
            setattr(context, "cost_tracker", tracker)
        self.cost_tracker = tracker
        self._ensure_metric_buckets()

    def _load_config(self) -> Dict:
        from lumina_core.config_loader import ConfigLoader  # noqa: PLC0415

        ConfigLoader.invalidate()
        self.config_mtime = self.config_path.stat().st_mtime if self.config_path.exists() else 0.0
        return dict(ConfigLoader.get())

    def _reload_config_if_needed(self) -> None:
        try:
            current_mtime = self.config_path.stat().st_mtime
        except FileNotFoundError:
            return
        if current_mtime > self.config_mtime:
            self.config = self._load_config()
            if self.backend_override is None:
                self.active_provider = str(self.config.get("inference", {}).get("primary_provider", "ollama"))

    def _ensure_metric_buckets(self) -> None:
        self.cost_tracker.setdefault("local_inference_requests", 0)
        self.cost_tracker.setdefault("local_inference_latency_ms_total", 0.0)
        self.cost_tracker.setdefault("local_inference_last_provider", "")
        self.cost_tracker.setdefault("local_inference_last_latency_ms", 0.0)
        self.cost_tracker.setdefault("local_inference_failures", 0)
        self.cost_tracker.setdefault("local_inference_cost_today", 0.0)
        self.cost_tracker.setdefault("local_inference_provider_stats", {})
        self.cost_tracker.setdefault("local_inference_warning", "")
        self.cost_tracker.setdefault("local_inference_vllm_runtime_reason", "")

    def _resolve_regime_label(self) -> str:
        snapshot = getattr(self.context, "current_regime_snapshot", None)
        if isinstance(snapshot, dict):
            label = snapshot.get("label")
            if label:
                return str(label).strip().upper()

        engine = getattr(self.context, "engine", None)
        if engine is not None:
            engine_snapshot = getattr(engine, "current_regime_snapshot", None)
            if isinstance(engine_snapshot, dict):
                label = engine_snapshot.get("label")
                if label:
                    return str(label).strip().upper()

        current = getattr(self.context, "CURRENT_REGIME", None)
        if current:
            return str(current).strip().upper()
        return "NEUTRAL"

    def _resolve_calibration_factor(self, provider: str) -> float:
        inference_cfg = self.config.get("inference", {})
        if not isinstance(inference_cfg, dict):
            return 1.0

        base = 1.0
        global_cfg = inference_cfg.get("provider_calibration", {})
        if isinstance(global_cfg, dict):
            base = float(global_cfg.get(provider, 1.0) or 1.0)

        regime_label = self._resolve_regime_label()
        by_regime = inference_cfg.get("provider_calibration_by_regime", {})
        if not isinstance(by_regime, dict):
            return max(0.1, base)

        if provider in by_regime and isinstance(by_regime.get(provider), dict):
            provider_cfg = by_regime.get(provider, {})
            regime_factor = float(provider_cfg.get(regime_label, provider_cfg.get("DEFAULT", 1.0)) or 1.0)
            return max(0.1, base * regime_factor)

        if regime_label in by_regime and isinstance(by_regime.get(regime_label), dict):
            regime_cfg = by_regime.get(regime_label, {})
            regime_factor = float(regime_cfg.get(provider, regime_cfg.get("DEFAULT", 1.0)) or 1.0)
            return max(0.1, base * regime_factor)

        return max(0.1, base)

    def _record_metrics(self, provider: str, latency_ms: float, success: bool, estimated_cost: float = 0.0) -> None:
        self._ensure_metric_buckets()
        self.cost_tracker["local_inference_requests"] = int(self.cost_tracker.get("local_inference_requests", 0)) + 1
        self.cost_tracker["local_inference_latency_ms_total"] = float(
            self.cost_tracker.get("local_inference_latency_ms_total", 0.0)
        ) + float(latency_ms)
        self.cost_tracker["local_inference_last_provider"] = provider
        self.cost_tracker["local_inference_last_latency_ms"] = float(latency_ms)
        self.cost_tracker["local_inference_cost_today"] = float(
            self.cost_tracker.get("local_inference_cost_today", 0.0)
        ) + float(estimated_cost)

        if not success:
            self.cost_tracker["local_inference_failures"] = (
                int(self.cost_tracker.get("local_inference_failures", 0)) + 1
            )

        provider_stats = self.cost_tracker.setdefault("local_inference_provider_stats", {})
        stats = provider_stats.setdefault(
            provider,
            {"requests": 0, "successes": 0, "failures": 0, "latency_ms_total": 0.0, "cost": 0.0},
        )
        stats["requests"] = int(stats.get("requests", 0)) + 1
        stats["latency_ms_total"] = float(stats.get("latency_ms_total", 0.0)) + float(latency_ms)
        stats["cost"] = float(stats.get("cost", 0.0)) + float(estimated_cost)
        if success:
            stats["successes"] = int(stats.get("successes", 0)) + 1
        else:
            stats["failures"] = int(stats.get("failures", 0)) + 1

    def get_metrics_summary(self) -> Dict[str, Any]:
        self._ensure_metric_buckets()
        requests_count = int(self.cost_tracker.get("local_inference_requests", 0))
        total_latency = float(self.cost_tracker.get("local_inference_latency_ms_total", 0.0))
        avg_latency = total_latency / requests_count if requests_count > 0 else 0.0
        return {
            "active_provider": str(self.active_provider or self.get_backend()),
            "last_provider": str(self.cost_tracker.get("local_inference_last_provider", "")),
            "last_latency_ms": float(self.cost_tracker.get("local_inference_last_latency_ms", 0.0)),
            "avg_latency_ms": float(avg_latency),
            "requests": requests_count,
            "failures": int(self.cost_tracker.get("local_inference_failures", 0)),
            "local_cost_today": float(self.cost_tracker.get("local_inference_cost_today", 0.0)),
            "vllm_runtime_reason": str(self.cost_tracker.get("local_inference_vllm_runtime_reason", "")),
        }

    def _get_vllm_runtime_reason(self) -> str:
        if importlib.util.find_spec("vllm._C") is None:
            if platform.system() == "Windows":
                return "vLLM native extension vllm._C is unavailable on this Windows runtime; use WSL2 or Docker Linux for real vLLM serving"
            return "vLLM native extension vllm._C is missing in the active Python environment"
        return ""

    def _is_vllm_healthy(self, force: bool = False) -> bool:
        del force
        runtime_reason = self._get_vllm_runtime_reason()
        self.cost_tracker["local_inference_vllm_runtime_reason"] = runtime_reason
        if runtime_reason:
            self.cost_tracker["local_inference_warning"] = runtime_reason
            return False
        try:
            host = str(self.config.get("vllm", {}).get("host", "http://localhost:8000")).rstrip("/")
            resp = self.session.get(f"{host}/health", timeout=1.2)
            return resp.status_code < 400
        except requests.RequestException:
            return False

    def _try_vllm(self, messages: list, model: str) -> Optional[Dict]:
        """Run vLLM provider call without silent fallback behavior."""
        del model
        host = str(self.config["vllm"]["host"])
        try:
            resp = requests.post(
                f"{host}/v1/chat/completions",
                json={
                    "model": self.config["vllm"]["model_name"],
                    "messages": messages,
                    "temperature": self.config["inference"]["temperature"],
                    "max_tokens": self.config["inference"]["max_tokens"],
                },
                timeout=15,
            )
        except requests.RequestException as exc:
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="INFERENCE_VLLM_REQUEST_FAILED",
                message="vLLM request failed.",
            ) from exc
        if resp.status_code != 200:
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="INFERENCE_VLLM_HTTP_ERROR",
                message=f"vLLM returned non-200 status: {resp.status_code}",
            )
        return resp.json()["choices"][0]["message"]["content"]

    def _try_ollama(self, messages: list, model: str) -> Optional[Dict]:
        try:
            resp = ollama.chat(
                model=model,
                messages=messages,
                options={
                    "temperature": self.config["inference"]["temperature"],
                    "num_ctx": 16384,
                    "num_gpu": -1,
                },
            )
        except Exception as exc:
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="INFERENCE_OLLAMA_REQUEST_FAILED",
                message="Ollama inference call failed.",
            ) from exc
        return resp["message"]["content"]

    def _try_remote_grok(self, messages: list) -> Optional[Dict]:
        """Run direct xAI inference provider call."""
        xai_key = (
            getattr(self.context, "XAI_KEY", None)
            or getattr(self.context, "xai_key", None)
            or getattr(getattr(self.context, "config", None), "xai_key", None)
        )
        if not xai_key:
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="XAI_KEY_MISSING",
                message="xAI key is required for grok_remote provider.",
            )

        inference_cfg = self.config.get("inference", {})
        xai_cfg = self.config.get("xai", {})
        payload = {
            "model": str(xai_cfg.get("model", "grok-4.1-fast") or "grok-4.1-fast"),
            "messages": messages,
            "temperature": float(inference_cfg.get("temperature", 0.1) or 0.1),
            "max_tokens": int(inference_cfg.get("max_tokens", 1200) or 1200),
            "response_format": {"type": "json_object"},
        }

        response = post_xai_chat(
            payload=payload,
            xai_key=str(xai_key),
            logger=self.logger,
            timeout=int(xai_cfg.get("timeout", 20) or 20),
            context="local_inference.grok_remote",
            max_retries=int(xai_cfg.get("max_retries", 1) or 1),
        )
        if response is None:
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="XAI_CALL_FAILED",
                message="xAI chat call returned no response.",
            )

        if response.status_code >= 400:
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code=f"XAI_HTTP_{response.status_code}",
                message=f"xAI returned HTTP {response.status_code}.",
            )

        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            return content if isinstance(content, str) else json.dumps(content)
        except Exception as exc:
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="XAI_RESPONSE_SCHEMA_INVALID",
                message="xAI response schema invalid for chat completion payload.",
            ) from exc

    # Compat met bestaande tests/callers
    def _infer_via_vllm(self, messages: list, model_type: str, **_kwargs: Any) -> Optional[Dict]:
        model = self.config["models"].get(model_type, "qwen2.5:7b")
        return self._try_vllm(messages, model)

    def _infer_via_ollama(self, messages: list, model_type: str, **_kwargs: Any) -> Optional[Dict]:
        model = self.config["models"].get(model_type, "qwen2.5:7b")
        return self._try_ollama(messages, model)

    def _infer_via_remote_grok(self, messages: list, **_kwargs: Any) -> Optional[Dict]:
        return self._try_remote_grok(messages)

    def set_backend(self, backend: str) -> str:
        normalized = str(backend).strip().lower()
        if normalized not in {"ollama", "vllm", "grok_remote"}:
            raise ValueError(f"Unsupported backend: {backend}")
        self.backend_override = normalized
        self.active_provider = normalized
        return normalized

    def get_backend(self) -> str:
        if self.backend_override:
            return self.backend_override
        return str(self.config.get("inference", {}).get("primary_provider", "ollama")).strip().lower()

    def infer(self, prompt: str | list, model_type: str = "reasoning", image_base64: Optional[str] = None) -> Dict:
        del image_base64
        self._reload_config_if_needed()

        start = time.time()
        model = self.config["models"].get(model_type, "qwen2.5:7b")
        messages = (
            prompt
            if isinstance(prompt, list)
            else [
                {"role": "system", "content": "Je bent LUMINA Grok-Trader-1B. Geef ALLEEN strikte JSON."},
                {"role": "user", "content": prompt},
            ]
        )

        provider = self.get_backend()
        provider_chain = [provider]
        try:
            if provider == "vllm":
                if not self._is_vllm_healthy():
                    runtime_reason = str(self.cost_tracker.get("local_inference_vllm_runtime_reason", "") or "health_down")
                    raise LuminaError(
                        severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                        code="INFERENCE_VLLM_UNHEALTHY",
                        message=f"vLLM provider unavailable: {runtime_reason}",
                    )
                result = self._infer_via_vllm(messages, model_type)
            elif provider == "ollama":
                result = self._infer_via_ollama(messages, model_type)
            elif provider == "grok_remote":
                result = self._infer_via_remote_grok(messages)
            else:
                raise LuminaError(
                    severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                    code="INFERENCE_PROVIDER_UNSUPPORTED",
                    message=f"Unsupported inference provider: {provider}",
                )

            if not result:
                raise LuminaError(
                    severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                    code="INFERENCE_EMPTY_RESPONSE",
                    message=f"Inference provider returned empty response: {provider}",
                )

            parsed = json.loads(result) if isinstance(result, str) else result
            if not isinstance(parsed, dict):
                raise LuminaError(
                    severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                    code="INFERENCE_RESPONSE_NOT_OBJECT",
                    message="Inference provider returned non-object payload.",
                )

            latency_ms = round((time.time() - start) * 1000.0, 2)
            previous_provider = str(self.active_provider or "")
            self.active_provider = provider
            calibration_factor = self._resolve_calibration_factor(provider)
            parsed = self.normalization_layer.normalize(
                provider=provider,
                payload=parsed,
                provider_chain=provider_chain,
                calibration_factor=calibration_factor,
            )
            self._record_metrics(provider, latency_ms, success=True, estimated_cost=0.0)
            if previous_provider and previous_provider != provider:
                self.logger.info(
                    f"LOCAL_INFERENCE_PROVIDER_SWITCH,from={previous_provider},to={provider},model_type={model_type}"
                )
            self.logger.info(
                f"INFERENCE,{provider},{model_type}={model},latency={round(latency_ms / 1000.0, 3)}s,profile={self.profile}"
            )
            return parsed
        except Exception as exc:
            latency_ms = round((time.time() - start) * 1000.0, 2)
            self._record_metrics(provider, latency_ms, success=False, estimated_cost=0.0)
            self.logger.warning(f"INFERENCE_PROVIDER_FAILED,{provider},{exc}")
            if isinstance(exc, LuminaError):
                raise
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="INFERENCE_PROVIDER_EXECUTION_FAILED",
                message=f"Inference provider execution failed: {provider}",
            ) from exc

    # Convenience wrappers (blijven hetzelfde)
    def vision_infer(self, chart_base64: str, text_prompt: str) -> Dict:
        messages = [
            {"role": "system", "content": "Chart-analist. Geef JSON: summary, ai_fibs, signal, confidence."},
            {"role": "user", "content": text_prompt},
        ]
        return self.infer(messages, "vision", chart_base64)

    def multi_agent_infer(self, full_context: list) -> Dict:
        return self.infer(full_context, "reasoning")

    # Compat met bestaande ReasoningService
    def infer_json(
        self,
        payload: dict[str, Any],
        timeout: int = 20,
        context: str = "xai_json",
        max_retries: int = 1,
    ) -> dict[str, Any] | None:
        del timeout, context, max_retries

        messages = payload.get("messages")
        if not isinstance(messages, list):
            return None

        model_name = str(payload.get("model", "")).lower()
        model_type = "vision" if "vision" in model_name or "-vl" in model_name else "reasoning"
        result = self.infer(messages, model_type=model_type)
        return result if isinstance(result, dict) else None

    def start_vllm_server(self, *args: Any, **kwargs: Any) -> bool:
        del args, kwargs
        ok = self._is_vllm_healthy(force=True)
        host = str(self.config.get("vllm", {}).get("host", "http://localhost:8000")).rstrip("/")
        reason = str(self.cost_tracker.get("local_inference_vllm_runtime_reason", ""))
        self.logger.info(f"start_vllm_server health_check={ok} host={host}")
        if reason:
            self.logger.warning(f"VLLM_RUNTIME_UNAVAILABLE,{reason}")
        return ok

    def stop_vllm_server(self) -> None:
        self.logger.info("stop_vllm_server noop - external vLLM lifecycle expected")

    # Model request template voor xAI (kopieer dit en stuur naar xAI)
    def generate_grok_trader_request(self) -> str:
        return """
Subject: Request for Grok-Trader-1B Fine-Tune (1B parameters)

We request a distilled Grok-Trader-1B model based on the following dataset:
- All lumina_thought_log.jsonl
- trade_reflection_history + user_feedback
- 1.000.000+ trades from Infinite Simulator
- Full Bible + evolvable_layer + HUMAN PLAYBOOK

Requirements:
- Output: always strict JSON (signal, confidence, stop, target, reason, fib_levels, chosen_strategy)
- Vision + text in single forward pass
- Context: 32k
- Temperature: 0.1 (trading)
- Optimized for vLLM / Ollama deployment
- Quantized versions (Q4, Q5, Q8)

We will provide the full training dataset via secure upload.
"""
