"""Wave A PR4.1 — split plateau_escalator into bounded modules + thin façade."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIRTH = ROOT / "lumina_core" / "birth"
SRC = BIRTH / "plateau_escalator.py"


def extract(lines: list[str], start: int, end: int) -> str:
    """1-based inclusive line extract."""
    return "".join(lines[start - 1 : end])


def main() -> None:
    lines = SRC.read_text(encoding="utf-8").splitlines(keepends=True)

    # --- plateau_rolling.py (lines 231-377) ---
    rolling = '''"""Rolling winrate helpers for birth plateau detection (Raptor v13)."""
from __future__ import annotations


'''
    rolling += extract(lines, 231, 377)
    (BIRTH / "plateau_rolling.py").write_text(rolling.rstrip() + "\n", encoding="utf-8")

    # --- plateau_enter.py ---
    enter = '''"""Plateau entry, quarantine, and trades-beyond-gate helpers."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage, stage_trade_target
from lumina_core.logging_utils import get_logger

if TYPE_CHECKING:
    from lumina_core.birth.plateau_escalator import PlateauState

logger = get_logger("lumina.birth.plateau_enter")


'''
    # gate helpers 107-125, PlateauEnterContext 128-142, min trades + quarantine 145-228,
    # skill/enter/sanitize 433-541, enter/reset 547-586
    enter += extract(lines, 107, 125)
    enter += "\n"
    enter += extract(lines, 128, 228)
    enter += "\n"
    enter += extract(lines, 433, 541)
    enter += "\n"
    enter += extract(lines, 547, 586)
    (BIRTH / "plateau_enter.py").write_text(enter.rstrip() + "\n", encoding="utf-8")

    # --- plateau_terminal.py ---
    terminal = '''"""Plateau terminal stall, evolution advance, and recovery brake helpers."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import stage1_winrate_pass_threshold
from lumina_core.birth.plateau_enter import should_trades_beyond_gate_hard_stop
from lumina_core.birth.plateau_evolution_ladder import (
    EVOLUTION_STEP_ACTIONS,
    EvolutionAction,
    evolution_ladder_exhausted,
)
from lumina_core.logging_utils import get_logger

if TYPE_CHECKING:
    from lumina_core.birth.plateau_escalator import PlateauState

logger = get_logger("lumina.birth.plateau_terminal")

TERMINAL_STALL_REASON = "plateau_evolution_exhausted"

_NO_LIFT_EPS = 1e-9
_PLATEAU_GAP_PROGRESS_MIN = 0.25


'''
    # revert 380-384, brake through increment 589-1117
    terminal += extract(lines, 380, 384)
    terminal += "\n"
    terminal += extract(lines, 589, 1117)
    (BIRTH / "plateau_terminal.py").write_text(terminal.rstrip() + "\n", encoding="utf-8")

    # --- plateau_telemetry.py ---
    telemetry = '''"""Plateau progress / quarantine / audit telemetry payloads."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.plateau_enter import (
    is_plateau_quarantine_blocking,
    plateau_max_trades_beyond_gate,
    plateau_trades_beyond_gate,
)
from lumina_core.birth.plateau_evolution_ladder import (
    ACTION_LABELS,
    EVOLUTION_STEP_ACTIONS,
    EvolutionAction,
    action_for_step,
    evolution_actions_completed,
    evolution_phantom_steps,
)
from lumina_core.birth.plateau_terminal import (
    TERMINAL_STALL_REASON,
    detect_hold_trap,
    detect_over_trading_trap,
    evolution_ladder_blocked_reason,
    plateau_elapsed_sec,
    should_phoenix_reset,
    should_terminal_plateau_stall,
)

if TYPE_CHECKING:
    from lumina_core.birth.plateau_escalator import PlateauState


'''
    telemetry += extract(lines, 387, 430)
    telemetry += "\n"
    telemetry += extract(lines, 1120, 1265)
    (BIRTH / "plateau_telemetry.py").write_text(telemetry.rstrip() + "\n", encoding="utf-8")

    # --- façade ---
    facade = '''"""Learning plateau detection + evolution host (ADR-0023).

Bounded modules:
``plateau_evolution_ladder``, ``plateau_rolling``, ``plateau_enter``,
``plateau_terminal``, ``plateau_telemetry``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lumina_core.birth.plateau_enter import (  # noqa: F401
    PlateauEnterContext,
    apply_plateau_quarantine_on_resume,
    enter_plateau,
    is_plateau_quarantine_blocking,
    is_valid_best_policy_snapshot,
    plateau_max_trades_beyond_gate,
    plateau_min_stage_trades,
    plateau_trades_beyond_gate,
    reset_plateau_for_new_cycle,
    sanitize_plateau_best_snapshot,
    should_enter_plateau,
    should_trades_beyond_gate_hard_stop,
    update_plateau_quarantine_after_rollout,
)
from lumina_core.birth.plateau_evolution_ladder import (  # noqa: F401
    ACTION_LABELS,
    EVOLUTION_STEP_ACTIONS,
    STAGE3_EVOLUTION_STEP_ACTIONS,
    EvolutionAction,
    action_for_step,
    begin_evolution_step,
    evolution_actions_completed,
    evolution_actions_for_stage,
    evolution_ladder_exhausted,
    evolution_phantom_steps,
)
from lumina_core.birth.plateau_rolling import (  # noqa: F401
    prune_rolling_trade_chunks,
    rolling_winrate_from_chunks,
    rolling_winrate_last_n_trades,
)
from lumina_core.birth.plateau_telemetry import (  # noqa: F401
    build_plateau_audit,
    progress_fields,
    quarantine_progress_payload,
    quarantine_trades_remaining,
)
from lumina_core.birth.plateau_terminal import (  # noqa: F401
    TERMINAL_STALL_REASON,
    adaptation_stuck_escape_allowed,
    can_force_never_stop_recovery,
    detect_hold_trap,
    detect_over_trading_trap,
    evolution_ladder_blocked_reason,
    increment_evolution_rollout,
    maybe_update_best_winrate,
    plateau_elapsed_sec,
    record_evolution_outcome,
    record_forced_recovery,
    remediation_is_exhausted,
    revert_evolution_step_on_noop,
    sanitize_phantom_evolution_steps,
    sanitize_stuck_plateau_evolution,
    should_advance_evolution_step,
    should_block_phoenix_no_lift,
    should_block_plateau_recovery,
    should_brake_recovery_no_lift,
    should_force_advance_evolution_step,
    should_phoenix_reset,
    should_start_evolution_step,
    should_terminal_plateau_stall,
    should_trigger_plateau_evolution_step,
    winrate_improvement_blocks_ladder,
)

__all__ = [
    "ACTION_LABELS",
    "EVOLUTION_STEP_ACTIONS",
    "STAGE3_EVOLUTION_STEP_ACTIONS",
    "EvolutionAction",
    "PlateauEnterContext",
    "PlateauState",
    "TERMINAL_STALL_REASON",
    "action_for_step",
    "adaptation_stuck_escape_allowed",
    "apply_plateau_quarantine_on_resume",
    "begin_evolution_step",
    "build_plateau_audit",
    "can_force_never_stop_recovery",
    "detect_hold_trap",
    "detect_over_trading_trap",
    "enter_plateau",
    "evolution_actions_completed",
    "evolution_actions_for_stage",
    "evolution_ladder_blocked_reason",
    "evolution_ladder_exhausted",
    "evolution_phantom_steps",
    "increment_evolution_rollout",
    "is_plateau_quarantine_blocking",
    "is_valid_best_policy_snapshot",
    "maybe_update_best_winrate",
    "plateau_elapsed_sec",
    "plateau_max_trades_beyond_gate",
    "plateau_min_stage_trades",
    "plateau_trades_beyond_gate",
    "progress_fields",
    "prune_rolling_trade_chunks",
    "quarantine_progress_payload",
    "quarantine_trades_remaining",
    "record_evolution_outcome",
    "record_forced_recovery",
    "remediation_is_exhausted",
    "reset_plateau_for_new_cycle",
    "revert_evolution_step_on_noop",
    "rolling_winrate_from_chunks",
    "rolling_winrate_last_n_trades",
    "sanitize_phantom_evolution_steps",
    "sanitize_plateau_best_snapshot",
    "sanitize_stuck_plateau_evolution",
    "should_advance_evolution_step",
    "should_block_phoenix_no_lift",
    "should_block_plateau_recovery",
    "should_brake_recovery_no_lift",
    "should_enter_plateau",
    "should_force_advance_evolution_step",
    "should_phoenix_reset",
    "should_start_evolution_step",
    "should_terminal_plateau_stall",
    "should_trades_beyond_gate_hard_stop",
    "should_trigger_plateau_evolution_step",
    "update_plateau_quarantine_after_rollout",
    "winrate_improvement_blocks_ladder",
]


@dataclass(slots=True)
class PlateauState:
    active: bool = False
    plateau_started_at: float = 0.0
    trades_at_plateau_start: int = 0
    best_winrate: float = 0.0
    best_winrate_at_trade: int = 0
    best_policy_path: str = ""
    # Raptor v14: best rolling-window skill snapshot (preferred for stage3 rollback).
    best_rolling_winrate: float = 0.0
    best_rolling_at_trade: int = 0
    best_rolling_policy_path: str = ""
    evolution_step: int = 0
    evolution_rollouts_this_step: int = 0
    forced_recoveries_count: int = 0
    evolution_history: list[dict[str, Any]] = field(default_factory=list)
    winrate_at_step_start: float = 0.0
    full_recovery_cycles: int = 0
    evolution_noop_count: int = 0
    # Best winrate snapshot at cycle start — used to detect no-lift thrash.
    best_winrate_at_cycle_start: float = 0.0

    def to_metrics(self) -> dict[str, Any]:
        return {
            "plateau_active": self.active,
            "plateau_started_at": float(self.plateau_started_at),
            "plateau_trades_at_start": int(self.trades_at_plateau_start),
            "plateau_best_winrate": round(float(self.best_winrate), 6),
            "plateau_best_winrate_at_trade": int(self.best_winrate_at_trade),
            "plateau_best_policy_path": str(self.best_policy_path or ""),
            "plateau_best_rolling_winrate": round(float(self.best_rolling_winrate), 6),
            "plateau_best_rolling_at_trade": int(self.best_rolling_at_trade),
            "plateau_best_rolling_policy_path": str(self.best_rolling_policy_path or ""),
            "plateau_evolution_step": int(self.evolution_step),
            "plateau_evolution_rollouts_this_step": int(self.evolution_rollouts_this_step),
            "plateau_forced_recoveries_count": int(self.forced_recoveries_count),
            "plateau_evolution_history": list(self.evolution_history),
            "plateau_winrate_at_step_start": round(float(self.winrate_at_step_start), 6),
            "plateau_full_recovery_cycles": int(self.full_recovery_cycles),
            "plateau_evolution_noop_count": int(self.evolution_noop_count),
            "plateau_best_winrate_at_cycle_start": round(
                float(self.best_winrate_at_cycle_start), 6
            ),
        }

    @classmethod
    def from_metrics(cls, metrics: dict[str, Any] | None) -> PlateauState:
        if not isinstance(metrics, dict):
            return cls()
        history = metrics.get("plateau_evolution_history")
        return cls(
            active=bool(metrics.get("plateau_active", False)),
            plateau_started_at=float(metrics.get("plateau_started_at", 0) or 0),
            trades_at_plateau_start=int(metrics.get("plateau_trades_at_start", 0) or 0),
            best_winrate=float(metrics.get("plateau_best_winrate", 0) or 0),
            best_winrate_at_trade=int(metrics.get("plateau_best_winrate_at_trade", 0) or 0),
            best_policy_path=str(metrics.get("plateau_best_policy_path", "") or ""),
            best_rolling_winrate=float(metrics.get("plateau_best_rolling_winrate", 0) or 0),
            best_rolling_at_trade=int(metrics.get("plateau_best_rolling_at_trade", 0) or 0),
            best_rolling_policy_path=str(metrics.get("plateau_best_rolling_policy_path", "") or ""),
            evolution_step=int(metrics.get("plateau_evolution_step", 0) or 0),
            evolution_rollouts_this_step=int(
                metrics.get("plateau_evolution_rollouts_this_step", 0) or 0
            ),
            forced_recoveries_count=int(metrics.get("plateau_forced_recoveries_count", 0) or 0),
            evolution_history=[dict(x) for x in history if isinstance(x, dict)]
            if isinstance(history, list)
            else [],
            winrate_at_step_start=float(metrics.get("plateau_winrate_at_step_start", 0) or 0),
            full_recovery_cycles=int(metrics.get("plateau_full_recovery_cycles", 0) or 0),
            evolution_noop_count=int(metrics.get("plateau_evolution_noop_count", 0) or 0),
            best_winrate_at_cycle_start=float(
                metrics.get("plateau_best_winrate_at_cycle_start", 0) or 0
            ),
        )
'''
    SRC.write_text(facade.rstrip() + "\n", encoding="utf-8")
    print("plateau split done")
    for name in (
        "plateau_escalator.py",
        "plateau_rolling.py",
        "plateau_enter.py",
        "plateau_terminal.py",
        "plateau_telemetry.py",
    ):
        n = len((BIRTH / name).read_text(encoding="utf-8").splitlines())
        print(f"  {name}: {n}")


if __name__ == "__main__":
    main()
