"""Compatibility shim — implementation in `lumina_core.rl.ppo_evolution_logger`."""
from __future__ import annotations

import sys

from lumina_core.rl import ppo_evolution_logger as _impl

sys.modules[__name__] = _impl
