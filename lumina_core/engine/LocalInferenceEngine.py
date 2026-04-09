# DEPRECATED compat shim — import from local_inference_engine instead.
# Will be removed after all callers are migrated.
import warnings
warnings.warn(
    "lumina_core.engine.LocalInferenceEngine is deprecated; "
    "use lumina_core.engine.local_inference_engine",
    DeprecationWarning,
    stacklevel=2,
)
from lumina_core.engine.local_inference_engine import LocalInferenceEngine  # noqa: F401, E402

__all__ = ["LocalInferenceEngine"]
