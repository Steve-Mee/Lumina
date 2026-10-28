"""BirthCurriculumConfig builder (M5: composed kwargs tables)."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.config_curriculum import BirthCurriculumConfig
from lumina_core.birth.config_coercion_curriculum_core import (
    curriculum_kwargs as _kw_core,
)
from lumina_core.birth.config_coercion_curriculum_mid import (
    curriculum_kwargs as _kw_mid,
)
from lumina_core.birth.config_coercion_curriculum_tail import (
    curriculum_kwargs as _kw_tail,
)


def build_curriculum_config(cur_raw: dict[str, Any]) -> BirthCurriculumConfig:
    merged: dict[str, Any] = {}
    merged.update(_kw_core(cur_raw))
    merged.update(_kw_mid(cur_raw))
    merged.update(_kw_tail(cur_raw))
    return BirthCurriculumConfig(**merged)


__all__ = ["build_curriculum_config"]
