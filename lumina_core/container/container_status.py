"""ApplicationContainer status and cleanup helpers."""
from __future__ import annotations

from typing import Any

class ContainerStatusMixin:
    """get_status + _register_cleanup."""

    def _register_cleanup(self) -> None:
        """Register cleanup handlers for graceful shutdown."""

        def cleanup_traded_reconciler() -> None:
            try:
                if self.trade_reconciler:
                    self.trade_reconciler.stop()
            except Exception as e:
                self.logger.error(f"Error stopping trade reconciler: {e}")

        def cleanup_observability() -> None:
            try:
                self.observability_service.stop()
            except Exception as e:
                self.logger.error(f"Error stopping observability service: {e}")

        def cleanup_tts() -> None:
            try:
                if self.tts_engine:
                    self.tts_engine.stop()
            except Exception as e:
                self.logger.error(f"Error stopping TTS engine: {e}")

        def cleanup_broker() -> None:
            try:
                self.broker.disconnect()
            except Exception as e:
                self.logger.error(f"Error disconnecting broker: {e}")

        def cleanup_maturation_autopilot() -> None:
            try:
                from lumina_core.maturity.autopilot import stop_maturation_autopilot

                stop_maturation_autopilot()
            except Exception as e:
                self.logger.error(f"Error stopping maturation autopilot: {e}")

        atexit.register(cleanup_traded_reconciler)
        atexit.register(cleanup_observability)
        atexit.register(cleanup_tts)
        atexit.register(cleanup_broker)
        atexit.register(cleanup_maturation_autopilot)

        self.logger.info("Cleanup handlers registered")

    def get_status(self) -> dict[str, Any]:
        """Get container initialization status."""
        current_adaptive_intelligence = self._refresh_adaptive_intelligence(
            source="container_status_poll",
            refresh_hardware=False,
        )
        launcher_setup: dict[str, Any] = {}
        try:
            from lumina_launcher.core.setup_gate import launcher_setup_status_payload

            launcher_setup = launcher_setup_status_payload(
                Path.cwd(),
                smart_setup_service=self.smart_setup_service,
            )
        except Exception as exc:
            self.logger.warning("container.launcher_setup_status_failed detail=%s", exc)
        return {
            "engine_initialized": self.engine is not None,
            "services_count": sum(
                [
                    1
                    for attr in [
                        self.market_data_service,
                        self.memory_service,
                        self.reasoning_service,
                        self.operations_service,
                        self.analysis_service,
                        self.dashboard_service,
                        self.visualization_service,
                        self.reporting_service,
                        self.news_agent,
                        self.ppo_trainer,
                        self.emotional_twin_agent,
                        self.infinite_simulator,
                        self.trade_reconciler,
                        self.swarm_manager,
                        self.performance_validator,
                    ]
                    if attr is not None
                ]
            ),
            "voice_input_enabled": self.voice_recognizer is not None,
            "tts_enabled": self.tts_engine is not None,
            "swarm_symbols": self.swarm_symbols,
            "primary_instrument": self.primary_instrument,
            "adaptive_intelligence": current_adaptive_intelligence,
            "launcher_setup": launcher_setup,
        }


