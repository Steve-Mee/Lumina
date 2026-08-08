"""Birth engine lifecycle façade (M5 composite mixin)."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.config import load_birth_v2_config  # noqa: F401 — conftest patch site
from lumina_core.birth.engine_lifecycle_certificate import EngineLifecycleCertificateMixin
from lumina_core.birth.engine_lifecycle_core import EngineLifecycleCoreMixin
from lumina_core.birth.engine_lifecycle_event import EngineLifecycleEventMixin
from lumina_core.birth.engine_lifecycle_ops import EngineLifecycleOpsMixin


class EngineLifecycleMixin(
    EngineLifecycleCoreMixin,
    EngineLifecycleOpsMixin,
    EngineLifecycleCertificateMixin,
    EngineLifecycleEventMixin,
):
    ppo_trainer: Any


__all__ = ["EngineLifecycleMixin", "load_birth_v2_config"]
