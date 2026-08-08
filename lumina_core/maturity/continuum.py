"""Phase continuum SSOT — durable post-birth lifecycle (operator hub + checkpoints).

Keeps ``lumina_maturity_progress.json`` as milestone ledger; this file owns
session lifecycle: completed phases, active runner, advance mode, learned summaries.
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from lumina_core.logging_utils import get_logger
from lumina_core.maturity.maturation_progress import (
    MaturationPhase,
)

logger = get_logger("lumina.maturity.continuum")

CONTINUUM_REL = Path("state") / "lumina_phase_continuum.json"
SCHEMA_VERSION = 1

AdvanceMode = Literal["manual", "telegram", "auto_evolve"]
PhaseStatus = Literal["pending", "running", "completed", "failed", "wiped"]

OPERATOR_PHASES: tuple[str, ...] = (
    MaturationPhase.GENESIS.value,
    MaturationPhase.BIRTH.value,
    MaturationPhase.AWAKENING.value,
    MaturationPhase.PLAYGROUND.value,
    MaturationPhase.APPRENTICESHIP.value,
    MaturationPhase.PROVING_GROUND.value,
    MaturationPhase.REAL.value,
)


def continuum_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / CONTINUUM_REL


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_continuum() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "active_phase": None,
        "completed_phases": [],
        "phase_records": {},
        "advance_mode": "manual",
        "pending_advance": None,
        "updated_at": _utcnow(),
    }


def load_continuum(workspace_root: Path | str) -> dict[str, Any]:
    path = continuum_path(workspace_root)
    if not path.is_file():
        return migrate_from_milestones(workspace_root)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return migrate_from_milestones(workspace_root)
        data = _empty_continuum()
        data.update(raw)
        data["schema_version"] = SCHEMA_VERSION
        if data.get("advance_mode") not in ("manual", "telegram", "auto_evolve"):
            data["advance_mode"] = "manual"
        if not isinstance(data.get("completed_phases"), list):
            data["completed_phases"] = []
        if not isinstance(data.get("phase_records"), dict):
            data["phase_records"] = {}
        return data
    except Exception as exc:
        logger.warning("maturity.continuum.load_failed: %s", exc)
        return migrate_from_milestones(workspace_root)


def save_continuum(workspace_root: Path | str, data: dict[str, Any]) -> None:
    path = continuum_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(data)
    payload["schema_version"] = SCHEMA_VERSION
    payload["updated_at"] = _utcnow()
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    tmp.replace(path)




def _birth_artifacts_ok(workspace_root: Path | str) -> bool:
    try:
        from lumina_launcher.services.birth_service import BirthService

        svc = BirthService()
        svc.configure_workspace(Path(workspace_root))
        return bool(svc.artifacts_ok() or svc.certificate_ok())
    except Exception:
        return False


def _birth_learned_snapshot(workspace_root: Path | str) -> dict[str, Any]:
    root = Path(workspace_root)
    progress_path = root / "state" / "lumina_birth_progress.json"
    out: dict[str, Any] = {}
    if progress_path.is_file():
        try:
            raw = json.loads(progress_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                out = {
                    "trades": int(raw.get("trades_done") or raw.get("cumulative_trades") or 0),
                    "stage_winrate": raw.get("stage_winrate"),
                    "edgescore": raw.get("edgescore"),
                    "soft_block_rate_per_1k_signals": raw.get("soft_block_rate_per_1k_signals"),
                    "curriculum_stage": raw.get("curriculum_stage"),
                    "training_mode": raw.get("training_mode"),
                    "message": raw.get("message"),
                }
        except Exception:
            pass
    return out


def next_phase_id(completed: list[str]) -> str | None:
    done = set(completed)
    for phase in OPERATOR_PHASES:
        if phase not in done:
            return phase
    return None


def mark_phase_running(
    workspace_root: Path | str,
    phase: str,
    *,
    learned: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_continuum(workspace_root)
    data["active_phase"] = phase
    rec = dict(data["phase_records"].get(phase) or {})
    rec["status"] = "running"
    rec["started_at"] = rec.get("started_at") or _utcnow()
    if learned:
        rec["learned"] = {**(rec.get("learned") or {}), **learned}
    data["phase_records"][phase] = rec
    save_continuum(workspace_root, data)
    return data


def mark_phase_completed(
    workspace_root: Path | str,
    phase: str,
    *,
    learned: dict[str, Any] | None = None,
    exit_proofs: list[str] | None = None,
) -> dict[str, Any]:
    data = load_continuum(workspace_root)
    if data.get("active_phase") == phase:
        data["active_phase"] = None
    rec = dict(data["phase_records"].get(phase) or {})
    rec["status"] = "completed"
    rec["completed_at"] = _utcnow()
    if learned:
        rec["learned"] = {**(rec.get("learned") or {}), **learned}
    if exit_proofs is not None:
        rec["exit_proofs"] = list(exit_proofs)
    data["phase_records"][phase] = rec
    completed = list(data.get("completed_phases") or [])
    if phase not in completed:
        completed.append(phase)
    order = list(OPERATOR_PHASES)
    data["completed_phases"] = [p for p in order if p in set(completed)]
    save_continuum(workspace_root, data)
    return data


def mark_phase_failed(
    workspace_root: Path | str,
    phase: str,
    *,
    error: str,
) -> dict[str, Any]:
    data = load_continuum(workspace_root)
    if data.get("active_phase") == phase:
        data["active_phase"] = None
    rec = dict(data["phase_records"].get(phase) or {})
    rec["status"] = "failed"
    rec["error"] = str(error)[:500]
    rec["failed_at"] = _utcnow()
    data["phase_records"][phase] = rec
    save_continuum(workspace_root, data)
    return data


def set_advance_mode(workspace_root: Path | str, mode: AdvanceMode) -> dict[str, Any]:
    data = load_continuum(workspace_root)
    if mode not in ("manual", "telegram", "auto_evolve"):
        mode = "manual"
    data["advance_mode"] = mode
    save_continuum(workspace_root, data)
    return data


def set_pending_advance(
    workspace_root: Path | str,
    *,
    from_phase: str,
    to_phase: str,
    ttl_sec: int | None = None,
) -> dict[str, Any]:
    data = load_continuum(workspace_root)
    token = secrets.token_urlsafe(16)
    if ttl_sec is None:
        try:
            from lumina_core.maturity.maturity_config import load_maturity_config

            ttl_sec = load_maturity_config().telegram_advance_token_ttl_sec
        except Exception:
            ttl_sec = 86400
    ttl = max(300, min(604800, int(ttl_sec or 86400)))
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=ttl)
    data["pending_advance"] = {
        "from": from_phase,
        "to": to_phase,
        "telegram_token": token,
        "created_at": now.isoformat(),
        "expires_at": expires.isoformat(),
        "ttl_sec": ttl,
    }
    save_continuum(workspace_root, data)
    return data


def clear_pending_advance(workspace_root: Path | str) -> dict[str, Any]:
    data = load_continuum(workspace_root)
    data["pending_advance"] = None
    save_continuum(workspace_root, data)
    return data


def _parse_expires_at(exp_raw: str) -> datetime | None:
    try:
        exp = datetime.fromisoformat(str(exp_raw).replace("Z", "+00:00"))
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return exp
    except ValueError:
        return None


def pending_advance_expired(pending: dict[str, Any] | None, *, now: datetime | None = None) -> bool:
    """True if pending_advance is present and past expires_at (fail-closed if unparsable)."""
    if not isinstance(pending, dict):
        return False
    exp_raw = str(pending.get("expires_at") or "").strip()
    if not exp_raw:
        # Legacy tokens without expiry: treat as still valid (migration)
        return False
    exp = _parse_expires_at(exp_raw)
    if exp is None:
        return True
    ref = now or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    return ref >= exp


def pending_advance_remaining_sec(
    pending: dict[str, Any] | None,
    *,
    now: datetime | None = None,
) -> int | None:
    """Seconds until expiry (0 if expired). None if no pending / no expires_at."""
    if not isinstance(pending, dict):
        return None
    exp_raw = str(pending.get("expires_at") or "").strip()
    if not exp_raw:
        return None
    exp = _parse_expires_at(exp_raw)
    if exp is None:
        return 0
    ref = now or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    return max(0, int((exp - ref).total_seconds()))


def pending_advance_public(
    pending: dict[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Hub-safe view of pending telegram advance (no raw token leak)."""
    if not isinstance(pending, dict):
        return None
    expired = pending_advance_expired(pending, now=now)
    remaining = pending_advance_remaining_sec(pending, now=now)
    status = "expired" if expired else "active"
    return {
        "from": pending.get("from"),
        "to": pending.get("to"),
        "created_at": pending.get("created_at"),
        "expires_at": pending.get("expires_at"),
        "ttl_sec": pending.get("ttl_sec"),
        "remaining_sec": remaining,
        "expired": expired,
        "status": status,
        "has_token": bool(pending.get("telegram_token")),
        # Never expose raw token in hub poll (paste from Telegram message)
    }


def clear_expired_pending_advance(workspace_root: Path | str) -> dict[str, Any]:
    """Clear pending advance if token TTL elapsed. Returns action summary."""
    data = load_continuum(workspace_root)
    pending = data.get("pending_advance")
    if not isinstance(pending, dict):
        return {"cleared": False, "reason": "no_pending"}
    if not pending_advance_expired(pending):
        remaining = pending_advance_remaining_sec(pending)
        return {
            "cleared": False,
            "reason": "not_expired",
            "expires_at": pending.get("expires_at"),
            "remaining_sec": remaining,
        }
    clear_pending_advance(workspace_root)
    logger.info(
        "maturity.pending_advance.expired from=%s to=%s",
        pending.get("from"),
        pending.get("to"),
    )
    return {
        "cleared": True,
        "reason": "token_expired",
        "from": pending.get("from"),
        "to": pending.get("to"),
        "expires_at": pending.get("expires_at"),
        "remaining_sec": 0,
    }

from lumina_core.maturity.continuum_migrate import migrate_from_milestones, wipe_all_continuum, wipe_phase_record  # noqa: F401, E402

