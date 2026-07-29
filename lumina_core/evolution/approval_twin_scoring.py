"""Approval Twin scoring / feature / calibration helpers."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from lumina_core.evolution.dna_registry import PolicyDNA
from lumina_core.evolution.steve_values_registry import SteveValueRecord
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.evolution.twin")


class ApprovalTwinScoringMixin:
    def _score(self, features: dict[str, float]) -> float:
        logit = float(self._state.intercept)
        for key, value in features.items():
            logit += float(self._state.weights.get(key, 0.0)) * float(value)
        # Stable sigmoid for confidence in [0,1].
        if logit >= 0.0:
            z = math.exp(-logit)
            out = 1.0 / (1.0 + z)
            try:
                logger.debug(
                    "twin.score_internal",
                    extra={"event_data": {"event": "twin.score_internal", "features": features, "score": out}},
                )
            except Exception:
                pass
            return out
        z = math.exp(logit)
        out = z / (1.0 + z)
        try:
            logger.debug(
                "twin.score_internal",
                extra={"event_data": {"event": "twin.score_internal", "features": features, "score": out}},
            )
        except Exception:
            pass
        return out

    def _calibrate(self, raw: float) -> float:
        """Simple confidence calibration driven by recent training error.

        When mimicry error (avg_prediction_error) is high, pull extreme
        confidences toward 0.5 so that "high confidence" decisions used for
        autonomous birth loops are honest.
        """
        err = float(getattr(self._state, "last_avg_error", 0.15) or 0.15)
        blend = min(0.45, max(0.0, err * 1.8))
        return max(0.0, min(1.0, raw * (1.0 - blend) + 0.5 * blend))

    @staticmethod
    def _load_emotional_profile() -> dict[str, float]:
        """Load Steve's emotional twin sensitivities (used as bias features for approval mimicry).
        Safe fallback to neutral 1.0 sensitivities if file missing/unreadable.
        """
        defaults = {
            "fomo_sensitivity": 1.0,
            "tilt_sensitivity": 1.0,
            "boredom_sensitivity": 1.0,
            "revenge_sensitivity": 1.0,
        }
        try:
            p = Path("lumina_agents/emotional_twin_profile.json")
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                for k in defaults:
                    if k in data:
                        defaults[k] = float(data[k])
        except Exception:
            pass
        return defaults

    @staticmethod
    def _features_from_dna(dna: PolicyDNA) -> dict[str, float]:
        """Richer feature set for Steve-mimicry.

        Sources:
        - SteveValuesRegistry (via training labels)
        - emotional_twin_profile.json (emotional bias signals Steve exhibits)
        - decision_lineage (lineage_hash presence as provenance signal)
        """
        content = str(dna.content).lower()
        emo = ApprovalTwinScoringMixin._load_emotional_profile()
        lineage = getattr(dna, "lineage_hash", "") or ""
        has_lineage = 1.0 if lineage and str(lineage).upper() not in ("", "GENESIS", "BIRTH", "AUTO") else 0.0
        fitness = float(dna.fitness_score)
        return {
            "bias": 1.0,
            "fitness": fitness,
            "mutation_rate": float(dna.mutation_rate),
            "generation": float(dna.generation),
            "content_len_norm": min(1.0, len(str(dna.content)) / 600.0),
            "high_fitness": 1.0 if fitness > 1.0 else 0.0,
            "contains_risk_word": 1.0
            if any(token in content for token in ("aggressive", "leverage", "martingale"))
            else 0.0,
            "contains_safety_word": 1.0
            if any(token in content for token in ("risk", "guard", "stop", "cooldown", "constitution"))
            else 0.0,
            "has_lineage": has_lineage,
            # Emotional profile as Steve risk-tolerance / bias proxy (weights will learn correlations)
            "fomo_sens": emo["fomo_sensitivity"],
            "tilt_sens": emo["tilt_sensitivity"],
            "boredom_sens": emo["boredom_sensitivity"],
            "revenge_sens": emo["revenge_sensitivity"],
        }

    @staticmethod
    def _features_from_record(record: SteveValueRecord) -> dict[str, float]:
        """Richer record features (Steve's explicit answers drive weights)."""
        text = f"{record.vraag} {record.steve_antwoord}".lower()
        return {
            "bias": 1.0,
            "record_confidence": float(record.confidence_score),
            "mentions_real": 1.0 if "real" in text else 0.0,
            "mentions_risk": 1.0 if "risk" in text or "risico" in text else 0.0,
            "mentions_drawdown": 1.0 if "drawdown" in text else 0.0,
            "mentions_constitution": 1.0 if "constitution" in text or "kapitaal" in text else 0.0,
            "mentions_fitness": 1.0 if "fitness" in text else 0.0,
            "mentions_guard": 1.0 if "guard" in text or "safety" in text else 0.0,
            "approve_token": 1.0 if "approve" in text else 0.0,
            "veto_token": 1.0 if "veto" in text else 0.0,
            "modify_token": 1.0 if "modify" in text else 0.0,
        }

    @staticmethod
    def _label_from_answer(answer: str) -> float | None:
        """Map Steve answers to RLHF targets.

        Primary token (before optional ``: notes``) wins so
        ``MODIFY: still approve size cut`` stays soft-reject (0.35), not 1.0.
        """
        lowered = str(answer).strip().lower()
        if not lowered:
            return None
        head = lowered.split(":", 1)[0].strip()
        if head in {"modify", "m"} or lowered.startswith("modify"):
            return 0.35
        if head in {"approve", "a", "yes", "y"} or "approve" in lowered:
            return 1.0
        if head in {"veto", "reject", "v", "n", "no"} or "veto" in lowered or "reject" in lowered:
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
