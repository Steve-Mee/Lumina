"""
LUMINA Core - Admin Authentication
Password hashing and verification using PBKDF2.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from pathlib import Path
from typing import Any


class AdminAuth:
    def __init__(self, password_file: Path):
        self.password_file = password_file

    def _load_record(self) -> dict[str, Any] | None:
        if not self.password_file.exists():
            return None
        try:
            payload = json.loads(self.password_file.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return None
            required = {"salt_b64", "hash_b64", "iterations"}
            if not required.issubset(set(payload.keys())):
                return None
            return payload
        except Exception:
            return None

    def _derive_hash(self, password: str, salt_bytes: bytes, iterations: int) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, iterations)

    def verify_password(self, candidate: str) -> bool:
        record = self._load_record()
        if not record:
            return False
        try:
            salt_bytes = base64.b64decode(str(record.get("salt_b64", "")))
            expected_hash = base64.b64decode(str(record.get("hash_b64", "")))
            iterations = int(record.get("iterations", 0))
        except Exception:
            return False
        if iterations < 100_000 or not salt_bytes or not expected_hash:
            return False
        candidate_hash = self._derive_hash(candidate, salt_bytes, iterations)
        return hmac.compare_digest(candidate_hash, expected_hash)

    def set_password(self, new_password: str) -> None:
        salt_bytes = secrets.token_bytes(16)
        iterations = 240_000
        pwd_hash = self._derive_hash(new_password, salt_bytes, iterations)
        self.password_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "algo": "pbkdf2_sha256",
            "iterations": iterations,
            "salt_b64": base64.b64encode(salt_bytes).decode("ascii"),
            "hash_b64": base64.b64encode(pwd_hash).decode("ascii"),
        }
        self.password_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
