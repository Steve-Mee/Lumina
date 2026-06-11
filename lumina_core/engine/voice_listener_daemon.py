"""

VoiceListenerDaemon — D2 sub-slice 13: voice input loop extraction from runtime_workers.



Compat wrapper; canonical logic lives in VoiceLegacyHandler.

"""



from __future__ import annotations



import logging

from typing import Any



from lumina_core.engine.voice_legacy_handler import VoiceLegacyHandler



logger = logging.getLogger(__name__)





class VoiceListenerDaemon:

    """Compat wrapper (D2 sub-slice 13). Delegates to VoiceLegacyHandler."""



    def __init__(self, *, app: Any) -> None:

        self.app = app

        self._logger = getattr(app, "logger", logger)



    def run(self) -> None:

        """Compat entry; delegates to VoiceLegacyHandler (exact behavior preserved)."""

        VoiceLegacyHandler(app=self.app).run_listener(app=self.app)


