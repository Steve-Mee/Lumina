"""Wave A PR4.2 — split starship_birth into edgescore + swarm_gates façades."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIRTH = ROOT / "lumina_core" / "birth"
SRC = BIRTH / "starship_birth.py"


def extract(lines: list[str], start: int, end: int) -> str:
    return "".join(lines[start - 1 : end])


def main() -> None:
    lines = SRC.read_text(encoding="utf-8").splitlines(keepends=True)

    edgescore = '''"""Starship Birth EdgeScore + entropy life-support helpers.

Canonical re-export: ``lumina_core.birth.starship_birth``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.starship_edgescore")


'''
    edgescore += extract(lines, 19, 568)
    (BIRTH / "starship_edgescore.py").write_text(edgescore.rstrip() + "\n", encoding="utf-8")

    swarm = '''"""Starship Birth swarm-first gates + pause SSOT helpers.

Canonical re-export: ``lumina_core.birth.starship_birth``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.starship_swarm_gates")


'''
    swarm += extract(lines, 571, 826)
    (BIRTH / "starship_swarm_gates.py").write_text(swarm.rstrip() + "\n", encoding="utf-8")

    facade = '''"""Starship Birth Phase A — EdgeScore, entropy life-support, swarm-first gates.

SIM/birth learning gates only. Certificate OOS thresholds remain untouched.

Bounded modules: ``starship_edgescore``, ``starship_swarm_gates``.
"""
from __future__ import annotations

from lumina_core.birth.starship_edgescore import (  # noqa: F401
    EdgeScoreResult,
    compute_expectancy_proxy,
    edgescore_champion_min_trades,
    evaluate_stage1_edgescore,
    evaluate_stage2_edgescore,
    evaluate_stage3_edgescore,
    gate_rolling_winrate,
    humanize_edgescore_blocker,
    hygiene_wr_telemetry,
    is_edgescore_champion_eligible,
    policy_entropy_alive,
    read_last_ppo_entropy,
    rolling_pass_min_covered,
    rolling_wr_pass_eligible,
    sanitize_edgescore_champion,
    should_force_exploration_burst,
)
from lumina_core.birth.starship_swarm_gates import (  # noqa: F401
    build_pause_ssot_payload,
    edgescore_from_swarm_result,
    effective_plateau_max_evolution_steps,
    should_block_phoenix_until_swarm,
    should_force_swarm_retearnament,
    should_hard_stop_training_after_swarm_reject,
    should_skip_plateau_ladder_theater,
    should_start_swarm_before_recovery,
    swarm_edgescore_lift,
    swarm_tournament_done,
    swarm_tournament_lift,
    tournament_lift_required_delta,
    tournament_score,
    write_pause_ssot,
)

__all__ = [
    "EdgeScoreResult",
    "build_pause_ssot_payload",
    "compute_expectancy_proxy",
    "edgescore_champion_min_trades",
    "edgescore_from_swarm_result",
    "effective_plateau_max_evolution_steps",
    "evaluate_stage1_edgescore",
    "evaluate_stage2_edgescore",
    "evaluate_stage3_edgescore",
    "gate_rolling_winrate",
    "humanize_edgescore_blocker",
    "hygiene_wr_telemetry",
    "is_edgescore_champion_eligible",
    "policy_entropy_alive",
    "read_last_ppo_entropy",
    "rolling_pass_min_covered",
    "rolling_wr_pass_eligible",
    "sanitize_edgescore_champion",
    "should_block_phoenix_until_swarm",
    "should_force_exploration_burst",
    "should_force_swarm_retearnament",
    "should_hard_stop_training_after_swarm_reject",
    "should_skip_plateau_ladder_theater",
    "should_start_swarm_before_recovery",
    "swarm_edgescore_lift",
    "swarm_tournament_done",
    "swarm_tournament_lift",
    "tournament_lift_required_delta",
    "tournament_score",
    "write_pause_ssot",
]
'''
    SRC.write_text(facade.rstrip() + "\n", encoding="utf-8")
    print("starship split done")
    for name in ("starship_birth.py", "starship_edgescore.py", "starship_swarm_gates.py"):
        n = len((BIRTH / name).read_text(encoding="utf-8").splitlines())
        print(f"  {name}: {n}")


if __name__ == "__main__":
    main()
