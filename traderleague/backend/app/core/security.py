import hashlib
import hmac


def sign_payload(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_signature(secret: str, body: bytes, provided_signature: str | None) -> bool:
    if not provided_signature:
        return False
    expected = sign_payload(secret, body)
    return hmac.compare_digest(expected, provided_signature)
