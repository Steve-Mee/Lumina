from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import random
import urllib.error
import urllib.request

from .dna_registry import PolicyDNA


def _mutate_with_local_model(base_prompt: str, rate: float) -> str | None:
    endpoint = str(os.getenv("LUMINA_VLLM_MUTATOR_URL", "http://localhost:8000/v1/chat/completions")).strip()
    model = str(os.getenv("LUMINA_VLLM_MUTATOR_MODEL", "grok-trader-1b")).strip()
    if not endpoint or not model:
        return None

    payload = {
        "model": model,
        "temperature": max(0.05, min(0.9, float(rate))),
        "max_tokens": 120,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Mutate this trading policy prompt while preserving capital-first behavior. "
                    "Return only the mutated prompt text."
                ),
            },
            {
                "role": "user",
                "content": base_prompt,
            },
        ],
    }

    try:
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=True).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        def _fetch() -> str | None:
            with urllib.request.urlopen(request, timeout=1.5) as response:
                body = response.read().decode("utf-8")
            parsed = json.loads(body)
            choices = parsed.get("choices") if isinstance(parsed, dict) else None
            if not isinstance(choices, list) or not choices:
                return None
            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, str) and content.strip():
                return content.strip()
            return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as _pool:
            _future = _pool.submit(_fetch)
            result = _future.result(timeout=2.0)
        return result
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError,
            concurrent.futures.TimeoutError):
        return None
    except Exception:
        return None
    return None


def _content_text(content: str) -> str:
    try:
        payload = json.loads(content)
    except Exception:
        return str(content).strip()

    if not isinstance(payload, dict):
        return str(content).strip()
    for key in ("prompt_tweak", "candidate_name", "prompt_fingerprint"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return json.dumps(payload, sort_keys=True, ensure_ascii=True)


def mutate_prompt(prompt: str, rate: float) -> str:
    base_prompt = str(prompt or "Preserve capital and prefer HOLD under uncertainty.").strip()
    local_model_mutation = _mutate_with_local_model(base_prompt, float(rate or 0.1))
    if isinstance(local_model_mutation, str) and local_model_mutation:
        return local_model_mutation

    strategies = [
        "Prioritize capital preservation before directional conviction.",
        "Reduce exposure when regime drift spikes or confidence splits.",
        "Favor HOLD when cross-agent consensus degrades.",
        "Bias execution toward lower drawdown paths before upside expansion.",
        "Escalate caution when liquidity or correlation stress is detected.",
    ]
    normalized_rate = max(0.05, min(1.0, float(rate or 0.1)))
    mutation_count = max(1, min(len(strategies), int(round(normalized_rate * len(strategies)))))
    seed = int(hashlib.sha256(f"{base_prompt}|{normalized_rate:.4f}".encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed)
    clauses = rng.sample(strategies, mutation_count)
    return " ".join([base_prompt, *clauses]).strip()


def crossover(parent1: PolicyDNA, parent2: PolicyDNA) -> str:
    left = _content_text(parent1.content)
    right = _content_text(parent2.content)
    left_parts = [part.strip() for part in left.split(".") if part.strip()]
    right_parts = [part.strip() for part in right.split(".") if part.strip()]

    left_pick = left_parts[0] if left_parts else left
    right_pick = right_parts[-1] if right_parts else right
    if not left_pick:
        return right_pick
    if not right_pick:
        return left_pick
    if left_pick == right_pick:
        return left_pick
    return f"{left_pick}. {right_pick}".strip()


def calculate_fitness(
    pnl: float,
    max_dd: float,
    sharpe: float,
    *,
    capital_preservation_threshold: float = 25000.0,
    drawdown_weight: float = 0.0001,
) -> float:
    pnl_value = float(pnl or 0.0)
    drawdown_value = float(max_dd or 0.0)
    sharpe_value = float(sharpe or 0.0)
    if drawdown_value > float(capital_preservation_threshold):
        return float("-inf")
    return sharpe_value + (pnl_value / 10000.0) - (drawdown_value * float(drawdown_weight))