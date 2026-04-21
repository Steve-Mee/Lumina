"""Veto window logic for 30-minute fail-closed promotion blocking."""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class VetoWindow:
    """Fail-closed 30-minute veto window for DNA promotions.

    Architecture:
    - Wraps VetoRegistry queries
    - Blocks promotion if any veto found within window
    - Logs veto decisions for audit trail
    - Thread-safe (delegates to VetoRegistry locking)
    """

    def __init__(
        self,
        veto_registry: Optional[Any] = None,
        window_seconds: int = 1800,  # 30 minutes
    ):
        """Initialize veto window.

        Args:
            veto_registry: VetoRegistry instance for veto lookups
            window_seconds: Veto window duration in seconds (default 30 min)
        """
        self._veto_registry = veto_registry
        self._window_seconds = window_seconds

    def is_promotion_blocked(self, dna_id: str, reason_callback: Optional[Any] = None) -> bool:
        """Check if DNA promotion is blocked by active veto (fail-closed).

        Args:
            dna_id: DNA ID to check
            reason_callback: Optional callable(reason_str) for logging block reason

        Returns:
            True if veto found within window (blocks promotion)
            False if no veto (promotion allowed, subject to other gates)
        """
        if not self._veto_registry:
            # No registry: veto window disabled, promotion proceeds
            return False

        try:
            blocked = self._veto_registry.is_veto_active(dna_id, window_seconds=self._window_seconds)

            if blocked:
                reason = (
                    f"DNA {dna_id} has active veto within {self._window_seconds // 60}-min window. "
                    f"Promotion blocked (fail-closed)."
                )
                logger.info(reason)
                if reason_callback:
                    try:
                        reason_callback(reason)
                    except Exception as e:
                        logger.error(f"Error in reason_callback: {e}")
            else:
                logger.debug(f"DNA {dna_id}: no active veto. Promotion not blocked by veto window.")

            return blocked

        except Exception as e:
            # Fail-closed: if registry check fails, assume veto is active (block promotion)
            logger.error(f"Veto window check failed for {dna_id}: {e}. Assuming veto active (fail-closed).")
            return True

    def check_with_details(self, dna_id: str) -> dict[str, Any]:
        """Detailed veto window check with metadata.

        Args:
            dna_id: DNA ID to check

        Returns:
            Dictionary with keys:
            - is_blocked: bool
            - active_veto_records: list of VetoRecord if blocked, else []
            - window_seconds: veto window duration
            - reason: human-readable reason if blocked
        """
        if not self._veto_registry:
            return {
                "is_blocked": False,
                "active_veto_records": [],
                "window_seconds": self._window_seconds,
                "reason": "No veto registry configured",
            }

        try:
            is_blocked = self._veto_registry.is_veto_active(dna_id, window_seconds=self._window_seconds)
            active_records = []

            if is_blocked:
                # Fetch veto records for this DNA
                all_records = self._veto_registry.list_recent(limit=100, dna_id_filter=dna_id)
                # Filter to active window
                from datetime import datetime, timedelta

                cutoff = datetime.utcnow() - timedelta(seconds=self._window_seconds)
                active_records = [r for r in all_records if datetime.fromisoformat(r.veto_timestamp) >= cutoff]

            return {
                "is_blocked": is_blocked,
                "active_veto_records": active_records,
                "window_seconds": self._window_seconds,
                "reason": (
                    f"Active veto (issuer: {active_records[0].issuer if active_records else 'unknown'})"
                    if is_blocked
                    else "No active veto"
                ),
            }

        except Exception as e:
            # Fail-closed: errors result in blocked state
            logger.error(f"Detailed veto check failed for {dna_id}: {e}")
            return {
                "is_blocked": True,
                "active_veto_records": [],
                "window_seconds": self._window_seconds,
                "reason": f"Veto check error (fail-closed): {e}",
            }

    def set_window_duration(self, seconds: int) -> None:
        """Update veto window duration.

        Args:
            seconds: New window duration in seconds
        """
        if seconds < 60:
            logger.warning(f"Veto window too short ({seconds}s). Using minimum 60s.")
            self._window_seconds = 60
        else:
            self._window_seconds = seconds
            logger.info(f"Veto window updated to {seconds}s ({seconds // 60}min {seconds % 60}s)")
