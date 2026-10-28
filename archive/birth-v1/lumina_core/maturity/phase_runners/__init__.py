"""Phase runners package — strict exit proofs, honest incomplete."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def run_phase(workspace_root: Path | str, phase: str) -> dict[str, Any]:
    phase = str(phase or "").strip().lower()
    if phase == "awakening":
        from lumina_core.maturity.phase_runners.awakening import run_awakening

        return run_awakening(workspace_root)
    if phase == "playground":
        from lumina_core.maturity.phase_runners.playground import run_playground

        return run_playground(workspace_root)
    if phase == "apprenticeship":
        from lumina_core.maturity.phase_runners.apprenticeship import run_apprenticeship

        return run_apprenticeship(workspace_root)
    if phase == "proving_ground":
        from lumina_core.maturity.phase_runners.proving_ground import run_proving_ground

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


def __getattr__(name: str) -> Any:
    if name == "run_awakening":
        from lumina_core.maturity.phase_runners.awakening import run_awakening

        return run_awakening
    if name == "run_playground":
        from lumina_core.maturity.phase_runners.playground import run_playground

        return run_playground
    if name == "run_apprenticeship":
        from lumina_core.maturity.phase_runners.apprenticeship import run_apprenticeship

        return run_apprenticeship
    if name == "run_proving_ground":
        from lumina_core.maturity.phase_runners.proving_ground import run_proving_ground

        return run_proving_ground
    raise AttributeError(name)


__all__ = [
    "run_phase",
    "run_awakening",
    "run_playground",
    "run_apprenticeship",
    "run_proving_ground",
]
