"""HMAC provenance for ValidationResult and PromotionCandidate.

The key lives in a closure. Agents read ``passed`` only from MAC-authenticated
canonical bytes. Forged, edited, or replayed-under-another-trial-id events fail.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from collections.abc import Callable, Mapping

from lumina_core.agent_orchestration.schemas_research import (
    PROMOTION_SCHEMA_VERSION,
    VALIDATION_SCHEMA_VERSION,
    PromotionCandidate,
    ValidationResult,
)
from lumina_research.agents.frozen import Frozen
from lumina_research.agents.objects import as_object_dict, as_object_list
from lumina_research.agents.payloads import dump_json

_HEX = 64
_Signer = Callable[[bytes], str]
_Verifier = Callable[[bytes, str], bool]


class ProvenanceError(ValueError):
    """Sealed payload failed authentication."""


class ProvenanceAuthority(Frozen):
    """HMAC-SHA256 sealer. The key is not stored as a public attribute."""

    _sign: _Signer
    _verify: _Verifier

    def __init_subclass__(cls) -> None:
        raise TypeError("ProvenanceAuthority cannot be subclassed")

    def __init__(self, key: bytes | None = None) -> None:
        material = key if key is not None else os.urandom(32)
        if len(material) < 16:
            raise ProvenanceError("provenance key is too short")

        def sign(message: bytes) -> str:
            return hmac.new(material, message, hashlib.sha256).hexdigest()

        def verify(message: bytes, mac: str) -> bool:
            if len(mac) != _HEX:
                return False
            expected = hmac.new(material, message, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, mac)

        self._sign = sign
        self._verify = verify
        self._freeze()

    def seal_validation(self, fields: Mapping[str, object]) -> tuple[str, str]:
        canonical = _canonical_validation(fields)
        digest = hashlib.sha256(canonical).hexdigest()
        return digest, self._sign(canonical)

    def verify_validation(self, payload: Mapping[str, object]) -> dict[str, object] | None:
        mac = payload.get("provenance_mac")
        if not isinstance(mac, str):
            return None
        try:
            canonical = _canonical_validation(payload)
        except KeyError:
            return None
        if not self._verify(canonical, mac):
            return None
        digest = hashlib.sha256(canonical).hexdigest()
        reported = payload.get("report_sha256")
        if reported != digest:
            return None
        trial_id = payload.get("trial_id")
        if not isinstance(trial_id, int) or isinstance(trial_id, bool) or trial_id < 1:
            return None
        parsed = as_object_dict(json.loads(canonical.decode("utf-8")))
        return parsed

    def seal_issue(self, fields: Mapping[str, object]) -> str:
        canonical = _canonical_issue(fields)
        return self._sign(canonical)

    def verify_issue(self, payload: Mapping[str, object]) -> bool:
        mac = payload.get("issue_mac")
        if not isinstance(mac, str):
            return False
        try:
            canonical = _canonical_issue(payload)
        except KeyError:
            return False
        return self._verify(canonical, mac)

    def guard_promotion(self, producer: str, payload: dict[str, object]) -> bool:
        if producer.strip() != "promotion_agent":
            return False
        try:
            PromotionCandidate.model_validate(payload)
        except Exception:
            return False
        return self.verify_issue(payload)


def validation_fields_from_result(result: ValidationResult) -> dict[str, object]:
    dumped = dump_json(result)
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
        "reject_reasons": _require_sequence(fields["reject_reasons"]),
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


def _require_sequence(value: object) -> list[object]:
    items = as_object_list(value)
    if items is None:
        raise KeyError("reject_reasons")
    return items


def _stable(value: object) -> object:
    as_dict = as_object_dict(value)
    if as_dict is not None:
        return {key: _stable(as_dict[key]) for key in sorted(as_dict)}
    as_list = as_object_list(value)
    if as_list is not None:
        return [_stable(item) for item in as_list]
    return value
