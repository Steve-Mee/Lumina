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
import yaml

from lumina_core.runtime_context import RuntimeContext

_FALLBACK_LOGGER = logging.getLogger("lumina.local_inference")


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
        self.logger = getattr(context, "logger", _FALLBACK_LOGGER)
        self.profile = self.config["hardware_profile"]
        self.backend_override: str | None = None
        self.active_provider = str(self.config.get("inference", {}).get("primary_provider", "ollama"))
        self.session = requests.Session()

        tracker = getattr(context, "COST_TRACKER", None)
        if tracker is None:
            tracker = getattr(context, "cost_tracker", None)
        if not isinstance(tracker, dict):
            tracker = {}
            setattr(context, "cost_tracker", tracker)
        self.cost_tracker = tracker
        self._ensure_metric_buckets()

    def _load_config(self) -> Dict:
        with self.config_path.open(encoding="utf-8") as f:
            config = yaml.safe_load(f)
        self.config_mtime = self.config_path.stat().st_mtime
        return config

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
            self.cost_tracker["local_inference_failures"] = int(
                self.cost_tracker.get("local_inference_failures", 0)
            ) + 1

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
        if importlib.util.find_spec("vllm") is None:
            return "vLLM package not installed in the active Python environment"
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
        """Probeer vLLM (snelste voor Grok-Trader-1B)"""
        try:
            resp = requests.post(
                f"{self.config['vllm']['host']}/v1/chat/completions",
                json={
                    "model": self.config["vllm"]["model_name"],
                    "messages": messages,
                    "temperature": self.config["inference"]["temperature"],
                    "max_tokens": self.config["inference"]["max_tokens"],
                },
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
        except Exception:
            pass
        return None

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
            return resp["message"]["content"]
        except Exception:
            return None

    def _try_remote_grok(self, messages: list) -> Optional[Dict]:
        """Fallback naar echte Grok-4 als alles faalt"""
        if not getattr(self.context, "XAI_KEY", None):
            return None
        # Je bestaande post_xai_chat logic hier (indien gewenst)
        return None

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

        chain = [self.get_backend(), *self.config.get("inference", {}).get("fallback_order", [])]
        provider_chain: list[str] = []
        for provider in chain:
            normalized = str(provider).strip().lower()
            if normalized and normalized not in provider_chain:
                provider_chain.append(normalized)

        # Probeer providers in volgorde
        for provider in provider_chain:
            try:
                if provider == "vllm":
                    if not self._is_vllm_healthy():
                        if not self.cost_tracker.get("local_inference_warning"):
                            self.cost_tracker["local_inference_warning"] = "vLLM unavailable - auto-routed to fallback providers"
                        self.logger.warning("LOCAL_INFERENCE_GATE,provider=vllm,action=skip,reason=health_down")
                        continue
                    result = self._infer_via_vllm(messages, model_type)
                elif provider == "ollama":
                    result = self._infer_via_ollama(messages, model_type)
                elif provider == "grok_remote":
                    result = self._infer_via_remote_grok(messages)
                else:
                    result = None
            except Exception as exc:
                latency_ms = round((time.time() - start) * 1000.0, 2)
                self._record_metrics(provider, latency_ms, success=False, estimated_cost=0.0)
                self.logger.warning(f"INFERENCE_PROVIDER_FAILED,{provider},{exc}")
                continue

            if result:
                try:
                    parsed = json.loads(result) if isinstance(result, str) else result
                except Exception:
                    parsed = {"signal": "HOLD", "reason": "Parse error", "confidence": 0.5}

                latency_ms = round((time.time() - start) * 1000.0, 2)
                previous_provider = str(self.active_provider or "")
                self.active_provider = provider
                self._record_metrics(provider, latency_ms, success=True, estimated_cost=0.0)
                if previous_provider and previous_provider != provider:
                    self.logger.info(
                        f"LOCAL_INFERENCE_PROVIDER_SWITCH,from={previous_provider},to={provider},model_type={model_type}"
                    )
                self.logger.info(
                    f"INFERENCE,{provider},{model_type}={model},latency={round(latency_ms / 1000.0, 3)}s,profile={self.profile}"
                )
                return parsed

            latency_ms = round((time.time() - start) * 1000.0, 2)
            self._record_metrics(provider, latency_ms, success=False, estimated_cost=0.0)

        # Ultimate fallback
        return {"signal": "HOLD", "reason": "All inference providers failed", "confidence": 0.3}

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
