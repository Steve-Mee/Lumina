# DEPRECATED compat shim — import from realistic_backtester_engine instead.
# Will be removed after all callers are migrated.
import warnings
warnings.warn(
    "lumina_core.engine.RealisticBacktesterEngine is deprecated; "
    "use lumina_core.engine.realistic_backtester_engine",
    DeprecationWarning,
    stacklevel=2,
)
from lumina_core.engine.realistic_backtester_engine import RealisticBacktesterEngine  # noqa: F401, E402

__all__ = ["RealisticBacktesterEngine"]
