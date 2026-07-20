"""Phase 2 Autonomy feature flags — fail-closed defaults (all off)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_PERFECT_BIRTH_FLAG = Path("state/perfect_birth_complete.flag")


@dataclass(frozen=True, slots=True)
class Phase2AutonomyFeatures:
    """Master + per-pillar switches. Defaults keep Phase 2 completely inert."""

    enabled: bool = False
    dynamic_wall_enabled: bool = False
    self_adaptive_params_enabled: bool = False
    instance_adapt_enabled: bool = False
    require_perfect_birth_flag: bool = True
    allow_sim_scaffold: bool = False
    require_twin_for_apply: bool = True
    perfect_birth_flag_path: str = "state/perfect_birth_complete.flag"

    def pillar_enabled(self, pillar: str) -> bool:
        if not self.enabled:
            return False
        key = str(pillar or "").strip().lower()
        if key in {"dynamic_wall", "wall"}:
            return bool(self.dynamic_wall_enabled)
        if key in {"self_adaptive_params", "params", "param"}:
            return bool(self.self_adaptive_params_enabled)
        if key in {"instance_adapt", "instance", "spawn"}:
            return bool(self.instance_adapt_enabled)
        return False

    def perfect_birth_path(self) -> Path:
        return Path(self.perfect_birth_flag_path or str(DEFAULT_PERFECT_BIRTH_FLAG))

    def perfect_birth_unlocked(self) -> bool:
        path = self.perfect_birth_path()
        try:
            return path.is_file()
        except OSError:
            return False

    @classmethod
    def from_curriculum_cfg(cls, cfg: Any) -> Phase2AutonomyFeatures:
        """Build features from BirthCurriculumConfig (or any object with attrs)."""
        if cfg is None:
            return cls()
        return cls(
            enabled=bool(getattr(cfg, "phase2_autonomy_enabled", False)),
            dynamic_wall_enabled=bool(getattr(cfg, "phase2_dynamic_wall_enabled", False)),
            self_adaptive_params_enabled=bool(
                getattr(cfg, "phase2_self_adaptive_params_enabled", False)
            ),
            instance_adapt_enabled=bool(getattr(cfg, "phase2_instance_adapt_enabled", False)),
            require_perfect_birth_flag=bool(
                getattr(cfg, "phase2_require_perfect_birth_flag", True)
            ),
            allow_sim_scaffold=bool(getattr(cfg, "phase2_allow_sim_scaffold", False)),
            require_twin_for_apply=bool(getattr(cfg, "phase2_require_twin_for_apply", True)),
            perfect_birth_flag_path=str(
                getattr(
                    cfg,
                    "phase2_perfect_birth_flag_path",
                    "state/perfect_birth_complete.flag",
                )
                or "state/perfect_birth_complete.flag"
            ),
        )


__all__ = [
    "DEFAULT_PERFECT_BIRTH_FLAG",
    "Phase2AutonomyFeatures",
]
