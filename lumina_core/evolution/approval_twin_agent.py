from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from lumina_core.config_loader import ConfigLoader
from .dna_registry import PolicyDNA
from .steve_values_registry import SteveValueRecord, SteveValuesRegistry


@dataclass(slots=True)
class ApprovalTwinState:
    intercept: float
    weights: dict[str, float]
    threshold: float
    training_steps: int


class ApprovalTwinBackend(Protocol):
    def score(self, *, dna: PolicyDNA, local_score: float, threshold: float) -> tuple[float | None, str]:
        ...


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
            return None, "ollama_error_fallback_local"


class ApprovalTwinAgent:
    """Small local approval model trained only on Steve's answers."""

    def __init__(
        self,
        *,
        registry: SteveValuesRegistry | None = None,
        model_path: Path | str = Path("state/approval_twin_model.json"),
        learning_rate: float = 0.08,
        backend: str | None = None,
        ollama_model: str | None = None,
    ) -> None:
        self._registry = registry
        self._model_path = Path(model_path)
        self._learning_rate = float(learning_rate)
        self._state = self._load_state()
        self._backend_name, self._backend = self._build_backend(backend=backend, ollama_model=ollama_model)

    def evaluate_dna_promotion(self, dna: PolicyDNA) -> dict[str, Any]:
        features = self._features_from_dna(dna)
        local_score = self._score(features)
        backend_score, backend_explanation = self._backend.score(
            dna=dna,
            local_score=local_score,
            threshold=self._state.threshold,
        )
        score = float(backend_score if backend_score is not None else local_score)
        score = max(0.0, min(1.0, score))
        risk_flags = self._risk_flags(dna)
        recommendation = bool(score >= self._state.threshold and not risk_flags)
        explanation = (
            f"Twin score={score:.2%}, threshold={self._state.threshold:.0%}, backend={self._backend_name}, "
            f"fitness={float(dna.fitness_score):.4f}, mutation_rate={float(dna.mutation_rate):.2f}, "
            f"source={backend_explanation}"
        )
        return {
            "recommendation": recommendation,
            "confidence": round(score, 6),
            "explanation": explanation,
            "risk_flags": risk_flags,
        }

    def _build_backend(self, *, backend: str | None, ollama_model: str | None) -> tuple[str, ApprovalTwinBackend]:
        cfg = ConfigLoader.section("evolution", "approval_twin", default={})
        cfg = cfg if isinstance(cfg, dict) else {}

        resolved_backend = str(
            backend
            or cfg.get("backend")
            or ConfigLoader.section("ai", "approval_twin_backend", default="")
            or "local"
        ).strip().lower()

        if resolved_backend == "ollama":
            model = str(
                ollama_model
                or cfg.get("ollama_model")
                or ConfigLoader.section("ai", "approval_twin_ollama_model", default="")
                or "qwen2.5:3b-instruct"
            ).strip()
            return "ollama", OllamaTwinBackend(model=model)

        return "local", LocalHeuristicBackend()

    def fine_tune_from_registry(self, *, limit: int = 250) -> dict[str, Any]:
        if self._registry is None:
            return {"updated": False, "reason": "registry_unavailable"}
        records = self._registry.list_recent(limit=max(1, int(limit)))
        return self.rlhf_light_update(records=records)

    def rlhf_light_update(self, *, records: list[SteveValueRecord]) -> dict[str, Any]:
        updates = 0
        abs_errors: list[float] = []

        # Replay from oldest to newest so recent Steve judgments dominate.
        for record in reversed(records):
            label = self._label_from_answer(record.steve_antwoord)
            if label is None:
                continue
            features = self._features_from_record(record)
            pred = self._score(features)
            error = float(label) - pred

            self._state.intercept += self._learning_rate * error
            for key, value in features.items():
                self._state.weights[key] = float(self._state.weights.get(key, 0.0)) + self._learning_rate * error * value

            abs_errors.append(abs(error))
            updates += 1

        if updates > 0:
            self._state.training_steps += updates
            self._save_state()

        avg_error = sum(abs_errors) / len(abs_errors) if abs_errors else 1.0
        reward = max(0.0, min(1.0, 1.0 - avg_error))
        return {
            "updated": updates > 0,
            "updates": updates,
            "avg_prediction_error": round(avg_error, 6),
            "reward": round(reward, 6),
            "training_steps": int(self._state.training_steps),
        }

    def _score(self, features: dict[str, float]) -> float:
        logit = float(self._state.intercept)
        for key, value in features.items():
            logit += float(self._state.weights.get(key, 0.0)) * float(value)
        # Stable sigmoid for confidence in [0,1].
        if logit >= 0.0:
            z = math.exp(-logit)
            return 1.0 / (1.0 + z)
        z = math.exp(logit)
        return z / (1.0 + z)

    @staticmethod
    def _features_from_dna(dna: PolicyDNA) -> dict[str, float]:
        content = str(dna.content).lower()
        return {
            "bias": 1.0,
            "fitness": float(dna.fitness_score),
            "mutation_rate": float(dna.mutation_rate),
            "generation": float(dna.generation),
            "contains_risk_word": 1.0 if any(token in content for token in ("aggressive", "leverage", "martingale")) else 0.0,
            "contains_safety_word": 1.0 if any(token in content for token in ("risk", "guard", "stop", "cooldown")) else 0.0,
        }

    @staticmethod
    def _features_from_record(record: SteveValueRecord) -> dict[str, float]:
        text = f"{record.vraag} {record.steve_antwoord}".lower()
        return {
            "bias": 1.0,
            "record_confidence": float(record.confidence_score),
            "mentions_real": 1.0 if "real" in text else 0.0,
            "mentions_risk": 1.0 if "risk" in text or "risico" in text else 0.0,
            "mentions_drawdown": 1.0 if "drawdown" in text else 0.0,
            "approve_token": 1.0 if "approve" in text else 0.0,
            "veto_token": 1.0 if "veto" in text else 0.0,
        }

    @staticmethod
    def _label_from_answer(answer: str) -> float | None:
        lowered = str(answer).strip().lower()
        if "approve" in lowered:
            return 1.0
        if "veto" in lowered:
            return 0.0
        return None

    @staticmethod
    def _risk_flags(dna: PolicyDNA) -> list[str]:
        flags: list[str] = []
        if float(dna.fitness_score) <= 0.0:
            flags.append("non_positive_fitness")
        if float(dna.mutation_rate) > 0.35:
            flags.append("high_mutation_rate")
        content = str(dna.content).lower()
        if "martingale" in content:
            flags.append("martingale_detected")
        return flags

    def _load_state(self) -> ApprovalTwinState:
        if not self._model_path.exists():
            return ApprovalTwinState(intercept=0.0, weights={}, threshold=0.6, training_steps=0)
        try:
            payload = json.loads(self._model_path.read_text(encoding="utf-8"))
            return ApprovalTwinState(
                intercept=float(payload.get("intercept", 0.0) or 0.0),
                weights={str(k): float(v) for k, v in dict(payload.get("weights", {})).items()},
                threshold=max(0.5, min(0.95, float(payload.get("threshold", 0.6) or 0.6))),
                training_steps=int(payload.get("training_steps", 0) or 0),
            )
        except Exception:
            return ApprovalTwinState(intercept=0.0, weights={}, threshold=0.6, training_steps=0)

    def _save_state(self) -> None:
        self._model_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "intercept": float(self._state.intercept),
            "weights": dict(self._state.weights),
            "threshold": float(self._state.threshold),
            "training_steps": int(self._state.training_steps),
        }
        self._model_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
