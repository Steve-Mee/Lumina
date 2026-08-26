"""Encryption-at-rest helpers (v51 / ADR-0042).

Uses Fernet (symmetric) with ``LUMINA_STATE_ENCRYPTION_KEY`` (url-safe base64 32-byte key).
Fail-closed: encrypt requires key; decrypt of ciphertext without key raises.

Plaintext files remain supported for local dev when key is unset.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PREFIX = "LUMINA1:"  # versioned ciphertext envelope prefix


def encryption_enabled() -> bool:
    return bool(str(os.getenv("LUMINA_STATE_ENCRYPTION_KEY", "") or "").strip())


def _fernet():  # type: ignore[no-untyped-def]
    raw = str(os.getenv("LUMINA_STATE_ENCRYPTION_KEY", "") or "").strip()
    if not raw:
        return None
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "cryptography package required for encryption-at-rest (pip install cryptography)"
        ) from exc
    # Accept raw Fernet key or derive from passphrase via SHA256→urlsafe.
    try:
        return Fernet(raw.encode("ascii") if isinstance(raw, str) else raw)
    except Exception:
        digest = hashlib.sha256(raw.encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
        return Fernet(key)


def generate_key() -> str:
    """Generate a new Fernet key string for ops to store in env."""
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("cryptography package required") from exc
    return Fernet.generate_key().decode("ascii")


def encrypt_bytes(data: bytes) -> bytes:
    f = _fernet()
    if f is None:
        return data
    token = f.encrypt(data)
    return (_PREFIX + token.decode("ascii")).encode("utf-8")


def decrypt_bytes(data: bytes) -> bytes:
    text = data.decode("utf-8", errors="replace")
    if not text.startswith(_PREFIX):
        return data  # plaintext legacy
    f = _fernet()
    if f is None:
        raise RuntimeError(
            "Encrypted blob requires LUMINA_STATE_ENCRYPTION_KEY to decrypt (fail-closed)"
        )
    token = text[len(_PREFIX) :].encode("ascii")
    return f.decrypt(token)


def encrypt_text(text: str) -> str:
    return encrypt_bytes(text.encode("utf-8")).decode("utf-8")


def decrypt_text(text: str) -> str:
    return decrypt_bytes(text.encode("utf-8")).decode("utf-8")


def write_json_secure(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON; encrypt file body when LUMINA_STATE_ENCRYPTION_KEY is set."""
    raw = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encrypt_bytes(raw))


def read_json_secure(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = decrypt_bytes(path.read_bytes())
        parsed = json.loads(data.decode("utf-8"))
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        logger.warning("read_json_secure failed path=%s", path, exc_info=True)
        return None
