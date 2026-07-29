"""Wave B PR-B4 follow-up — thin PPOTrainer via ops mixin."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "lumina_core"
src = CORE / "ppo_trainer.py"
lines = src.read_text(encoding="utf-8").splitlines(keepends=True)


def extract(start: int, end: int) -> str:
    return "".join(lines[start - 1 : end])


# Find class method line numbers via markers
text = src.read_text(encoding="utf-8")
# Methods from get_weights through infer_live_action stay in mixin;
# façade keeps dataclass fields + __post_init__ + _resolve_active_model

# Parse by searching
import re

method_starts = []
for m in re.finditer(r"^    def (\w+)", text, re.M):
    method_starts.append((m.group(1), text[: m.start()].count("\n") + 1))

print("methods:", method_starts)

# Keep on façade: __post_init__, _resolve_active_model
# Move rest to PPOTrainerOpsMixin

# Find line of class end
# After extracting helpers, structure is:
# imports, _sb3_ppo_load, @dataclass class PPOTrainer

# We'll rewrite programmatically from AST
import ast

tree = ast.parse(text)
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "PPOTrainer")
keep = {"__post_init__", "_resolve_active_model"}
keep_nodes = []
move_nodes = []
for item in cls.body:
    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if item.name in keep:
            keep_nodes.append(item)
        else:
            move_nodes.append(item)
    else:
        # fields stay on façade class
        keep_nodes.append(item)

# Reconstruct method source from original lines using lineno
def method_src(node: ast.AST) -> str:
    assert hasattr(node, "lineno") and hasattr(node, "end_lineno")
    return "".join(lines[node.lineno - 1 : node.end_lineno])  # type: ignore[attr-defined]


ops_methods = "\n\n".join(method_src(n) for n in move_nodes)
ops = f'''"""PPOTrainerOpsMixin — weights, train, birth, live inference (Wave B PR-B4)."""
from __future__ import annotations

from dataclasses import asdict
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


def _sb3_ppo_load(path: str | Path) -> Any | None:
    try:
        from stable_baselines3 import PPO

        return PPO.load(str(path))
    except Exception:
        logging.exception("Unhandled broad exception fallback in lumina_core/ppo_trainer.py:19")
        return None


class PPOTrainerOpsMixin:
    """Training / weight / live-policy operations for PPOTrainer."""

{ops_methods}
'''

# Fix: methods have 4-space class indent already — good inside class
# But we need them indented under PPOTrainerOpsMixin — they already have 4 spaces

(CORE / "ppo_trainer_ops.py").write_text(ops.rstrip() + "\n", encoding="utf-8")
print("wrote ppo_trainer_ops.py", len(ops.splitlines()))

keep_src = "\n\n".join(method_src(n) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) else "".join(lines[n.lineno - 1 : n.end_lineno]) for n in keep_nodes)  # type: ignore[attr-defined]

# Simpler: rebuild façade manually
facade = '''from __future__ import annotations
# pyright: reportMissingImports=false

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.ppo_callbacks import (
    _notify_first_boot_ppo_progress,
)
from lumina_core.ppo_device import _resolve_ppo_device, _scale_timesteps_for_device
from lumina_core.ppo_trainer_ops import PPOTrainerOpsMixin

logger = get_logger("lumina.rl.ppo")

# Public / test re-exports (behavior-preserving import surface).
__all__ = [
    "PPOTrainer",
    "_notify_first_boot_ppo_progress",
    "_resolve_ppo_device",
    "_scale_timesteps_for_device",
]


@dataclass(slots=True)
class PPOTrainer(PPOTrainerOpsMixin):
    """Stable-Baselines3 PPO trainer and live-policy adapter."""

    engine: Any
    model_dir: Path = Path("lumina_agents/ppo")
    logger: Any = field(init=False, repr=False)
    last_policy_entropy: float | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.logger = logger
        self.last_policy_entropy = None

    def _resolve_active_model(self) -> Any | None:
        return getattr(self.engine, "rl_policy_model", None)
'''
src.write_text(facade.rstrip() + "\n", encoding="utf-8")
print("wrote ppo_trainer.py", len(facade.splitlines()))
