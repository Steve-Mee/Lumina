"""Approval Twin scoring backends (local heuristic + Ollama)."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Protocol

from lumina_core.evolution.dna_registry import PolicyDNA


class ApprovalTwinBackend(Protocol):
    def score(self, *, dna: PolicyDNA, local_score: float, threshold: float) -> tuple[float | None, str]: ...


@dataclass(slots=True)
class LocalHeuristicBackend:
    def score(self, *, dna: PolicyDNA, local_score: float, threshold: float) -> tuple[float | None, str]:
        del dna
        return local_score, f"local_heuristic(threshold={threshold:.0%})"


@dataclass(slots=True)
class OllamaTwinBackend:
    model: str = "qwen2.5:3b-instruct"

    def score(self, *, dna: PolicyDNA, local_score: float, threshold: float) -> tuple[float | None, str]:
        try:
            import ollama  # type: ignore
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/evolution/approval_twin_agent.py:40")
            return None, "ollama_unavailable_fallback_local"

        prompt = (
            "You are an approval gate for REAL DNA promotion. "
            "Return strict JSON only with keys score (0..1) and explanation. "
            "Score should represent approval confidence.\n"
            f"threshold={threshold:.2f}\n"
            f"local_score={local_score:.4f}\n"
            f"dna_content={dna.content}\n"
            f"dna_fitness={float(dna.fitness_score):.6f}\n"
            f"dna_mutation_rate={float(dna.mutation_rate):.6f}\n"
            f"dna_generation={int(dna.generation)}"
        )
        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Respond with valid compact JSON only."},
                    {"role": "user", "content": prompt},
                ],
                options={"temperature": 0.0},
            )
            content = str(response.get("message", {}).get("content", "") or "").strip()
            payload = json.loads(content)
            score = float(payload.get("score", local_score))
            score = max(0.0, min(1.0, score))
            explanation = str(payload.get("explanation", "ollama_decision")).strip() or "ollama_decision"
            return score, f"ollama:{self.model}:{explanation}"
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/evolution/approval_twin_agent.py:69")
            return None, "ollama_error_fallback_local"
