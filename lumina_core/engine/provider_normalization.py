from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ProviderNormalizationLayer:
    default_confidence: float = 0.5

    @staticmethod
    def _normalize_signal(value: Any) -> str:
        token = str(value or "HOLD").upper().strip()
        return token if token in {"BUY", "SELL", "HOLD"} else "HOLD"

    @staticmethod
    def _extract_confidence(payload: dict[str, Any], default_confidence: float) -> float:
        candidates = [
            payload.get("harmonized_confidence"),
            payload.get("confidence"),
            payload.get("conf"),
            payload.get("score"),
        ]
        for item in candidates:
            if item is None:
                continue
            try:
                value = float(item)
                if value > 1.0 and value <= 100.0:
                    value /= 100.0
                return max(0.0, min(1.0, value))
            except Exception:
                continue
        return max(0.0, min(1.0, float(default_confidence)))

    def normalize(
        self,
        *,
        provider: str,
        payload: dict[str, Any],
        provider_chain: list[str],
        calibration_factor: float,
    ) -> dict[str, Any]:
        normalized = dict(payload or {})
        normalized["signal"] = self._normalize_signal(normalized.get("signal"))

        raw_confidence = self._extract_confidence(normalized, self.default_confidence)
        factor = max(0.1, float(calibration_factor or 1.0))
        harmonized = max(0.0, min(1.0, raw_confidence * factor))

        normalized["confidence"] = float(raw_confidence)
        normalized["harmonized_confidence"] = float(harmonized)
        normalized["provider"] = str(provider)
        normalized["provider_route"] = [str(item) for item in provider_chain]
        normalized["calibration_factor"] = factor
        return normalized
