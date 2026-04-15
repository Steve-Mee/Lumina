# DEPRECATED compat shim — import from fast_path_engine instead.
# Will be removed after all callers are migrated.
import warnings

DEPRECATION_TRACKER_ID = "B2-legacy-compat"
DEPRECATION_DEADLINE_UTC = "2026-06-30T00:00:00Z"

warnings.warn(
    "lumina_core.engine.FastPathEngine is deprecated; "
    "use lumina_core.engine.fast_path_engine; "
    "removal deadline=2026-06-30T00:00:00Z",
    DeprecationWarning,
    stacklevel=2,
)
from lumina_core.engine.fast_path_engine import FastPathEngine, PositionSizer  # noqa: F401, E402

__all__ = ["FastPathEngine", "PositionSizer"]
