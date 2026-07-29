"""Wave B PR-B4 — ppo_trainer + stage_loop data/session splits."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "lumina_core"
BIRTH = CORE / "birth"


def lines_of(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines(keepends=True)


def extract(lines: list[str], start: int, end: int) -> str:
    return "".join(lines[start - 1 : end])


def write(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)} ({len(text.splitlines())} lines)")


def split_ppo() -> None:
    print("== ppo_trainer ==")
    src = CORE / "ppo_trainer.py"
    lines = lines_of(src)

    device = '''"""PPO device selection helpers (Wave B PR-B4)."""
from __future__ import annotations


def _resolve_ppo_device() -> str:
    """Select CUDA when available; CPU otherwise (BRO PR-N)."""
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    return "cpu"


def _scale_timesteps_for_device(timesteps: int) -> int:
    device = _resolve_ppo_device()
    if device == "cuda":
        return max(int(timesteps), int(timesteps) * 2)
    return int(timesteps)


__all__ = ["_resolve_ppo_device", "_scale_timesteps_for_device"]
'''
    write(CORE / "ppo_device.py", device)

    # callbacks: entropy extract + progress notify + SB3 callbacks (L46-179)
    callbacks_header = '''"""PPO training callbacks and first-boot progress helpers (Wave B PR-B4)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.ppo_evolution_logger import PPOEvolutionLogger

logger = get_logger("lumina.rl.ppo")

'''
    callbacks_body = extract(lines, 46, 179)
    write(CORE / "ppo_callbacks.py", callbacks_header + callbacks_body + '''

__all__ = [
    "_extract_policy_entropy",
    "_notify_first_boot_ppo_progress",
    "_ppo_first_boot_progress_callback",
    "_ppo_heartbeat_callbacks",
]
''')

    # Thin façade: keep class + sb3 load; import helpers; re-export public symbols
    facade = '''from __future__ import annotations
# pyright: reportMissingImports=false

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
from typing import Any

import numpy as np

from lumina_core.first_boot_progress import resolve_ppo_progress_interval
from lumina_core.evolution.simulator_data_support import coerce_rl_training_bars
from lumina_core.logging_utils import (
    correlation_id,
    get_logger,
    record_model_load_time_monitoring,
    resolve_monitoring_state_dir,
    write_ppo_policy_metadata,
)
from lumina_core.ppo_callbacks import (
    _extract_policy_entropy,
    _notify_first_boot_ppo_progress,
    _ppo_first_boot_progress_callback,
    _ppo_heartbeat_callbacks,
)
from lumina_core.ppo_device import _resolve_ppo_device, _scale_timesteps_for_device
from lumina_core.ppo_evolution_logger import PPOEvolutionLogger
from lumina_core.rl import RLConfig, RLTradingEnvironment

logger = get_logger("lumina.rl.ppo")

# Public / test re-exports (behavior-preserving import surface).
__all__ = [
    "PPOTrainer",
    "_notify_first_boot_ppo_progress",
    "_resolve_ppo_device",
    "_scale_timesteps_for_device",
]


def _sb3_ppo_load(path: str | Path) -> Any | None:
    try:
        from stable_baselines3 import PPO

        return PPO.load(str(path))
    except Exception:
        logging.exception("Unhandled broad exception fallback in lumina_core/ppo_trainer.py:19")
        return None


'''
    # Class from L192 (blank before @dataclass) through end — use L192-747
    class_body = extract(lines, 192, 747)
    write(src, facade + class_body)


def split_data_ops() -> None:
    print("== stage_loop_data_ops ==")
    src = BIRTH / "stage_loop_data_ops.py"
    lines = lines_of(src)

    # Enrich: entropy / edgescore / exploration (L54-219) + swarm (L413-777)
    enrich_methods = extract(lines, 54, 219) + "\n" + extract(lines, 413, 777)
    enrich = '''"""StageLoopDataEnrichMixin — entropy, EdgeScore, exploration, swarm.

Part of StageLoopDataOpsMixin (Wave B PR-B4).
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from lumina_core.birth.birth_bus_serde import reward_config_to_dict
from lumina_core.birth.birth_control_plane import (
    should_force_swarm_retearnament,
    should_start_swarm_before_recovery,
    swarm_tournament_lift,
    tournament_score,
)
from lumina_core.birth.policy_swarm import (
    PolicySwarmState,
    build_swarm_variants,
    record_swarm_rollout,
    select_swarm_winner,
    swarm_rollout_target,
)
from lumina_core.birth.starship_birth import (
    edgescore_from_swarm_result,
    evaluate_stage1_edgescore,
    read_last_ppo_entropy,
    should_force_exploration_burst,
)
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_data_enrich")


class StageLoopDataEnrichMixin(StageLoopMixinBase):
    """Policy/signal enrichment for StageLoopSession."""

'''
    write(BIRTH / "stage_loop_data_enrich.py", enrich + enrich_methods)

    # Cache: pools / oracle / expand (L221-411)
    cache_methods = extract(lines, 221, 411)
    cache = '''"""StageLoopDataCacheMixin — intra pools, oracle harvest, data expansion.

Part of StageLoopDataOpsMixin (Wave B PR-B4).
"""
from __future__ import annotations

from typing import Any

from lumina_core.birth.curriculum import (
    CurriculumStage,
    filter_ticks_for_stage,
    split_stage1_trend_ticks,
    split_stage2_range_ticks,
)
from lumina_core.birth.data_expansion import (
    clamp_expansion_steps,
    expand_birth_data,
    expansion_ladder_at_max,
)
from lumina_core.birth.news_enricher import enrich_ticks_with_news
from lumina_core.birth.pattern_miner import mine_winning_patterns
from lumina_core.birth.stall_remediation import curate_buffer_top_quartile
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_data_cache")


class StageLoopDataCacheMixin(StageLoopMixinBase):
    """Tick-pool / buffer / expansion ops for StageLoopSession."""

'''
    write(BIRTH / "stage_loop_data_cache.py", cache + cache_methods)

    facade = '''"""StageLoopDataOpsMixin — StageLoopSession mixin.

Bounded modules: ``stage_loop_data_cache``, ``stage_loop_data_enrich`` (Wave B PR-B4).
"""
from __future__ import annotations

from lumina_core.birth.stage_loop_data_cache import StageLoopDataCacheMixin
from lumina_core.birth.stage_loop_data_enrich import StageLoopDataEnrichMixin
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase

__all__ = ["StageLoopDataOpsMixin"]


class StageLoopDataOpsMixin(
    StageLoopDataCacheMixin,
    StageLoopDataEnrichMixin,
    StageLoopMixinBase,
):
    """See StageLoopSession for attributes."""
'''
    write(src, facade)


def split_session() -> None:
    print("== stage_loop_session ==")
    src = BIRTH / "stage_loop_session.py"
    lines = lines_of(src)

    # run() method body is L100-740 inclusive
    run_method = extract(lines, 100, 740)

    runner = '''"""StageLoopSessionRunnerMixin — session.run() body (Wave B PR-B4).

Keeps StageLoopSession as composition root; heavy init/resume lives here.
"""
from __future__ import annotations

import time
from typing import Any

from lumina_core.birth.birth_bus_client import BirthBusClient
from lumina_core.birth.checkpoint import (
    apply_plateau_quarantine_on_checkpoint_resume,
    load_checkpoint_state,
)
from lumina_core.birth.curriculum import (
    CurriculumStage,
    Stage1IntraCurriculumState,
    Stage2IntraCurriculumState,
    stage1_intra_state_from_metrics,
    stage2_intra_state_from_metrics,
    stage_pass_trades,
)
from lumina_core.birth.meta_controller import MetaActionPlan
from lumina_core.birth.plateau_escalator import (
    EvolutionAction,
    enter_plateau,
    evolution_ladder_exhausted,
    is_valid_best_policy_snapshot,
    reset_plateau_for_new_cycle,
    sanitize_phantom_evolution_steps,
    sanitize_plateau_best_snapshot,
    sanitize_stuck_plateau_evolution,
    should_block_phoenix_no_lift,
    should_brake_recovery_no_lift,
    should_trades_beyond_gate_hard_stop,
)
from lumina_core.birth.policy_swarm import PolicySwarmState
from lumina_core.birth.progress import read_birth_progress
from lumina_core.birth.stage_scorecard import (
    learning_metric_target,
    pass_criteria_for_stage,
)
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_session_runner")

__all__ = ["StageLoopSessionRunnerMixin"]


class StageLoopSessionRunnerMixin:
    """Owns StageLoopSession.run(); see StageLoopSession for attributes."""

'''
    write(BIRTH / "stage_loop_session_runner.py", runner + run_method)

    # Thin session façade: imports for composition + __init__ + run_stage_research_loop
    # Keep stage1_winrate_pass_threshold if used in __init__ only — check
    facade = '''"""Stage loop session — composition root + StageLoopSession class.

Recovery/progress/plateau/meta/data-ops live in mixin modules.
run() body: ``stage_loop_session_runner`` (Wave B PR-B4).
"""
from __future__ import annotations

from typing import Any

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.plateau_evolution_handler import PlateauEvolutionMixin
from lumina_core.birth.stage_loop_data_ops import StageLoopDataOpsMixin
from lumina_core.birth.stage_loop_iteration import StageLoopIterationMixin
from lumina_core.birth.stage_loop_meta import StageLoopMetaMixin
from lumina_core.birth.stage_loop_progress import StageLoopProgressMixin
from lumina_core.birth.stage_loop_recovery_mixin import StageLoopRecoveryMixin
from lumina_core.birth.stage_loop_session_runner import StageLoopSessionRunnerMixin
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_session")


class StageLoopSession(
    PlateauEvolutionMixin,
    StageLoopRecoveryMixin,
    StageLoopProgressMixin,
    StageLoopMetaMixin,
    StageLoopDataOpsMixin,
    StageLoopIterationMixin,
    StageLoopSessionRunnerMixin,
):
    """Mutable stage-research session."""

'''
    init_method = extract(lines, 67, 98)
    entry = extract(lines, 742, 775)
    write(src, facade + init_method + "\n\n" + entry)


def main() -> None:
    split_ppo()
    split_data_ops()
    split_session()
    print("done")


if __name__ == "__main__":
    main()
