from dataclasses import dataclass
from types import ModuleType
from typing import Any

from lumina_core.engine.lumina_engine import LuminaEngine


@dataclass(slots=True)
class RuntimeContext:
    """Typed adapter that exposes LuminaEngine as the runtime dependency surface."""

    engine: LuminaEngine
    app: ModuleType | None = None
    container: Any | None = None

    def __post_init__(self) -> None:
        if self.engine is None:
            raise ValueError("RuntimeContext.engine is required")
        if self.app is not None:
            self.engine.bind_app(self.app)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.engine, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in {"engine", "app", "container"}:
            object.__setattr__(self, name, value)
            return
        setattr(self.engine, name, value)
