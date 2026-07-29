"""Wave B PR-B0 — behavior-preserving LOC splits with thin façades."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIRTH = ROOT / "lumina_core" / "birth"
EVO = ROOT / "lumina_core" / "evolution"


def lines_of(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines(keepends=True)


def extract(lines: list[str], start: int, end: int) -> str:
    return "".join(lines[start - 1 : end])


def write(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)} ({len(text.splitlines())} lines)")


def split_certificate() -> None:
    print("== certificate_pipeline ==")
    src = BIRTH / "certificate_pipeline.py"
    lines = lines_of(src)

    # Methods run_stage8 (138-297) and complete (299-431) → module functions
    polish_body = extract(lines, 149, 297)  # docstring + body without def line
    complete_body = extract(lines, 307, 431)

    evaluate = '''"""Certificate S8 polish + certified-birth completion helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from lumina_core.birth.birth_certificate import (
    build_certificate_from_eval,
    certificate_path,
    write_certificate,
)
from lumina_core.birth.buffer_persist import clear_buffer
from lumina_core.birth.checkpoint import clear_checkpoint
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.certificate_evaluator import evaluate_holdout_certificate
from lumina_core.birth.dna_handoff import register_birth_gen0_dna
from lumina_core.birth.bible_meta import update_bible_after_birth
from lumina_core.birth.progress import write_birth_progress
from lumina_core.birth.stage_scorecard import build_scorecard_payload
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.certificate_evaluate")


def run_stage8_polish_and_certificate(
    pipeline: Any,
    *,
    split: Any,
    training_mode: str,
    ppo_steps_per_update: int,
    trade_budget_cap: int,
    prefer_real: bool,
    start_price: float,
) -> dict[str, Any]:
'''
    # Indent body was method-indented (8 spaces); convert to function body (4 spaces)
    polish_fn_body = _dedent_method(polish_body, from_indent=8)
    # Replace self. with pipeline. for method calls that stay on pipeline
    polish_fn_body = polish_fn_body.replace("self._host", "pipeline._host")
    polish_fn_body = polish_fn_body.replace("self.fail_certificate", "pipeline.fail_certificate")
    polish_fn_body = polish_fn_body.replace("self.run_certificate_remediation", "pipeline.run_certificate_remediation")
    polish_fn_body = polish_fn_body.replace("self.complete_certified_birth", "pipeline.complete_certified_birth")

    evaluate += polish_fn_body
    evaluate += '''


def complete_certified_birth(
    pipeline: Any,
    *,
    split: Any,
    eval_result: dict[str, Any],
    training_mode: str,
    trade_budget_cap: int,
) -> dict[str, Any]:
'''
    complete_fn_body = _dedent_method(complete_body, from_indent=8)
    complete_fn_body = complete_fn_body.replace("self._host", "pipeline._host")
    complete_fn_body = complete_fn_body.replace("self.resolve_birth_exit_winrate", "pipeline.resolve_birth_exit_winrate")
    evaluate += complete_fn_body

    write(BIRTH / "certificate_evaluate.py", evaluate)

    facade = '''"""Birth certificate preflight, runway, remediation, and completion pipeline.

Bounded modules: ``certificate_preflight``, ``certificate_remediation``,
``certificate_runway``, ``certificate_evaluate``. Host class keeps thin delegates.
"""
from __future__ import annotations

from typing import Any

from lumina_core.birth.certificate_evaluator import evaluate_holdout_certificate  # noqa: F401
from lumina_core.birth.data_expansion import clamp_expansion_steps, expand_birth_data  # noqa: F401
from lumina_core.birth.news_enricher import enrich_ticks_with_news  # noqa: F401
from lumina_core.birth.preflight import assess_split_preflight, data_manifest_from_split  # noqa: F401
from lumina_core.birth.runway import micro_oos_sanity_passed  # noqa: F401
from lumina_core.birth.sim_runner import run_policy_rollout  # noqa: F401
from lumina_core.birth import certificate_evaluate as _evaluate
from lumina_core.birth import certificate_preflight as _preflight
from lumina_core.birth import certificate_remediation as _remediation
from lumina_core.birth import certificate_runway as _runway
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.certificate_pipeline")


class BirthCertificatePipeline:
    def __init__(self, host: Any) -> None:
        self._host = host

    def ensure_holdout_preflight(
        self,
        *,
        ticks: list[dict[str, Any]],
        split: Any,
        max_days: int,
        prefer_real: bool,
        start_price: float,
        training_mode: str,
        reuse_manifest: bool = False,
        saved_manifest: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], Any, dict[str, Any]] | dict[str, Any]:
        return _preflight.ensure_holdout_preflight(
            self,
            ticks=ticks,
            split=split,
            max_days=max_days,
            prefer_real=prefer_real,
            start_price=start_price,
            training_mode=training_mode,
            reuse_manifest=reuse_manifest,
            saved_manifest=saved_manifest,
        )

    def run_certificate_remediation(
        self,
        *,
        split: Any,
        eval_result: dict[str, Any],
        training_mode: str,
        ppo_steps_per_update: int,
        trade_budget_cap: int,
        prefer_real: bool,
        start_price: float,
    ) -> dict[str, Any]:
        return _remediation.run_certificate_remediation(
            self,
            split=split,
            eval_result=eval_result,
            training_mode=training_mode,
            ppo_steps_per_update=ppo_steps_per_update,
            trade_budget_cap=trade_budget_cap,
            prefer_real=prefer_real,
            start_price=start_price,
        )

    def resolve_birth_exit_winrate(self) -> float:
        return _runway.resolve_birth_exit_winrate(self)

    def resolve_baseline_oos_winrate(self, *, checkpoint_state: dict[str, Any] | None = None) -> float:
        return _runway.resolve_baseline_oos_winrate(self, checkpoint_state=checkpoint_state)

    def bootstrap_runway_stage5(self, *, train_ticks: list[dict[str, Any]]) -> None:
        return _runway.bootstrap_runway_stage5(self, train_ticks=train_ticks)

    def run_certificate_runway_stages(
        self,
        *,
        split: Any,
        validation_ticks: list[dict[str, Any]],
        train_core_ticks: list[dict[str, Any]],
        training_mode: str,
        ppo_steps_per_update: int,
        trade_budget_cap: int,
        prefer_real: bool,
        start_price: float,
        baseline_oos_winrate: float,
        birth_exit_winrate: float,
    ) -> dict[str, Any] | None:
        return _runway.run_certificate_runway_stages(
            self,
            split=split,
            validation_ticks=validation_ticks,
            train_core_ticks=train_core_ticks,
            training_mode=training_mode,
            ppo_steps_per_update=ppo_steps_per_update,
            trade_budget_cap=trade_budget_cap,
            prefer_real=prefer_real,
            start_price=start_price,
            baseline_oos_winrate=baseline_oos_winrate,
            birth_exit_winrate=birth_exit_winrate,
        )

    def fail_certificate_with_runway_checkpoint(
        self,
        *,
        eval_result: dict[str, Any],
        training_mode: str,
        trade_budget_cap: int,
    ) -> dict[str, Any]:
        return _runway.fail_certificate_with_runway_checkpoint(
            self,
            eval_result=eval_result,
            training_mode=training_mode,
            trade_budget_cap=trade_budget_cap,
        )

    def run_stage8_polish_and_certificate(
        self,
        *,
        split: Any,
        training_mode: str,
        ppo_steps_per_update: int,
        trade_budget_cap: int,
        prefer_real: bool,
        start_price: float,
    ) -> dict[str, Any]:
        return _evaluate.run_stage8_polish_and_certificate(
            self,
            split=split,
            training_mode=training_mode,
            ppo_steps_per_update=ppo_steps_per_update,
            trade_budget_cap=trade_budget_cap,
            prefer_real=prefer_real,
            start_price=start_price,
        )

    def complete_certified_birth(
        self,
        *,
        split: Any,
        eval_result: dict[str, Any],
        training_mode: str,
        trade_budget_cap: int,
    ) -> dict[str, Any]:
        return _evaluate.complete_certified_birth(
            self,
            split=split,
            eval_result=eval_result,
            training_mode=training_mode,
            trade_budget_cap=trade_budget_cap,
        )
'''
    write(src, facade)


def _dedent_method(body: str, *, from_indent: int) -> str:
    """Strip method indentation; keep relative structure."""
    prefix = " " * from_indent
    out: list[str] = []
    for line in body.splitlines(keepends=True):
        if line.startswith(prefix):
            out.append("    " + line[from_indent:])
        elif line.strip() == "":
            out.append("\n" if line.endswith("\n") else "")
        else:
            out.append(line)
    return "".join(out)


def split_starship_edgescore() -> None:
    print("== starship_edgescore ==")
    src = BIRTH / "starship_edgescore.py"
    lines = lines_of(src)

    # Shared core used by stages + champion (types, rolling, expectancy, entropy)
    core = '''"""Starship EdgeScore shared types, rolling hygiene, expectancy, entropy."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.starship_edgescore")


'''
    # EdgeScoreResult through hygiene_wr_telemetry (18-98), expectancy (219-239), entropy (512-567)
    core += extract(lines, 18, 98)
    core += "\n"
    core += extract(lines, 219, 239)
    core += "\n"
    core += extract(lines, 512, 567)
    write(BIRTH / "starship_edgescore_core.py", core)

    champion = '''"""Starship EdgeScore champion eligibility + poison sanitize + humanize."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.starship_edgescore_core import (
    EdgeScoreResult,
    compute_expectancy_proxy,
    rolling_pass_min_covered,
)
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.starship_edgescore")


'''
    champion += extract(lines, 101, 216)
    write(BIRTH / "starship_edgescore_champion.py", champion)

    stage1 = '''"""Starship Stage-1 EdgeScore evaluator."""
from __future__ import annotations

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.starship_edgescore_core import (
    EdgeScoreResult,
    compute_expectancy_proxy,
)


'''
    stage1 += extract(lines, 242, 344)
    write(BIRTH / "starship_edgescore_stage1.py", stage1)

    stage2 = '''"""Starship Stage-2 EdgeScore evaluator."""
from __future__ import annotations

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.starship_edgescore_core import (
    EdgeScoreResult,
    compute_expectancy_proxy,
)


'''
    stage2 += extract(lines, 347, 421)
    write(BIRTH / "starship_edgescore_stage2.py", stage2)

    stage3 = '''"""Starship Stage-3 EdgeScore evaluator."""
from __future__ import annotations

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.starship_edgescore_core import (
    EdgeScoreResult,
    compute_expectancy_proxy,
)


'''
    stage3 += extract(lines, 424, 509)
    write(BIRTH / "starship_edgescore_stage3.py", stage3)

    facade = '''"""Starship Birth EdgeScore + entropy life-support helpers.

Canonical re-export: ``lumina_core.birth.starship_birth``.

Bounded modules: ``starship_edgescore_core``, ``starship_edgescore_champion``,
``starship_edgescore_stage1``, ``starship_edgescore_stage2``, ``starship_edgescore_stage3``.
"""
from __future__ import annotations

from lumina_core.birth.starship_edgescore_champion import (  # noqa: F401
    edgescore_champion_min_trades,
    humanize_edgescore_blocker,
    is_edgescore_champion_eligible,
    sanitize_edgescore_champion,
)
from lumina_core.birth.starship_edgescore_core import (  # noqa: F401
    EdgeScoreResult,
    compute_expectancy_proxy,
    gate_rolling_winrate,
    hygiene_wr_telemetry,
    policy_entropy_alive,
    read_last_ppo_entropy,
    rolling_pass_min_covered,
    rolling_wr_pass_eligible,
    should_force_exploration_burst,
)
from lumina_core.birth.starship_edgescore_stage1 import evaluate_stage1_edgescore  # noqa: F401
from lumina_core.birth.starship_edgescore_stage2 import evaluate_stage2_edgescore  # noqa: F401
from lumina_core.birth.starship_edgescore_stage3 import evaluate_stage3_edgescore  # noqa: F401

__all__ = [
    "EdgeScoreResult",
    "compute_expectancy_proxy",
    "edgescore_champion_min_trades",
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
    "should_force_exploration_burst",
]
'''
    write(src, facade)


def split_plateau_terminal() -> None:
    print("== plateau_terminal ==")
    src = BIRTH / "plateau_terminal.py"
    lines = lines_of(src)

    # Shared constants + early brake helpers used by both
    # Ladder: revert, start/advance/force/trigger, sanitize, blocked_reason, record, maybe_update, increment, winrate_improvement
    # Traps: brake/phoenix/terminal/recovery/remediation/elapsed/forced/traps/adaptation

    traps = '''"""Plateau terminal stall, recovery brake, phoenix, and trap detectors."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.plateau_enter import should_trades_beyond_gate_hard_stop
from lumina_core.birth.plateau_evolution_ladder import evolution_ladder_exhausted
from lumina_core.logging_utils import get_logger

if TYPE_CHECKING:
    from lumina_core.birth.plateau_escalator import PlateauState

logger = get_logger("lumina.birth.plateau_terminal")

TERMINAL_STALL_REASON = "plateau_evolution_exhausted"

_NO_LIFT_EPS = 1e-9


'''
    # Lines 28-170: revert through record_forced_recovery / should_start is ladder — take 28-172 carefully
    # 28-32 revert → ladder
    # 34-56 brake/phoenix block → traps
    # 58-61 elapsed → traps
    # 64-79 remediation → traps
    # 82-113 should_block_plateau_recovery → traps
    # 116-161 should_terminal → traps
    # 164-171 force never stop → traps
    # 174-175 should_start → ladder
    traps += extract(lines, 34, 171)
    traps += "\n"
    # traps detectors + phoenix + adaptation (439-489)
    traps += extract(lines, 439, 489)
    write(BIRTH / "plateau_terminal_traps.py", traps)

    ladder = '''"""Plateau evolution ladder advance, sanitize, and outcome helpers."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import stage1_winrate_pass_threshold
from lumina_core.birth.plateau_enter import should_trades_beyond_gate_hard_stop
from lumina_core.birth.plateau_evolution_ladder import (
    EVOLUTION_STEP_ACTIONS,
    EvolutionAction,
    evolution_ladder_exhausted,
)
from lumina_core.birth.plateau_terminal_traps import should_block_plateau_recovery
from lumina_core.logging_utils import get_logger

if TYPE_CHECKING:
    from lumina_core.birth.plateau_escalator import PlateauState

logger = get_logger("lumina.birth.plateau_terminal")

_PLATEAU_GAP_PROGRESS_MIN = 0.25


'''
    ladder += extract(lines, 28, 32)
    ladder += "\n"
    ladder += extract(lines, 174, 437)
    ladder += "\n"
    ladder += extract(lines, 492, 562)
    write(BIRTH / "plateau_terminal_ladder.py", ladder)

    facade = '''"""Plateau terminal stall, evolution advance, and recovery brake helpers.

Bounded modules: ``plateau_terminal_ladder``, ``plateau_terminal_traps``.
"""
from __future__ import annotations

from lumina_core.birth.plateau_terminal_ladder import (  # noqa: F401
    evolution_ladder_blocked_reason,
    increment_evolution_rollout,
    maybe_update_best_winrate,
    record_evolution_outcome,
    revert_evolution_step_on_noop,
    sanitize_phantom_evolution_steps,
    sanitize_stuck_plateau_evolution,
    should_advance_evolution_step,
    should_force_advance_evolution_step,
    should_start_evolution_step,
    should_trigger_plateau_evolution_step,
    winrate_improvement_blocks_ladder,
)
from lumina_core.birth.plateau_terminal_traps import (  # noqa: F401
    TERMINAL_STALL_REASON,
    adaptation_stuck_escape_allowed,
    can_force_never_stop_recovery,
    detect_hold_trap,
    detect_over_trading_trap,
    plateau_elapsed_sec,
    record_forced_recovery,
    remediation_is_exhausted,
    should_block_phoenix_no_lift,
    should_block_plateau_recovery,
    should_brake_recovery_no_lift,
    should_phoenix_reset,
    should_terminal_plateau_stall,
)

__all__ = [
    "TERMINAL_STALL_REASON",
    "adaptation_stuck_escape_allowed",
    "can_force_never_stop_recovery",
    "detect_hold_trap",
    "detect_over_trading_trap",
    "evolution_ladder_blocked_reason",
    "increment_evolution_rollout",
    "maybe_update_best_winrate",
    "plateau_elapsed_sec",
    "record_evolution_outcome",
    "record_forced_recovery",
    "remediation_is_exhausted",
    "revert_evolution_step_on_noop",
    "sanitize_phantom_evolution_steps",
    "sanitize_stuck_plateau_evolution",
    "should_advance_evolution_step",
    "should_block_phoenix_no_lift",
    "should_block_plateau_recovery",
    "should_brake_recovery_no_lift",
    "should_force_advance_evolution_step",
    "should_phoenix_reset",
    "should_start_evolution_step",
    "should_terminal_plateau_stall",
    "should_trigger_plateau_evolution_step",
    "winrate_improvement_blocks_ladder",
]
'''
    write(src, facade)


def split_approval_twin() -> None:
    print("== approval_twin bus/evaluators ==")
    bus_src = EVO / "approval_twin_bus.py"
    bus_lines = lines_of(bus_src)

    # Observe/bind: lines 25-313 (topics + methods through _record_observation)
    # Publish: 315-436 + observation_metrics 438-457

    observe = '''"""Approval Twin EventBus bind + shadow observation helpers."""
from __future__ import annotations

from typing import Any

from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus
from lumina_core.evolution.approval_twin_patch_bridge import twin_attr
from lumina_core.logging_utils import (
    get_logger,
    record_shadow_twin_alignment_monitoring,
)

logger = get_logger("lumina.evolution.twin")

# Topics Twin subscribes to for non-blocking shadow observation (ADR-0001 / 0031 finish).
_TWIN_SUBSCRIBE_TOPICS: tuple[str, ...] = (
    "evolution.shadow.verdict",
    "evolution.promotion.decision",
    "evolution.proposal.created",
    "safety.constitution.audit",
    "safety.constitution.violation",
    "risk.policy.decision",
)


class ApprovalTwinBusObserveMixin:
'''
    # Methods from bind through _record_observation (37-313), dedent class body stays
    observe_body = extract(bus_lines, 37, 313)
    observe += observe_body
    write(EVO / "approval_twin_bus_observe.py", observe)

    publish = '''"""Approval Twin EventBus publish helpers + observation metrics."""
from __future__ import annotations

from typing import Any

from lumina_core.agent_orchestration.schemas import (
    TwinDecisionEvent,
    TwinModePromotionEvent,
    TwinShadowObservationEvent,
    TwinTrainingUpdateEvent,
)
from lumina_core.evolution.twin_mode_promotion_gate import apply_mode_authority
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.evolution.twin")


class ApprovalTwinBusPublishMixin:
'''
    publish += extract(bus_lines, 315, 457)
    write(EVO / "approval_twin_bus_publish.py", publish)

    bus_facade = '''"""Approval Twin EventBus bind / observe / publish helpers.

Bounded modules: ``approval_twin_bus_observe``, ``approval_twin_bus_publish``.
"""
from __future__ import annotations

from lumina_core.evolution.approval_twin_bus_observe import (  # noqa: F401
    ApprovalTwinBusObserveMixin,
    _TWIN_SUBSCRIBE_TOPICS,
)
from lumina_core.evolution.approval_twin_bus_publish import ApprovalTwinBusPublishMixin  # noqa: F401


class ApprovalTwinBusMixin(ApprovalTwinBusObserveMixin, ApprovalTwinBusPublishMixin):
    """Combined bus surface kept for ApprovalTwinAgent MRO."""


__all__ = [
    "ApprovalTwinBusMixin",
    "ApprovalTwinBusObserveMixin",
    "ApprovalTwinBusPublishMixin",
    "_TWIN_SUBSCRIBE_TOPICS",
]
'''
    write(bus_src, bus_facade)

    # Evaluators: dna (31-225), code (227-311), backend (313-337), shadow (339-448)
    ev_src = EVO / "approval_twin_evaluators.py"
    ev_lines = lines_of(ev_src)

    dna = '''"""Approval Twin DNA promotion evaluation."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.evolution.approval_twin_patch_bridge import twin_attr
from lumina_core.evolution.dna_registry import PolicyDNA
from lumina_core.logging_utils import (
    classify_twin_decision_outcome,
    correlation_id,
    get_logger,
    log_twin_decision,
    record_twin_decision_monitoring,
)

logger = get_logger("lumina.evolution.twin")


class ApprovalTwinDnaEvaluatorMixin:
'''
    dna += extract(ev_lines, 31, 225)
    write(EVO / "approval_twin_eval_dna.py", dna)

    code = '''"""Approval Twin code-proposal evaluation."""
from __future__ import annotations

import json
from typing import Any

from lumina_core.logging_utils import correlation_id, get_logger

logger = get_logger("lumina.evolution.twin")


class ApprovalTwinCodeEvaluatorMixin:
'''
    code += extract(ev_lines, 227, 311)
    write(EVO / "approval_twin_eval_code.py", code)

    shadow = '''"""Approval Twin shadow promotion evaluation + backend builder."""
from __future__ import annotations

from typing import Any

from lumina_core.config_loader import ConfigLoader
from lumina_core.evolution.approval_twin_backends import (
    ApprovalTwinBackend,
    LocalHeuristicBackend,
    OllamaTwinBackend,
)
from lumina_core.evolution.approval_twin_patch_bridge import twin_attr
from lumina_core.evolution.dna_registry import PolicyDNA
from lumina_core.logging_utils import (
    correlation_id,
    get_logger,
    record_shadow_twin_alignment_monitoring,
)

logger = get_logger("lumina.evolution.twin")


class ApprovalTwinShadowEvaluatorMixin:
'''
    shadow += extract(ev_lines, 313, 448)
    write(EVO / "approval_twin_eval_shadow.py", shadow)

    ev_facade = '''"""Approval Twin DNA / code / shadow evaluation helpers.

Bounded modules: ``approval_twin_eval_dna``, ``approval_twin_eval_code``,
``approval_twin_eval_shadow``.
"""
from __future__ import annotations

from lumina_core.evolution.approval_twin_eval_code import ApprovalTwinCodeEvaluatorMixin  # noqa: F401
from lumina_core.evolution.approval_twin_eval_dna import ApprovalTwinDnaEvaluatorMixin  # noqa: F401
from lumina_core.evolution.approval_twin_eval_shadow import ApprovalTwinShadowEvaluatorMixin  # noqa: F401


class ApprovalTwinEvaluatorsMixin(
    ApprovalTwinDnaEvaluatorMixin,
    ApprovalTwinCodeEvaluatorMixin,
    ApprovalTwinShadowEvaluatorMixin,
):
    """Combined evaluator surface kept for ApprovalTwinAgent MRO."""


__all__ = [
    "ApprovalTwinCodeEvaluatorMixin",
    "ApprovalTwinDnaEvaluatorMixin",
    "ApprovalTwinEvaluatorsMixin",
    "ApprovalTwinShadowEvaluatorMixin",
]
'''
    write(ev_src, ev_facade)


def main() -> None:
    split_certificate()
    split_starship_edgescore()
    split_plateau_terminal()
    split_approval_twin()
    print("done")


if __name__ == "__main__":
    main()
