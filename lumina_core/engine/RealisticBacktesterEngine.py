# DEPRECATED compat shim — import from realistic_backtester_engine instead.
# Will be removed after all callers are migrated.
import warnings

DEPRECATION_TRACKER_ID = "B2-legacy-compat"
DEPRECATION_DEADLINE_UTC = "2026-06-30T00:00:00Z"

warnings.warn(
    "lumina_core.engine.RealisticBacktesterEngine is deprecated; "
    "use lumina_core.engine.realistic_backtester_engine; "
    "removal deadline=2026-06-30T00:00:00Z",
    DeprecationWarning,
    stacklevel=2,
)
from lumina_core.engine.realistic_backtester_engine import RealisticBacktesterEngine  # noqa: F401, E402

__all__ = ["RealisticBacktesterEngine"]
