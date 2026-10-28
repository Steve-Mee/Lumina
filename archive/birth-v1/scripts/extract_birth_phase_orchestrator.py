"""One-shot extract run_birth_phase from engine.py into birth_phase_orchestrator.py."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "lumina_core" / "birth" / "engine.py"
OUT = ROOT / "lumina_core" / "birth" / "birth_phase_orchestrator.py"

HEADER = '''"""Birth phase top-level orchestration (extracted from engine)."""

from __future__ import annotations

import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.buffer_persist import clear_buffer
from lumina_core.birth.certificate_evaluator import evaluate_holdout_certificate
from lumina_core.birth.checkpoint import (
    can_resume_checkpoint,
    clear_checkpoint,
    load_checkpoint_state,
    read_checkpoint_payload,
    reset_adaptation_budget_for_manual_resume,
    write_checkpoint_payload,
)
from lumina_core.birth.config import BRO_ENGINE_VERSION, resolve_effective_trade_budget
from lumina_core.birth.curriculum import (
    CurriculumStage,
    filter_ticks_for_stage,
    ordered_stages,
    stage_trade_target,
)
from lumina_core.birth.progress import read_birth_progress, write_birth_progress
from lumina_core.birth.purged_split import purged_validation_split
from lumina_core.birth.remediation import (
    reconstruct_checkpoint_from_progress,
    should_fast_path_remediation_from_state,
)
from lumina_core.birth.runway import micro_oos_probe
from lumina_core.birth.stage_pass_receipt import parse_stage_pass_receipts
from lumina_core.birth.stage_scorecard import build_scorecard_payload, compute_regime_distribution
from lumina_core.first_boot_progress import ensure_first_boot_hardware_profile
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.birth_phase_orchestrator")


def run_birth_phase(
    host: Any,
    *,
    target_trades: int | None = None,
    max_real_days: int = 365,
    prefer_real_data_only: bool = True,
    chunk_size: int = 50_000,
    ppo_update_timesteps: int = 25_000,
    force: bool = False,
    practice_mode: bool = False,
    reuse_existing_policy: bool | None = None,
    reuse_data_manifest: bool = False,
    expand_data: bool = False,
) -> dict[str, Any]:
'''


def main() -> None:
    lines = ENGINE.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip().startswith("def run_birth_phase("))
    end = next(
        i
        for i in range(start + 1, len(lines))
        if lines[i].startswith("    def ") and not lines[i].startswith("        ")
    )
    body_lines = lines[start + 1 : end]
    body_start = 0
    for i, line in enumerate(body_lines):
        if ") -> dict[str, Any]:" in line:
            body_start = i + 1
            break
    body = "\n".join(body_lines[body_start:]).replace("self.", "host.")
    # Normalize: method body was 8-space indented inside class; function body uses 4 spaces.
    body = "\n".join(
        line[4:] if line.startswith("        ") else line for line in body.splitlines()
    )
    OUT.write_text(HEADER + body + "\n", encoding="utf-8")
    print(f"extracted {end - start} method lines -> {OUT} ({len((HEADER + body).splitlines())} total)")


if __name__ == "__main__":
    main()