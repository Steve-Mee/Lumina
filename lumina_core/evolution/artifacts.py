"""Immutable evolution artifact bundles (overlay + DNA + weights + schema)."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.code_evolution.runtime_role import CHALLENGER, CHAMPION, normalize_runtime_role


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def content_digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ArtifactBundle:
    artifact_id: str
    role: str
    overlay_digest: str
    dna_hash: str
    policy_zip: str
    schema_ledger: str
    content_digest: str
    created_at: str
    requires_org_cols: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ArtifactBundle":
        return cls(
            artifact_id=str(raw.get("artifact_id") or ""),
            role=normalize_runtime_role(str(raw.get("role") or CHALLENGER)),
            overlay_digest=str(raw.get("overlay_digest") or ""),
            dna_hash=str(raw.get("dna_hash") or ""),
            policy_zip=str(raw.get("policy_zip") or ""),
            schema_ledger=str(raw.get("schema_ledger") or ""),
            content_digest=str(raw.get("content_digest") or ""),
            created_at=str(raw.get("created_at") or ""),
            requires_org_cols=bool(raw.get("requires_org_cols", False)),
        )


def artifacts_root(workspace: Path | str) -> Path:
    return Path(workspace) / "state" / "evolution_artifacts"


def bundle_dir(workspace: Path | str, artifact_id: str) -> Path:
    return artifacts_root(workspace) / artifact_id


def freeze_bundle(
    workspace: Path | str,
    *,
    artifact_id: str,
    role: str,
    overlay_digest: str,
    dna_hash: str,
    policy_zip: str,
    schema_ledger: str,
    requires_org_cols: bool = False,
    overlay_src: Path | str | None = None,
) -> ArtifactBundle:
    """Write an immutable copy. Missing policy_zip is allowed at freeze; cutover rejects it (K10)."""
    payload = {
        "artifact_id": artifact_id,
        "role": normalize_runtime_role(role),
        "overlay_digest": overlay_digest,
        "dna_hash": dna_hash,
        "policy_zip": policy_zip,
        "schema_ledger": schema_ledger,
        "requires_org_cols": requires_org_cols,
        "created_at": _utcnow(),
    }
    digest = content_digest(payload)
    payload["content_digest"] = digest
    target = bundle_dir(workspace, artifact_id)
    target.mkdir(parents=True, exist_ok=True)
    (target / "BUNDLE.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if overlay_src is not None:
        src_overlay = Path(overlay_src)
        if src_overlay.is_dir():
            dest_overlay = target / "overlay"
            if dest_overlay.exists():
                shutil.rmtree(dest_overlay)
            shutil.copytree(src_overlay, dest_overlay)
    if policy_zip:
        src = Path(policy_zip)
        if src.is_file():
            dest = target / src.name
            dest.write_bytes(src.read_bytes())
            payload["policy_zip"] = str(dest)
            digest = content_digest({k: v for k, v in payload.items() if k != "content_digest"})
            payload["content_digest"] = digest
            (target / "BUNDLE.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return ArtifactBundle.from_dict(payload)


def load_bundle(workspace: Path | str, artifact_id: str) -> ArtifactBundle | None:
    path = bundle_dir(workspace, artifact_id) / "BUNDLE.json"
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    return ArtifactBundle.from_dict(raw)


def bundle_complete_for_swap(bundle: ArtifactBundle) -> list[str]:
    """K10: transactional completeness. Empty policy_zip is a hard fail for swap."""
    fails: list[str] = []
    if not bundle.artifact_id:
        fails.append("missing_artifact_id")
    if not bundle.dna_hash:
        fails.append("missing_dna_hash")
    if not bundle.content_digest:
        fails.append("missing_content_digest")
    zip_path = str(bundle.policy_zip or "")
    if not zip_path or not Path(zip_path).is_file():
        fails.append("missing_policy_zip")
    if bool(bundle.requires_org_cols) and not str(bundle.schema_ledger or "").strip():
        fails.append("missing_schema_ledger")
    return fails


def pointer_path(workspace: Path | str, role: str) -> Path:
    name = "CHAMPION.json" if normalize_runtime_role(role) == CHAMPION else "CHALLENGER.json"
    return artifacts_root(workspace) / name


def read_pointer(workspace: Path | str, role: str) -> dict[str, Any]:
    path = pointer_path(workspace, role)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(raw) if isinstance(raw, dict) else {}


def write_pointer(workspace: Path | str, role: str, payload: dict[str, Any]) -> Path:
    path = pointer_path(workspace, role)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path
