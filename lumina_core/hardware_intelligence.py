from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lumina_core.engine.hardware_inspector import HardwareInspector, HardwareSnapshot
from lumina_core.engine.model_catalog import ModelCatalog, ModelDescriptor

_LEGACY_TO_CANONICAL_TIER = {
    "beast": "high",
    "sweet": "standard",
    "light": "light",
}


@dataclass(slots=True)
class HardwareIntelligenceSnapshot:
    profile_tier: str
    intelligence_tier: str
    recommended_model_key: str
    recommended_provider: str
    recommended_context_length: int
    ram_gb: float
    gpu_vram_gb: float
    vllm_supported: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_tier": self.profile_tier,
            "intelligence_tier": self.intelligence_tier,
            "recommended_model_key": self.recommended_model_key,
            "recommended_provider": self.recommended_provider,
            "recommended_context_length": self.recommended_context_length,
            "ram_gb": float(self.ram_gb),
            "gpu_vram_gb": float(self.gpu_vram_gb),
            "vllm_supported": bool(self.vllm_supported),
        }


class HardwareIntelligenceManager:
    """Hardware/model intelligence helper used by AdaptiveIntelligenceManager."""

    def __init__(self, workspace_root: Path | str | None = None) -> None:
        self.workspace_root = Path(workspace_root).resolve() if workspace_root is not None else Path.cwd().resolve()
        self.catalog = ModelCatalog(self.workspace_root / "lumina_model_catalog.json")
        self._latest_hardware_snapshot: HardwareSnapshot | None = None
        self._latest_intelligence_snapshot: HardwareIntelligenceSnapshot | None = None

    @staticmethod
    def _canonical_tier(profile_tier: str) -> str:
        normalized = str(profile_tier or "").strip().lower()
        return _LEGACY_TO_CANONICAL_TIER.get(normalized, "light")

    def resolve(self, *, refresh_hardware: bool = False) -> HardwareIntelligenceSnapshot:
        if refresh_hardware:
            hardware = HardwareInspector.capture()
        else:
            hardware = HardwareInspector.load_cached() or HardwareInspector.capture()
        self._latest_hardware_snapshot = hardware

        descriptor: ModelDescriptor = self.catalog.recommended_for(
            ram_gb=hardware.ram_gb,
            gpu_vram_gb=hardware.gpu_vram_gb,
            vllm_supported=hardware.vllm_supported,
        )
        snapshot = HardwareIntelligenceSnapshot(
            profile_tier=str(hardware.profile_tier),
            intelligence_tier=self._canonical_tier(str(hardware.profile_tier)),
            recommended_model_key=descriptor.key,
            recommended_provider=descriptor.recommended_provider,
            recommended_context_length=int(descriptor.context_length),
            ram_gb=float(hardware.ram_gb),
            gpu_vram_gb=float(hardware.gpu_vram_gb),
            vllm_supported=bool(hardware.vllm_supported),
        )
        self._latest_intelligence_snapshot = snapshot
        return snapshot

    def latest(self) -> HardwareIntelligenceSnapshot:
        if self._latest_intelligence_snapshot is None:
            return self.resolve(refresh_hardware=False)
        return self._latest_intelligence_snapshot
