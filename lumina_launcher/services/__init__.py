"""Launcher-facing service facades."""

from .hardware_service import HardwareService
from .model_service import ModelService
from lumina_launcher.core.workspace_root import resolve_birth_workspace_root
from .smart_setup_service import (
    SmartSetupOptions,
    SmartSetupService,
    SetupProgressEvent,
    SmartSetupResult,
)
from .tauri_signing_service import TauriSigningResult, TauriSigningService
from .ppo_realtime import PPORealtimeTailer, ppo_realtime_tailer

__all__ = [
    "HardwareService",
    "ModelService",
    "resolve_birth_workspace_root",
    "SmartSetupOptions",
    "SmartSetupService",
    "SetupProgressEvent",
    "SmartSetupResult",
    "TauriSigningResult",
    "TauriSigningService",
    "PPORealtimeTailer",
    "ppo_realtime_tailer",
]
