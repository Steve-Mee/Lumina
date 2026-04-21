from __future__ import annotations

import ast
import concurrent.futures
import hashlib
import json
import os
import textwrap
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


def _stable_seed(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:8], 16)


@dataclass(slots=True)
class StrategySandboxResult:
    code: str
    function_name: str
    metadata: dict[str, Any]


class _SafetyVisitor(ast.NodeVisitor):
    _blocked_nodes = (
        ast.Import,
        ast.ImportFrom,
        ast.With,
        ast.AsyncWith,
        ast.Try,
        ast.Raise,
        ast.Global,
        ast.Nonlocal,
        ast.Lambda,
        ast.ClassDef,
        ast.Delete,
        ast.While,
    )

    _allowed_call_names = {
        "abs",
        "all",
        "any",
        "float",
        "int",
        "list",
        "len",
        "max",
        "min",
        "round",
        "sum",
        "sorted",
        "range",
    }

    def __init__(self) -> None:
        self.violations: list[str] = []

    def visit(self, node: ast.AST) -> Any:
        if isinstance(node, self._blocked_nodes):
            self.violations.append(f"blocked_node:{type(node).__name__}")
            return None
        return super().visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        if str(node.attr).startswith("_"):
            self.violations.append("blocked_private_attribute")
            return None
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> Any:
        lowered = str(node.id).strip().lower()
        if lowered in {"__import__", "open", "exec", "eval", "compile", "globals", "locals", "vars"}:
            self.violations.append(f"blocked_name:{node.id}")
            return None
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        if isinstance(node.func, ast.Name):
            func_name = str(node.func.id)
            if func_name not in self._allowed_call_names:
                self.violations.append(f"blocked_call:{func_name}")
                return None
        elif isinstance(node.func, ast.Attribute):
            attr_name = str(node.func.attr)
            base = node.func.value
            is_context_get = isinstance(base, ast.Name) and str(base.id) == "context" and attr_name == "get"
            if not is_context_get:
                self.violations.append("blocked_method_call")
                return None
        self.generic_visit(node)


class StrategyGenerator:
    """Generates sandbox-safe strategy snippets via vLLM/Ollama."""

    def __init__(self) -> None:
        self._vllm_endpoint = str(
            os.getenv("LUMINA_VLLM_STRATEGY_URL")
            or os.getenv("LUMINA_VLLM_MUTATOR_URL")
            or "http://localhost:8000/v1/chat/completions"
        ).strip()
        self._vllm_model = str(
            os.getenv("LUMINA_VLLM_STRATEGY_MODEL") or os.getenv("LUMINA_VLLM_MUTATOR_MODEL") or "grok-trader-1b"
        ).strip()
        self._ollama_model = str(os.getenv("LUMINA_OLLAMA_STRATEGY_MODEL") or "qwen2.5:7b-instruct").strip()
        provider_chain = str(os.getenv("LUMINA_STRATEGY_PROVIDERS") or "vllm,ollama").strip().lower()
        self._providers = [item.strip() for item in provider_chain.split(",") if item.strip()]

    def generate_new_strategy(self, hypothesis: str) -> str:
        """Return a validated Python snippet with generated_strategy(context) -> dict."""
        normalized_hypothesis = str(hypothesis or "regime-adaptive confluence strategy").strip()
        prompt = self._build_prompt(normalized_hypothesis)

        generated: str | None = None
        for provider in self._providers:
            if provider == "vllm":
                generated = self._generate_with_vllm(prompt=prompt)
            elif provider == "ollama":
                generated = self._generate_with_ollama(prompt=prompt)
            if isinstance(generated, str) and generated.strip():
                break

        if not generated:
            generated = self._fallback_template(normalized_hypothesis)

        sandboxed = self.compile_and_validate(generated)
        return sandboxed.code

    def compile_and_validate(self, code_snippet: str) -> StrategySandboxResult:
        candidate = self._normalize_code(code_snippet)
        if len(candidate) > 6000:
            raise ValueError("generated_strategy_too_large")

        parsed = ast.parse(candidate, mode="exec")
        visitor = _SafetyVisitor()
        visitor.visit(parsed)
        if visitor.violations:
            raise ValueError(f"generated_strategy_unsafe:{','.join(visitor.violations)}")

        safe_builtins = {
            "abs": abs,
            "all": all,
            "any": any,
            "float": float,
            "int": int,
            "list": list,
            "len": len,
            "max": max,
            "min": min,
            "range": range,
            "round": round,
            "sorted": sorted,
            "sum": sum,
        }
        namespace: dict[str, Any] = {}
        code_obj = compile(parsed, "<generated_strategy>", "exec")
        exec(code_obj, {"__builtins__": safe_builtins}, namespace)

        func = namespace.get("generated_strategy")
        if not callable(func):
            raise ValueError("generated_strategy_missing_entrypoint")

        sample_context = {
            "close": [100.0, 101.2, 100.8, 102.0, 103.1],
            "volume": [1100.0, 1200.0, 1150.0, 1400.0, 1500.0],
            "volatility": 0.42,
            "trend": 0.58,
        }
        output = func(sample_context)
        if not isinstance(output, dict):
            raise ValueError("generated_strategy_invalid_output")

        name = str(output.get("name") or "generated_strategy").strip() or "generated_strategy"
        metadata = {
            "name": name,
            "regime_focus": str(output.get("regime_focus") or "neutral").strip().lower(),
            "signal_bias": str(output.get("signal_bias") or "neutral").strip().lower(),
            "confidence": float(output.get("confidence", 0.0) or 0.0),
        }
        return StrategySandboxResult(code=candidate, function_name="generated_strategy", metadata=metadata)

    def _normalize_code(self, raw: str) -> str:
        text = str(raw or "").strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            while lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return text

    def _build_prompt(self, hypothesis: str) -> str:
        return (
            "Generate only Python code. No markdown. No imports. No file/network/system access. "
            "Create one deterministic function: generated_strategy(context: dict) -> dict. "
            "Include a concise docstring. Keep code testable and side-effect free. "
            "Returned dict must contain keys: name, regime_focus, signal_bias, confidence, rules. "
            "Use only arithmetic and list operations on context values. "
            f"Hypothesis: {hypothesis}"
        )

    def _generate_with_vllm(self, *, prompt: str) -> str | None:
        if not self._vllm_endpoint or not self._vllm_model:
            return None
        if not self._vllm_endpoint.startswith(("http://", "https://")):
            return None

        payload = {
            "model": self._vllm_model,
            "temperature": 0.25,
            "max_tokens": 500,
            "messages": [
                {"role": "system", "content": "Return only valid Python code."},
                {"role": "user", "content": prompt},
            ],
        }
        request = urllib.request.Request(
            self._vllm_endpoint,
            data=json.dumps(payload, ensure_ascii=True).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        def _fetch() -> str | None:
            with urllib.request.urlopen(request, timeout=2.0) as response:  # nosec B310
                body = response.read().decode("utf-8")
            parsed = json.loads(body)
            choices = parsed.get("choices") if isinstance(parsed, dict) else None
            if not isinstance(choices, list) or not choices:
                return None
            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            content = message.get("content") if isinstance(message, dict) else None
            return str(content).strip() if isinstance(content, str) and content.strip() else None

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(_fetch).result(timeout=2.5)
        except (urllib.error.URLError, ValueError, json.JSONDecodeError, concurrent.futures.TimeoutError, TimeoutError):
            return None
        except Exception:
            return None

    def _generate_with_ollama(self, *, prompt: str) -> str | None:
        try:
            import ollama  # type: ignore
        except Exception:
            return None

        try:
            response = ollama.chat(
                model=self._ollama_model,
                messages=[
                    {"role": "system", "content": "Return only valid Python code."},
                    {"role": "user", "content": prompt},
                ],
                options={"temperature": 0.2, "num_ctx": 8192},
            )
            content = str(response.get("message", {}).get("content", "") or "").strip()
            return content if content else None
        except Exception:
            return None

    def _fallback_template(self, hypothesis: str) -> str:
        seed = _stable_seed(hypothesis)
        fast_window = 3 + (seed % 4)
        slow_window = fast_window + 4 + (seed % 3)
        regime = "trending" if seed % 2 == 0 else "ranging"
        signal = "buy" if seed % 3 == 0 else "sell"
        confidence = 0.55 + ((seed % 20) / 100.0)

        return textwrap.dedent(
            f'''\
            def generated_strategy(context: dict) -> dict:
                """Deterministic generated strategy using moving-average confluence and volatility filter."""
                close = list(context.get("close", []) or [])
                volatility = float(context.get("volatility", 0.0) or 0.0)
                if len(close) < {slow_window}:
                    return {{
                        "name": "auto_{seed}",
                        "regime_focus": "neutral",
                        "signal_bias": "neutral",
                        "confidence": 0.0,
                        "rules": ["insufficient_history"],
                    }}

                fast = sum(close[-{fast_window}:]) / {fast_window}
                slow = sum(close[-{slow_window}:]) / {slow_window}
                bias = "buy" if fast > slow and volatility < 0.8 else "sell"
                return {{
                    "name": "auto_{seed}",
                    "regime_focus": "{regime}",
                    "signal_bias": bias if bias in ("buy", "sell") else "{signal}",
                    "confidence": {confidence:.2f},
                    "rules": [
                        "ma_{fast_window}_cross_ma_{slow_window}",
                        "volatility_filter_lt_0.8",
                    ],
                }}
            '''
        ).strip()
