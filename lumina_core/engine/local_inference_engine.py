"""LocalInferenceEngine façade — routing, metrics, Hybrid vLLM lifecycle gates.

Bounded module: ``local_inference_providers`` (_try_vllm / _try_ollama / _try_remote_grok + health).
Public symbols remain importable from this module.
"""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from lumina_core.engine.errors import ErrorSeverity, LuminaError
from lumina_core.runtime_context import RuntimeContext
from lumina_core.xai_client import post_xai_chat  # noqa: F401 — monkeypatch surface
from .local_inference_providers import LocalInferenceProvidersMixin
from .provider_normalization import ProviderNormalizationLayer

_DEFAULT_LOGGER = logging.getLogger("lumina.local_inference")

__all__ = ["LocalInferenceEngine"]


class LocalInferenceEngine(LocalInferenceProvidersMixin):
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
        self._ollama_install_cache_ts: float = 0.0
        self._ollama_install_cache_host: str | None = None
        self._ollama_install_cache_names: list[str] | None = None

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
            self._ollama_install_cache_ts = 0.0
            self._ollama_install_cache_host = None
            self._ollama_install_cache_names = None
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
        self.cost_tracker.setdefault("local_inference_consecutive_failures", 0)

    def _http_timeout_sec(
        self,
        fallback: float,
        *,
        min_timeout_sec: float = 3.0,
        respect_fallback_cap: bool = False,
    ) -> float:
        inf = self.config.get("inference", {})
        if not isinstance(inf, dict):
            return float(fallback)
        raw = inf.get("request_timeout_sec", fallback)
        try:
            t = float(raw)
        except (TypeError, ValueError):
            t = float(fallback)
        if respect_fallback_cap:
            t = min(t, float(fallback))
        bounded_min = max(0.1, float(min_timeout_sec))
        return max(bounded_min, min(180.0, t))

    def _max_consecutive_failures(self) -> int:
        inf = self.config.get("inference", {})
        if not isinstance(inf, dict):
            return 5
        try:
            return max(1, int(inf.get("max_consecutive_failures", 5) or 5))
        except (TypeError, ValueError):
            return 5

    def _bump_inference_failure_streak(self) -> None:
        self._ensure_metric_buckets()
        n = int(self.cost_tracker.get("local_inference_consecutive_failures", 0)) + 1
        self.cost_tracker["local_inference_consecutive_failures"] = n
        if n >= self._max_consecutive_failures():
            self._trip_inference_kill_switch(n)

    def _reset_inference_failure_streak(self) -> None:
        self._ensure_metric_buckets()
        self.cost_tracker["local_inference_consecutive_failures"] = 0

    def _trip_inference_kill_switch(self, streak: int) -> None:
        engine = getattr(self.context, "engine", None)
        app = getattr(engine, "app", None) if engine is not None else None
        if app is not None and hasattr(app, "logger"):
            setattr(app, "FAST_PATH_ONLY", True)
            app.logger.warning(
                "FAST_PATH_ONLY enabled (local_inference kill-switch): consecutive_failures=%s",
                streak,
            )

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

    def apply_adaptive_intelligence(self, status: dict[str, Any] | None) -> None:
        if not isinstance(status, dict):
            return
        provider = str(status.get("recommended_provider", "") or "").strip().lower()
        if provider in {"ollama", "vllm", "grok_remote"}:
            self.backend_override = provider
            self.active_provider = provider
        self.cost_tracker["adaptive_intelligence"] = {
            "tier": str(status.get("tier", "light")),
            "reasoning_mode": str(status.get("reasoning_mode", "fast_path_only")),
            "degraded_state": bool(status.get("degraded_state", False)),
            "status_reason": str(status.get("status_reason", "")),
            "recommended_model": str(status.get("recommended_model", "")),
        }

    def infer(
        self,
        prompt: str | list,
        model_type: str = "reasoning",
        image_base64: Optional[str] = None,
        temperature: float | None = None,
    ) -> Dict:
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
                    runtime_reason = str(
                        self.cost_tracker.get("local_inference_vllm_runtime_reason", "") or "health_down"
                    )
                    raise LuminaError(
                        severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                        code="INFERENCE_VLLM_UNHEALTHY",
                        message=f"vLLM provider unavailable: {runtime_reason}",
                    )
                result = self._infer_via_vllm(messages, model_type, temperature=temperature)
            elif provider == "ollama":
                result = self._infer_via_ollama(messages, model_type, temperature=temperature)
            elif provider == "grok_remote":
                result = self._infer_via_remote_grok(messages, temperature=temperature)
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
            self._reset_inference_failure_streak()
            return parsed
        except Exception as exc:
            latency_ms = round((time.time() - start) * 1000.0, 2)
            self._record_metrics(provider, latency_ms, success=False, estimated_cost=0.0)
            self._bump_inference_failure_streak()
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
        temperature_override: float | None = None,
    ) -> dict[str, Any] | None:
        del context, max_retries

        messages = payload.get("messages")
        if not isinstance(messages, list):
            return None

        model_name = str(payload.get("model", "")).lower()
        model_type = "vision" if "vision" in model_name or "-vl" in model_name else "reasoning"
        wall_timeout = self._http_timeout_sec(
            float(timeout),
            min_timeout_sec=0.1,
            respect_fallback_cap=True,
        )
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(self.infer, messages, model_type, None, temperature_override)
                result = fut.result(timeout=wall_timeout)
        except FuturesTimeoutError:
            self._bump_inference_failure_streak()
            self.logger.warning("INFERENCE_JSON_TIMEOUT,timeout_sec=%s", wall_timeout)
            return None
        return result if isinstance(result, dict) else None

    def start_vllm_server(self, *args: Any, **kwargs: Any) -> bool:
        """Health-check an external vLLM host (does not spawn a local process)."""
        del args, kwargs
        from lumina_core.hybrid_quarantine import (
            VLLM_LIFECYCLE,
            log_quarantine,
            manage_vllm_lifecycle,
        )

        strict = manage_vllm_lifecycle()
        log_quarantine(VLLM_LIFECYCLE, strict=strict, detail="start_vllm_server")
        ok = self._is_vllm_healthy(force=True)
        host = str(self.config.get("vllm", {}).get("host", "http://localhost:8000")).rstrip("/")
        reason = str(self.cost_tracker.get("local_inference_vllm_runtime_reason", ""))
        self.logger.info(f"start_vllm_server health_check={ok} host={host}")
        if reason:
            self.logger.warning(f"VLLM_RUNTIME_UNAVAILABLE,{reason}")
        if strict and not ok:
            self.logger.error("vllm.manage_lifecycle=true but external vLLM host is unhealthy")
            return False
        return ok

    def stop_vllm_server(self) -> None:
        """No-op: external vLLM lifecycle is expected (not managed in-process)."""
        from lumina_core.hybrid_quarantine import VLLM_LIFECYCLE, log_quarantine, manage_vllm_lifecycle

        log_quarantine(VLLM_LIFECYCLE, strict=manage_vllm_lifecycle(), detail="stop_vllm_server noop")
        self.logger.info("stop_vllm_server noop - external vLLM lifecycle expected")
