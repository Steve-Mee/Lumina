"""Provider call + health helpers mixed into LocalInferenceEngine."""

from __future__ import annotations

import importlib.util
import json
import logging
import platform
import time
from typing import Any, Dict

import ollama
import requests

from lumina_core.engine.errors import ErrorSeverity, LuminaError
from lumina_core.engine.ollama_model_resolve import list_installed_ollama_models, resolve_ollama_model_tag


def _lie():
    """Late-bind façade module so monkeypatches on local_inference_engine still apply."""
    from lumina_core.engine import local_inference_engine as lie

    return lie


class LocalInferenceProvidersMixin:
    """vLLM / Ollama / remote Grok provider calls and vLLM health checks."""

    __slots__ = ()
    _ollama_install_cache_names: list[str] | None
    _ollama_install_cache_host: str | None
    _ollama_install_cache_ts: float

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

    def _ollama_base_url(self) -> str | None:
        oc = self.config.get("ollama")
        if not isinstance(oc, dict):
            return None
        u = str(oc.get("base_url") or "").strip()
        return u or None

    def _cached_installed_ollama_models(self) -> list[str]:
        """Short TTL cache so hot inference paths do not call ollama.list every request."""
        host = self._ollama_base_url()
        now = time.monotonic()
        if (
            self._ollama_install_cache_names is not None
            and self._ollama_install_cache_host == host
            and now - self._ollama_install_cache_ts < 45.0
        ):
            return self._ollama_install_cache_names
        names = list_installed_ollama_models(host=host)
        self._ollama_install_cache_ts = now
        self._ollama_install_cache_host = host
        self._ollama_install_cache_names = names
        return names

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

    def _try_vllm(self, messages: list, model: str, temperature: float | None = None) -> str | Dict | None:
        """Run vLLM provider call without silent fallback behavior."""
        del model
        host = str(self.config["vllm"]["host"])
        effective_temperature = (
            float(self.config["inference"]["temperature"]) if temperature is None else float(temperature)
        )
        try:
            resp = requests.post(
                f"{host}/v1/chat/completions",
                json={
                    "model": self.config["vllm"]["model_name"],
                    "messages": messages,
                    "temperature": effective_temperature,
                    "max_tokens": self.config["inference"]["max_tokens"],
                },
                timeout=self._http_timeout_sec(15.0),
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

    def _try_ollama(self, messages: list, model: str, temperature: float | None = None) -> str | Dict | None:
        effective_temperature = (
            float(self.config["inference"]["temperature"]) if temperature is None else float(temperature)
        )
        oc = self.config.get("ollama") if isinstance(self.config.get("ollama"), dict) else {}
        num_ctx = int(oc.get("num_ctx", 16384) or 16384)
        installed = self._cached_installed_ollama_models()
        resolved_model = resolve_ollama_model_tag(model, installed)
        host = self._ollama_base_url()
        client = ollama.Client(host=host) if host else ollama.Client()
        try:
            resp = client.chat(
                model=resolved_model,
                messages=messages,
                options={
                    "temperature": effective_temperature,
                    "num_ctx": num_ctx,
                    "num_gpu": -1,
                },
            )
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            detail = str(exc).lower()
            if status == 404 or ("not found" in detail and "model" in detail):
                logging.warning(
                    "Ollama model unavailable for chat (configured=%s resolved=%s status=%s): %s",
                    model,
                    resolved_model,
                    status,
                    exc,
                )
                raise LuminaError(
                    severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                    code="INFERENCE_OLLAMA_MODEL_NOT_FOUND",
                    message=(
                        f"Ollama model not usable (configured '{model}', attempted '{resolved_model}'). "
                        "Run `ollama list` / `ollama pull <tag>` or point config `ollama.base_url` at your daemon; "
                        "optional: set models.* to a tag you have, or `LUMINA_OLLAMA_STRICT_MODEL=1` to disable "
                        "automatic substitution from installed models."
                    ),
                ) from exc
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/local_inference_providers.py")
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="INFERENCE_OLLAMA_REQUEST_FAILED",
                message="Ollama inference call failed.",
            ) from exc
        return resp["message"]["content"]

    def _try_remote_grok(self, messages: list, temperature: float | None = None) -> str | Dict | None:
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
            "temperature": (
                float(inference_cfg.get("temperature", 0.1) or 0.1) if temperature is None else float(temperature)
            ),
            "max_tokens": int(inference_cfg.get("max_tokens", 1200) or 1200),
            "response_format": {"type": "json_object"},
        }

        response = _lie().post_xai_chat(
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
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/local_inference_providers.py")
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="XAI_RESPONSE_SCHEMA_INVALID",
                message="xAI response schema invalid for chat completion payload.",
            ) from exc

    # Compat met bestaande tests/callers
    def _infer_via_vllm(self, messages: list, model_type: str, **kwargs: Any) -> str | Dict | None:
        model = self.config["models"].get(model_type, "qwen2.5:7b")
        temperature = kwargs.get("temperature")
        return self._try_vllm(messages, model, temperature=temperature)

    def _infer_via_ollama(self, messages: list, model_type: str, **kwargs: Any) -> str | Dict | None:
        model = self.config["models"].get(model_type, "qwen2.5:7b")
        temperature = kwargs.get("temperature")
        return self._try_ollama(messages, model, temperature=temperature)

    def _infer_via_remote_grok(self, messages: list, **kwargs: Any) -> str | Dict | None:
        temperature = kwargs.get("temperature")
        return self._try_remote_grok(messages, temperature=temperature)


__all__ = ["LocalInferenceProvidersMixin"]
