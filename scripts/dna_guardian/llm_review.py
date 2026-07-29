"""DNA Guardian — experimental local Ollama LLM review."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from structure import DNA_ROOT

def _call_ollama_chat(
    prompt: str,
    model: str = "qwen3.5:9b",
    base_url: str = "http://localhost:11434",
    timeout_sec: float = 20.0,
) -> dict[str, Any] | None:
    """
    Very small, dependency-free call to Ollama /api/chat.
    Returns parsed JSON response or None on any failure (timeout, error, bad JSON).
    Designed for the narrow experimental --llm-review path only.
    """
    url = f"{base_url.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.3},  # low temp for more consistent analysis
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, Exception):
        return None


def _get_ollama_models() -> list[str]:
    """
    Returns preferred model order for LLM review.
    Can be overridden with DNA_GUARDIAN_OLLAMA_MODELS (comma-separated).
    """
    env_models = os.getenv("DNA_GUARDIAN_OLLAMA_MODELS", "").strip()
    if env_models:
        parsed = [m.strip() for m in env_models.split(",") if m.strip()]
        if parsed:
            return parsed

    return ["qwen3.5:9b", "qwen2.5:7b", "qwen2.5:3b"]


def _get_ollama_timeout_sec() -> float:
    """
    Returns Ollama timeout in seconds.
    Can be overridden with DNA_GUARDIAN_OLLAMA_TIMEOUT_SEC.
    """
    raw = os.getenv("DNA_GUARDIAN_OLLAMA_TIMEOUT_SEC", "").strip()
    if not raw:
        return 20.0

    try:
        value = float(raw)
        return value if value > 0 else 20.0
    except ValueError:
        return 20.0


def run_llm_review_on_file(
    file_path: str,
    heuristic_result: dict[str, Any],
    context_summary: str,
) -> dict[str, Any] | None:
    """
    Runs a narrow, experimental LLM review on a single file.
    Returns structured dict or None if anything fails.
    The prompt is deliberately conservative and focused.
    """
    full_path = DNA_ROOT / file_path
    if not full_path.exists():
        return None

    try:
        content = full_path.read_text(encoding="utf-8")
    except Exception:
        return None

    # Load few-shot examples for better prompting (part of Double Down Local proposal)
    examples_dir = DNA_ROOT / "operating-system" / "llm-review-examples"
    few_shot_text = ""
    if examples_dir.exists():
        example_files = sorted(examples_dir.glob("*.md"))[:3]  # max 3 examples for now
        for ex_file in example_files:
            try:
                few_shot_text += "\n\n--- FEW-SHOT EXAMPLE ---\n" + ex_file.read_text(encoding="utf-8")[:2500]
            except Exception:
                pass

    # LLM Review Prompt v3.0 — Double Down Local (14-day evaluation sprint)
    prompt = f"""You are an extremely rigorous, first-principles reviewer of self-improvement systems for a high-stakes autonomous trading organism.

Your mission: Maximize the future evolution speed of this system by ruthlessly exposing weaknesses in documentation that slow down or derail high-quality, evidence-based improvement.

Core principles you must follow:
- Be brutally honest. Vague language and aspirational claims are technical debt.
- Always reference the official Evolvability Score definition when relevant.
- Prefer specific quotes and concrete examples over general statements.
- Every finding must be actionable.

File: {file_path}
Heuristic findings: {heuristic_result.get('findings', [])}
DNA context: {context_summary}

Relevant high-quality review examples (for style and depth reference):
{few_shot_text}

File content:
{content[:10000]}

**Required thinking structure (do this internally):**
1. Falsifiability & Evidence — Quote exact sentences that are not testable or lack evidence.
2. Evolvability Impact — How does this document currently slow down or increase risk of future improvements? Use the Evolvability Score lens.
3. Missing Forcing Functions & Precision — What specific mechanisms or definitions are missing that would make good evolution obvious and bad evolution painful?
4. Top Actionable Improvement — What is the single highest-leverage concrete change for this file right now?

Output ONLY this exact JSON structure (no markdown, no extra text):
{{
  "refined_score": <0-10, be strict and consistent>,
  "additional_findings": [
    "Specific, quoted finding 1",
    "Specific, quoted finding 2"
  ],
  "evolvability_impact": "<1-2 sentences using Evolvability Score concepts>",
  "top_actionable_improvement": "<one concrete, high-leverage action>",
  "missing_precision_areas": ["e.g. definition of X is unclear", "no criteria for Y"],
  "confidence": <0.0-1.0>,
  "one_sentence_summary": "<extremely concise and direct>"
}}"""

    timeout_sec = _get_ollama_timeout_sec()
    response = None
    for model_name in _get_ollama_models():
        response = _call_ollama_chat(prompt, model=model_name, timeout_sec=timeout_sec)
        if response and "message" in response:
            break

    if not response or "message" not in response:
        return None

    try:
        llm_text = response["message"].get("content", "")
        # Try to extract JSON even if model adds a little noise
        start = llm_text.find("{")
        end = llm_text.rfind("}") + 1
        if start == -1 or end <= start:
            return None
        parsed = json.loads(llm_text[start:end])
        # Basic validation
        if "refined_score" not in parsed:
            return None
        return parsed
    except Exception:
        return None

