"""HMAC provenance for ValidationResult and PromotionCandidate.

The key lives in a closure. Agents read ``passed`` only from MAC-authenticated
canonical bytes. Forged, edited, or replayed-under-another-trial-id events fail.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Mapping

from lumina_core.agent_orchestration.schemas_research import (
    PROMOTION_SCHEMA_VERSION,
    VALIDATION_SCHEMA_VERSION,
    PromotionCandidate,
    ValidationResult,
)

_HEX = 64


class ProvenanceError(ValueError):
    """Sealed payload failed authentication."""


class ProvenanceAuthority:
    """HMAC-SHA256 sealer. The key is not stored as a public attribute."""

    def __init_subclass__(cls) -> None:
        raise TypeError("ProvenanceAuthority cannot be subclassed")

    def __init__(self, key: bytes | None = None) -> None:
        material = key if key is not None else os.urandom(32)
        if len(material) < 16:
            raise ProvenanceError("provenance key is too short")

        def sign(message: bytes) -> str:
            return hmac.new(material, message, hashlib.sha256).hexdigest()

        def verify(message: bytes, mac: str) -> bool:
            if not isinstance(mac, str) or len(mac) != _HEX:
                return False
            expected = hmac.new(material, message, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, mac)

        object.__setattr__(self, "_sign", sign)
        object.__setattr__(self, "_verify", verify)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("ProvenanceAuthority attributes are frozen")

    def seal_validation(self, fields: Mapping[str, object]) -> tuple[str, str]:
        canonical = _canonical_validation(fields)
        digest = hashlib.sha256(canonical).hexdigest()
        mac: str = self._sign(canonical)  # type: ignore[attr-defined]
        return digest, mac

    def verify_validation(self, payload: Mapping[str, object]) -> dict[str, object] | None:
        mac = payload.get("provenance_mac")
        if not isinstance(mac, str):
            return None
        canonical = _canonical_validation(payload)
        verify = self._verify  # type: ignore[attr-defined]
        if not bool(verify(canonical, mac)):
            return None
        digest = hashlib.sha256(canonical).hexdigest()
        reported = payload.get("report_sha256")
        if reported != digest:
            return None
        trial_id = payload.get("trial_id")
        if not isinstance(trial_id, int) or trial_id < 1:
            return None
        return json.loads(canonical.decode("utf-8"))

    def seal_issue(self, fields: Mapping[str, object]) -> str:
        canonical = _canonical_issue(fields)
        mac: str = self._sign(canonical)  # type: ignore[attr-defined]
        return mac

    def verify_issue(self, payload: Mapping[str, object]) -> bool:
        mac = payload.get("issue_mac")
        if not isinstance(mac, str):
            return False
        canonical = _canonical_issue(payload)
        verify = self._verify  # type: ignore[attr-defined]
        return bool(verify(canonical, mac))

    def guard_promotion(self, producer: str, payload: dict[str, object]) -> bool:
        if producer.strip() != "promotion_agent":
            return False
        try:
            PromotionCandidate.model_validate(payload)
        except Exception:
            return False
        return self.verify_issue(payload)


def validation_fields_from_result(result: ValidationResult) -> dict[str, object]:
    dumped = result.model_dump(mode="json", exclude_none=False)
    dumped.pop("provenance_mac", None)
    dumped.pop("report_sha256", None)
    return dumped


def _canonical_validation(fields: Mapping[str, object]) -> bytes:
    body = {
        "schema_version": fields.get("schema_version", VALIDATION_SCHEMA_VERSION),
        "hypothesis_id": fields["hypothesis_id"],
        "config_id": fields["config_id"],
        "trial_id": fields["trial_id"],
        "agent_id": fields["agent_id"],
        "passed": fields["passed"],
        "reject_reasons": list(fields["reject_reasons"]),
        "oos_distribution": fields["oos_distribution"],
        "dsr": fields["dsr"],
        "pbo": fields["pbo"],
        "wfe": fields["wfe"],
        "regimes": fields["regimes"],
        "n_oos_windows": fields["n_oos_windows"],
        "median_oos_after_costs": fields["median_oos_after_costs"],
    }
    return _dumps(body)


def _canonical_issue(fields: Mapping[str, object]) -> bytes:
    body = {
        "schema_version": fields.get("schema_version", PROMOTION_SCHEMA_VERSION),
        "hypothesis_id": fields["hypothesis_id"],
        "config_id": fields["config_id"],
        "trial_id": fields["trial_id"],
        "agent_id": fields["agent_id"],
        "instrument": fields["instrument"],
        "decision_kind": fields["decision_kind"],
        "scaled": fields["scaled"],
        "quantity": fields["quantity"],
        "notional": fields["notional"],
        "risk_reason": fields["risk_reason"],
        "validation_report_sha256": fields["validation_report_sha256"],
        "validation_mac": fields["validation_mac"],
    }
    return _dumps(body)


def _dumps(value: object) -> bytes:
    return json.dumps(_stable(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _stable(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _stable(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_stable(item) for item in value]
    return value
