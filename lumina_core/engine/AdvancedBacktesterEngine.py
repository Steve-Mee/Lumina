# DEPRECATED compat shim — import from advanced_backtester_engine instead.
# Will be removed after all callers are migrated.
import warnings
warnings.warn(
    "lumina_core.engine.AdvancedBacktesterEngine is deprecated; "
    "use lumina_core.engine.advanced_backtester_engine",
    DeprecationWarning,
    stacklevel=2,
)
from lumina_core.engine.advanced_backtester_engine import AdvancedBacktesterEngine  # noqa: F401, E402

__all__ = ["AdvancedBacktesterEngine"]
