from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from lumina_core.audit.hash_chain import validate_hash_chain
from lumina_core.governance import ApprovalChain, ApprovalPolicy, RealPromotionPayload, SignedApproval


def _public_hex(private_key: Ed25519PrivateKey) -> str:
    return (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        .hex()
    )


def _payload(dna_hash: str = "dna_approved_12345678") -> RealPromotionPayload:
    now = datetime.now(timezone.utc)
    return RealPromotionPayload(
        dna_hash=dna_hash,
        target_mode="real",
        dna_content_digest="a" * 64,
        promotion_epoch="gen:1:dna",
        reason_context="governance_unit_test",
        created_at=now,
        expires_at=now + timedelta(minutes=10),
    )


@pytest.mark.unit
def test_verify_rejects_without_valid_threshold(tmp_path: Path) -> None:
    # gegeven
    chain = ApprovalChain(audit_path=tmp_path / "approval_audit.jsonl")
    key_a = Ed25519PrivateKey.generate()
    key_b = Ed25519PrivateKey.generate()
    key_c = Ed25519PrivateKey.generate()
    outsider = Ed25519PrivateKey.generate()
    policy = ApprovalPolicy(
        threshold=2,
        signer_public_keys_ed25519=(_public_hex(key_a), _public_hex(key_b), _public_hex(key_c)),
    )
    payload = _payload()
    outsider_signature = ApprovalChain.sign_payload(
        payload=payload,
        approver_id="outsider",
        reason="unauthorized_approval",
        private_key=outsider,
    )

    # wanneer
    ok, reason = chain.verify(payload=payload, signatures=[outsider_signature], policy=policy)

    # dan
    assert ok is False
    assert reason == "threshold_not_met"


@pytest.mark.unit
def test_verify_accepts_two_of_three_signatures(tmp_path: Path) -> None:
    # gegeven
    chain = ApprovalChain(audit_path=tmp_path / "approval_audit.jsonl")
    key_a = Ed25519PrivateKey.generate()
    key_b = Ed25519PrivateKey.generate()
    key_c = Ed25519PrivateKey.generate()
    policy = ApprovalPolicy(
        threshold=2,
        signer_public_keys_ed25519=(_public_hex(key_a), _public_hex(key_b), _public_hex(key_c)),
    )
    payload = _payload("dna_promotion_abcdefgh")
    approval_a = ApprovalChain.sign_payload(
        payload=payload,
        approver_id="alice",
        reason="risk_review_green",
        private_key=key_a,
    )
    approval_b = ApprovalChain.sign_payload(
        payload=payload,
        approver_id="bob",
        reason="ops_review_green",
        private_key=key_b,
    )

    # wanneer
    ok, reason = chain.verify(payload=payload, signatures=[approval_a, approval_b], policy=policy)

    # dan
    assert ok is True
    assert reason == "approved"


@pytest.mark.unit
def test_audit_trail_hash_chain_remains_intact(tmp_path: Path) -> None:
    # gegeven
    audit_path = tmp_path / "approval_audit.jsonl"
    chain = ApprovalChain(audit_path=audit_path)
    key_a = Ed25519PrivateKey.generate()
    key_b = Ed25519PrivateKey.generate()
    key_c = Ed25519PrivateKey.generate()
    policy = ApprovalPolicy(
        threshold=2,
        signer_public_keys_ed25519=(_public_hex(key_a), _public_hex(key_b), _public_hex(key_c)),
    )
    payload = _payload("dna_chain_integrity_123")
    approval_a = ApprovalChain.sign_payload(
        payload=payload,
        approver_id="alice",
        reason="first_signature",
        private_key=key_a,
    )
    approval_b = ApprovalChain.sign_payload(
        payload=payload,
        approver_id="bob",
        reason="second_signature",
        private_key=key_b,
    )

    # wanneer
    ok, _ = chain.verify(payload=payload, signatures=[approval_a, approval_b], policy=policy)
    chain.append_audit_record(
        payload=payload,
        approval=SignedApproval(
            approver_id="observer",
            public_key_fingerprint="feedfacecafebeef",
            signature_b64=base64.b64encode(b"manual_audit_payload").decode("ascii"),
            reason="manual_audit_entry",
        ),
        verified=ok,
        reason="post_verify_audit_check",
        threshold=2,
        valid_count=2,
    )
    is_valid, message = validate_hash_chain(audit_path)

    # dan
    assert ok is True
    assert is_valid is True
    assert message == "ok"
