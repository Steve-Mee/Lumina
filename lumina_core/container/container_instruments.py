"""ApplicationContainerInstrumentsMixin (M5 extract)."""
from __future__ import annotations


from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.container")


class ApplicationContainerInstrumentsMixin:
    def _init_instruments(self) -> None:
        """Initialize instrument symbols from config."""
        self.swarm_symbols = [str(s).strip().upper() for s in self.config.swarm_symbols]
        self.primary_instrument = str(self.config.instrument).strip().upper()

        # Ensure primary instrument is first in swarm list
        if self.primary_instrument not in self.swarm_symbols:
            self.swarm_symbols.insert(0, self.primary_instrument)

        self.logger.info(f"Instruments configured: primary={self.primary_instrument}, swarm={self.swarm_symbols}")


