from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from pydantic import BaseModel, ConfigDict, Field

from lumina_core.audit import get_audit_logger
from lumina_core.config_loader import ConfigLoader

_DEFAULT_AUDIT_PATH = Path("state/real_promotion_approval_audit.jsonl")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_public_key_hex(key_hex: str) -> str:
    return str(key_hex).strip().lower()


def _public_key_fingerprint(public_key: Ed25519PublicKey) -> str:
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return hashlib.sha256(raw).hexdigest()


class RealPromotionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="v1", min_length=1)
    dna_hash: str = Field(min_length=8)
    target_mode: str = Field(default="real", min_length=4, max_length=4)
    dna_content_digest: str = Field(min_length=64, max_length=64)
    promotion_epoch: str = Field(min_length=1)
    reason_context: str = Field(default="real_promotion", min_length=1)
    created_at: datetime = Field(default_factory=_utcnow)
    expires_at: datetime = Field(default_factory=lambda: _utcnow() + timedelta(minutes=30))


class SignedApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approver_id: str = Field(min_length=1)
    public_key_fingerprint: str = Field(min_length=16)
    signature_b64: str = Field(min_length=16)
    reason: str = Field(min_length=1)
    timestamp: datetime = Field(default_factory=_utcnow)


class ApprovalPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    threshold: int = Field(ge=1)
    signer_public_keys_ed25519: tuple[str, ...] = Field(min_length=1)


class ApprovalChain:
    """Fail-closed multi-party approval verifier for REAL promotions."""

    def __init__(self, *, audit_path: Path | None = None, config_section: str = "governance") -> None:
        self._audit_path = audit_path or _DEFAULT_AUDIT_PATH
        self._config_section = str(config_section)
        get_audit_logger().register_stream("governance.real_promotion", self._audit_path)

    @staticmethod
    def canonical_payload_bytes(payload: RealPromotionPayload) -> bytes:
        as_dict = payload.model_dump(mode="json")
        canonical = json.dumps(as_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return canonical.encode("utf-8")

    @classmethod
    def payload_digest(cls, payload: RealPromotionPayload) -> str:
        return hashlib.sha256(cls.canonical_payload_bytes(payload)).hexdigest()

    @staticmethod
    def dna_content_digest(dna_content: dict[str, object]) -> str:
        canonical = json.dumps(dna_content, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def load_policy(self) -> ApprovalPolicy | None:
        cfg = ConfigLoader.section(self._config_section, default={}) or {}
        if not isinstance(cfg, dict):
            return None

        threshold = int(cfg.get("real_approval_threshold", 0) or 0)
        key_values = cfg.get("real_approval_public_keys_hex", [])
        if not isinstance(key_values, list):
            return None

        normalized_keys = tuple(
            _normalize_public_key_hex(item) for item in key_values if isinstance(item, str) and item.strip()
        )
        if threshold < 1 or not normalized_keys:
            return None
        if threshold > len(normalized_keys):
            return None
        return ApprovalPolicy(
            threshold=threshold,
            signer_public_keys_ed25519=normalized_keys,
        )

    @staticmethod
    def sign_payload(
        *,
        payload: RealPromotionPayload,
        approver_id: str,
        reason: str,
        private_key: Ed25519PrivateKey,
        timestamp: datetime | None = None,
    ) -> SignedApproval:
        payload_bytes = ApprovalChain.canonical_payload_bytes(payload)
        signature = private_key.sign(payload_bytes)
        public_key = private_key.public_key()
        return SignedApproval(
            approver_id=str(approver_id),
            public_key_fingerprint=_public_key_fingerprint(public_key),
            signature_b64=base64.b64encode(signature).decode("ascii"),
            reason=str(reason),
            timestamp=timestamp or _utcnow(),
        )

    def append_audit_record(
        self,
        *,
        payload: RealPromotionPayload,
        approval: SignedApproval | None,
        verified: bool,
        reason: str,
        threshold: int,
        valid_count: int,
    ) -> dict[str, object]:
        audit_entry: dict[str, object] = {
            "event": "real_promotion_approval",
            "timestamp": _utcnow().isoformat(),
            "dna_hash": payload.dna_hash,
            "dna_content_digest": payload.dna_content_digest,
            "payload_digest": self.payload_digest(payload),
            "approved": bool(verified),
            "reason": str(reason),
            "threshold": int(threshold),
            "valid_count": int(valid_count),
            "target_mode": payload.target_mode,
        }
        if approval is not None:
            audit_entry["approver"] = approval.approver_id
            audit_entry["approval_reason"] = approval.reason
            audit_entry["approval_timestamp"] = approval.timestamp.isoformat()
            audit_entry["public_key_fingerprint"] = approval.public_key_fingerprint
        else:
            audit_entry["approver"] = "system"
            audit_entry["approval_reason"] = "missing_or_invalid_signatures"
        return get_audit_logger().append(
            stream="governance.real_promotion",
            payload=audit_entry,
            path=self._audit_path,
            mode="real",
            actor_id="approval_chain",
            severity="info",
        )

    def verify(
        self,
        *,
        payload: RealPromotionPayload,
        signatures: Sequence[SignedApproval] | None,
        policy: ApprovalPolicy | None = None,
    ) -> tuple[bool, str]:
        try:
            if payload.target_mode != "real":
                self.append_audit_record(
                    payload=payload,
                    approval=None,
                    verified=False,
                    reason="invalid_target_mode",
                    threshold=0,
                    valid_count=0,
                )
                return False, "invalid_target_mode"

            active_policy = policy or self.load_policy()
            if active_policy is None:
                self.append_audit_record(
                    payload=payload,
                    approval=None,
                    verified=False,
                    reason="approval_policy_missing",
                    threshold=0,
                    valid_count=0,
                )
                return False, "approval_policy_missing"

            now = _utcnow()
            if payload.expires_at <= now:
                self.append_audit_record(
                    payload=payload,
                    approval=None,
                    verified=False,
                    reason="payload_expired",
                    threshold=active_policy.threshold,
                    valid_count=0,
                )
                return False, "payload_expired"

            payload_bytes = self.canonical_payload_bytes(payload)
            allowed_keys: dict[str, Ed25519PublicKey] = {}
            for key_hex in active_policy.signer_public_keys_ed25519:
                key_bytes = bytes.fromhex(_normalize_public_key_hex(key_hex))
                key = Ed25519PublicKey.from_public_bytes(key_bytes)
                allowed_keys[_public_key_fingerprint(key)] = key

            seen_signers: set[str] = set()
            valid_count = 0
            for approval in list(signatures or []):
                if approval.public_key_fingerprint in seen_signers:
                    self.append_audit_record(
                        payload=payload,
                        approval=approval,
                        verified=False,
                        reason="duplicate_signer",
                        threshold=active_policy.threshold,
                        valid_count=valid_count,
                    )
                    continue

                signer_key = allowed_keys.get(approval.public_key_fingerprint)
                if signer_key is None:
                    self.append_audit_record(
                        payload=payload,
                        approval=approval,
                        verified=False,
                        reason="signer_not_allowed",
                        threshold=active_policy.threshold,
                        valid_count=valid_count,
                    )
                    continue

                try:
                    signature = base64.b64decode(approval.signature_b64.encode("ascii"), validate=True)
                    signer_key.verify(signature, payload_bytes)
                    seen_signers.add(approval.public_key_fingerprint)
                    valid_count += 1
                    self.append_audit_record(
                        payload=payload,
                        approval=approval,
                        verified=True,
                        reason="signature_verified",
                        threshold=active_policy.threshold,
                        valid_count=valid_count,
                    )
                except (InvalidSignature, ValueError):
                    self.append_audit_record(
                        payload=payload,
                        approval=approval,
                        verified=False,
                        reason="invalid_signature",
                        threshold=active_policy.threshold,
                        valid_count=valid_count,
                    )

            if valid_count < active_policy.threshold:
                self.append_audit_record(
                    payload=payload,
                    approval=None,
                    verified=False,
                    reason="threshold_not_met",
                    threshold=active_policy.threshold,
                    valid_count=valid_count,
                )
                return False, "threshold_not_met"

            self.append_audit_record(
                payload=payload,
                approval=None,
                verified=True,
                reason="threshold_met",
                threshold=active_policy.threshold,
                valid_count=valid_count,
            )
            return True, "approved"
        except Exception:
            self.append_audit_record(
                payload=payload,
                approval=None,
                verified=False,
                reason="verification_exception",
                threshold=0,
                valid_count=0,
            )
            return False, "verification_exception"
