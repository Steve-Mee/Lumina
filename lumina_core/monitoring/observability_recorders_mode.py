"""Mode/blackboard observability recorders (M5)."""
from __future__ import annotations

from lumina_core.monitoring.observability_metric_names import (
    M_BLACKBOARD_DROP_TOTAL,
    M_BLACKBOARD_PUBLISH_LATENCY,
    M_BLACKBOARD_REJECT_TOTAL,
    M_BLACKBOARD_SUBSCRIPTION_ERROR_TOTAL,
    M_MODE_EOD_FORCE_CLOSE_TOTAL,
    M_MODE_GUARD_BLOCK_TOTAL,
    M_MODE_PARITY_DRIFT_TOTAL,
    M_RESTARTS,
)


class ObservabilityModeBlackboardMixin:
    """Mode guard + blackboard metrics (extracted for LOC hygiene)."""

    def record_process_restart(self) -> None:
        """Increment the process-restart counter (used by watchdog)."""
        self.collector.inc(M_RESTARTS, help_="Total supervised process restarts by watchdog")

    def record_mode_guard_block(self, *, mode: str, reason: str) -> None:
        self.collector.inc(
            M_MODE_GUARD_BLOCK_TOTAL,
            labels={"mode": str(mode).lower(), "reason": str(reason).lower()},
            help_="Total pre-trade guard rejections by mode and reason",
        )

    def record_mode_eod_force_close(self, *, mode: str) -> None:
        self.collector.inc(
            M_MODE_EOD_FORCE_CLOSE_TOTAL,
            labels={"mode": str(mode).lower()},
            help_="Total EOD force-close activations by mode",
        )

    def record_mode_parity_drift(self, *, baseline: str, candidate: str, delta: float) -> None:
        self.collector.inc(
            M_MODE_PARITY_DRIFT_TOTAL,
            amount=float(abs(delta)),
            labels={"baseline": str(baseline).lower(), "candidate": str(candidate).lower()},
            help_="Accumulated mode parity drift (absolute delta)",
        )

    def record_blackboard_publish(self, *, topic: str, producer: str, elapsed_ms: float) -> None:
        self.collector.observe(
            M_BLACKBOARD_PUBLISH_LATENCY,
            float(elapsed_ms),
            labels={"topic": str(topic).lower(), "producer": str(producer).lower()},
            help_="Blackboard publish latency in milliseconds",
        )

    def record_blackboard_reject(self, *, topic: str, producer: str, reason: str) -> None:
        self.collector.inc(
            M_BLACKBOARD_REJECT_TOTAL,
            labels={"topic": str(topic).lower(), "producer": str(producer).lower(), "reason": str(reason).lower()},
            help_="Total rejected blackboard events",
        )

    def record_blackboard_drop(self, *, topic: str, producer: str, reason: str, critical: bool) -> None:
        self.collector.inc(
            M_BLACKBOARD_DROP_TOTAL,
            labels={
                "topic": str(topic).lower(),
                "producer": str(producer).lower(),
                "reason": str(reason).lower(),
                "critical": str(bool(critical)).lower(),
            },
            help_="Total dropped blackboard events due to backpressure",
        )

    def record_blackboard_subscription_error(self, *, topic: str, producer: str) -> None:
        self.collector.inc(
            M_BLACKBOARD_SUBSCRIPTION_ERROR_TOTAL,
            labels={"topic": str(topic).lower(), "producer": str(producer).lower()},
            help_="Total blackboard subscriber callback errors",
        )
