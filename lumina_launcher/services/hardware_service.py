"""
LUMINA Services - Hardware Service
Wrapper around HardwareInspector for clean access to hardware info.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.engine.hardware_inspector import HardwareInspector, HardwareSnapshot
from lumina_core.engine.model_catalog import ModelCatalog, ModelDescriptor


class HardwareService:
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self._snapshot: HardwareSnapshot | None = None

    def get_snapshot(self, refresh: bool = False) -> HardwareSnapshot:
        if refresh or self._snapshot is None:
            self._snapshot = HardwareInspector.capture()
        return self._snapshot

    def get_cached_snapshot(self) -> HardwareSnapshot | None:
        cached = HardwareInspector.load_cached()
        if cached:
            self._snapshot = cached
        return cached

    def refresh(self) -> HardwareSnapshot:
        self._snapshot = HardwareInspector.capture()
        return self._snapshot

    def recommended_model(self, catalog: ModelCatalog) -> ModelDescriptor:
        snap = self.get_snapshot()
        return catalog.recommended_for(
            ram_gb=snap.ram_gb,
            gpu_vram_gb=snap.gpu_vram_gb,
            vllm_supported=snap.vllm_supported,
        )

    def supports_unsloth(self) -> bool:
        snap = self.get_snapshot()
        return (
            snap.os_name != "Windows"
            and snap.compute_capability >= 7.0
            and snap.gpu_vram_gb >= 8.0
        )

    def get_tier_requirements(self) -> dict[str, Any]:
        return HardwareInspector.tier_requirements()

    def fits_hardware(self, model: ModelDescriptor) -> bool:
        snap = self.get_snapshot()
        return (
            snap.ram_gb >= model.ram_min_gb
            and snap.gpu_vram_gb >= model.vram_min_gb
        )
