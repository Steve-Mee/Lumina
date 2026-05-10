"""Map configured Ollama model tags to tags that are actually installed locally."""

from __future__ import annotations

import logging
import os
from typing import Sequence

logger = logging.getLogger(__name__)


def list_installed_ollama_models(*, host: str | None = None) -> list[str]:
    """Return model names from ``ollama list`` (empty if daemon unreachable)."""
    try:
        import ollama

        client = ollama.Client(host=host) if (host or "").strip() else ollama.Client()
        lr = client.list()
        models = getattr(lr, "models", None) or []
        out: list[str] = []
        for m in models:
            name = getattr(m, "model", None)
            if name is None and isinstance(m, dict):
                name = m.get("model")
            if name:
                out.append(str(name))
        return out
    except Exception as exc:
        logger.debug("ollama.list failed: %s", exc)
        return []


def resolve_ollama_model_tag(requested: str, installed: Sequence[str]) -> str:
    """Pick an installed tag if the configured one is missing.

    Order: exact match → case-insensitive → same family (prefix before ``:``) →
    first compatible non-embedding name by heuristic → first sorted installed name.

    Set ``LUMINA_OLLAMA_STRICT_MODEL=1`` to disable substitution (exact tag only).
    """
    req = str(requested or "").strip()
    if not req:
        return req
    strict = str(os.getenv("LUMINA_OLLAMA_STRICT_MODEL", "")).strip().lower() in {"1", "true", "yes", "on"}
    if strict:
        return req

    names = list(installed)
    if not names:
        return req

    if req in names:
        return req

    lower_map = {n.lower(): n for n in names}
    if req.lower() in lower_map:
        return lower_map[req.lower()]

    fam = req.split(":", 1)[0].strip()
    if fam:
        matches = [n for n in names if n.split(":", 1)[0] == fam]
        if not matches:
            matches = [n for n in names if n.startswith(fam + ":")]
        if matches:
            tag = req.split(":", 1)[1].strip().lower() if ":" in req else ""
            scored: list[tuple[int, str]] = []
            for n in matches:
                score = 0
                nl = n.lower()
                if tag and tag in nl:
                    score += 10
                if nl.endswith(":latest"):
                    score += 2
                scored.append((score, n))
            scored.sort(key=lambda x: (-x[0], x[1]))
            chosen = scored[0][1]
            if chosen != req:
                logger.info(
                    "Ollama model '%s' not installed; using same-family installed model '%s'",
                    req,
                    chosen,
                )
            return chosen

    for needle in ("qwen3", "qwen2", "llama", "mistral", "gemma"):
        for n in sorted(names):
            nl = n.lower()
            if needle in nl and "embed" not in nl:
                logger.info(
                    "Ollama model '%s' not installed; using compatible installed model '%s'",
                    req,
                    n,
                )
                return n

    fallback = sorted(names)[0]
    logger.warning(
        "Ollama model '%s' not installed; falling back to '%s'",
        req,
        fallback,
    )
    return fallback
