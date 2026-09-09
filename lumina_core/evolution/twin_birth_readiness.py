"""Twin Birth-ready flag. Session on the current curriculum is SSOT; the JSON flag is derived."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.evolution.twin_base_curriculum import BASE_CURRICULUM_VERSION

_DEFAULT_SESSION = Path("state/twin_base_training.json")
_DEFAULT_READINESS = Path("state/twin_birth_readiness.json")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_birth_readiness(path: Path | str = _DEFAULT_READINESS) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {
            "base_trained": False,
            "birth_ready": False,
            "curriculum_version": BASE_CURRICULUM_VERSION,
            "question_count": 0,
            "completed_at": None,
        }
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {"base_trained": False, "birth_ready": False}
        return raw
    except (OSError, json.JSONDecodeError):
        return {"base_trained": False, "birth_ready": False}


def write_birth_readiness(
    path: Path | str,
    *,
    base_trained: bool,
    question_count: int,
    curriculum_version: str = BASE_CURRICULUM_VERSION,
    session_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "base_trained": bool(base_trained),
        "birth_ready": bool(base_trained),
        "curriculum_version": curriculum_version,
        "question_count": int(question_count),
        "completed_at": _utcnow() if base_trained else None,
        "session_id": session_id,
        "local_only": True,
    }
    if extra:
        payload.update(extra)
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def load_base_session(path: Path | str = _DEFAULT_SESSION) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def session_qualifies_for_birth_ready(
    session: dict[str, Any],
    *,
    required_version: str = BASE_CURRICULUM_VERSION,
) -> bool:
    """True when every session question is answered on the current curriculum version."""
    if not session:
        return False
    ver = str(session.get("curriculum_version") or "").strip()
    if ver != str(required_version):
        return False
    qids = [str(item) for item in (session.get("question_ids") or [])]
    if not qids:
        return False
    answers = session.get("answers")
    if not isinstance(answers, dict):
        return False
    return all(qid in answers for qid in qids)


def default_session_path_for_readiness(readiness_path: Path | str) -> Path:
    return Path(readiness_path).parent / "twin_base_training.json"


def heal_birth_readiness(
    *,
    readiness_path: Path | str = _DEFAULT_READINESS,
    session_path: Path | str | None = None,
    required_version: str = BASE_CURRICULUM_VERSION,
) -> dict[str, Any]:
    """Persist the derived flag when the completed session already proves Birth-ready.

    Never invents answers. Stale curriculum versions do not heal.
    """
    session_file = Path(session_path) if session_path is not None else default_session_path_for_readiness(
        readiness_path
    )
    session = load_base_session(session_file)
    if not session_qualifies_for_birth_ready(session, required_version=required_version):
        return load_birth_readiness(readiness_path)
    answers = session.get("answers") if isinstance(session.get("answers"), dict) else {}
    return write_birth_readiness(
        readiness_path,
        base_trained=True,
        question_count=len(answers),
        curriculum_version=str(required_version),
        session_id=str(session.get("session_id") or "") or None,
        extra={"healed_from_session": True},
    )


def is_twin_birth_ready(
    path: Path | str = _DEFAULT_READINESS,
    *,
    required_version: str = BASE_CURRICULUM_VERSION,
    session_path: Path | str | None = None,
) -> bool:
    """True only when base completed on the *current* curriculum version (fail-closed)."""
    heal_birth_readiness(
        readiness_path=path,
        session_path=session_path,
        required_version=required_version,
    )
    raw = load_birth_readiness(path)
    if not bool(raw.get("base_trained") or raw.get("birth_ready")):
        return False
    ver = str(raw.get("curriculum_version") or "").strip()
    return ver == str(required_version)
