"""Wave B PR-B1 — engine / config / plateau_evolution façade splits."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIRTH = ROOT / "lumina_core" / "birth"


def lines_of(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines(keepends=True)


def extract(lines: list[str], start: int, end: int) -> str:
    return "".join(lines[start - 1 : end])


def write(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)} ({len(text.splitlines())} lines)")


def split_engine() -> None:
    print("== engine ==")
    src = BIRTH / "engine.py"
    lines = lines_of(src)

    # --- trajectory: dataclasses + tick/stall/provisional ---
    traj = '''"""Birth engine trajectory buffer, stall detection, provisional pass."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import (
    CurriculumStage,
    Stage1IntraCurriculumState,
    Stage2IntraCurriculumState,
    sample_intra_stage1_pool,
    sample_intra_stage2_pool,
    should_gen0_soft_pass,
)
from lumina_core.birth.meta_controller import StallDetectionResult
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.engine")


'''
    traj += extract(lines, 63, 98)
    traj += "\n\nclass EngineTrajectoryMixin:\n"
    traj += extract(lines, 789, 1003)
    write(BIRTH / "engine_trajectory.py", traj)

    # --- graduation ---
    grad = '''"""Birth engine stage graduation + pass-receipt integrity."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.checkpoint import (
    read_checkpoint_payload,
    write_checkpoint_payload,
)
from lumina_core.birth.curriculum import (
    CurriculumStage,
    is_runway_stage,
    ordered_runway_stages,
    ordered_stages,
)
from lumina_core.birth.graduation_result import GraduationResult
from lumina_core.birth.progress import (
    read_birth_progress,
    write_birth_progress,
)
from lumina_core.birth.stage_pass_receipt import (
    audit_curriculum_integrity,
    fresh_stage_metrics_for_stage,
    receipt_for_stage,
    verify_stage_pass_receipt,
)
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.engine")


class EngineGraduationMixin:
'''
    grad += extract(lines, 463, 620)
    write(BIRTH / "engine_graduation.py", grad)

    # --- lifecycle ---
    life = '''"""Birth engine lifecycle: wiring helpers, progress, checkpoint, certificate delegates."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.certificate_pipeline import BirthCertificatePipeline
from lumina_core.birth.checkpoint_coordinator import BirthCheckpointCoordinator
from lumina_core.birth.config import BirthCurriculumConfig, load_birth_v2_config
from lumina_core.birth.curriculum_orchestrator import CurriculumOrchestrator
from lumina_core.birth.data_pipeline import (
    BirthDataPipeline,
    generate_synthetic_ticks,
    train_hash,
)
from lumina_core.birth.progress_reporter import BirthProgressReporter
from lumina_core.birth.progress import (
    read_birth_progress,
    write_birth_progress,
)
from lumina_core.hardware_intelligence import HARDWARE_PROFILES
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.engine")


class EngineLifecycleMixin:
'''
    # Methods 191-461 (before graduation snapshot) + 622-727 (checkpoint/cert) + 759-787 paused + 1045-1085
    life += extract(lines, 191, 461)
    life += "\n"
    life += extract(lines, 622, 727)
    life += "\n"
    life += extract(lines, 759, 787)
    life += "\n"
    life += extract(lines, 1045, 1085)
    write(BIRTH / "engine_lifecycle.py", life)

    facade = '''"""Birth Phase v2 orchestrator (ADR-0012/0013/0014).

Composition root façade — lifecycle / trajectory / graduation helpers live in
``engine_lifecycle``, ``engine_trajectory``, ``engine_graduation``.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from lumina_core.birth.birth_constitution_guard import BirthConstitutionGuard
from lumina_core.birth.birth_bus_client import BirthBusClient
from lumina_core.birth.birth_handler_registry import BirthHandlerRegistry
from lumina_core.birth.config import load_birth_v2_config
from lumina_core.birth.constitution_enforcer import ConstitutionEnforcer
from lumina_core.birth.curriculum_orchestrator import CurriculumOrchestrator
from lumina_core.birth.curriculum_stage_handler import create_and_attach_stage_handler
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.engine_graduation import EngineGraduationMixin
from lumina_core.birth.engine_lifecycle import EngineLifecycleMixin
from lumina_core.birth.engine_trajectory import (  # noqa: F401
    EngineTrajectoryMixin,
    ProvisionalPassDecision,
    TrajectoryBuffer,
)
from lumina_core.birth.stage_pass_receipt import StagePassReceipt
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.engine")

__all__ = [
    "BirthPhaseEngineV2",
    "ProvisionalPassDecision",
    "TrajectoryBuffer",
]


class BirthPhaseEngineV2(
    EngineLifecycleMixin,
    EngineGraduationMixin,
    EngineTrajectoryMixin,
):
'''
    # Keep __init__ (101-189) and public orchestration methods
    facade += extract(lines, 101, 189)
    facade += "\n"
    facade += extract(lines, 730, 757)
    facade += "\n"
    facade += extract(lines, 1005, 1041)
    write(src, facade)


def split_config() -> None:
    print("== config ==")
    src = BIRTH / "config.py"
    lines = lines_of(src)

    curr = '''"""Birth v2 curriculum / news / reward / root config dataclasses."""
from __future__ import annotations

from dataclasses import dataclass, field

from lumina_core.birth.birth_certificate import BirthCertificateThresholds

BRO_ENGINE_VERSION = "BRO-v2"


'''
    curr += extract(lines, 19, 260)
    write(BIRTH / "config_curriculum.py", curr)

    coer = '''"""Birth v2 config coercion + section builders."""
from __future__ import annotations

import logging
from typing import Any

from lumina_core.birth.birth_certificate import BirthCertificateThresholds
from lumina_core.birth.config_curriculum import (
    BirthCurriculumConfig,
    BirthNewsConfig,
    BirthRewardConfig,
)

logger = logging.getLogger("lumina.birth.config")


'''
    coer += extract(lines, 263, 331)
    coer += "\n\n"
    # Extract curriculum/news/reward construction from load_birth_v2_config body
    # Lines 364-849 are the BirthCurriculumConfig(...) / news / reward builders
    coer += '''def build_curriculum_config(cur_raw: dict[str, Any]) -> BirthCurriculumConfig:
    return BirthCurriculumConfig(
'''
    # The kwargs start at line 365 (after BirthCurriculumConfig() ) through 822
    # Line 364 is `curriculum = BirthCurriculumConfig(`
    # Line 365-821 are kwargs, line 822 is `)`
    kwargs_block = extract(lines, 365, 821)
    # These lines are indented with 8 spaces inside load; keep as function body (4 spaces relative to return)
    # Currently 8-space indent for kwargs; under `return BirthCurriculumConfig(` we want 8 spaces still
    coer += kwargs_block
    coer += "    )\n\n\n"
    coer += '''def build_news_config(news_raw: dict[str, Any]) -> BirthNewsConfig:
    return BirthNewsConfig(
'''
    coer += extract(lines, 825, 827)
    coer += "    )\n\n\n"
    coer += '''def build_reward_config(reward_raw: dict[str, Any]) -> BirthRewardConfig:
    return BirthRewardConfig(
'''
    coer += extract(lines, 831, 848)
    coer += "    )\n\n\n"
    coer += '''def build_certificate_thresholds(thr_raw: dict[str, Any]) -> BirthCertificateThresholds:
    try:
        return BirthCertificateThresholds.model_validate(thr_raw or {})
    except Exception:
        return BirthCertificateThresholds()
'''
    write(BIRTH / "config_coercion.py", coer)

    facade = '''"""Birth v2 configuration loader.

Bounded modules: ``config_curriculum`` (dataclasses), ``config_coercion`` (parse helpers).
Public imports remain stable via this façade.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from lumina_core.birth.config_coercion import (  # noqa: F401
    _coerce_float,
    _coerce_int,
    _coerce_wall_behavior,
    _parse_expansion_steps,
    build_certificate_thresholds,
    build_curriculum_config,
    build_news_config,
    build_reward_config,
    resolve_effective_trade_budget,
    resolve_trade_budget_cap,
)
from lumina_core.birth.config_curriculum import (  # noqa: F401
    BRO_ENGINE_VERSION,
    BirthCurriculumConfig,
    BirthNewsConfig,
    BirthRewardConfig,
    BirthV2Config,
)

logger = logging.getLogger("lumina.birth.config")

__all__ = [
    "BRO_ENGINE_VERSION",
    "BirthCurriculumConfig",
    "BirthNewsConfig",
    "BirthRewardConfig",
    "BirthV2Config",
    "load_birth_v2_config",
    "resolve_effective_trade_budget",
    "resolve_trade_budget_cap",
]


def load_birth_v2_config(workspace_root: Path | str | None = None) -> BirthV2Config:
    root = Path(workspace_root or Path.cwd())
    cfg_path = root / "config.yaml"
    raw: dict[str, Any] = {}
    if cfg_path.is_file():
        try:
            loaded = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                raw = loaded
        except Exception as exc:
            logger.warning("birth_v2.config_load_failed detail=%s", exc)

    section = raw.get("birth_v2")
    if not isinstance(section, dict):
        section = {}
        fb = raw.get("first_boot")
        if isinstance(fb, dict):
            logger.warning("birth_v2: using deprecated first_boot keys; migrate to birth_v2 in config.yaml")
            section = {
                "prefer_real_data_only": fb.get("prefer_real_data_only", True),
                "max_real_days": fb.get("max_real_days", 90),
                "trade_budget_cap": fb.get("training_trades", 10_000),
                "ppo_update_timesteps": fb.get("ppo_update_timesteps", 25_000),
            }

    cur_raw = section.get("curriculum") if isinstance(section.get("curriculum"), dict) else {}
    news_raw = section.get("news") if isinstance(section.get("news"), dict) else {}
    reward_raw = section.get("reward") if isinstance(section.get("reward"), dict) else {}
    thr_raw = section.get("certificate_thresholds") if isinstance(section.get("certificate_thresholds"), dict) else {}

    curriculum = build_curriculum_config(cur_raw if isinstance(cur_raw, dict) else {})
    news = build_news_config(news_raw if isinstance(news_raw, dict) else {})
    reward = build_reward_config(reward_raw if isinstance(reward_raw, dict) else {})
    thresholds = build_certificate_thresholds(thr_raw if isinstance(thr_raw, dict) else {})

    trade_budget_cap, budget_source = resolve_trade_budget_cap(raw)
    logger.info("birth.budget cap=%s source=%s", trade_budget_cap, budget_source)

    return BirthV2Config(
        curriculum=curriculum,
        news=news,
        reward=reward,
        holdout_pct=max(0.05, min(0.4, _coerce_float(section.get("holdout_pct"), 0.20))),
        certificate_thresholds=thresholds,
        prefer_real_data_only=bool(section.get("prefer_real_data_only", True)),
        max_real_days=max(30, min(3650, _coerce_int(section.get("max_real_days"), 90))),
        ppo_update_timesteps=max(1000, _coerce_int(section.get("ppo_update_timesteps"), 25_000)),
        chunk_size=max(2500, _coerce_int(section.get("chunk_size"), 50_000)),
        trade_budget_cap=trade_budget_cap,
    )
'''
    write(src, facade)


def split_plateau_evolution() -> None:
    print("== plateau_evolution_handler ==")
    src = BIRTH / "plateau_evolution_handler.py"
    lines = lines_of(src)

    actions = '''"""Plateau evolution action application + phoenix reset bodies."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.plateau_escalator import (
    EvolutionAction,
    is_valid_best_policy_snapshot,
)
from lumina_core.birth.stall_remediation import curate_buffer_top_quartile
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_mixin")


class PlateauEvolutionActionsMixin(StageLoopMixinBase):
'''
    actions += extract(lines, 74, 193)
    actions += "\n"
    actions += extract(lines, 654, 684)
    write(BIRTH / "plateau_evolution_actions.py", actions)

    loop = '''"""Plateau evolution step finalize / advance / detect / terminal helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.plateau_escalator import (
    TERMINAL_STALL_REASON,
    EvolutionAction,
    PlateauEnterContext,
    begin_evolution_step,
    evolution_ladder_exhausted,
    is_plateau_quarantine_blocking,
    maybe_update_best_winrate,
    record_evolution_outcome,
    revert_evolution_step_on_noop,
    sanitize_plateau_best_snapshot,
    should_force_advance_evolution_step,
    should_terminal_plateau_stall,
    should_trigger_plateau_evolution_step,
)
from lumina_core.birth.stage_scorecard import (
    calculate_simple_slope,
    compute_stage_blocker,
    learning_metric_target,
)
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_mixin")


class PlateauEvolutionLoopMixin(StageLoopMixinBase):
'''
    # finalize through try_plateau_evolution + save best + meta + effective max
    loop += extract(lines, 195, 602)
    loop += "\n"
    loop += extract(lines, 604, 652)
    loop += "\n"
    loop += extract(lines, 686, 700)
    write(BIRTH / "plateau_evolution_loop.py", loop)

    facade = '''"""PlateauEvolutionMixin — StageLoopSession mixin.

Bounded modules: ``plateau_evolution_actions``, ``plateau_evolution_loop``.
Dispatches over ``plateau_evolution_ladder`` / ``plateau_escalator``.
"""
from __future__ import annotations

from typing import Any

from lumina_core.birth.plateau_escalator import (
    EvolutionAction,  # noqa: F401
    rolling_winrate_last_n_trades,
)
from lumina_core.birth.plateau_evolution_actions import PlateauEvolutionActionsMixin
from lumina_core.birth.plateau_evolution_loop import PlateauEvolutionLoopMixin
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_mixin")


class PlateauEvolutionMixin(
    PlateauEvolutionActionsMixin,
    PlateauEvolutionLoopMixin,
    StageLoopMixinBase,
):
    """See StageLoopSession for attributes."""

    def _rolling_winrate_500(self) -> float:
        chunks = getattr(self, "rolling_trade_chunks", None)
        result = rolling_winrate_last_n_trades(
            stage_trades=self.stage_trades,
            stage_wins=self.stage_wins,
            wins_at_trade=getattr(self, "wins_at_trade_milestones", {}) or {},
            chunks=chunks if isinstance(chunks, list) else None,
            return_meta=True,
        )
        if isinstance(result, tuple):
            wr, source, covered = result
            self._rolling_winrate_source = str(source)
            self._rolling_window_trades_covered = int(covered)
            return float(wr)
        return float(result)

    def _rolling_winrate_meta(self) -> tuple[float, str, int]:
        chunks = getattr(self, "rolling_trade_chunks", None)
        result = rolling_winrate_last_n_trades(
            stage_trades=self.stage_trades,
            stage_wins=self.stage_wins,
            wins_at_trade=getattr(self, "wins_at_trade_milestones", {}) or {},
            chunks=chunks if isinstance(chunks, list) else None,
            return_meta=True,
        )
        if isinstance(result, tuple):
            return float(result[0]), str(result[1]), int(result[2])
        return float(result), "lifetime_fallback", 0

    def _ppo_steps_since_evolution_step(self) -> int:
        return max(0, int(self.host.ppo_steps) - int(self.ppo_steps_at_plateau_evolution_step))


__all__ = ["PlateauEvolutionMixin"]
'''
    write(src, facade)


def main() -> None:
    split_engine()
    split_config()
    split_plateau_evolution()
    print("done")


if __name__ == "__main__":
    main()
