# DEPRECATED compat shim — import from tape_reading_agent instead.
# Will be removed after all callers are migrated.
import warnings
warnings.warn(
    "lumina_core.engine.TapeReadingAgent is deprecated; "
    "use lumina_core.engine.tape_reading_agent",
    DeprecationWarning,
    stacklevel=2,
)
from lumina_core.engine.tape_reading_agent import TapeReadingAgent  # noqa: F401, E402

__all__ = ["TapeReadingAgent"]
