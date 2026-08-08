"""Shared helpers for phase runners."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.maturity.continuum import load_continuum, mark_phase_completed, mark_phase_failed, save_continuum
from lumina_core.maturity.maturity_config import MaturityConfig, load_maturity_config
from lumina_core.maturity.phase_specs import evaluate_exit_proofs


def cfg() -> MaturityConfig:
    return load_maturity_config()


def write_phase_progress(
    workspace_root: Path | str,
    phase: str,
    *,
    progress_pct: float | None = None,
    message: str | None = None,
    learned: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    root = Path(workspace_root)
    data = load_continuum(root)
    rec = dict((data.get("phase_records") or {}).get(phase) or {})
    if progress_pct is not None:
        rec["progress_pct"] = max(0.0, min(100.0, float(progress_pct)))
    if message is not None:
        rec["message"] = str(message)[:500]
    if learned:
        rec["learned"] = {**(rec.get("learned") or {}), **learned}
    if extra:
        rec.update(extra)
    data.setdefault("phase_records", {})[phase] = rec
    save_continuum(root, data)


def finish_from_exit_eval(
    workspace_root: Path | str,
    phase: str,
    *,
    default_proofs: list[str] | None = None,
) -> dict[str, Any]:
    """Evaluate hard proofs; complete or fail honestly."""
    root = Path(workspace_root)
    ok, missing, learned = evaluate_exit_proofs(root, phase)
    if ok:
        proofs = list(learned.get("exit_proofs") or default_proofs or [])
        if not proofs and not missing:
            proofs = default_proofs or [f"{phase}_passed"]
        mark_phase_completed(root, phase, learned=learned, exit_proofs=proofs)
        return {"ok": True, "phase": phase, "learned": learned, "missing": []}
    mark_phase_failed(root, phase, error=f"missing:{','.join(missing)}")
    return {
        "ok": False,
        "phase": phase,
        "missing": missing,
        "learned": learned,
        "status": "incomplete",
    }
