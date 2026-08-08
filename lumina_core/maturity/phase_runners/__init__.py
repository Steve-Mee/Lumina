"""Phase runners package — strict exit proofs, honest incomplete."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.maturity.phase_runners.apprenticeship import run_apprenticeship
from lumina_core.maturity.phase_runners.awakening import run_awakening
from lumina_core.maturity.phase_runners.playground import run_playground
from lumina_core.maturity.phase_runners.proving_ground import run_proving_ground


def run_phase(workspace_root: Path | str, phase: str) -> dict[str, Any]:
    phase = str(phase or "").strip().lower()
    if phase == "awakening":
        return run_awakening(workspace_root)
    if phase == "playground":
        return run_playground(workspace_root)
    if phase == "apprenticeship":
        return run_apprenticeship(workspace_root)
    if phase == "proving_ground":
        return run_proving_ground(workspace_root)
    if phase == "birth":
        return {
            "ok": False,
            "error": "Birth is started via /api/birth/start, not maturity start-phase",
        }
    if phase == "real":
        return {
            "ok": False,
            "error": "REAL requires POST /api/maturity/approve-real + mode switch (human)",
        }
    return {"ok": False, "error": f"unknown phase: {phase}"}


__all__ = [
    "run_phase",
    "run_awakening",
    "run_playground",
    "run_apprenticeship",
    "run_proving_ground",
]
