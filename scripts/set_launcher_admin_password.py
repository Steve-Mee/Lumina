from __future__ import annotations

import base64
import getpass
import hashlib
import hmac
import json
import secrets
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ADMIN_PASSWORD_HASH_PATH = REPO_ROOT / "state" / "launcher_admin_password.json"


def _derive_password_hash(password: str, salt_bytes: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, iterations)


def _load_record() -> dict | None:
    if not ADMIN_PASSWORD_HASH_PATH.exists():
        return None
    try:
        payload = json.loads(ADMIN_PASSWORD_HASH_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        return payload
    except Exception:
        return None


def _verify_password(candidate: str, record: dict) -> bool:
    try:
        salt_bytes = base64.b64decode(str(record.get("salt_b64", "")))
        expected_hash = base64.b64decode(str(record.get("hash_b64", "")))
        iterations = int(record.get("iterations", 0))
    except Exception:
        return False

    if iterations < 100_000 or not salt_bytes or not expected_hash:
        return False

    candidate_hash = _derive_password_hash(candidate, salt_bytes, iterations)
    return hmac.compare_digest(candidate_hash, expected_hash)


def _write_password(new_password: str) -> None:
    salt_bytes = secrets.token_bytes(16)
    iterations = 240_000
    pwd_hash = _derive_password_hash(new_password, salt_bytes, iterations)

    ADMIN_PASSWORD_HASH_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "algo": "pbkdf2_sha256",
        "iterations": iterations,
        "salt_b64": base64.b64encode(salt_bytes).decode("ascii"),
        "hash_b64": base64.b64encode(pwd_hash).decode("ascii"),
    }
    ADMIN_PASSWORD_HASH_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    print("LUMINA launcher admin password setup")
    existing = _load_record()
    if existing is not None:
        current = getpass.getpass("Current password: ")
        if not _verify_password(current, existing):
            raise SystemExit("Current password is incorrect")

    new_password = getpass.getpass("New password (min 12 chars): ")
    confirm = getpass.getpass("Confirm new password: ")

    if len(new_password) < 12:
        raise SystemExit("Password must be at least 12 characters")
    if new_password != confirm:
        raise SystemExit("Password confirmation does not match")

    _write_password(new_password)
    print(f"Password hash saved to {ADMIN_PASSWORD_HASH_PATH}")


if __name__ == "__main__":
    main()
