"""Phase 2 Autonomy feature flags — fail-closed defaults (all off)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lumina_core.birth.phase2_autonomy.execution_mode import (
    Phase2ExecutionMode,
    normalize_execution_mode,
)


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
    # Slice C: require evidence sidecar (passed=true), not hollow flag alone
    require_perfect_birth_evidence: bool = True
    # Optional live KPI recheck on apply path
    recheck_perfect_birth_kpis: bool = False
    # Slice D: observe | shadow | apply (default observe = fail-closed mutate)
    execution_mode: str = "observe"

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

    def execution_mode_enum(self) -> Phase2ExecutionMode:
        return normalize_execution_mode(self.execution_mode)

    def perfect_birth_unlocked(self) -> bool:
        """Flag file exists (raw). Prefer perfect_birth_unlock_status for full check."""
        path = self.perfect_birth_path()
        try:
            return path.is_file()
        except OSError:
            return False

    def perfect_birth_unlock_status(
        self,
        *,
        recheck: bool = False,
        curriculum_cfg: Any | None = None,
    ) -> tuple[bool, str]:
        """Full unlock: flag + evidence sidecar (+ optional live KPI recheck)."""
        from lumina_core.birth.perfect_birth_gate import (
            PerfectBirthThresholds,
            gather_perfect_birth_kpis,
            perfect_birth_unlock_valid,
        )

        recheck_kpis = None
        thr = None
        if recheck or self.recheck_perfect_birth_kpis:
            recheck_kpis = gather_perfect_birth_kpis()
            thr = PerfectBirthThresholds.from_curriculum_cfg(curriculum_cfg)
        return perfect_birth_unlock_valid(
            flag_path=self.perfect_birth_path(),
            require_evidence=bool(self.require_perfect_birth_evidence),
            recheck_kpis=recheck_kpis,
            thresholds=thr,
        )

    @classmethod
    def from_curriculum_cfg(cls, cfg: Any) -> Phase2AutonomyFeatures:
        """Build features from BirthCurriculumConfig (or any object with attrs)."""
        if cfg is None:
            return cls()
        mode = str(getattr(cfg, "phase2_execution_mode", "observe") or "observe")
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
            require_perfect_birth_evidence=bool(
                getattr(cfg, "phase2_require_perfect_birth_evidence", True)
            ),
            recheck_perfect_birth_kpis=bool(
                getattr(cfg, "phase2_recheck_perfect_birth_kpis", False)
            ),
            execution_mode=normalize_execution_mode(mode).value,
        )


__all__ = [
    "DEFAULT_PERFECT_BIRTH_FLAG",
    "Phase2AutonomyFeatures",
]
