"""lumina_core.safety — AGI Safety enforcement layer for LUMINA.

Public surface:
  - TradingConstitution / ConstitutionalPrinciple / ConstitutionalViolation
  - SandboxedMutationExecutor / SandboxedResult
  - ConstitutionalGuard  (top-level integration point)
"""

from lumina_core.safety.trading_constitution import (
    ConstitutionalPrinciple,
    ConstitutionalViolation,
    ConstitutionalViolationError,
    TradingConstitution,
    TRADING_CONSTITUTION,
)
from lumina_core.safety.sandboxed_executor import (
    SandboxedMutationExecutor,
    SandboxedResult,
)
from lumina_core.safety.constitutional_guard import ConstitutionalGuard

__all__ = [
    "ConstitutionalPrinciple",
    "ConstitutionalViolation",
    "ConstitutionalViolationError",
    "TradingConstitution",
    "TRADING_CONSTITUTION",
    "SandboxedMutationExecutor",
    "SandboxedResult",
    "ConstitutionalGuard",
]
