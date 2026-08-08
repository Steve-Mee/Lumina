"""Compatibility shim — implementation in `lumina_core.rl.ppo_trainer_ops`."""
from __future__ import annotations

import sys

from lumina_core.rl import ppo_trainer_ops as _impl

sys.modules[__name__] = _impl
