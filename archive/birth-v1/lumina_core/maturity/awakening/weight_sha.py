"""Canonical policy identity. Zip timestamps and optimizer state are not weights."""
from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

POLICY_MEMBER = "policy.pth"
STORAGE_PREFIX = "archive/data/"


class PolicyWeightShaError(RuntimeError):
    """The zip has no readable tensor storages. Fail closed. Do not hash the container."""


def policy_weight_sha256(path: Path) -> str:
    """Hash tensor storages inside ``policy.pth``.

    A Stable-Baselines resave changes the outer zip and ``serialization_id``
    without changing weights. Those bytes are excluded. Optimizer state is excluded.
    """
    if not path.is_file() or path.stat().st_size <= 0:
        raise PolicyWeightShaError("policy_zip_missing")
    try:
        with zipfile.ZipFile(path) as outer:
            if POLICY_MEMBER not in outer.namelist():
                raise PolicyWeightShaError("policy_pth_missing")
            raw = outer.read(POLICY_MEMBER)
    except zipfile.BadZipFile as exc:
        raise PolicyWeightShaError("policy_zip_unreadable") from exc
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as inner:
            names = sorted(
                name
                for name in inner.namelist()
                if name.startswith(STORAGE_PREFIX) and not name.endswith("/")
            )
            if not names:
                raise PolicyWeightShaError("policy_storages_missing")
            digest = hashlib.sha256()
            for name in names:
                payload = inner.read(name)
                digest.update(name.encode("utf-8"))
                digest.update(len(payload).to_bytes(8, "big"))
                digest.update(payload)
            return digest.hexdigest()
    except zipfile.BadZipFile as exc:
        raise PolicyWeightShaError("policy_pth_unreadable") from exc


def pack_policy_weight_zip(*storages: bytes, serialization_id: bytes = b"sid") -> bytes:
    """Build a zip whose weight hash is exactly ``storages`` and nothing else."""
    if not storages or any(not isinstance(blob, (bytes, bytearray)) or len(blob) == 0 for blob in storages):
        raise PolicyWeightShaError("policy_storages_missing")
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as zf:
        for index, blob in enumerate(storages):
            zf.writestr(f"{STORAGE_PREFIX}{index}", bytes(blob))
        zf.writestr("archive/.data/serialization_id", serialization_id)
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w") as zf:
        zf.writestr(POLICY_MEMBER, inner.getvalue())
        zf.writestr("policy.optimizer.pth", b"optimizer-state-is-not-weights")
        zf.writestr("_stable_baselines3_version", b"test")
    return outer.getvalue()
