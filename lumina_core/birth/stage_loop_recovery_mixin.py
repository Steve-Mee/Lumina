"""StageLoopRecoveryMixin — composite recovery surface for StageLoopSession.

Bounded contexts:
- stage_loop_recovery_terminal: wall + certified stall finalization
- stage_loop_recovery_remediation: phoenix + stall remediation
- stage_loop_recovery_adaptation: adaptive recovery / never-stop / budget
"""

from __future__ import annotations

from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.birth.stage_loop_recovery_adaptation import StageLoopRecoveryAdaptationMixin
from lumina_core.birth.stage_loop_recovery_remediation import StageLoopRecoveryRemediationMixin
from lumina_core.birth.stage_loop_recovery_terminal import StageLoopRecoveryTerminalMixin


class StageLoopRecoveryMixin(
    StageLoopRecoveryTerminalMixin,
    StageLoopRecoveryRemediationMixin,
    StageLoopRecoveryAdaptationMixin,
    StageLoopMixinBase,
):
    """Composite recovery mixin; see StageLoopSession for attributes."""


__all__ = ["StageLoopRecoveryMixin"]
